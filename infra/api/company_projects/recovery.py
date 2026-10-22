"""Explicit recovery and durable cancellation fences; never replays engine work."""
import os
from datetime import timedelta
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, HTTPException

from company_projects import access, agents, requests, stages, team
from company_projects.store import uid
from models.account import Account, AccountStatus, TenantAccountJoin


def limit(name, default, minimum, maximum):
    try:
        return max(minimum, min(int(os.environ.get(name, str(default))), maximum))
    except ValueError:
        return default


def retry_limit():
    return limit('KARA_TEAM_STAGE_RETRY_LIMIT', 3, 1, 20)


def cancellation(session, value):
    table = stages.table(session, 'company_team_cancellations')
    return session.execute(sa.select(table).where(table.c.instance_id == value['id'])).mappings().first()


def ensure_active(session, value):
    if cancellation(session, value):
        raise Conflict('این اجرای تیمی لغو شده است؛ ادامهٔ آن مجاز نیست.')


def manager(session, scope, actor):
    return access.can_manage_members(session, scope['workspace_id'], actor)


def can_cancel(session, scope, actor):
    return manager(session, scope, actor) or requests.is_po(session, scope, actor)


def overdue(stage, attempt):
    start = attempt['started_at'] or attempt['created_at']
    return start <= agents.now() - timedelta(seconds=limit('KARA_TEAM_RECOVERY_AFTER_SECONDS', 900, 60, 86400))


def stage_controls(session, scope, value, stage, actor):
    if cancellation(session, value):
        return []
    result = []
    if manager(session, scope, actor):
        if stage['state'] not in ('completed', 'cancelled') and stages.valid_intake(session, value):
            result.append('reassign')
        if stage['state'] == 'running':
            attempts = stages.table(session, 'company_team_agent_attempts')
            attempt = session.execute(sa.select(attempts).where(attempts.c.id == stage['active_attempt_id'])).mappings().first()
            if attempt and overdue(stage, attempt):
                result.append('recover')
        elif stage['state'] == 'failed' and stage['retry_count'] >= retry_limit():
            result.append('recover')
    if stage['state'] == 'completed' and stages.valid_intake(session, value):
        try:
            stages.require(session, scope, stage, actor, 'finalize')
            result.append('reopen')
        except HTTPException:
            pass
    return result


def overview(session, project, workspace, actor, instance_id):
    scope = stages.scoped(session, project, workspace, actor)
    value = stages.instance(session, scope, instance_id)
    rows = stages.stage_rows(session, value)
    result = stages.summary(session, value, actor)
    result.update(recovery_after_seconds=limit('KARA_TEAM_RECOVERY_AFTER_SECONDS', 900, 60, 86400),
        retry_limit=retry_limit(), can_manage=bool(manager(session, scope, actor)),
        can_cancel=bool(can_cancel(session, scope, actor) and not cancellation(session, value)
            and any(row['state'] != 'completed' for row in rows)),
        controls={row['id']: stage_controls(session, scope, value, row, actor) for row in rows}, members=[])
    if result['can_manage']:
        result['members'] = [dict(account_id=a.id, membership_id=j.id, name=a.name) for a, j in session.execute(
            sa.select(Account, TenantAccountJoin).join(TenantAccountJoin, TenantAccountJoin.account_id == Account.id)
            .where(TenantAccountJoin.tenant_id == workspace, Account.status == AccountStatus.ACTIVE).order_by(Account.name, Account.id))]
    events = stages.table(session, 'company_team_agent_events')
    result['history'] = [dict(kind=row['event_type'], actor_id=row['actor_id'], at=row['occurred_at'].isoformat(),
        change=row['result']['change']) for row in session.execute(sa.select(events).where(
            *(events.c[k] == v for k, v in scope.items()),
            events.c.event_type.like('recovery.%'), events.c.result['id'].astext == value['id'])
            .order_by(events.c.occurred_at, events.c.id)).mappings()]
    return result


def fence(session, scope, stage, reason):
    if not stage['active_attempt_id']:
        return
    attempts = stages.table(session, 'company_team_agent_attempts')
    # Tenant -> attempt is also the completion/claim lock order.
    session.execute(attempts.update().where(attempts.c.id == stage['active_attempt_id'],
        attempts.c.status.in_(['pending', 'running'])).values(status='interrupted', finished_at=agents.now(),
            result={'error': reason, 'stop_requested': True}))


