"""Project workflow executions and identity-bound native human approvals."""
import json
from datetime import datetime, timezone

import sqlalchemy as sa
from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import access, store
from company_projects.controller import guarded, identity, payload, visible_filters
from configs import dify_config
from controllers.console import console_ns
from core.rbac import RBACPermission
from extensions.ext_database import db
from models.human_input import HumanInputForm, HumanInputFormRecipient, RecipientType
from models.model import App
from models.workflow import WorkflowRun
from services.enterprise.rbac_service import RBACService
from services.human_input_service import HumanInputService, FormExpiredError, FormSubmittedError, InvalidFormDataError

STATUSES = {'running', 'paused', 'succeeded', 'failed', 'stopped', 'partial-succeeded'}


def can_read_payload(session, tenant_id, account, app_id):
    member = access.membership(session, tenant_id, account.id)
    if dify_config.RBAC_ENABLED:
        return RBACService.CheckAccess.check(tenant_id, account.id,
            scene=RBACPermission.APP_CREATE_AND_MANAGEMENT, resource_type='app', resource_id=app_id)
    return member is not None and member.role in {'owner', 'admin', 'editor'}


def recipient_condition(account_id):
    record = sa.cast(HumanInputFormRecipient.recipient_payload, sa.JSON)
    return sa.or_(sa.and_(HumanInputFormRecipient.recipient_type == 'email_member', record['user_id'].as_string() == account_id),
        sa.and_(HumanInputFormRecipient.recipient_type.in_(['console', 'backstage']), sa.or_(
            record['account_id'].as_string() == account_id,
            sa.and_(record['account_id'].as_string().is_(None), WorkflowRun.created_by_role == 'account', WorkflowRun.created_by == account_id))))


def run_conditions(session, tenant_id, account):
    filters = visible_filters(session, tenant_id, account.id)
    app_ids = list(session.scalars(sa.select(App.id).where(*filters))) if filters else []
    manageable = [app_id for app_id in app_ids if can_read_payload(session, tenant_id, account, app_id)]
    assigned = sa.select(HumanInputForm.workflow_run_id).join(HumanInputFormRecipient,
        HumanInputFormRecipient.form_id == HumanInputForm.id).join(WorkflowRun,
        WorkflowRun.id == HumanInputForm.workflow_run_id).where(
            HumanInputForm.tenant_id == tenant_id, HumanInputForm.form_kind == 'runtime',
            HumanInputForm.status == 'waiting', HumanInputForm.expiration_time > datetime.now(timezone.utc).replace(tzinfo=None),
            recipient_condition(account.id))
    return [WorkflowRun.tenant_id == tenant_id, WorkflowRun.app_id.in_(app_ids), sa.or_(
        WorkflowRun.app_id.in_(manageable),
        sa.and_(WorkflowRun.created_by_role == 'account', WorkflowRun.created_by == account.id),
        WorkflowRun.id.in_(assigned))]


def scoped_run(session, project_id, tenant_id, account, run_id):
    access.validate_app_project(session, tenant_id, project_id, account.id)
    run = session.scalar(sa.select(WorkflowRun).where(*run_conditions(session, tenant_id, account), WorkflowRun.id == store.uid(run_id)))
    if run is None:
        raise NotFound('اجرا پیدا نشد.')
    return run


