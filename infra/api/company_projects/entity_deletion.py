"""Name-confirmed removal of team definitions while keeping immutable history."""
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from company_projects import agents, flows, team


def confirm_name(supplied, actual):
    # Do not trim/casefold: the user must submit the entire current name exactly.
    if not isinstance(supplied, str) or supplied != actual:
        raise BadRequest('برای تأیید حذف، نام کامل را دقیقاً مطابق نام نمایش‌داده‌شده وارد کنید.')


def require_idle_agent(session, row):
    attempts = agents.tables(session)[2]
    if session.scalar(sa.select(attempts.c.id).where(attempts.c.agent_id == row['id'],
            attempts.c.status.in_(['pending', 'running'])).limit(1)):
        raise Conflict('این ایجنت اجرای در صف یا در حال اجرا دارد؛ ابتدا وضعیت اجرا را مشخص کنید.')
    stages = agents.reflected(session, 'company_team_stages')
    if session.scalar(sa.select(stages.c.id).where(stages.c.workspace_id == row['workspace_id'],
            stages.c.project_id == row['project_id'], stages.c.binding['agent_id'].astext == row['id'],
            stages.c.state.notin_(['completed', 'cancelled'])).limit(1)):
        raise Conflict('این ایجنت در یک اجرای تیمی ناتمام استفاده می‌شود؛ ابتدا آن اجرا را تکمیل یا لغو کنید.')


def remove(session, project_id, workspace_id, actor_id, entity_id, data, key, kind):
    if kind not in {'agent', 'flow'}:
        raise BadRequest('نوع مورد برای حذف معتبر نیست.')
    agents.body(data, ('expected_revision', 'confirmation_name'))
    expected, key = agents.revision(data['expected_revision']), agents.action_key(key)
    # Same tenant lock as authoring, grants, run admission and instance creation.
    scoped = (team.scope if kind == 'agent' else flows.scope)(session, project_id, workspace_id, actor_id, write=True)
    table = agents.definitions(session) if kind == 'agent' else flows.tables(session)[0]
    row = (agents.load if kind == 'agent' else flows.load)(session, scoped, entity_id, lock=True)
    digest = agents.digest(dict(operation=kind+'.delete', id=row['id'], **data))
    previous = agents.replay(session, scoped, actor_id, key, digest)
    if previous:
        return previous
    if row.get('deleted_at') is not None:
        raise NotFound('این مورد قبلاً حذف شده است.')
    if row['revision'] != expected:
        raise Conflict('این مورد تغییر کرده است؛ اطلاعات تازه را دریافت و نام را دوباره تأیید کنید.')
    confirm_name(data['confirmation_name'], row['name'])
    if kind == 'agent':
        require_idle_agent(session, row)
    changes = dict(archived=True, deleted_at=agents.now(), revision=expected + 1)
    if kind == 'flow':
        changes['updated_at'] = changes['deleted_at']
    session.execute(table.update().where(table.c.id == row['id']).values(**changes))
    result = dict(id=row['id'], name=row['name'], deleted=True, revision=expected + 1)
    agents.event(session, scoped, actor_id, key, digest, kind+'.deleted', result)
    return result
