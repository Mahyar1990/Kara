"""Committed outbox, at-most-once claim and native Workflow execution boundary.

Pending records may be delivered repeatedly. A claimed record is never executed
again automatically, including after worker loss. KP-07 owns operator recovery.
"""
import logging
from contextvars import ContextVar
from uuid import uuid4

import sqlalchemy as sa
from celery import shared_task
from sqlalchemy.orm import Session
from werkzeug.exceptions import Conflict, Forbidden, HTTPException

from company_projects import agents, access, team
from extensions.ext_database import db
from models.account import Account, Tenant
from models.model import App
from models.workflow import Workflow, WorkflowRun

logger = logging.getLogger(__name__)
# In-process capability; it is never accepted from JSON, headers, task payloads or args.
_execution = ContextVar('kara_agent_execution', default=None)


def managed(session, app_id):
    """Existence/scope probe only; never use this arbitrary agent for authorization."""
    if not app_id:
        return None
    table = agents.definitions(session)
    return session.execute(sa.select(table).where(table.c.app_id == str(app_id), table.c.deleted_at.is_(None))).mappings().first()


def deny_native(app_id, *, session=None):
    if session is None:
        with Session(db.engine) as own:
            return deny_native(app_id, session=own)
    if managed(session, app_id):
        raise Forbidden('این برنامه ایجنت تیمی است؛ از صفحهٔ ایجنت‌های تیم اجرا کنید.')
    from company_projects.personal_agent_sources import metadata
    app = session.get(App, str(app_id)) if app_id else None
    if app and metadata(session.get(Workflow, app.workflow_id)) is not None:
        raise Forbidden('این برنامه اتصال ثابت ایجنت شخصی است؛ یک ایجنت تیمی تازه ثبت کنید.')


def assert_execution(tenant_id, app_id, workflow_id, user_id, run_id=None):
    with Session(db.engine) as session:
        capability = _execution.get()
        if managed(session, app_id) is None and capability is None:
            # Deleting the final binding releases fresh native runs, never old team attempts.
            if run_id:
                attempts = agents.reflected(session, 'company_team_agent_attempts')
                if session.scalar(sa.select(attempts.c.id).where(attempts.c.id == str(run_id)).limit(1)):
                    raise Forbidden('اجرای تیمی قبلی از مسیر اجرای بومی قابل شروع یا ادامه نیست.')
            return
        if capability is None or capability[1:] != (str(app_id), str(workflow_id), str(user_id)):
            raise Forbidden('اجرای ایجنت تیمی فقط از مسیر کنترل‌شده مجاز است.')
        _, _, attempts = agents.tables(session)
        attempt = session.execute(sa.select(attempts).where(attempts.c.id == capability[0])).mappings().first()
        table = agents.definitions(session)
        agent = session.execute(sa.select(table).where(table.c.id == attempt['agent_id'],
            table.c.app_id == str(app_id), table.c.project_id == attempt['project_id'],
            table.c.workspace_id == attempt['workspace_id'])).mappings().first() if attempt else None
        if not agent or attempt['status'] != 'running' or attempt['workspace_id'] != str(tenant_id) or (
                attempt['agent_id'] != agent['id'] or attempt['actor_id'] != str(user_id) or
                attempt['workflow_id'] != str(workflow_id)) or (
                run_id is not None and str(run_id) != attempt['id']):
            raise Forbidden('این تلاش اجرای معتبر نیست.')
        join = agents.require(session, agent, user_id, 'run')
        workflow = session.get(Workflow, str(workflow_id))
        if attempt['membership_id'] != join.id or agent['workflow_id'] != str(workflow_id) or workflow is None or (
                workflow.app_id != str(app_id) or workflow.tenant_id != str(tenant_id) or
                agents.fingerprint(workflow) != agent['workflow_digest']):
            raise Forbidden('مرجع اجرا، نسخه یا عضویت تغییر کرده است.')
        from company_projects.stages import validate_attempt
        validate_attempt(session, attempt)


