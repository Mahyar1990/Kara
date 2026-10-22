"""Versioned manual requests and authenticated PO intake; never dispatch work."""
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import agents, flows, team
from company_projects.store import uid
from models.account import Tenant

MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 5 * 1024 * 1024
MAX_FILES = 5


def tables(session):
    return tuple(agents.reflected(session, name) for name in ('company_team_requests',
        'company_team_request_revisions', 'company_team_request_attachments', 'company_team_intake_decisions'))


def scope(session, project_id, workspace_id, actor_id, *, write=False):
    if write:
        session.scalar(sa.select(Tenant).where(Tenant.id == str(workspace_id)).with_for_update())
    result = team.scope(session, project_id, workspace_id, actor_id)
    team.member(session, workspace_id, actor_id)
    return result


def is_po(session, scoped, actor_id):
    return 'po' in team.get_roles(session, scoped['project_id'], scoped['workspace_id'], actor_id, actor_id)['roles']


def load(session, table, scoped, request_id, *, lock=False):
    query = sa.select(table).where(table.c.id == str(request_id), *(table.c[k] == v for k, v in scoped.items()))
    row = session.execute(query.with_for_update() if lock else query).mappings().first()
    if not row:
        raise NotFound('درخواست در این پروژه پیدا نشد.')
    return dict(row)


def serial(row):
    return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in row.items()}


def attachment_list(session, row, attachments):
    if not row['attachment_ids']:
        return []
    values = session.execute(sa.select(attachments.c.id, attachments.c.name, attachments.c.size, attachments.c.digest)
        .where(attachments.c.id.in_(row['attachment_ids']), attachments.c.request_id == row['request_id'])).mappings()
    by_id = {v['id']: dict(v) for v in values}
    return [by_id[key] for key in row['attachment_ids']]


def public_revision(session, row, attachments):
    return serial(row) | {'attachments': attachment_list(session, row, attachments)}


def public(session, row, po, actor_id, *, detail=False):
    _, revisions, attachments, decisions = tables(session)
    current = session.execute(sa.select(revisions).where(revisions.c.id == row['current_revision_id'])).mappings().one()
    decision = session.execute(sa.select(decisions).where(decisions.c.id == row['current_decision_id'])).mappings().first()
    valid = bool(decision and decision['outcome'] == 'approved' and decision['mode'] == 'real'
        and decision['request_revision_id'] == current['id'] and decision['request_digest'] == current['digest']
        and (decision['expires_at'] is None or decision['expires_at'] > agents.now()))
    result = serial(row) | dict(title=current['title'], version=current['version'], can_edit=po or row['created_by'] == str(actor_id),
        can_decide=po, intake_valid=valid, state=('approved' if valid else 'expired') if decision and decision['outcome'] == 'approved'
        else decision['outcome'] if decision else 'pending', current=public_revision(session, current, attachments),
        decision=serial(decision) if decision else None)
    if detail:
        result['revisions'] = [public_revision(session, value, attachments) for value in session.execute(
            sa.select(revisions).where(revisions.c.request_id == row['id']).order_by(revisions.c.version.desc())).mappings()]
        result['decisions'] = [serial(value) for value in session.execute(sa.select(decisions)
            .where(decisions.c.request_id == row['id']).order_by(decisions.c.created_at, decisions.c.id)).mappings()]
    return result


def list_requests(session, project_id, workspace_id, actor_id):
    scoped = scope(session, project_id, workspace_id, actor_id)
    po = is_po(session, scoped, actor_id)
    table, _, _, _ = tables(session)
    rows = session.execute(sa.select(table).where(*(table.c[k] == v for k, v in scoped.items()))
        .order_by(table.c.updated_at.desc(), table.c.id)).mappings()
    return dict(can_decide=po, data=[public(session, row, po, actor_id) for row in rows])


def get_request(session, project_id, workspace_id, actor_id, request_id):
    scoped = scope(session, project_id, workspace_id, actor_id)
    return public(session, load(session, tables(session)[0], scoped, request_id),
        is_po(session, scoped, actor_id), actor_id, detail=True)


