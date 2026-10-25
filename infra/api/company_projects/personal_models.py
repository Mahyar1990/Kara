"""Personal model registry. No migration or fallback from shared workspace keys."""
import base64
import json
import os
import re
from uuid import uuid4

import sqlalchemy as sa
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from werkzeug.exceptions import BadGateway, BadRequest, Conflict, Forbidden, NotFound, ServiceUnavailable

from company_projects import agents, jira_connections, store, team
from configs import dify_config
from extensions.ext_database import db
from graphon.model_runtime.entities.model_entities import ModelType
from models.provider_ids import ModelProviderID


def table(session):
    return agents.reflected(session, 'company_user_model_connections')


def provider_id(value):
    if not isinstance(value, str) or not value or len(value) > 255:
        raise BadRequest('ارائه‌دهندهٔ مدل معتبر نیست.')
    try:
        return str(ModelProviderID(value))
    except ValueError:
        raise BadRequest('شناسهٔ ارائه‌دهنده معتبر نیست.') from None


def cipher():
    if not dify_config.SECRET_KEY:
        raise ServiceUnavailable('کلید رمزگذاری سرور تنظیم نشده است.')
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
        info=b'kara:personal-model:v1').derive(dify_config.SECRET_KEY.encode())
    return AESGCM(key)


def aad(row):
    return json.dumps([str(row['account_id']), str(row['id']), row['provider'], row['model_name'], row['model_type']],
        separators=(',', ':')).encode()


def encrypt(row, credentials):
    nonce = os.urandom(12)
    return 'v1:' + base64.b64encode(nonce + cipher().encrypt(nonce,
        json.dumps(credentials, ensure_ascii=False, allow_nan=False).encode(), aad(row))).decode()


def decrypt(row):
    try:
        if not row['encrypted_credentials'].startswith('v1:'):
            raise ValueError()
        raw = base64.b64decode(row['encrypted_credentials'][3:], validate=True)
        value = json.loads(cipher().decrypt(raw[:12], raw[12:], aad(row)))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError, InvalidTag):
        raise ServiceUnavailable('اتصال مدل قابل خواندن نیست؛ اعتبارنامهٔ خودتان را دوباره ذخیره کنید.') from None


def rows(session, actor_id):
    jira_connections.account(session, actor_id)
    entity = table(session)
    return [dict(row) for row in session.execute(sa.select(entity).where(entity.c.account_id == str(actor_id))
        .order_by(entity.c.is_default.desc(), entity.c.name, entity.c.id)).mappings()]


def load(session, actor_id, identity, *, lock=False):
    jira_connections.account(session, actor_id)
    entity = table(session)
    query = sa.select(entity).where(entity.c.id == str(store.uid(identity)), entity.c.account_id == str(actor_id))
    row = session.execute(query.with_for_update() if lock else query).mappings().first()
    if row is None:
        raise NotFound('اتصال مدل در حساب شما پیدا نشد.')
    return dict(row)


def resolve(session, actor_id, provider, model, model_type):
    jira_connections.account(session, actor_id)
    entity = table(session)
    row = session.execute(sa.select(entity).where(entity.c.account_id == str(actor_id),
        entity.c.provider == provider_id(provider), entity.c.model_name == model,
        entity.c.model_type == str(model_type))).mappings().first()
    if row is None:
        raise Forbidden('برای این مدل، اتصال شخصی ندارید؛ اتصال خودتان را در «اتصال به مدل هوش مصنوعی» ثبت کنید.')
    return dict(row)


def schemas(tenant_id, actor_id):
    from core.plugin.impl.model_runtime_factory import create_plugin_model_runtime
    from sqlalchemy.orm import Session
    with Session(db.engine) as session:
        jira_connections.account(session, actor_id)
        team.member(session, tenant_id, actor_id)
    runtime = create_plugin_model_runtime(tenant_id=str(tenant_id), user_id=str(actor_id))
    return list(runtime.fetch_model_providers())


def form_schema(provider):
    custom = provider.model_credential_schema
    if custom and custom.credential_form_schemas:
        return custom.credential_form_schemas
    regular = provider.provider_credential_schema
    return regular.credential_form_schemas if regular else []