def intended(recipient, run, account_id):
    try:
        data = json.loads(recipient.recipient_payload)
    except (TypeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    if recipient.recipient_type == RecipientType.EMAIL_MEMBER:
        return data.get('user_id') == account_id
    if recipient.recipient_type in {RecipientType.CONSOLE, RecipientType.BACKSTAGE}:
        target = data.get('account_id')
        return target == account_id if target else run.created_by_role == 'account' and run.created_by == account_id
    return False


def assigned_recipient(session, form, run, account_id):
    return next((recipient for recipient in session.scalars(sa.select(HumanInputFormRecipient).where(
        HumanInputFormRecipient.form_id == form.id)) if intended(recipient, run, account_id)), None)


def timestamp(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value and value.tzinfo is None else value.isoformat() if value else None


def summary(run, app_name):
    return dict(id=run.id, app_id=run.app_id, app_name=app_name, status=str(run.status),
        triggered_from=str(run.triggered_from), created_at=timestamp(run.created_at), finished_at=timestamp(run.finished_at),
        elapsed_time=run.elapsed_time, total_tokens=run.total_tokens or 0)


def authorized_form(session, project_id, tenant_id, account, run_id, form_id):
    run = scoped_run(session, project_id, tenant_id, account, run_id)
    form = session.scalar(sa.select(HumanInputForm).where(HumanInputForm.id == store.uid(form_id),
        HumanInputForm.tenant_id == tenant_id, HumanInputForm.app_id == run.app_id,
        HumanInputForm.workflow_run_id == run.id, HumanInputForm.form_kind == 'runtime'))
    if form is None:
        raise NotFound('فرم پیدا نشد.')
    recipient = assigned_recipient(session, form, run, account.id)
    if recipient is None or not recipient.access_token:
        raise Forbidden('این فرم برای تصمیم‌گیری شما تعیین نشده است.')
    return form, recipient


def form_payload(service, form, recipient):
    native = service.get_form_by_token(recipient.access_token)
    if native is None:
        raise NotFound('فرم پیدا نشد.')
    service.ensure_form_active(native)
    definition = native.get_definition()
    inputs = [item.model_dump(mode='json') for item in service.resolve_form_inputs(native)]
    # Native imports allow no paragraph default; the web renderer expects a source.
    for item in inputs:
        if item['type'] == 'paragraph' and item.get('default') is None:
            item['default'] = dict(type='constant', selector=[], value='')
    return dict(id=form.id, node_id=form.node_id, title=definition.node_title or 'بررسی و ثبت تصمیم',
        content=definition.rendered_content, inputs=inputs,
        actions=[item.model_dump(mode='json') for item in definition.user_actions],
        default_values=definition.default_values, expiration_time=timestamp(form.expiration_time))


@console_ns.route('/company/projects/<uuid:project_id>/runs')
class ProjectRunsApi(Resource):
    @guarded()
    def get(self, project_id):
        account, tenant_id = identity()
        status = request.args.get('status', 'all')
        if status != 'all' and status not in STATUSES:
            raise BadRequest('وضعیت اجرا معتبر نیست.')
        try:
            page = max(1, int(request.args.get('page', 1)))
        except ValueError:
            raise BadRequest('شمارهٔ صفحه معتبر نیست.') from None
        with Session(db.engine) as session:
            access.validate_app_project(session, tenant_id, project_id, account.id)
            base = run_conditions(session, tenant_id, account)
            counts = dict((str(state), count) for state, count in session.execute(sa.select(
                WorkflowRun.status, sa.func.count()).where(*base).group_by(WorkflowRun.status)))
            conditions = list(base)
            if status != 'all':
                conditions.append(WorkflowRun.status == status)
            name = request.args.get('name', '').strip()[:120]
            if name:
                conditions.append(WorkflowRun.app_id.in_(sa.select(App.id).where(App.tenant_id == tenant_id, App.name.contains(name, autoescape=True))))
            total = session.scalar(sa.select(sa.func.count()).select_from(WorkflowRun).where(*conditions)) or 0
            rows = session.execute(sa.select(WorkflowRun, App.name).join(App, App.id == WorkflowRun.app_id).where(
                *conditions).order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc()).offset((page - 1) * 25).limit(25)).all()
            return dict(data=[summary(run, name) for run, name in rows], total=total, page=page,
                has_more=page * 25 < total, counts=counts)


@console_ns.route('/company/projects/<uuid:project_id>/runs/<uuid:run_id>')
class ProjectRunApi(Resource):
    @guarded()
    def get(self, project_id, run_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            run = scoped_run(session, project_id, tenant_id, account, run_id)
            result = summary(run, session.get(App, run.app_id).name)
            show = can_read_payload(session, tenant_id, account, run.app_id) or (run.created_by_role == 'account' and run.created_by == account.id)
            # Contents may be large; never include them in list responses or expose recipient bearer URLs.
            def preview(value):
                return (value or '')[:200000]
            result.update(inputs=preview(run.inputs) if show else '', outputs=preview(run.outputs) if show else '',
                error=preview(run.error) if show else '', can_read_payload=show,
                truncated=bool(show and any(len(value or '') > 200000 for value in [run.inputs, run.outputs, run.error])))
            forms = []
            for form in session.scalars(sa.select(HumanInputForm).where(HumanInputForm.workflow_run_id == run.id,
                HumanInputForm.tenant_id == tenant_id, HumanInputForm.form_kind == 'runtime').order_by(HumanInputForm.created_at)):
                active = form.status == 'waiting' and form.expiration_time > datetime.now(timezone.utc).replace(tzinfo=None)
                recipient = assigned_recipient(session, form, run, account.id)
                forms.append(dict(id=form.id, status=str(form.status), expiration_time=timestamp(form.expiration_time),
                    can_submit=bool(active and recipient), selected_action_id=form.selected_action_id,
                    submitted_at=timestamp(form.submitted_at)))
            result['forms'] = forms
            return result


@console_ns.route('/company/projects/<uuid:project_id>/runs/<uuid:run_id>/forms/<uuid:form_id>')
class ProjectRunFormApi(Resource):
    @guarded()
    def get(self, project_id, run_id, form_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            form, recipient = authorized_form(session, project_id, tenant_id, account, run_id, form_id)
            try:
                return form_payload(HumanInputService(db.engine), form, recipient)
            except (FormExpiredError, FormSubmittedError):
                raise Conflict('مهلت این فرم تمام شده یا تصمیم آن قبلاً ثبت شده است.') from None

    @guarded()
    def post(self, project_id, run_id, form_id):
        account, tenant_id = identity()
        data = payload()
        if not isinstance(data.get('inputs'), dict) or not isinstance(data.get('action'), str):
            raise BadRequest('مقادیر فرم و اقدام انتخاب‌شده الزامی‌اند.')
        with Session(db.engine) as session:
            _, recipient = authorized_form(session, project_id, tenant_id, account, run_id, form_id)
            try:
                HumanInputService(db.engine).submit_form_by_token(recipient_type=recipient.recipient_type,
                    form_token=recipient.access_token, selected_action_id=data['action'], form_data=data['inputs'],
                    submission_user_id=account.id)
            except (FormExpiredError, FormSubmittedError):
                raise Conflict('مهلت این فرم تمام شده یا تصمیم آن قبلاً ثبت شده است.') from None
            except InvalidFormDataError:
                raise BadRequest('مقادیر فرم یا اقدام انتخاب‌شده معتبر نیستند.') from None
            return dict(result='submitted')