def invalidate_from(session, value, ordinal, reason):
    entity = stages.tables(session)[1]
    affected = []
    for row in stages.stage_rows(session, value):
        if row['ordinal'] < ordinal or row['state'] == 'cancelled':
            continue
        fence(session, value, row, reason)
        untouched = row['ordinal'] > ordinal and row['state'] == 'blocked' and row['inputs'] is None
        new_round = row['round'] + 1
        session.execute(entity.update().where(entity.c.id == row['id']).values(
            state='blocked' if untouched else 'stale', revision=row['revision'] + 1, round=new_round,
            inputs=None, dependencies=None, input_digest=None, active_attempt_id=None, selected_artifact_id=None,
            retry_count=0, feedback_floor=new_round, updated_at=agents.now()))
        affected.append(row['id'])
    return affected


def record(session, scope, actor, key, digest, action, instance_id, change):
    # Audit stores control metadata only, never outputs or private agent history.
    result = dict(id=instance_id, change=change)
    agents.event(session, scope, actor, key, digest, 'recovery.' + action, result)
    return result


def cancel(session, project, workspace, actor, instance_id, data, key):
    agents.body(data, ('expected_revision', 'reason'))
    key, expected = agents.action_key(key), agents.revision(data['expected_revision'])
    scope = stages.scoped(session, project, workspace, actor, write=True)
    value = stages.instance(session, scope, instance_id)
    if not can_cancel(session, scope, actor):
        raise Forbidden('لغو اجرای تیمی با مالک محصول یا مدیر مجاز پروژه است.')
    reason = validated_reason(data)
    digest = agents.digest(dict(action='cancel', instance_id=str(instance_id), body=data))
    replay = agents.replay(session, scope, actor, key, digest)
    if replay:
        return replay
    ensure_active(session, value)
    rows = stages.stage_rows(session, value)
    if sum(row['revision'] for row in rows) != expected or all(row['state'] == 'completed' for row in rows):
        raise Conflict('اجرا تغییر کرده یا تمام شده است؛ وضعیت تازه را بررسی کنید.')
    entity = stages.table(session, 'company_team_cancellations')
    session.execute(entity.insert().values(instance_id=value['id'], **scope, actor_id=str(actor),
        membership_id=team.member(session, workspace, actor).id, reason=reason, created_at=agents.now()))
    entity = stages.tables(session)[1]
    for row in rows:
        if row['state'] == 'completed':
            continue
        fence(session, scope, row, reason)
        session.execute(entity.update().where(entity.c.id == row['id']).values(state='cancelled',
            active_attempt_id=None, selected_artifact_id=None, revision=row['revision'] + 1, updated_at=agents.now()))
    return record(session, scope, actor, key, digest, 'cancelled', value['id'], dict(reason=reason))


def validated_reason(data):
    reason = data['reason']
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise BadRequest('علت اقدام لازم و حداکثر ۲۰۰۰ نویسه است.')
    return reason


