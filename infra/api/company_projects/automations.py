"""Project automation management backed by Dify's native triggers and queues."""
from datetime import datetime, timezone

import sqlalchemy as sa
import yaml
from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import access, store
from company_projects.automation_schedule import AutomationError, schedule_data, scheduled_graph, source_fields
from company_projects.controller import guarded, identity, payload, visible_app, visible_filters
from company_projects.inbox import timestamp
from configs import dify_config
from controllers.console import console_ns
from controllers.console.wraps import cloud_edition_billing_resource_check
from core.rbac import RBACPermission
from core.workflow.nodes.trigger_schedule.entities import TriggerScheduleNodeData, VisualConfig
from extensions.ext_database import db
from libs.schedule_utils import calculate_next_run_at
from models.model import App
from models.trigger import AppTrigger, AppTriggerStatus, WorkflowSchedulePlan, WorkflowTriggerLog
from models.workflow import Workflow, WorkflowRun
from services.app_dsl_service import AppDslService, ImportStatus
from services.enterprise.rbac_service import RBACService
from services.trigger.schedule_service import ScheduleService
from services.workflow_service import WorkflowService


def allowed(session, tenant_id, account, app_id, scene):
    if dify_config.RBAC_ENABLED:
        return RBACService.CheckAccess.check(tenant_id, account.id, scene=scene, resource_type='app', resource_id=app_id)
    member = access.membership(session, tenant_id, account.id)
    return member is not None and member.role in {'owner', 'admin', 'editor'}


def require_permission(session, tenant_id, account, app_id, scene):
    if not allowed(session, tenant_id, account, app_id, scene):
        raise Forbidden('دسترسی لازم برای مدیریت این اتوماسیون را ندارید.')


def schedule_config(value):
    try:
        data = schedule_data(value)
        parsed = TriggerScheduleNodeData.model_validate(data)
        cron = ScheduleService.visual_to_cron(parsed.frequency, VisualConfig.model_validate(parsed.visual_config))
        next_at = calculate_next_run_at(cron, parsed.timezone)
        return data, cron, next_at
    except (AutomationError, ValueError, TypeError):
        raise BadRequest('زمان‌بندی معتبر نیست. ساعت، دقیقه و روزهای انتخاب‌شده را بررسی کنید.') from None


def available_sources(session, project_id, tenant_id, account):
    access.validate_app_project(session, tenant_id, project_id, account.id)
    filters = visible_filters(session, tenant_id, account.id)
    if not filters:
        return []
    rows = session.execute(sa.select(App, Workflow).join(Workflow, sa.and_(Workflow.id == App.workflow_id,
        Workflow.app_id == App.id, Workflow.tenant_id == tenant_id)).where(*filters, App.mode == 'workflow',
        Workflow.version != Workflow.VERSION_DRAFT).order_by(App.name)).all()
    result = []
    for app, workflow in rows:
        if not allowed(session, tenant_id, account, app.id, RBACPermission.APP_IMPORT_EXPORT_DSL):
            continue
        reason, fields = '', []
        try:
            _, fields = source_fields(workflow.graph_dict)
        except AutomationError as exc:
            reason = str(exc)
        result.append(dict(id=app.id, name=app.name, workflow_id=workflow.id, available=not reason, reason=reason,
            fields=[{key: field.get(key) for key in ('variable', 'label', 'type', 'required', 'options', 'max_length')} for field in fields]))
    return result


def scoped_trigger(session, project_id, tenant_id, account, trigger_id, lock=False):
    access.validate_app_project(session, tenant_id, project_id, account.id)
    trigger = session.scalar(sa.select(AppTrigger).where(AppTrigger.id == store.uid(trigger_id), AppTrigger.tenant_id == tenant_id))
    if trigger is None:
        raise NotFound('اتوماسیون پیدا نشد.')
    app = visible_app(session, tenant_id, account.id, trigger.app_id)
    require_permission(session, tenant_id, account, app.id, RBACPermission.APP_VIEW_LAYOUT)
    if lock:
        # Lock the app, not the trigger: native publication reconciles triggers in
        # separate sessions, so holding a trigger row would deadlock that handler.
        app = session.scalar(sa.select(App).where(App.id == app.id, App.tenant_id == tenant_id).with_for_update())
    return trigger, app


