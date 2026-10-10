"""Explicit one-time migration of the pinned local grouping to native workspaces.

App identifiers and relational history are retained. Unsupported shared/runtime
dependencies abort the transaction rather than silently exposing another team's data.
The original workspace becomes the legacy project, preserving paused executions.
"""
import base64
import json
import time
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from company_projects import access, ownership, store
from core.helper import encrypter
from core.plugin.plugin_service import PluginService
from extensions.ext_storage import storage
from libs import rsa
from models.account import Account, Tenant
from services.account_service import TenantService
from services.model_provider_service import ModelProviderService


def encrypt_for_workspace(value, source_id, tenant):
    secret = encrypter.decrypt_token(source_id, value)
    return base64.b64encode(rsa.encrypt(secret, tenant.encrypt_public_key)).decode()


def copy_connections(connection, metadata, source_id, tenant):
    credential_ids = {}
    configurations = {}
    for name in ['provider_credentials', 'provider_model_credentials', 'providers', 'provider_models',
            'tenant_default_models', 'tenant_preferred_model_providers', 'provider_orders',
            'provider_model_settings', 'load_balancing_model_configs']:
        table = metadata.tables.get(name)
        if table is None:
            continue
        for original in connection.execute(sa.select(table).where(table.c.tenant_id == source_id)).mappings():
            row = dict(original)
            row['tenant_id'] = tenant.id
            if 'id' in row:
                row['id'] = str(uuid4())
                credential_ids[str(original['id'])] = row['id']
            if row.get('credential_id'):
                row['credential_id'] = credential_ids[str(row['credential_id'])]
            if row.get('encrypted_config'):
                provider = row['provider_name']
                if provider not in configurations:
                    configurations[provider] = ModelProviderService()._get_provider_configuration(source_id, provider)
                config = configurations[provider]
                schema = config.provider.provider_credential_schema if name == 'provider_credentials' else config.provider.model_credential_schema
                keys = config.extract_secret_variables(schema.credential_form_schemas if schema else [])
                credentials = json.loads(row['encrypted_config'])
                for key in keys:
                    if credentials.get(key):
                        credentials[key] = encrypt_for_workspace(credentials[key], source_id, tenant)
                row['encrypted_config'] = json.dumps(credentials)
            connection.execute(table.insert().values(**row))
    return credential_ids


def ensure_plugins(source_id, target_id):
    plugins = PluginService.list(source_id)
    identifiers = [plugin.plugin_unique_identifier for plugin in plugins]
    if not identifiers:
        return
    PluginService.install_from_local_pkg(target_id, identifiers)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        installed = {plugin.plugin_unique_identifier for plugin in PluginService.list(target_id)}
        if set(identifiers) <= installed:
            return
        time.sleep(1)
    raise RuntimeError('Model plugins were not ready; project migration was rolled back.')


def references(metadata, connection, source_id, app_ids):
    agents = metadata.tables['agents']
    agent_ids = list(connection.scalars(sa.select(agents.c.id).where(agents.c.tenant_id == source_id,
        sa.or_(agents.c.app_id.in_(app_ids), agents.c.backing_app_id.in_(app_ids)))))
    workflows = metadata.tables['workflows']
    workflow_ids = list(connection.scalars(sa.select(workflows.c.id).where(
        workflows.c.tenant_id == source_id, workflows.c.app_id.in_(app_ids))))
    return agent_ids, workflow_ids


def preflight(connection, metadata, source_id, app_ids):
    if not app_ids:
        return
    runs = metadata.tables['workflow_runs']
    if connection.scalar(sa.select(sa.func.count()).select_from(runs).where(runs.c.tenant_id == source_id,
            runs.c.app_id.in_(app_ids), runs.c.status.in_(['running', 'paused']))):
        raise RuntimeError('Assigned apps have active executions; finish them before moving these apps.')
    # Existing installations with shared knowledge/skills need an explicit
    # dependency migration. This local installation has neither at migration time.
    for name in ['datasets', 'skills', 'tool_api_providers', 'tool_builtin_providers', 'tool_mcp_providers', 'tool_workflow_providers']:
        table = metadata.tables.get(name)
        if table is not None and connection.scalar(sa.select(sa.func.count()).select_from(table).where(table.c.tenant_id == source_id)):
            raise RuntimeError(f'Shared dependency {name} requires an explicit migration plan.')
    agent_ids, _ = references(metadata, connection, source_id, app_ids)
    for name in ['agent_home_snapshots', 'agent_workspace_bindings']:
        table = metadata.tables[name]
        if connection.scalar(sa.select(sa.func.count()).select_from(table).where(
                table.c.tenant_id == source_id, table.c.agent_id.in_(agent_ids))):
            raise RuntimeError('Materialized Agent runtime assets require an explicit migration plan.')