def validate(data, uploads):
    agents.body(data, ('title', 'content', 'attachment_ids', 'expected_revision'))
    agents.revision(data['expected_revision'])
    if not isinstance(data['title'], str) or not data['title'].strip() or len(data['title']) > 200:
        raise BadRequest('عنوان لازم و حداکثر ۲۰۰ نویسه است.')
    try:
        size = len(data['content'].encode()) if isinstance(data['content'], str) else 0
    except UnicodeError:
        raise BadRequest('متن درخواست باید UTF-8 معتبر باشد.') from None
    if not isinstance(data['content'], str) or not data['content'].strip() or size > 262144:
        raise BadRequest('متن درخواست لازم و حداکثر ۲۵۶ کیلوبایت است.')
    ids = data['attachment_ids']
    if not isinstance(ids, list) or len(ids) + len(uploads) > MAX_FILES:
        raise BadRequest('حداکثر پنج پیوست مجاز است.')
    ids = [uid(value) for value in ids]
    if len(ids) != len(set(ids)):
        raise BadRequest('پیوست تکراری معتبر نیست.')
    prepared = []
    for name, content in uploads:
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or any(ord(c) < 32 or ord(c) == 127 or c in '/\\' for c in name):
            raise BadRequest('نام پیوست معتبر نیست.')
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_FILE:
            raise BadRequest('اندازهٔ هر پیوست باید بین یک بایت و دو مگابایت باشد.')
        prepared.append(dict(name=name, size=len(content), digest=hashlib.sha256(content).hexdigest(), content=content))
    return ids, prepared


def save(session, project_id, workspace_id, actor_id, data, key, request_id=None, uploads=()):
    ids, files = validate(data, uploads)
    key = agents.action_key(key)
    scoped = scope(session, project_id, workspace_id, actor_id, write=True)
    table, revisions, attachments, _ = tables(session)
    row = load(session, table, scoped, request_id, lock=True) if request_id else None
    po = is_po(session, scoped, actor_id)
    if row and not (po or row['created_by'] == str(actor_id)):
        raise Forbidden('اصلاح درخواست با ثبت‌کننده یا PO پروژه است.')
    fingerprint = agents.digest(dict(operation='request.save', request_id=str(request_id) if request_id else None,
        body=data, uploads=[{k: v for k, v in value.items() if k != 'content'} for value in files]))
    replay = agents.replay(session, scoped, actor_id, key, fingerprint)
    if replay:
        return replay
    expected = data['expected_revision']
    if row and row['revision'] != expected:
        raise Conflict('درخواست تغییر کرده است؛ نسخهٔ تازه را دریافت کنید.')
    if row is None and expected != 1:
        raise BadRequest('درخواست تازه با نسخهٔ یک ثبت می‌شود.')
    retained = []
    for attachment_id in ids:
        value = session.execute(sa.select(attachments.c.id, attachments.c.name, attachments.c.size, attachments.c.digest)
            .where(attachments.c.id == attachment_id, attachments.c.request_id == str(request_id),
                *(attachments.c[k] == v for k, v in scoped.items()))).mappings().first()
        if value is None:
            raise NotFound('پیوست متعلق به این درخواست نیست.')
        retained.append(dict(value))
    if sum(value['size'] for value in [*retained, *files]) > MAX_TOTAL:
        raise BadRequest('مجموع پیوست‌های هر نسخه حداکثر پنج مگابایت است.')
    if row is None:
        row = dict(id=str(uuid4()), **scoped, revision=1, current_revision_id=None, current_decision_id=None,
            created_by=str(actor_id), created_at=agents.now(), updated_at=agents.now())
        session.execute(table.insert().values(**row))
    for value in files:
        record = dict(id=str(uuid4()), request_id=row['id'], **scoped, **value, created_by=str(actor_id), created_at=agents.now())
        session.execute(attachments.insert().values(**record))
        retained.append({k: record[k] for k in ('id', 'name', 'size', 'digest')})
    version = (session.scalar(sa.select(sa.func.max(revisions.c.version)).where(revisions.c.request_id == row['id'])) or 0) + 1
    content = dict(title=data['title'], content=data['content'], origin='manual', attachments=retained)
    revision = dict(id=str(uuid4()), request_id=row['id'], **scoped, version=version,
        title=data['title'], content=data['content'], origin='manual', attachment_ids=[v['id'] for v in retained],
        digest=agents.digest(content), author_id=str(actor_id), membership_id=team.member(session, workspace_id, actor_id).id,
        created_at=agents.now())
    session.execute(revisions.insert().values(**revision))
    row.update(revision=expected + 1 if request_id else 1, current_revision_id=revision['id'],
        current_decision_id=None, updated_at=agents.now())
    session.execute(table.update().where(table.c.id == row['id']).values(revision=row['revision'],
        current_revision_id=row['current_revision_id'], current_decision_id=None, updated_at=row['updated_at']))
    result = public(session, row, po, actor_id, detail=True)
    agents.event(session, scoped, actor_id, key, fingerprint, 'request.revised', result)
    return result


def expiry(value):
    if value is None:
        return None
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result <= agents.now():
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError):
        raise BadRequest('انقضا باید زمان آینده همراه منطقهٔ زمانی باشد.') from None


