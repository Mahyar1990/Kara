"""Account-owned Jira PATs and bounded REST v2 reads; never expose credentials."""
import base64
import json
import os
import time
from uuid import UUID, uuid4, uuid5

import httpx
import sqlalchemy as sa
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from werkzeug.exceptions import BadGateway, BadRequest, Conflict, Forbidden, NotFound, ServiceUnavailable

from company_projects import agents, jira_intake
from configs import dify_config
from core.helper import ssrf_proxy
from core.tools.errors import ToolSSRFError
from models.account import Account, AccountStatus

MAX_BYTES = 2 * 1024 * 1024
FIELDS = ['summary', 'description', 'status', 'priority', 'reporter', 'assignee', 'created', 'updated']


def table(session):
    return agents.reflected(session, 'company_user_jira_connections')


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
        raise NotFound('اتصال جیرا در حساب شما پیدا نشد.')
    return dict(row)


def cipher():
    if not dify_config.SECRET_KEY:
        raise ServiceUnavailable('کلید رمزگذاری سرور تنظیم نشده است.')
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
        info=b'kara:personal-jira:v1').derive(dify_config.SECRET_KEY.encode())
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
    address = jira_intake.base_url(data['base_url'])
    entity = table(session)
    old = load(session, actor_id, connection_id, lock=True) if connection_id else None
    expected = agents.revision(data['expected_revision'])
    if expected != (old['revision'] if old else 1):
        raise Conflict('اطلاعات اتصال تغییر کرده است؛ فهرست را تازه کنید.')
    if not token and (old is None or old['base_url'] != address):
        raise BadRequest('برای اتصال تازه یا تغییر نشانی جیرا، توکن را وارد کنید.')
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


def read_jira(row, path, *, body=None):
    """Fixed relative endpoint, verified TLS, no redirect/retry or remote error text."""
    response = None
    deadline = time.monotonic() + 30
    try:
        call = ssrf_proxy.get if body is None else ssrf_proxy.post
        options = dict(headers={'Accept': 'application/json', 'Authorization': 'Bearer ' + decrypt(row),
            'Accept-Encoding': 'identity'}, timeout=httpx.Timeout(20, connect=5),
            follow_redirects=False, ssl_verify=True, max_retries=0, stream_response=True)
        if body is not None:
            options['json'] = body
        response = call(row['base_url'] + path, **options)
        status = response.status_code
        if status != 200:
            messages = {400: 'درخواست جست‌وجو یا JQL معتبر نیست.', 401: 'توکن نامعتبر یا منقضی شده است.',
                403: 'این کاربر در جیرا مجوز فراخوانی این سرویس را ندارد.',
                404: 'نشانی جیرا یا مسیر سرویس پیدا نشد.', 429: 'محدودیت تعداد فراخوانی جیرا؛ بعداً تلاش کنید.'}
            raise BadGateway(f'جیرا پاسخ HTTP {status} داد. ' + messages.get(status, 'نشانی و وضعیت سرویس جیرا را بررسی کنید.'))
        chunks, size = [], 0
        for chunk in response.iter_bytes(chunk_size=65536):
            if time.monotonic() > deadline:
                raise BadGateway('دریافت پاسخ جیرا بیش از زمان مجاز طول کشید؛ دوباره تلاش کنید.')
            size += len(chunk)
            if size > MAX_BYTES:
                raise BadGateway('پاسخ جیرا بیش از دو مگابایت است؛ تعداد درخواست‌های هر صفحه را کاهش دهید.')
            chunks.append(chunk)
        value = json.loads(b''.join(chunks))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except ToolSSRFError:
        raise BadGateway('دسترسی شبکهٔ سرور کارا به این نشانی مجاز نیست؛ تنظیمات پراکسی سرور باید بررسی شود.') from None
    except (httpx.HTTPError, ssrf_proxy.MaxRetriesExceededError):
        raise BadGateway('اتصال به جیرا برقرار نشد؛ شبکه، گواهی HTTPS و دسترسی سرور کارا به جیرا را بررسی کنید.') from None
    except (ValueError, UnicodeError):
        raise BadGateway('پاسخ جیرا JSON معتبر نیست؛ نشانی پایه و سرویس را بررسی کنید.') from None
    finally:
        if response is not None:
            response.close()


def test_connection(session, actor_id, connection_id):
    row = load(session, actor_id, connection_id, lock=True)
    result = read_jira(row, '/rest/api/2/myself')
    if not (result.get('name') or result.get('accountId') or result.get('key')):
        raise BadGateway('پاسخ سرویس احراز هویت جیرا معتبر نیست.')
    return dict(connected=True, message='اتصال و احراز هویت موفق است؛ دسترسی جست‌وجو هنگام دریافت درخواست‌ها بررسی می‌شود.')


def import_selected(session, project_id, workspace_id, actor_id, data, key):
    if not isinstance(data, dict) or set(data) not in ({'connection_id', 'response'}, {'connection_id', 'run_id'}):
        raise BadRequest('اتصال جیرا و پاسخ ذخیره‌شده یا اجرای انتخاب‌شده لازم است.')
    jira_intake.authorize(session, project_id, workspace_id, actor_id, write=True)
    row = load(session, actor_id, data['connection_id'], lock=True)
    return jira_intake.import_response(session, project_id, workspace_id, actor_id,
        {key: value for key, value in data.items() if key != 'connection_id'} | {'base_url': row['base_url']}, key)


def fetch(session, project_id, workspace_id, actor_id, data, key):
    agents.body(data, ('connection_id', 'jql', 'start_at', 'max_results'))
    scoped = jira_intake.authorize(session, project_id, workspace_id, actor_id, write=True)
    row = load(session, actor_id, data['connection_id'], lock=True)
    key = agents.action_key(key)
    if not isinstance(data['jql'], str) or not data['jql'].strip() or len(data['jql']) > 4000:
        raise BadRequest('عبارت JQL باید بین ۱ تا ۴۰۰۰ نویسه باشد.')
    if (type(data['start_at']) is not int or data['start_at'] < 0 or data['start_at'] > 2147483647
            or type(data['max_results']) is not int or not 1 <= data['max_results'] <= 100):
        raise BadRequest('شروع صفحه باید عدد نامنفی و تعداد هر صفحه بین ۱ تا ۱۰۰ باشد.')
    fingerprint = agents.digest(dict(operation='jira.fetch', **data, connection_revision=row['revision']))
    previous = agents.replay(session, scoped, actor_id, key, fingerprint)
    if previous:
        return previous
    response = read_jira(row, '/rest/api/2/search', body=dict(jql=data['jql'], startAt=data['start_at'],
        maxResults=data['max_results'], fields=FIELDS))
    _, _, start = jira_intake.parse(response)
    if start != data['start_at'] or len(response['issues']) > data['max_results']:
        raise BadGateway('صفحه‌بندی پاسخ جیرا با درخواست سازگار نیست.')
    result = jira_intake.import_response(session, project_id, workspace_id, actor_id,
        dict(base_url=row['base_url'], response=response), str(uuid5(UUID(key), 'jira-response')))
    agents.event(session, scoped, actor_id, key, fingerprint, 'jira.fetched', result)
    return result