def remap_credentials(value, mapping):
    if isinstance(value, dict):
        return {key: mapping.get(str(item), item) if key in ('credential_id', 'model_credential_id')
                else remap_credentials(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [remap_credentials(item, mapping) for item in value]
    return value


def move_apps(connection, metadata, source_id, tenant, app_ids, credential_ids):
    preflight(connection, metadata, source_id, app_ids)
    agent_ids, workflow_ids = references(metadata, connection, source_id, app_ids)
    workflows = metadata.tables['workflows']
    for row in connection.execute(sa.select(workflows).where(workflows.c.id.in_(workflow_ids))).mappings():
        variables = json.loads(row['environment_variables'] or '{}')
        for variable in variables.values():
            if variable.get('value_type') == 'secret' and variable.get('value'):
                variable['value'] = encrypt_for_workspace(variable['value'], source_id, tenant)
        graph = remap_credentials(json.loads(row['graph']), credential_ids)
        connection.execute(workflows.update().where(workflows.c.id == row['id']).values(
            environment_variables=json.dumps(variables), graph=json.dumps(graph)))
    for name, table in metadata.tables.items():
        if name.startswith('company_') or 'tenant_id' not in table.c:
            continue
        filters = []
        if name == 'apps':
            filters.append(table.c.id.in_(app_ids))
        for column, ids in [('app_id', app_ids), ('backing_app_id', app_ids), ('agent_id', agent_ids), ('workflow_id', workflow_ids)]:
            if column in table.c:
                filters.append(table.c[column].in_(ids))
        if filters:
            changes = {'tenant_id': tenant.id}
            if 'app_owner_tenant_id' in table.c:
                changes['app_owner_tenant_id'] = tenant.id
            connection.execute(table.update().where(table.c.tenant_id == source_id, sa.or_(*filters)).values(**changes))


def migrate(session, *, copy_models=True):
    connection = session.connection()
    connection.execute(sa.text('SELECT pg_advisory_xact_lock(210610003)'))
    root = dict(access.authority(session))
    source_id, owner_id = str(root['tenant_id']), str(root['account_id'])
    rows = store.list_projects(connection, source_id)
    mapped = connection.scalar(sa.select(sa.func.count()).select_from(store.workspaces.join(store.projects,
        store.projects.c.id == store.workspaces.c.project_id)).where(store.projects.c.tenant_id == source_id))
    if mapped:
        if mapped == len(rows):
            return dict(result='already_migrated')
        raise RuntimeError('Mixed legacy and isolated projects require an explicit migration plan.')
    metadata = sa.MetaData(); metadata.reflect(connection)
    apps = metadata.tables['apps']
    initial_ids = set(connection.scalars(sa.select(apps.c.id)))
    conserved = {name: set(connection.scalars(sa.select(metadata.tables[name].c.id)))
                 for name in ('workflows', 'workflow_runs', 'agents')}
    links = [dict(row) for row in connection.execute(sa.select(store.bindings).where(store.bindings.c.tenant_id == source_id)).mappings()]
    assigned = {row['app_id'] for row in links}
    preflight(connection, metadata, source_id, list(assigned))
    new_tenants = []
    try:
        central = TenantService.create_tenant(name='مدیریت محصول', is_from_dashboard=True, session=session)
        new_tenants.append(central.id)
        TenantService.create_tenant_member(central, session.get(Account, owner_id), session, role='owner')
        for row in rows:
            tenant = ownership.provision(session, row, owner_id, owner_id)
            new_tenants.append(tenant.id)
            ids = [link['app_id'] for link in links if link['project_id'] == row['id']]
            credential_ids = copy_connections(connection, metadata, source_id, tenant) if copy_models else {}
            if copy_models:
                ensure_plugins(source_id, tenant.id)
            move_apps(connection, metadata, source_id, tenant, ids, credential_ids)
        legacy_name = 'برنامه‌های قبلی'
        while connection.scalar(sa.select(sa.func.count()).select_from(store.projects).where(
                store.projects.c.tenant_id == source_id, store.projects.c.name_key == legacy_name.casefold())):
            legacy_name += ' — بایگانی'
        legacy = store.create_project(connection, source_id, owner_id, legacy_name,
            'فضای نگهداری برنامه‌ها و فرایندهای سازمان')
        source = session.get(Tenant, source_id)
        source.name = legacy['name']
        session.execute(store.workspaces.insert().values(project_id=legacy['id'], workspace_id=source_id))
        remaining = list(connection.scalars(sa.select(apps.c.id).where(apps.c.tenant_id == source_id)))
        for app_id in remaining:
            store.assign(connection, source_id, legacy['id'], app_id)
        links = [dict(row) for row in connection.execute(sa.select(store.bindings).where(store.bindings.c.tenant_id == source_id)).mappings()]
        # Rebase the catalog without changing native App IDs or the original
        # runtime workspace. Remove/reinsert only catalog bindings for the FK.
        session.execute(store.bindings.delete().where(store.bindings.c.tenant_id == source_id))
        session.execute(store.projects.update().where(store.projects.c.tenant_id == source_id).values(tenant_id=central.id))
        for link in links:
            link['tenant_id'] = central.id
        if links:
            session.execute(store.bindings.insert(), links)
        session.execute(store.product.update().where(store.product.c.id == 1).values(tenant_id=central.id))
        session.flush()
        if set(connection.scalars(sa.select(apps.c.id))) != initial_ids:
            raise RuntimeError('App conservation check failed.')
        for name, ids in conserved.items():
            if set(connection.scalars(sa.select(metadata.tables[name].c.id))) != ids:
                raise RuntimeError(f'{name} conservation check failed.')
        TenantService.switch_tenant(session.get(Account, owner_id), central.id, session=session)
        return dict(result='migrated', projects=len(rows) + 1, apps=len(initial_ids), preserved_legacy_apps=len(remaining))
    except Exception:
        # Only resources provisioned by this migration are cleaned up.
        for tenant_id in new_tenants:
            try:
                if copy_models:
                    for plugin in PluginService.list(tenant_id):
                        PluginService.uninstall(tenant_id, plugin.installation_id)
                storage.delete(f'privkeys/{tenant_id}/private.pem')
            except Exception:
                pass  # The DB still rolls back; the private backup also retains recovery material.
        raise


def main():
    from app_factory import create_app
    from extensions.ext_database import db
    _, app = create_app()
    with app.app_context(), db.engine.begin() as connection, Session(bind=connection, join_transaction_mode='create_savepoint') as session:
        result = migrate(session)
        session.commit()
    print(json.dumps(result))


if __name__ == '__main__':
    main()