def mutate(session, project, workspace, actor, instance_id, stage_id, action, data, key):
    extra = dict(reassign=('executor_id', 'executor_membership_id', 'finalizer_id', 'finalizer_membership_id'),
        recover=('acknowledge_effects',), reopen=(), revalidate=())
    if action not in extra:
        raise BadRequest('اقدام بازیابی معتبر نیست.')
    agents.body(data, ('expected_revision', 'reason', *extra[action]))
    key, expected = agents.action_key(key), agents.revision(data['expected_revision'])
    reason = validated_reason(data)
    scope = stages.scoped(session, project, workspace, actor, write=True)
    value = stages.instance(session, scope, instance_id)
    ensure_active(session, value)
    entity = stages.tables(session)[1]
    row = stages.load(session, entity, scope, stage_id, lock=True)
    if row['instance_id'] != value['id']:
        from werkzeug.exceptions import NotFound
        raise NotFound('مرحله در این اجرا پیدا نشد.')
    if action == 'revalidate':
        stages.require(session, scope, row, actor, 'run')
    elif action == 'reopen':
        stages.require(session, scope, row, actor, 'finalize')
    elif not manager(session, scope, actor):
        raise Forbidden('این اقدام با مدیر مجاز پروژه است.')
    digest = agents.digest(dict(action=action, instance_id=str(instance_id), stage_id=str(stage_id), body=data))
    replay = agents.replay(session, scope, actor, key, digest)
    if replay:
        return replay
    if row['revision'] != expected:
        raise Conflict('مرحله تغییر کرده است؛ وضعیت تازه را دریافت کنید.')
    if action == 'revalidate':
        if row['state'] != 'stale':
            raise Conflict('فقط مرحلهٔ نیازمند بررسی مجدد قابل بازاعتبارسنجی است.')
        inputs, _ = stages.resolve(session, value, row)
        agents.validate_inputs(row['binding']['input_contract'], inputs)
        session.execute(entity.update().where(entity.c.id == row['id']).values(state='ready',
            revision=expected + 1, updated_at=agents.now()))
        change = dict(stage_id=row['id'], reason=reason)
    elif action == 'recover':
        if action not in stage_controls(session, scope, value, row, actor):
            raise Conflict('هنوز مهلت بررسی اجرای معلق یا سقف تلاش مجدد نرسیده است.')
        if data['acknowledge_effects'] is not True:
            raise BadRequest('آثار احتمالی اجرای قبلی باید صریح بررسی و تأیید شوند.')
        fence(session, scope, row, reason)
        session.execute(entity.update().where(entity.c.id == row['id']).values(state='failed', retry_count=0,
            active_attempt_id=None, selected_artifact_id=None, revision=expected + 1, updated_at=agents.now()))
        change = dict(stage_id=row['id'], reason=reason, fenced_attempt_id=row['active_attempt_id'], acknowledge_effects=True)
    else:
        stages.intake(session, value)
        if action == 'reopen' and row['state'] != 'completed':
            raise Conflict('بازگشایی فقط برای مرحلهٔ نهایی‌شده است.')
        if action == 'reassign' and row['state'] in ('completed', 'cancelled'):
            raise Conflict('پیش از تغییر مسئول مرحلهٔ نهایی‌شده، نهایی‌کننده باید آن را بازگشایی کند.')
        change = dict(stage_id=row['id'], reason=reason, previous_round=row['round'],
            previous_selected_artifact_id=row['selected_artifact_id'], fenced_attempt_id=row['active_attempt_id'])
        if action == 'reassign':
            people = {}
            for field, permission in (('executor', 'run'), ('finalizer', 'finalize')):
                person, membership = uid(data[field + '_id']), uid(data[field + '_membership_id'])
                join = team.member(session, workspace, person)
                account = session.get(Account, person)
                if join.id != membership or account.status != AccountStatus.ACTIVE:
                    raise Conflict('عضویت یا وضعیت مسئول منتخب تغییر کرده است.')
                people[field] = dict(account_id=person, membership_id=membership, name=account.name)
                candidate = dict(row, binding=dict(row['binding'], **people))
                stages.require(session, scope, candidate, person, permission)
            if all(people[k] == row['binding'][k] for k in people):
                raise Conflict('مسئول‌ها تغییری نکرده‌اند.')
            session.execute(entity.update().where(entity.c.id == row['id']).values(assignment=people))
            change.update(before={k: row['binding'][k] for k in people}, after=people)
        change['affected_stage_ids'] = invalidate_from(session, value, row['ordinal'], reason)
    return record(session, scope, actor, key, digest, action, value['id'], change)


def request_changed(session, scope, request_id, actor):
    entity = stages.tables(session)[0]
    for value in session.execute(sa.select(entity).where(entity.c.request_id == request_id,
            *(entity.c[k] == v for k, v in scope.items()))).mappings():
        if cancellation(session, value) or stages.valid_intake(session, value):
            continue
        rows = stages.stage_rows(session, value)
        if not any(row['state'] != 'stale' and row['state'] != 'blocked' for row in rows):
            continue
        affected = invalidate_from(session, value, 0, 'نسخهٔ درخواست یا تصمیم ورود تغییر کرده است.')
        key = str(uuid4())
        record(session, scope, actor, key, agents.digest(dict(request_id=request_id, key=key)),
            'request_invalidated', value['id'], dict(reason='نسخهٔ درخواست یا تصمیم ورود تغییر کرده است.', affected_stage_ids=affected))
