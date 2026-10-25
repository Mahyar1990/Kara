"""Authoritative account resolution and the final, fresh credential boundary."""
from contextlib import contextmanager
from contextvars import ContextVar

import sqlalchemy as sa
from flask import has_request_context, request
from sqlalchemy.orm import Session
from werkzeug.exceptions import Forbidden

from company_projects import jira_connections, personal_models, store, team
from extensions.ext_database import db
from models.account import Account, Tenant

_validation = ContextVar('kara_personal_model_validation', default=None)


@contextmanager
def validation_connection(identity):
    token = _validation.set(str(identity))
    try:
        yield
    finally:
        _validation.reset(token)


def actor(tenant_id, proposed=None):
    """Console identity wins; internal signed calls/workers carry native account IDs."""
    if has_request_context():
        if request.path.startswith('/console/api/'):
            from libs.login import current_account_with_tenant
            try:
                current, workspace = current_account_with_tenant()
            except Exception:
                return None
            if str(workspace) != str(tenant_id) or (proposed and str(current.id) != str(proposed)):
                raise Forbidden('هویت اجرا با حساب واردشده یا پروژهٔ فعال یکسان نیست.')
            proposed = current.id
        elif not request.path.startswith('/inner/api/'):
            return None
    if not proposed:
        return None
    try:
        identity = str(store.uid(proposed))
    except store.ProjectError:
        return None
    with Session(db.engine) as session:
        jira_connections.account(session, identity)
        team.member(session, str(tenant_id), identity)
    return identity


def require_actor(tenant_id, proposed=None):
    identity = actor(tenant_id, proposed)
    if identity is None:
        raise Forbidden('اتصال مدل شخصی به حساب فعال کارا نیاز دارد؛ استفاده از توکن مشترک مجاز نیست.')
    return identity


def require_account_execution(tenant_id, user):
    if not isinstance(user, Account):
        raise Forbidden('اجرای مدل به حساب شخصی کارا نیاز دارد؛ اجرای ناشناس از اعتبارنامهٔ مشترک استفاده نمی‌کند.')
    require_actor(tenant_id, user.id)


def require_run_identity(context):
    if str(context.user_from) != 'account':
        raise Forbidden('این اجرا به حساب کاربر کارا منتسب نیست و نمی‌تواند از توکن مدل استفاده کند.')
    require_actor(context.tenant_id, context.user_id)


def personal_configurations(runtime, tenant_id):
    from company_projects.personal_provider_configuration import PersonalProviderConfiguration
    from core.entities.provider_configuration import ProviderConfigurations
    from core.entities.provider_entities import CustomConfiguration, CustomModelConfiguration, SystemConfiguration
    from graphon.model_runtime.entities.model_entities import ModelType
    from models.provider import ProviderType
    result = ProviderConfigurations(tenant_id=str(tenant_id))
    identity = actor(tenant_id, runtime.user_id)
    if identity is None:
        return result
    with Session(db.engine) as session:
        owned = personal_models.rows(session, identity)
    # Assemble only personal rows; never decrypt or cache workspace/system keys.
    for schema in runtime.fetch_model_providers():
        provider = personal_models.provider_id(schema.provider)
        models = [CustomModelConfiguration(model=row['model_name'], model_type=ModelType(row['model_type']),
            credentials=personal_models.decrypt(row)) for row in owned if row['provider'] == provider]
        configuration = PersonalProviderConfiguration(tenant_id=str(tenant_id), provider=schema,
            preferred_provider_type=ProviderType.CUSTOM, using_provider_type=ProviderType.CUSTOM,
            system_configuration=SystemConfiguration(enabled=False),
            custom_configuration=CustomConfiguration(models=models), model_settings=[])
        configuration.bind_model_runtime(runtime)
        result[provider] = configuration
    return result


def personal_default(runtime, tenant_id, model_type):
    from core.entities.model_entities import DefaultModelEntity, DefaultModelProviderEntity
    identity = actor(tenant_id, runtime.user_id)
    if identity is None:
        return None
    with Session(db.engine) as session:
        row = next((row for row in personal_models.rows(session, identity) if row['model_type'] == str(model_type)), None)
    if row is None:
        return None
    schema = next((item for item in runtime.fetch_model_providers()
        if personal_models.provider_id(item.provider) == row['provider']), None)
    if schema is None:
        return None
    return DefaultModelEntity(model=row['model_name'], model_type=model_type, provider=DefaultModelProviderEntity(
        provider=row['provider'], label=schema.label, icon_small=schema.icon_small,
        supported_model_types=schema.supported_model_types))


def bound_credentials(method, arguments):
    from company_projects.model_client_boundary import MODEL_METHODS
    identity = require_actor(arguments['tenant_id'], arguments.get('user_id'))
    provider = personal_models.provider_id(arguments['plugin_id'] + '/' + arguments['provider'])
    with Session(db.engine) as session:
        if method == 'validate_provider_credentials':
            if _validation.get() is None:
                raise Forbidden('آزمون اعتبارنامه فقط از اتصال شخصی ذخیره‌شده مجاز است.')
            row = personal_models.load(session, identity, _validation.get())
            if row['provider'] != provider:
                raise Forbidden('ارائه‌دهندهٔ اتصال با درخواست یکسان نیست.')
        else:
            kind = arguments.get('model_type') or MODEL_METHODS[method]
            row = personal_models.resolve(session, identity, provider, arguments['model'], kind)
        credentials = personal_models.decrypt(row)
    arguments['user_id'] = identity
    arguments['credentials'] = credentials


def schedule_account(session, schedule):
    """Use the recorded automation/app creator, never an arbitrary tenant owner."""
    from models.model import App
    owner = session.scalar(sa.select(store.automations.c.created_by).where(store.automations.c.app_id == schedule.app_id,
        store.automations.c.tenant_id == schedule.tenant_id))
    if owner is None:
        app = session.get(App, schedule.app_id)
        owner = app.created_by if app and app.tenant_id == schedule.tenant_id else None
    if not owner:
        raise Forbidden('حساب اجراکنندهٔ زمان‌بندی مشخص نیست.')
    account = jira_connections.account(session, owner)
    team.member(session, schedule.tenant_id, owner)
    account.set_current_tenant_with_session(session.get(Tenant, schedule.tenant_id), session=session)
    return account


def install_http_guard(app):
    @app.before_request
    def guard_personal_model_settings():
        roots = ('/console/api/workspaces/current/model-providers', '/console/api/workspaces/current/default-model')
        if not request.path.startswith(roots):
            return
        if request.method not in ('GET', 'HEAD', 'OPTIONS') or '/credentials' in request.path or request.path.endswith(('/summary', '/credits')):
            raise Forbidden('تنظیم و آزمون مدل را از بخش «اتصال به مدل هوش مصنوعی» با اتصال شخصی خودتان انجام دهید.')