def trigger_summary(session, trigger, app, account):
    schedule = session.scalar(sa.select(WorkflowSchedulePlan).where(WorkflowSchedulePlan.tenant_id == app.tenant_id,
        WorkflowSchedulePlan.app_id == app.id, WorkflowSchedulePlan.node_id == trigger.node_id))
    latest = session.scalar(sa.select(WorkflowTriggerLog).where(WorkflowTriggerLog.tenant_id == app.tenant_id,
        WorkflowTriggerLog.app_id == app.id, WorkflowTriggerLog.root_node_id == trigger.node_id)
        .order_by(WorkflowTriggerLog.created_at.desc(), WorkflowTriggerLog.id.desc()).limit(1))
    last = None
    if latest:
        run = session.scalar(sa.select(WorkflowRun).where(WorkflowRun.id == latest.workflow_run_id,
            WorkflowRun.tenant_id == app.tenant_id, WorkflowRun.app_id == app.id)) if latest.workflow_run_id else None
        last = dict(id=latest.id, status=str(run.status if run else latest.status), created_at=timestamp(latest.created_at),
            run_id=run.id if run else None)
    managed = session.scalar(sa.select(store.automations.c.app_id).where(store.automations.c.app_id == app.id,
        store.automations.c.tenant_id == app.tenant_id)) is not None
    return dict(id=trigger.id, app_id=app.id, name=app.name, title=trigger.title, type=str(trigger.trigger_type), managed=managed,
        status=str(trigger.status), published=bool(app.workflow_id),
        can_manage=allowed(session, app.tenant_id, account, app.id, RBACPermission.APP_EDIT),
        can_publish=allowed(session, app.tenant_id, account, app.id, RBACPermission.APP_RELEASE_AND_VERSION),
        timezone=schedule.timezone if schedule else None,
        next_run_at=timestamp(schedule.next_run_at) if schedule and trigger.status == AppTriggerStatus.ENABLED else None,
        last_run=last)


def create_automation(session, project_id, tenant_id, account, data):
    access.validate_app_project(session, tenant_id, project_id, account.id)
    name = data.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise BadRequest('نام اتوماسیون الزامی و حداکثر ۱۲۰ نویسه است.')
    source = visible_app(session, tenant_id, account.id, data.get('source_app_id'))
    require_permission(session, tenant_id, account, source.id, RBACPermission.APP_IMPORT_EXPORT_DSL)
    if source.mode != 'workflow' or not source.workflow_id or source.workflow_id != data.get('source_workflow_id'):
        raise Conflict('نسخهٔ منتشرشدهٔ فرایند تغییر کرده است. فهرست فرایندها را به‌روزرسانی کنید.')
    workflow = WorkflowService().get_published_workflow(source, session=session)
    if workflow is None:
        raise Conflict('ابتدا فرایند مبنا را منتشر کنید.')
    schedule_config(data.get('schedule'))
    try:
        # Export only the chosen published version. Secrets stay in memory and are
        # re-encrypted by native import into the SAME tenant; no DSL leaves the API.
        dsl = yaml.safe_load(AppDslService.export_dsl(source, session=session, include_secret=True, workflow_id=workflow.id))
        graph, node_id = scheduled_graph(dsl['workflow']['graph'], data.get('schedule'), data.get('inputs', {}))
        dsl['workflow']['graph'] = graph
    except AutomationError as exc:
        raise BadRequest(str(exc)) from None
    result = AppDslService(session).import_app(account=account, import_mode='yaml-content',
        yaml_content=yaml.safe_dump(dsl, allow_unicode=True), name=name.strip(), description=source.description or '')
    if result.status != ImportStatus.COMPLETED or not result.app_id:
        # The caller wraps native internal commits in one outer transaction.
        raise Conflict('ساخت اتوماسیون انجام نشد. وابستگی‌ها و دسترسی فرایند را بررسی کنید.')
    app = session.get(App, result.app_id)
    if app.tenant_id != tenant_id:
        raise Conflict('فضای اتوماسیون با پروژه یکسان نیست.')
    app.enable_api = False
    app.enable_site = False
    store.assign(session.connection(), access.authority(session)['tenant_id'], project_id, app.id)
    session.execute(store.automations.insert().values(app_id=app.id, tenant_id=tenant_id, source_app_id=source.id,
        source_workflow_id=workflow.id, created_by=account.id, created_at=datetime.now(timezone.utc)))
    trigger = AppTrigger(tenant_id=tenant_id, app_id=app.id, node_id=node_id, trigger_type='trigger-schedule',
        title='زمان‌بندی', status=AppTriggerStatus.DISABLED)
    session.add(trigger)
    session.flush()
    return trigger_summary(session, trigger, app, account)


