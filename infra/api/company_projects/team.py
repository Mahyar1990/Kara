"""Project business roles; native memberships and technical permissions stay intact."""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import access, store
from models.account import Account, AccountStatus, Tenant, TenantAccountJoin

BUSINESS_ROLES = ('po', 'tl', 'designer', 'developer', 'qc')


def tables(session):
    # Reflection uses the current transactional connection, including test savepoints.
    metadata = sa.MetaData()
    return tuple(sa.Table(name, metadata, autoload_with=session.connection()) for name in (
        'company_team_member_policies', 'company_team_roles', 'company_team_audit_events'))


def scope(session, project_id, workspace_id, actor_id, *, write=False):
    row = access.project_for_account(session, project_id, actor_id)
    if not row['workspace_id'] or str(row['workspace_id']) != str(workspace_id):
        raise Forbidden('ابتدا وارد فضای مستقل همین پروژه شوید.')
    if write:
        # Same lock as owner reassignment. Re-evaluate authority under the lock.
        session.scalar(sa.select(Tenant).where(Tenant.id == str(workspace_id)).with_for_update())
    actor = session.scalar(sa.select(Account).where(Account.id == str(actor_id)).execution_options(populate_existing=True))
    if actor is None or actor.status != AccountStatus.ACTIVE:
        raise Forbidden('حساب فعال لازم است.')
    if write and not access.can_manage_members(session, workspace_id, actor_id):
        raise Forbidden('تعیین نقش‌های کاری فقط با ادمین کل Kara و مدیر پروژه است.')
    return dict(project_id=str(project_id), workspace_id=str(workspace_id))


def member(session, workspace_id, account_id, *, lock=False):
    query = sa.select(TenantAccountJoin).where(TenantAccountJoin.tenant_id == str(workspace_id),
        TenantAccountJoin.account_id == str(account_id)).execution_options(populate_existing=True)
    result = session.scalar(query.with_for_update() if lock else query)
    if result is None:
        raise NotFound('کاربر عضو این پروژه نیست.')
    return result


def snapshot(session, key, join, *, reflected=None):
    policies, roles, _ = reflected or tables(session)
    conditions = [policies.c[k] == v for k, v in key.items()]
    policy = session.execute(sa.select(policies).where(*conditions)).mappings().first()
    values = list(session.scalars(sa.select(roles.c.business_role).where(
        *(roles.c[k] == v for k, v in key.items())).order_by(roles.c.business_role)))
    return dict(**key, membership_id=join.id, revision=policy['revision'] if policy else 1, roles=values)


def get_roles(session, project_id, workspace_id, actor_id, account_id):
    key = scope(session, project_id, workspace_id, actor_id)
    key['account_id'] = store.uid(account_id)
    return snapshot(session, key, member(session, workspace_id, account_id))


def list_roles(session, project_id, workspace_id, actor_id):
    key = scope(session, project_id, workspace_id, actor_id)
    reflected = tables(session)
    joins = session.scalars(sa.select(TenantAccountJoin).where(TenantAccountJoin.tenant_id == str(workspace_id)))
    return [snapshot(session, dict(**key, account_id=join.account_id), join, reflected=reflected) for join in joins]


def set_roles(session, project_id, workspace_id, actor_id, account_id, data, action_key):
    if not isinstance(data, dict) or set(data) != {'roles', 'expected_revision', 'expected_membership_id'}:
        raise BadRequest('نقش‌ها و نسخهٔ عضویت مبنا لازم است.')
    values, revision = data['roles'], data['expected_revision']
    if not isinstance(values, list) or any(type(role) is not str or role not in BUSINESS_ROLES for role in values) or len(values) != len(set(values)):
        raise BadRequest('نقش‌های کاری معتبر و بدون تکرار انتخاب کنید.')
    if type(revision) is not int or revision < 1:
        raise BadRequest('نسخهٔ مبنا معتبر نیست.')
    canonical_key = store.uid(action_key)
    if action_key != canonical_key:
        raise BadRequest('شناسهٔ اقدام باید UUID استاندارد باشد.')
    action_key = canonical_key
    membership_id = store.uid(data['expected_membership_id'])
    key = scope(session, project_id, workspace_id, actor_id, write=True)
    key['account_id'] = store.uid(account_id)
    join = member(session, workspace_id, account_id, lock=True)
    target = session.get(Account, str(account_id))
    if target is None or target.status != AccountStatus.ACTIVE:
        raise BadRequest('نقش کاری فقط به عضو فعال داده می‌شود.')
    if join.id != membership_id:
        raise Conflict('عضویت تغییر کرده است؛ فهرست اعضا را دوباره دریافت کنید.')
    policies, roles, audit = reflected = tables(session)
    digest = hashlib.sha256(json.dumps({**data, 'account_id': str(account_id), 'roles': sorted(values)},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    previous = session.execute(sa.select(audit).where(audit.c.project_id == key['project_id'],
        audit.c.workspace_id == key['workspace_id'], audit.c.actor_id == str(actor_id),
        audit.c.correlation_id == action_key)).mappings().first()
    if previous:
        if previous['request_digest'] != digest or str(previous['membership_id']) != membership_id:
            raise Conflict('این شناسهٔ اقدام برای درخواست دیگری استفاده شده است.')
        return previous['result']
    current = snapshot(session, key, join, reflected=reflected)
    if current['revision'] != revision:
        raise Conflict('نقش‌ها توسط فرد دیگری تغییر کرده‌اند؛ نسخهٔ تازه را دریافت کنید.')
    now = datetime.now(timezone.utc)
    if revision == 1:
        session.execute(policies.insert().values(**key, membership_id=join.id, revision=2))
    else:
        session.execute(policies.update().where(*(policies.c[k] == v for k, v in key.items())).values(revision=revision + 1))
    session.execute(roles.delete().where(*(roles.c[k] == v for k, v in key.items())))
    if values:
        session.execute(roles.insert(), [dict(**key, business_role=role, assigned_by=str(actor_id), assigned_at=now) for role in values])
    result = dict(**key, membership_id=join.id, revision=revision + 1, roles=sorted(values))
    session.execute(audit.insert().values(id=str(uuid4()), project_id=key['project_id'], workspace_id=key['workspace_id'],
        actor_id=str(actor_id), subject_id=str(account_id), membership_id=join.id,
        event_type='member.business_roles.replaced', occurred_at=now, correlation_id=action_key,
        request_digest=digest, result=result))
    return result


def before_member_removal(session, workspace_id, actor_id, account_id):
    """Native removal and its role revocation event share the native transaction."""
    project = access.workspace_project(session, workspace_id)
    if project is None:
        return
    key = scope(session, project['id'], workspace_id, actor_id, write=True)
    key['account_id'] = str(account_id)
    join = member(session, workspace_id, account_id, lock=True)
    reflected = tables(session)
    current = snapshot(session, key, join, reflected=reflected)
    _, _, audit = reflected
    session.execute(audit.insert().values(id=str(uuid4()), project_id=key['project_id'], workspace_id=key['workspace_id'],
        actor_id=str(actor_id), subject_id=str(account_id), membership_id=join.id,
        event_type='member.business_roles.revoked', occurred_at=datetime.now(timezone.utc),
        correlation_id=str(uuid4()), request_digest=hashlib.sha256(join.id.encode()).hexdigest(),
        result={**current, 'roles': [], 'removed_roles': current['roles'], 'membership_removed': True}))
