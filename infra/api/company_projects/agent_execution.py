"""Committed outbox, at-most-once claim and native Workflow execution boundary.

Pending records may be delivered repeatedly. A claimed record is never executed
again automatically, including after worker loss. KP-07 owns operator recovery.
"""
import logging
from contextvars import ContextVar

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
    if not app_id:
        return None
    table = agents.definitions(session)
    return session.execute(sa.select(table).where(table.c.app_id == str(app_id))).mappings().first()


def deny_native(app_id, *, session=None):
    if session is None:
        with Session(db.engine) as own:
            return deny_native(app_id, session=own)
    if managed(session, app_id):
        raise Forbidden('این برنامه ایجنت تیمی است؛ از صفحهٔ ایجنت‌های تیم اجرا کنید.')


def assert_execution(tenant_id, app_id, workflow_id, user_id, run_id=None):
    with Session(db.engine) as session:
        agent = managed(session, app_id)
        if agent is None:
            return
        capability = _execution.get()
        if capability is None or capability[1:] != (str(app_id), str(workflow_id), str(user_id)):
            raise Forbidden('اجرای ایجنت تیمی فقط از مسیر کنترل‌شده مجاز است.')
        _, _, attempts = agents.tables(session)
        attempt = session.execute(sa.select(attempts).where(attempts.c.id == capability[0])).mappings().first()
        if not attempt or attempt['status'] != 'running' or attempt['workspace_id'] != str(tenant_id) or (
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


def native_permission(session, app_id, actor_id, action='edit_definition'):
    agent = managed(session, app_id)
    if agent is None:
        return
    agents.require(session, agent, actor_id, action)
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


def claim(session, attempt_id):
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
    except HTTPException:
        session.execute(attempts.update().where(attempts.c.id == row['id']).values(status='blocked',
            finished_at=agents.now(), result={'error': 'دسترسی، عضویت یا نسخهٔ ایجنت تغییر کرده است.'}))
        return None
    session.execute(attempts.update().where(attempts.c.id == row['id']).values(status='running', started_at=agents.now()))
    return dict(row), dict(agent)


def execute(attempt_id):
    with Session(db.engine) as session, session.begin():
        claimed = claim(session, attempt_id)
    if claimed is None:
        return
    attempt, agent = claimed
    token = _execution.set((attempt['id'], agent['app_id'], attempt['workflow_id'], attempt['actor_id']))
    try:
        from core.app.apps.workflow.app_generator import WorkflowAppGenerator
        from core.app.entities.app_invoke_entities import InvokeFrom
        from services.app_generate_service import AppGenerateService
        with Session(db.engine, expire_on_commit=False) as session:
            app, workflow, actor = session.get(App, agent['app_id']), session.get(Workflow, attempt['workflow_id']), session.get(Account, attempt['actor_id'])
            # Reuse native rate/quota limits, engine, repositories, tracing and fixed run ID.
            AppGenerateService._run_with_guardrails(app_model=app, streaming=False,
                action=lambda rate, request_id: rate.generate(WorkflowAppGenerator.convert_to_event_stream(
                    WorkflowAppGenerator().generate(app_model=app, workflow=workflow, user=actor,
                        args={'inputs': attempt['inputs'], 'files': []}, invoke_from=InvokeFrom.EXPLORE,
                        streaming=False, workflow_run_id=attempt['id'])), request_id=request_id))
        with Session(db.engine) as session, session.begin():
            _, _, attempts = agents.tables(session)
            run = session.get(WorkflowRun, attempt['id'])
            if run and run.status == 'succeeded':
                output = {k: v for k, v in (run.outputs_dict or {}).items() if k in agent['output_contract']}
                status, result = 'succeeded', {'outputs': output}
            else:
                status, result = 'failed', {'error': 'اجرای فرایند موفق نشد. ورودی‌ها و تنظیمات را با مسئول ایجنت بررسی کنید.'}
            session.execute(attempts.update().where(attempts.c.id == attempt['id']).values(
                status=status, result=result, finished_at=agents.now()))
    except Exception:
        logger.exception('Team agent attempt failed: %s', attempt['id'])
        with Session(db.engine) as session, session.begin():
            _, _, attempts = agents.tables(session)
            session.execute(attempts.update().where(attempts.c.id == attempt['id']).values(status='failed',
                result={'error': 'اجرای ایجنت انجام نشد. تنظیمات و دسترسی‌ها را بررسی کنید.'}, finished_at=agents.now()))
    finally:
        _execution.reset(token)


@shared_task(queue='workflow_based_app_execution', name='kara.team_agent.execute')
def execute_task(attempt_id):
    execute(attempt_id)


def dispatch_pending():
    with Session(db.engine) as session:
        _, _, attempts = agents.tables(session)
        ids = list(session.scalars(sa.select(attempts.c.id).where(attempts.c.status == 'pending')
            .order_by(attempts.c.created_at).limit(100)))
    for attempt_id in ids:
        execute_task.delay(attempt_id)
    return len(ids)


@shared_task(queue='workflow_based_app_execution', name='kara.team_agent.dispatch')
def dispatch_task():
    dispatch_pending()