def set_enabled(session, project_id, tenant_id, account, trigger_id, data):
    trigger, app = scoped_trigger(session, project_id, tenant_id, account, trigger_id, lock=True)
    require_permission(session, tenant_id, account, app.id, RBACPermission.APP_EDIT)
    enabled = data.get('enabled')
    if type(enabled) is not bool:
        raise BadRequest('وضعیت فعال‌سازی معتبر نیست.')
    if enabled:
        if data.get('reviewed') is not True:
            raise BadRequest('ابتدا فرایند و ورودی‌ها را بررسی و آماده‌بودن آن را تأیید کنید.')
        require_permission(session, tenant_id, account, app.id, RBACPermission.APP_RELEASE_AND_VERSION)
        managed = session.scalar(sa.select(store.automations.c.app_id).where(store.automations.c.app_id == app.id,
            store.automations.c.tenant_id == tenant_id))
        if managed:
            draft = WorkflowService().get_draft_workflow(app, session=session)
            node = next((node for node in draft.graph_dict.get('nodes', []) if node.get('id') == trigger.node_id), None) if draft else None
            starts = [item for item in draft.graph_dict.get('nodes', []) if item.get('data', {}).get('type', '').startswith('trigger-')] if draft else []
            if not node or node.get('data', {}).get('type') != 'trigger-schedule' or len(starts) != 1:
                raise Conflict('شروع زمان‌بندی در فرایند تغییر کرده است. ابتدا فرایند را بررسی کنید.')
            if trigger.status != AppTriggerStatus.ENABLED:
                workflow = WorkflowService().publish_workflow(session=session, app_model=app, account=account)
                app.workflow_id = workflow.id
                session.flush()
                # Native handlers use their own transactions; reload the plan.
                plan = session.scalar(sa.select(WorkflowSchedulePlan).where(WorkflowSchedulePlan.app_id == app.id,
                    WorkflowSchedulePlan.tenant_id == tenant_id, WorkflowSchedulePlan.node_id == trigger.node_id))
                if plan is None:
                    raise Conflict('زمان‌بندی فرایند آماده نشده است.')
        elif not app.workflow_id:
            raise Conflict('ابتدا فرایند را از صفحهٔ آن منتشر کنید.')
        published = WorkflowService().get_published_workflow(app, session=session)
        if not published or not any(item.get('id') == trigger.node_id and item.get('data', {}).get('type') == trigger.trigger_type
                for item in published.graph_dict.get('nodes', [])):
            raise Conflict('شروع خودکار در نسخهٔ منتشرشده وجود ندارد. ابتدا فرایند را بررسی و منتشر کنید.')
        # Re-enabling advances the clock, so a paused overdue slot is not replayed.
        plan = session.scalar(sa.select(WorkflowSchedulePlan).where(WorkflowSchedulePlan.app_id == app.id,
            WorkflowSchedulePlan.tenant_id == tenant_id, WorkflowSchedulePlan.node_id == trigger.node_id))
        if trigger.trigger_type == 'trigger-schedule' and plan is None:
            raise Conflict('زمان‌بندی فرایند آماده نشده است. ابتدا فرایند را بررسی و منتشر کنید.')
        if plan and trigger.status != AppTriggerStatus.ENABLED:
            plan.next_run_at = calculate_next_run_at(plan.cron_expression, plan.timezone)
    trigger.status = AppTriggerStatus.ENABLED if enabled else AppTriggerStatus.DISABLED
    session.flush()
    return trigger_summary(session, trigger, app, account)