def native_permission(session, app_id, actor_id, action='edit_definition'):
    from company_projects.personal_agent_sources import metadata
    app = session.get(App, str(app_id))
    if app and metadata(session.get(Workflow, app.workflow_id)) is not None:
        raise Forbidden('اتصال ایجنت شخصی ثابت است؛ منبع شخصی را ویرایش و اتصال تازه‌ای ثبت کنید.')
    table = agents.definitions(session)
    linked = list(session.execute(sa.select(table).where(table.c.app_id == str(app_id), table.c.deleted_at.is_(None))).mappings())
    if not linked:
        return
    active = [agent for agent in linked if not agent['archived']]
    if not active:
        raise Forbidden('همهٔ ایجنت‌های این برنامه بایگانی شده‌اند.')
    # Editing the shared source affects every active binding, so one agent's
    # grant must not bypass another agent's definition restrictions.
    for agent in active:
        try:
            agents.require(session, agent, actor_id, action)
        except Forbidden:
            raise Forbidden('برای تغییر برنامهٔ مشترک، مجوز مربوط در همهٔ ایجنت‌های فعال متصل لازم است.') from None
    agent = active[0]
    # These grants supplement native permissions; they cannot promote a reader.
    from configs import dify_config
    from core.rbac import RBACPermission
    from services.enterprise.rbac_service import RBACService
    join = access.membership(session, agent['workspace_id'], actor_id)
    if not join or join.role not in {'owner', 'admin', 'editor'}:
        raise Forbidden('مجوز فنی ویرایش برنامه لازم است.')
    if dify_config.RBAC_ENABLED:
        scene = RBACPermission.APP_RELEASE_AND_VERSION if action == 'publish_definition' else RBACPermission.APP_EDIT
        if not RBACService.CheckAccess.check(agent['workspace_id'], str(actor_id), scene=scene,
                resource_type='app', resource_id=str(app_id)):
            raise Forbidden('مجوز بومی این برنامه لازم است.')


def protect_source(session, app_id=None, workflow_id=None):
    table = agents.definitions(session)
    query = sa.select(table.c.id)
    query = query.where(table.c.app_id == str(app_id)) if app_id else query.where(table.c.workflow_id == str(workflow_id))
    if session.scalar(query.limit(1)):
        raise Conflict('این منبع در سابقهٔ ایجنت تیمی استفاده شده است و قابل حذف نیست؛ ایجنت را بایگانی کنید.')


def install_http_guard(app):
    @app.before_request
    def guard_managed_app():
        from flask import request
        app_id = (request.view_args or {}).get('app_id')
        if not app_id:
            return
        with Session(db.engine) as session:
            from company_projects.personal_agent_sources import metadata
            source_app = session.get(App, str(app_id))
            if source_app and metadata(session.get(Workflow, source_app.workflow_id)) is not None:
                raise Forbidden('اتصال ایجنت شخصی نسخهٔ ثابت است؛ آن را از صفحهٔ ایجنت‌های تیم مدیریت کنید.')
            agent = managed(session, app_id)
            if agent is None:
                return
            from libs.login import current_account_with_tenant
            try:
                actor, workspace_id = current_account_with_tenant()
            except Exception:
                raise Forbidden('ورود با حساب عضو پروژه لازم است.') from None
            team.scope(session, agent['project_id'], workspace_id, actor.id)
            segments = set(request.path.split('/'))
            if segments & {'run', 'run-all', 'stop', 'resume', 'trigger', 'triggers'} or request.method == 'DELETE':
                raise Forbidden('برای اجرای ایجنت تیمی از صفحهٔ ایجنت‌های تیم استفاده کنید؛ حذف منبع مجاز نیست.')
            action = 'publish_definition' if request.method != 'GET' and segments & {'publish', 'published'} else 'edit_definition'
            native_permission(session, app_id, actor.id, action)


def claim(session, attempt_id, *, start=True):
    _, _, attempts = agents.tables(session)
    candidate = session.execute(sa.select(attempts).where(attempts.c.id == str(attempt_id))).mappings().first()
    if not candidate:
        return None
    session.scalar(sa.select(Tenant).where(Tenant.id == candidate['workspace_id']).with_for_update())
    agent = agents.load(session, {k: candidate[k] for k in ('project_id', 'workspace_id')}, candidate['agent_id'], lock=True)
    row = session.execute(sa.select(attempts).where(attempts.c.id == candidate['id']).with_for_update()).mappings().one()
    if row['status'] != 'pending':
        return None
    try:
        join = agents.require(session, agent, row['actor_id'], 'run')
        workflow, app = session.get(Workflow, row['workflow_id']), session.get(App, agent['app_id'])
        if join.id != row['membership_id'] or not app or app.status != 'normal' or app.mode != 'workflow' or not workflow or (
                workflow.tenant_id != row['workspace_id'] or workflow.app_id != app.id or
                row['workflow_id'] != agent['workflow_id'] or agents.fingerprint(workflow) != agent['workflow_digest']):
            raise Forbidden('نسخه یا عضویت تغییر کرده است.')
        from company_projects.stages import validate_attempt
        validate_attempt(session, row)
    except HTTPException:
        session.execute(attempts.update().where(attempts.c.id == row['id']).values(status='blocked',
            finished_at=agents.now(), result={'error': 'دسترسی، عضویت یا نسخهٔ ایجنت تغییر کرده است.'}))
        from company_projects.stages import complete_attempt
        complete_attempt(session, row['id'])
        return None
    if start:
        session.execute(attempts.update().where(attempts.c.id == row['id']).values(status='running', started_at=agents.now()))
    return dict(row), dict(agent)