def secret_field(field):
    return str(field.type) == 'secret-input' or bool(re.search(
        r'key|token|secret|password|credential|header', field.variable, re.I))


def selected_schema(tenant_id, actor_id, provider):
    result = next((item for item in schemas(tenant_id, actor_id) if provider_id(item.provider) == provider), None)
    if result is None:
        raise BadRequest('افزونهٔ این ارائه‌دهنده در پروژه نصب نیست.')
    return result


def public(row, *, values=None):
    result = {key: row[key] for key in ('id', 'name', 'provider', 'model_name', 'model_type', 'is_default', 'revision')}
    result.update(credentials_configured=True, created_at=row['created_at'].isoformat(), updated_at=row['updated_at'].isoformat())
    if values is not None:
        result['values'] = values
    return result


def list_connections(session, actor_id):
    return dict(data=[public(row) for row in rows(session, actor_id)])


def catalog(tenant_id, actor_id):
    return dict(data=[dict(provider=provider_id(item.provider), label=item.label.model_dump(mode='json'),
        model_types=[str(kind) for kind in item.supported_model_types],
        fields=[field.model_dump(mode='json') | {'secret': secret_field(field)} for field in form_schema(item)])
        for item in schemas(tenant_id, actor_id)])


def detail(session, tenant_id, actor_id, identity):
    row = load(session, actor_id, identity)
    schema = selected_schema(tenant_id, actor_id, row['provider'])
    fields = {field.variable for field in form_schema(schema) if not secret_field(field)}
    return public(row, values={key: value for key, value in decrypt(row).items() if key in fields
        and isinstance(value, (str, int, float, bool))})


def save(session, tenant_id, actor_id, data, identity=None):
    agents.body(data, ('name', 'provider', 'model_name', 'model_type', 'credentials', 'is_default', 'expected_revision'))
    jira_connections.account(session, actor_id, lock=True)
    team.member(session, tenant_id, actor_id)
    old = load(session, actor_id, identity, lock=True) if identity else None
    if agents.revision(data['expected_revision']) != (old['revision'] if old else 1):
        raise Conflict('اتصال تغییر کرده است؛ فهرست را تازه کنید.')
    if (not isinstance(data['name'], str) or not data['name'].strip() or len(data['name']) > 120
            or not isinstance(data['model_name'], str) or not data['model_name'].strip() or len(data['model_name']) > 255
            or type(data['is_default']) is not bool or not isinstance(data['credentials'], dict)):
        raise BadRequest('نام اتصال، نام مدل و اطلاعات اعتبارنامه معتبر نیستند.')
    try:
        kind = str(ModelType(data['model_type']))
        if len(json.dumps(data['credentials'], allow_nan=False).encode()) > 32768:
            raise ValueError()
    except (ValueError, TypeError):
        raise BadRequest('نوع مدل یا اطلاعات اتصال معتبر نیست.') from None
    provider = provider_id(data['provider'])
    schema = selected_schema(tenant_id, actor_id, provider)
    if kind not in [str(item) for item in schema.supported_model_types]:
        raise BadRequest('این نوع مدل توسط ارائه‌دهنده پشتیبانی نمی‌شود.')
    fields = form_schema(schema)
    definitions = {field.variable: field for field in fields}
    if set(data['credentials']) - set(definitions):
        raise BadRequest('فیلد اعتبارنامهٔ ناشناخته وارد شده است.')
    same_model = bool(old and (old['provider'], old['model_name'], old['model_type']) == (
        provider, data['model_name'].strip(), kind))
    previous = decrypt(old) if old else {}
    values = {field.variable: data['credentials'].get(field.variable,
        None if secret_field(field) else field.default) for field in fields}
    # Never silently forward a retained key to a changed endpoint or account configuration.
    unchanged = same_model and all(values.get(field.variable) == previous.get(field.variable)
        for field in fields if not secret_field(field))
    for field in fields:
        value = values.get(field.variable)
        if secret_field(field) and value in (None, ''):
            values[field.variable] = previous.get(field.variable) if unchanged else None
        context = values | {'__model_type': kind, '__model_name': data['model_name'].strip()}
        visible = all(context.get(condition.variable) == condition.value for condition in field.show_on)
        if visible and field.required and values.get(field.variable) in (None, ''):
            raise BadRequest('فیلدهای الزامی اتصال، از جمله توکن، را تکمیل کنید. با تغییر مقصد، توکن را دوباره وارد کنید.')
        if isinstance(values.get(field.variable), str) and (field.variable.lower().endswith('_url') or field.variable.lower() in {'api_base', 'base_url', 'azure_endpoint'}):
            value = values[field.variable]
            if value:
                values[field.variable] = jira_connections.jira_intake.base_url(value)
    values = {key: value for key, value in values.items() if value is not None}
    entity = table(session)
    existing = session.execute(sa.select(entity).where(entity.c.account_id == str(actor_id))).mappings().all()
    for item in existing:
        if old and item['id'] == old['id']:
            continue
        if item['name'] == data['name'].strip() or (item['provider'], item['model_name'], item['model_type']) == (
                provider, data['model_name'].strip(), kind):
            raise Conflict('برای این نام یا همین ارائه‌دهنده و مدل، اتصال شخصی دارید؛ همان اتصال را ویرایش کنید.')
    is_default = data['is_default'] or not any(item['model_type'] == kind and item['is_default']
        and (not old or item['id'] != old['id']) for item in existing)
    if is_default:
        session.execute(entity.update().where(entity.c.account_id == str(actor_id), entity.c.model_type == kind,
            entity.c.is_default == True).values(is_default=False, revision=entity.c.revision + 1, updated_at=agents.now()))
    now = agents.now()
    row = dict(id=old['id'] if old else str(uuid4()), account_id=str(actor_id), name=data['name'].strip(),
        provider=provider, model_name=data['model_name'].strip(), model_type=kind, is_default=is_default,
        revision=old['revision'] + 1 if old else 1, created_at=old['created_at'] if old else now, updated_at=now)
    row['encrypted_credentials'] = encrypt(row, values)
    if old:
        session.execute(entity.update().where(entity.c.id == old['id']).values(**row))
    else:
        session.execute(entity.insert().values(**row))
    return public(row)