def decide(session, project_id, workspace_id, actor_id, request_id, data, key, revoke_id=None):
    fields = ('expected_revision', 'reason') if revoke_id else ('expected_revision', 'request_revision_id',
        'flow_id', 'flow_version_id', 'outcome', 'reason', 'expires_at')
    agents.body(data, fields)
    expected = agents.revision(data['expected_revision'])
    if not isinstance(data['reason'], str) or not data['reason'].strip() or len(data['reason']) > 2000:
        raise BadRequest('علت تصمیم لازم و حداکثر ۲۰۰۰ نویسه است.')
    key = agents.action_key(key)
    scoped = scope(session, project_id, workspace_id, actor_id, write=True)
    if not is_po(session, scoped, actor_id):
        raise Forbidden('تصمیم ورود فقط با نقش PO همین پروژه است.')
    table, revisions, _, decisions = tables(session)
    row = load(session, table, scoped, request_id, lock=True)
    fingerprint = agents.digest(dict(operation='request.revoke' if revoke_id else 'request.decide',
        request_id=str(request_id), revoke_id=str(revoke_id) if revoke_id else None, body=data))
    replay = agents.replay(session, scoped, actor_id, key, fingerprint)
    if replay:
        return replay
    if row['revision'] != expected:
        raise Conflict('درخواست یا تصمیم تغییر کرده است؛ نسخهٔ تازه را دریافت کنید.')
    current = session.execute(sa.select(revisions).where(revisions.c.id == row['current_revision_id'])).mappings().one()
    flow = None
    if revoke_id:
        previous = session.execute(sa.select(decisions).where(decisions.c.id == str(revoke_id),
            decisions.c.request_id == row['id'], *(decisions.c[k] == v for k, v in scoped.items()))).mappings().first()
        if not previous:
            raise NotFound('تصمیم در این درخواست پیدا نشد.')
        if row['current_decision_id'] != str(revoke_id) or previous['outcome'] != 'approved':
            raise Conflict('فقط تأیید جاری قابل ابطال است.')
        outcome, until = 'revoked', None
        if previous['flow_version_id']:
            flow = dict(id=previous['flow_version_id'], flow_id=previous['flow_id'], digest=previous['flow_digest'])
    else:
        if uid(data['request_revision_id']) != current['id']:
            raise Conflict('تصمیم باید برای نسخهٔ جاری درخواست باشد.')
        outcome = data['outcome']
        if outcome not in ('approved', 'rejected', 'deferred'):
            raise BadRequest('نوع تصمیم معتبر نیست.')
        until = expiry(data['expires_at'])
        if (data['flow_id'] is None) != (data['flow_version_id'] is None):
            raise BadRequest('فلو و نسخهٔ آن را با هم انتخاب کنید.')
        if data['flow_id'] is not None:
            flow_id, version_id = uid(data['flow_id']), uid(data['flow_version_id'])
            header = flows.load(session, scoped, flow_id)
            flow = flows.version(session, scoped, flow_id, version_id)
            if outcome == 'approved' and header['archived']:
                raise UnprocessableEntity('فلو بایگانی شده و ورود تازه به آن مجاز نیست.')
        if outcome == 'approved' and flow is None:
            raise UnprocessableEntity('برای تأیید ورود، نسخهٔ منتشرشدهٔ فلو را انتخاب کنید.')
    decision = dict(id=str(uuid4()), request_id=row['id'], **scoped, request_revision_id=current['id'],
        request_digest=current['digest'], flow_id=flow['flow_id'] if flow else None,
        flow_version_id=flow['id'] if flow else None, flow_digest=flow['digest'] if flow else None,
        outcome=outcome, mode='real', reason=data['reason'], actor_id=str(actor_id),
        membership_id=team.member(session, workspace_id, actor_id).id, created_at=agents.now(),
        expires_at=until, revokes_id=str(revoke_id) if revoke_id else None)
    session.execute(decisions.insert().values(**decision))
    row.update(revision=expected + 1, current_decision_id=decision['id'], updated_at=agents.now())
    session.execute(table.update().where(table.c.id == row['id']).values(revision=row['revision'],
        current_decision_id=decision['id'], updated_at=row['updated_at']))
    result = public(session, row, True, actor_id, detail=True)
    agents.event(session, scoped, actor_id, key, fingerprint, 'request.intake.' + outcome, result)
    return result


def download(session, project_id, workspace_id, actor_id, request_id, attachment_id):
    scoped = scope(session, project_id, workspace_id, actor_id)
    table, _, attachments, _ = tables(session)
    load(session, table, scoped, request_id)
    row = session.execute(sa.select(attachments).where(attachments.c.id == str(attachment_id),
        attachments.c.request_id == str(request_id), *(attachments.c[k] == v for k, v in scoped.items()))).mappings().first()
    if not row:
        raise NotFound('پیوست در این درخواست پیدا نشد.')
    return dict(name=row['name'], content=bytes(row['content']))
