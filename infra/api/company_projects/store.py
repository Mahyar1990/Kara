"""Tenant-scoped project records; no changes to Dify's existing tables."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa

metadata = sa.MetaData()
schema = sa.Table('company_project_schema', metadata,
    sa.Column('version', sa.Integer, primary_key=True))
projects = sa.Table('company_projects', metadata,
    sa.Column('id', sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column('tenant_id', sa.Uuid(as_uuid=False), nullable=False, index=True),
    sa.Column('name', sa.String(120), nullable=False),
    sa.Column('name_key', sa.String(120), nullable=False),
    sa.Column('description', sa.String(2000), nullable=False, default=''),
    sa.Column('created_by', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint('tenant_id', 'name_key', name='company_project_name_unique'),
    sa.UniqueConstraint('id', 'tenant_id', name='company_project_tenant_unique'))
bindings = sa.Table('company_project_apps', metadata,
    sa.Column('tenant_id', sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column('app_id', sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column('project_id', sa.Uuid(as_uuid=False), nullable=False, index=True),
    sa.ForeignKeyConstraint(['project_id', 'tenant_id'], ['company_projects.id', 'company_projects.tenant_id']))
product = sa.Table('company_product', metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('account_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('tenant_id', sa.Uuid(as_uuid=False), nullable=False))
workspaces = sa.Table('company_project_workspaces', metadata,
    sa.Column('project_id', sa.Uuid(as_uuid=False), sa.ForeignKey('company_projects.id'), primary_key=True),
    sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False, unique=True))
template_copies = sa.Table('company_template_copies', metadata,
    sa.Column('app_id', sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column('tenant_id', sa.Uuid(as_uuid=False), nullable=False, index=True),
    sa.Column('template_id', sa.String(80), nullable=False),
    sa.Column('template_version', sa.String(40), nullable=False),
    sa.Column('source_commit', sa.String(40), nullable=False),
    sa.Column('created_by', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
automations = sa.Table('company_automations', metadata,
    sa.Column('app_id', sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column('tenant_id', sa.Uuid(as_uuid=False), nullable=False, index=True),
    sa.Column('source_app_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('source_workflow_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('created_by', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))


class ProjectError(ValueError):
    pass


class MissingProject(ProjectError):
    pass


def uid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ProjectError('شناسه معتبر نیست.') from None


def details(name, description=''):
    if not isinstance(name, str) or not isinstance(description, str):
        raise ProjectError('نام و توضیح باید متن باشند.')
    name = ' '.join(name.split())
    description = description.strip()
    if not name or len(name) > 120 or len(description) > 2000:
        raise ProjectError('نام پروژه الزامی و حداکثر ۱۲۰ نویسه و توضیح حداکثر ۲۰۰۰ نویسه است.')
    return {'name': name, 'name_key': name.casefold(), 'description': description}


def migrate(engine):
    with engine.begin() as connection:
        if engine.dialect.name == 'postgresql':
            connection.execute(sa.text('SELECT pg_advisory_xact_lock(210610001)'))
        metadata.create_all(connection)
        versions = set(connection.scalars(sa.select(schema.c.version)))
        if not versions:
            connection.execute(schema.insert().values(version=1))
        elif versions != {1}:
            raise RuntimeError('Unsupported company projects schema version')


def get_project(connection, tenant_id, project_id):
    result = connection.execute(sa.select(projects).where(
        projects.c.tenant_id == uid(tenant_id), projects.c.id == uid(project_id))).mappings().first()
    if result is None:
        raise MissingProject('پروژه پیدا نشد.')
    return dict(result)


def list_projects(connection, tenant_id):
    return [dict(row) for row in connection.execute(sa.select(projects).where(
        projects.c.tenant_id == uid(tenant_id)).order_by(projects.c.created_at, projects.c.id)).mappings()]


def create_project(connection, tenant_id, account_id, name, description=''):
    now = datetime.now(timezone.utc)
    row = dict(id=str(uuid4()), tenant_id=uid(tenant_id), created_by=uid(account_id),
               created_at=now, updated_at=now, **details(name, description))
    connection.execute(projects.insert().values(**row))
    return row


def update_project(connection, tenant_id, project_id, name, description=''):
    get_project(connection, tenant_id, project_id)
    connection.execute(projects.update().where(projects.c.tenant_id == uid(tenant_id),
        projects.c.id == uid(project_id)).values(**details(name, description), updated_at=datetime.now(timezone.utc)))
    return get_project(connection, tenant_id, project_id)


def app_ids(project_id, tenant_id):
    return sa.select(bindings.c.app_id).where(bindings.c.tenant_id == uid(tenant_id),
                                            bindings.c.project_id == uid(project_id))


def assign(connection, tenant_id, project_id, app_id):
    get_project(connection, tenant_id, project_id)
    values = dict(tenant_id=uid(tenant_id), project_id=uid(project_id), app_id=uid(app_id))
    # A resource has one project; moving it never changes its content or permissions.
    dialect = connection.dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError('Unsupported projects database dialect')
    statement = insert(bindings).values(**values)
    connection.execute(statement.on_conflict_do_update(
        index_elements=['tenant_id', 'app_id'], set_={'project_id': values['project_id']}))


def unassign(connection, tenant_id, project_id, app_id):
    get_project(connection, tenant_id, project_id)
    connection.execute(bindings.delete().where(bindings.c.tenant_id == uid(tenant_id),
        bindings.c.project_id == uid(project_id), bindings.c.app_id == uid(app_id)))


def public_project(row):
    return {key: (row[key].isoformat() if isinstance(row[key], datetime) else row[key])
            for key in ('id', 'name', 'description', 'created_at', 'updated_at')}