def delete(session, actor_id, identity, data):
    agents.body(data, ('expected_revision',))
    jira_connections.account(session, actor_id, lock=True)
    row = load(session, actor_id, identity, lock=True)
    if agents.revision(data['expected_revision']) != row['revision']:
        raise Conflict('اتصال تغییر کرده است؛ فهرست را تازه کنید.')
    entity = table(session)
    session.execute(entity.delete().where(entity.c.id == row['id'], entity.c.account_id == str(actor_id)))
    return dict(deleted=True)


def test_connection(session, tenant_id, actor_id, identity):
    from core.plugin.impl.model_runtime_factory import create_plugin_model_runtime
    row = load(session, actor_id, identity, lock=True)
    schema = selected_schema(tenant_id, actor_id, row['provider'])
    runtime = create_plugin_model_runtime(tenant_id=str(tenant_id), user_id=str(actor_id))
    from company_projects.personal_model_runtime import validation_connection
    try:
        with validation_connection(row['id']):
            if schema.model_credential_schema and schema.model_credential_schema.credential_form_schemas:
                runtime.validate_model_credentials(provider=row['provider'], model_type=ModelType(row['model_type']),
                    model=row['model_name'], credentials=decrypt(row))
            else:
                runtime.validate_provider_credentials(provider=row['provider'], credentials=decrypt(row))
    except (Forbidden, NotFound, ServiceUnavailable):
        raise
    except Exception:
        raise BadGateway('اعتبارسنجی اتصال مدل ناموفق بود؛ توکن، مجوز مدل، نشانی و دسترسی شبکهٔ سرور را بررسی کنید.') from None
    return dict(connected=True, message='اعتبارسنجی اتصال شخصی موفق بود؛ اجرای برنامه و سازگاری قابلیت‌های مدل جداگانه بررسی می‌شود.')
