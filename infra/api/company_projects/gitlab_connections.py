"""Account-owned GitLab PATs; never expose credentials."""
import base64
import json
import os
import time
from uuid import uuid4

import httpx
import sqlalchemy as sa
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from werkzeug.exceptions import BadGateway, BadRequest, Conflict, Forbidden, NotFound, ServiceUnavailable

from company_projects import agents
from kara_source_runner.contracts import https_url
from configs import dify_config
from core.helper import ssrf_proxy
from core.tools.errors import ToolSSRFError
from models.account import Account, AccountStatus


def table(session):
    return agents.reflected(session, 'company_user_gitlab_connections')


def account(session, actor_id, *, lock=False):
    query = sa.select(Account).where(Account.id == str(actor_id)).execution_options(populate_existing=True)
    value = session.scalar(query.with_for_update() if lock else query)
    if value is None or value.status != AccountStatus.ACTIVE:
        raise Forbidden('حساب فعال برای تنظیم اتصال شخصی لازم است.')
    return value


def load(session, actor_id, connection_id, *, lock=False):
    account(session, actor_id)
    entity = table(session)
    query = sa.select(entity).where(entity.c.id == str(agents.store.uid(connection_id)), entity.c.account_id == str(actor_id))
    row = session.execute(query.with_for_update() if lock else query).mappings().first()
    if row is None:
        raise NotFound('اتصال گیت‌لب در حساب شما پیدا نشد.')
    return dict(row)


def cipher():
    if not dify_config.SECRET_KEY:
        raise ServiceUnavailable('کلید رمزگذاری سرور تنظیم نشده است.')
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
        info=b'kara:personal-gitlab:v1').derive(dify_config.SECRET_KEY.encode())
    return AESGCM(key)


def aad(row):
    return json.dumps([str(row['account_id']), str(row['id']), row['base_url']], separators=(',', ':')).encode()


def encrypt(row, token):
    nonce = os.urandom(12)
    return 'v1:' + base64.b64encode(nonce + cipher().encrypt(nonce, token.encode(), aad(row))).decode()


def decrypt(row):
    try:
        if not row['encrypted_token'].startswith('v1:'):
            raise ValueError()
        data = base64.b64decode(row['encrypted_token'][3:], validate=True)
        return cipher().decrypt(data[:12], data[12:], aad(row)).decode()
    except (ValueError, InvalidTag, UnicodeError):
        raise ServiceUnavailable('توکن ذخیره‌شده قابل خواندن نیست؛ اتصال را با توکن تازه ذخیره کنید.') from None


def public(row):
    return {key: row[key] for key in ('id', 'name', 'base_url', 'revision')} | dict(token_configured=True,
        created_at=row['created_at'].isoformat(), updated_at=row['updated_at'].isoformat())


def list_connections(session, actor_id):
    account(session, actor_id)
    entity = table(session)
    return dict(data=[public(row) for row in session.execute(sa.select(entity).where(
        entity.c.account_id == str(actor_id)).order_by(entity.c.name, entity.c.id)).mappings()])


def save(session, actor_id, data, connection_id=None):
    agents.body(data, ('name', 'base_url', 'token', 'expected_revision'))
    account(session, actor_id, lock=True)
    name, token = data['name'], data['token']
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise BadRequest('نام اتصال باید بین ۱ تا ۱۲۰ نویسه باشد.')
    if not isinstance(token, str) or len(token) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise BadRequest('توکن را بدون Bearer، فاصله یا هدر وارد کنید.')
    if token.lower().startswith('bearer '):
        raise BadRequest('فقط مقدار توکن را وارد کنید.')
    address = validated_url(data['base_url'])
    entity = table(session)
    old = load(session, actor_id, connection_id, lock=True) if connection_id else None
    expected = agents.revision(data['expected_revision'])
    if expected != (old['revision'] if old else 1):
        raise Conflict('اطلاعات اتصال تغییر کرده است؛ فهرست را تازه کنید.')
    if not token and (old is None or old['base_url'] != address):
        raise BadRequest('برای اتصال تازه یا تغییر نشانی گیت‌لب، توکن را وارد کنید.')
    duplicate = sa.select(entity.c.id).where(entity.c.account_id == str(actor_id), entity.c.name == name.strip())
    if old:
        duplicate = duplicate.where(entity.c.id != old['id'])
    if session.scalar(duplicate.limit(1)):
        raise Conflict('اتصالی با این نام در حساب شما وجود دارد.')
    now = agents.now()
    row = dict(id=old['id'] if old else str(uuid4()), account_id=str(actor_id), name=name.strip(),
        base_url=address, revision=old['revision'] + 1 if old else 1,
        created_at=old['created_at'] if old else now, updated_at=now)
    row['encrypted_token'] = encrypt(row, token) if token else old['encrypted_token']
    if old:
        session.execute(entity.update().where(entity.c.id == old['id'], entity.c.account_id == str(actor_id)).values(**row))
    else:
        session.execute(entity.insert().values(**row))
    return public(row)


def delete(session, actor_id, connection_id, data):
    agents.body(data, ('expected_revision',))
    row = load(session, actor_id, connection_id, lock=True)
    if agents.revision(data['expected_revision']) != row['revision']:
        raise Conflict('اطلاعات اتصال تغییر کرده است؛ فهرست را تازه کنید.')
    entity = table(session)
    session.execute(entity.delete().where(entity.c.id == row['id'], entity.c.account_id == str(actor_id)))
    return dict(deleted=True)



def validated_url(value):
    try:
        result = https_url(value)
        if len(result) > 512:
            raise ValueError()
        return result
    except ValueError:
        raise BadRequest('آدرس پایهٔ HTTPS گیت‌لب را بدون توکن یا پارامتر وارد کنید.') from None


def test_connection(session, actor_id, connection_id):
    row = load(session, actor_id, connection_id)
    from company_projects.local_rpc import connection_request
    value=connection_request('gitlab',row,'/api/v4/user')
    if not isinstance(value.get('id'),int) or not value.get('username'):
        raise BadGateway('پاسخ احراز هویت گیت‌لب معتبر نیست.')
    return dict(connected=True,message='اتصال از Runner انتخاب‌شده موفق بود.')