@console_ns.route('/company/projects/<uuid:project_id>/automations')
class AutomationsApi(Resource):
    @guarded()
    def get(self, project_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            access.validate_app_project(session, tenant_id, project_id, account.id)
            filters = visible_filters(session, tenant_id, account.id)
            if not filters:
                return dict(data=[], total=0, page=1, has_more=False)
            try:
                page = max(1, int(request.args.get('page', 1)))
            except ValueError:
                raise BadRequest('شمارهٔ صفحه معتبر نیست.') from None
            apps = [app for app in session.scalars(sa.select(App).where(*filters, App.mode == 'workflow'))
                if allowed(session, tenant_id, account, app.id, RBACPermission.APP_VIEW_LAYOUT)]
            conditions = [AppTrigger.tenant_id == tenant_id, AppTrigger.app_id.in_([app.id for app in apps])]
            status = request.args.get('status', 'all')
            if status not in {'all', 'enabled', 'disabled', 'unauthorized', 'rate_limited'}:
                raise BadRequest('وضعیت معتبر نیست.')
            if status != 'all':
                conditions.append(AppTrigger.status == status)
            name = request.args.get('name', '')[:120]
            if name:
                conditions.append(AppTrigger.app_id.in_([app.id for app in apps if name.casefold() in app.name.casefold()]))
            total = session.scalar(sa.select(sa.func.count()).select_from(AppTrigger).where(*conditions))
            triggers = session.scalars(sa.select(AppTrigger).where(*conditions).order_by(AppTrigger.created_at.desc(),
                AppTrigger.id.desc()).offset((page - 1) * 25).limit(25))
            by_id = {app.id: app for app in apps}
            return dict(data=[trigger_summary(session, item, by_id[item.app_id], account) for item in triggers],
                total=total, page=page, has_more=page * 25 < total)

    @guarded(write=True)
    @cloud_edition_billing_resource_check('apps')
    def post(self, project_id):
        account, tenant_id = identity()
        data = payload()
        with db.engine.begin() as connection, Session(bind=connection, join_transaction_mode='create_savepoint') as session:
            result = create_automation(session, project_id, tenant_id, account, data)
            session.commit()
            return result, 201


@console_ns.route('/company/projects/<uuid:project_id>/automations/sources')
class AutomationSourcesApi(Resource):
    @guarded()
    def get(self, project_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            return dict(data=available_sources(session, project_id, tenant_id, account))


@console_ns.route('/company/projects/<uuid:project_id>/automations/preview')
class AutomationPreviewApi(Resource):
    @guarded()
    def post(self, project_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            access.validate_app_project(session, tenant_id, project_id, account.id)
            _, cron, next_at = schedule_config(payload().get('schedule'))
            return dict(timezone='Asia/Tehran', next_run_at=timestamp(next_at))


@console_ns.route('/company/projects/<uuid:project_id>/automations/<uuid:trigger_id>/state')
class AutomationStateApi(Resource):
    @guarded()
    def post(self, project_id, trigger_id):
        account, tenant_id = identity()
        with Session(db.engine) as session, session.begin():
            return set_enabled(session, project_id, tenant_id, account, trigger_id, payload())


@console_ns.route('/company/projects/<uuid:project_id>/automations/<uuid:trigger_id>/schedule')
class AutomationScheduleApi(Resource):
    @guarded()
    def get(self, project_id, trigger_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            trigger, app = scoped_trigger(session, project_id, tenant_id, account, trigger_id)
            draft = WorkflowService().get_draft_workflow(app, session=session)
            node = next((node for node in draft.graph_dict.get('nodes', []) if node.get('id') == trigger.node_id), None) if draft else None
            if not node or node.get('data', {}).get('type') != 'trigger-schedule':
                raise Conflict('زمان‌بندی را از صفحهٔ فرایند تنظیم کنید.')
            data = node['data']
            if data.get('mode') != 'visual' or data.get('timezone') != 'Asia/Tehran':
                raise Conflict('این زمان‌بندی تنظیمات پیشرفته دارد؛ آن را از صفحهٔ فرایند ویرایش کنید.')
            visual = data.get('visual_config', {})
            from libs.schedule_utils import convert_12h_to_24h
            hour, minute = convert_12h_to_24h(visual.get('time') or '12:00 AM')
            return dict(frequency=data.get('frequency'), time=f'{hour:02d}:{minute:02d}',
                minute=visual.get('on_minute', 0), weekdays=visual.get('weekdays', ['sat']),
                day=(visual.get('monthly_days') or [1])[0])

    @guarded()
    def put(self, project_id, trigger_id):
        account, tenant_id = identity()
        with Session(db.engine) as session, session.begin():
            trigger, app = scoped_trigger(session, project_id, tenant_id, account, trigger_id, lock=True)
            require_permission(session, tenant_id, account, app.id, RBACPermission.APP_EDIT)
            if trigger.status == AppTriggerStatus.ENABLED:
                raise Conflict('ابتدا اتوماسیون را متوقف کنید و سپس زمان‌بندی را تغییر دهید.')
            if not session.scalar(sa.select(store.automations.c.app_id).where(store.automations.c.app_id == app.id,
                    store.automations.c.tenant_id == tenant_id)):
                raise Conflict('زمان‌بندی این فرایند را از صفحهٔ خود آن ویرایش کنید.')
            service = WorkflowService()
            draft = service.get_draft_workflow(app, session=session)
            graph = draft.graph_dict if draft else {}
            node = next((node for node in graph.get('nodes', []) if node.get('id') == trigger.node_id), None)
            if not node or node.get('data', {}).get('type') != 'trigger-schedule':
                raise Conflict('شروع زمان‌بندی در فرایند تغییر کرده است.')
            data, _, next_at = schedule_config(payload().get('schedule'))
            node['data'] = {**node['data'], **data}
            service.sync_draft_workflow(app_model=app, graph=graph, features=draft.features_dict,
                unique_hash=draft.unique_hash, account=account, environment_variables=draft.environment_variables,
                conversation_variables=draft.conversation_variables, session=session, commit=False)
            return dict(result='success', next_run_at=timestamp(next_at), timezone='Asia/Tehran')