def native_task_id(app_id, run_id):
    capability = _execution.get()
    if capability and capability[0] == str(run_id) and capability[1] == str(app_id):
        return capability[0]
    return str(uuid4())


def finish(session, attempt_id, status, result):
    """A terminal fence wins even if the old engine returns success afterwards."""
    attempts = agents.tables(session)[2]
    row = session.execute(sa.select(attempts).where(attempts.c.id == str(attempt_id))).mappings().first()
    if not row:
        return False
    session.scalar(sa.select(Tenant).where(Tenant.id == row['workspace_id']).with_for_update())
    updated = session.execute(attempts.update().where(attempts.c.id == row['id'], attempts.c.status == 'running')
        .values(status=status, result=result, finished_at=agents.now()))
    if updated.rowcount != 1:
        return False
    from company_projects.stages import complete_attempt
    complete_attempt(session, row['id'])
    return True


def execute(attempt_id):
    """Dispatch only. No graph, model or tool execution is permitted centrally."""
    from company_projects.local_execution import dispatch_team
    with Session(db.engine) as session, session.begin():
        from company_projects import harness
        if harness.is_attempt(session,attempt_id):return
        dispatch_team(session, attempt_id)


@shared_task(queue='workflow_based_app_execution', name='kara.team_agent.execute')
def execute_task(attempt_id):
    execute(attempt_id)


def dispatch_stops():
    from core.app.apps.base_app_queue_manager import AppQueueManager
    from extensions.ext_redis import redis_client
    from graphon.graph_engine.manager import GraphEngineManager
    with Session(db.engine) as session:
        attempts = agents.tables(session)[2]
        rows = list(session.execute(sa.select(attempts.c.id).where(attempts.c.status == 'interrupted',
            attempts.c.result['stop_requested'].as_boolean() == True,
            sa.or_(attempts.c.result['stop_sent'].as_boolean().is_(None),
                attempts.c.result['stop_sent'].as_boolean() == False)).limit(100)).scalars())
    for identity in rows:
        try:
            AppQueueManager.set_stop_flag_no_user_check(identity)
            GraphEngineManager(redis_client).send_stop_command(identity)
            with Session(db.engine) as session, session.begin():
                attempts = agents.tables(session)[2]
                session.execute(attempts.update().where(attempts.c.id == identity, attempts.c.status == 'interrupted')
                    .values(result=attempts.c.result.op('||')(sa.func.jsonb_build_object('stop_sent', True))))
        except Exception:
            logger.exception('Team stop deferred: %s', identity)
    return len(rows)


def dispatch_pending():
    from company_projects.local_execution import expire
    with Session(db.engine) as session, session.begin():
        expire(session)
        from company_projects.local_rpc import expire as expire_rpc
        expire_rpc(session)
        from company_projects.harness import expire as expire_harness
        expire_harness(session)
    dispatch_stops()
    with Session(db.engine) as session:
        _, _, attempts = agents.tables(session)
        from company_projects.harness import table as harness_table
        harness_jobs=harness_table(session)
        ids = list(session.scalars(sa.select(attempts.c.id).where(attempts.c.status == 'pending')
            .where(~sa.exists(sa.select(1).select_from(harness_jobs).where(harness_jobs.c.attempt_id==attempts.c.id)))
            .order_by(attempts.c.created_at).limit(100)))
    for attempt_id in ids:
        execute_task.delay(attempt_id)
    return len(ids)


@shared_task(queue='workflow_based_app_execution', name='kara.team_agent.dispatch')
def dispatch_task():
    dispatch_pending()
