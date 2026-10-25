"""Live onboarding evidence; configuration is not a model connectivity test."""
import sqlalchemy as sa
from flask_restx import Resource
from sqlalchemy.orm import Session

from company_projects import access, personal_models
from company_projects.controller import guarded, identity, visible_filters
from controllers.console import console_ns
from extensions.ext_database import db
from models.account import Account, AccountStatus, TenantAccountJoin
from models.model import App
from models.workflow import WorkflowRun


def snapshot(session, project_id, tenant_id, account):
    access.validate_app_project(session, tenant_id, project_id, account.id)
    conditions = visible_filters(session, tenant_id, account.id)
    apps = sa.select(App.id).where(*conditions) if conditions else sa.select(App.id).where(sa.false())
    count = lambda statement: session.scalar(statement) or 0
    members = count(sa.select(sa.func.count()).select_from(TenantAccountJoin).join(
        Account, Account.id == TenantAccountJoin.account_id).where(
            TenantAccountJoin.tenant_id == tenant_id, Account.status == AccountStatus.ACTIVE))
    model = next((row for row in personal_models.rows(session, account.id) if row['model_type'] == 'llm'), None)
    app_count = count(sa.select(sa.func.count()).select_from(App).where(App.id.in_(apps)))
    published = count(sa.select(sa.func.count()).select_from(App).where(
        App.id.in_(apps), App.workflow_id.is_not(None)))
    # Evidence of the caller's successful trial, not another person's private output.
    successful = count(sa.select(sa.func.count()).select_from(WorkflowRun).where(
        WorkflowRun.tenant_id == tenant_id, WorkflowRun.app_id.in_(apps),
        WorkflowRun.created_by_role == 'account', WorkflowRun.created_by == account.id,
        WorkflowRun.status == 'succeeded'))
    project = access.public_project(session, access.project_for_account(session, project_id, account.id), account.id)
    steps = [
        dict(id='owner', title='مالک پروژه مشخص است', complete=bool(project['owner']), required=True,
             description='مالک پروژه اعضا و دسترسی‌های همین تیم را مدیریت می‌کند.', href=f'/projects/{project_id}'),
        dict(id='model', title='مدل شخصی شما ثبت شده است', complete=bool(model), required=True,
             description='اتصال متعلق به حساب شماست؛ اتصال واقعی با آزمون و اجرای آزمایشی بررسی می‌شود.', href=f'/projects/{project_id}/model-connections'),
        dict(id='team', title='همکاران به پروژه دعوت شده‌اند', complete=members > 1, required=False,
             description='برای کار تیمی، همکاران را دعوت کنید. استفادهٔ فردی هم امکان‌پذیر است.', href='/users'),
        dict(id='app', title='اولین برنامه ساخته شده است', complete=app_count > 0, required=True,
             description='یک برنامه بسازید و ورودی، خروجی و مراحل آن را مشخص کنید.', href=f'/projects/{project_id}'),
        dict(id='test', title='اجرای آزمایشی موفق دارید', complete=successful > 0, required=True,
             description='پیش از انتشار، با یک ورودی ساختگی نتیجه را بررسی کنید. کیفیت خروجی را خودتان تأیید کنید.', href=f'/projects/{project_id}/inbox'),
        dict(id='publish', title='یک فرایند منتشر شده است', complete=published > 0, required=False,
             description='بعد از بررسی خروجی، نسخهٔ تأییدشده را در ویرایشگر منتشر کنید.', href=f'/projects/{project_id}'),
    ]
    return dict(project=project, steps=steps, members=members, apps=app_count,
        completed=sum(item['complete'] for item in steps if item['required']),
        required=sum(item['required'] for item in steps), model_name=model['model_name'] if model else None)


@console_ns.route('/company/projects/<uuid:project_id>/setup')
class ProjectSetupApi(Resource):
    @guarded()
    def get(self, project_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            return snapshot(session, str(project_id), tenant_id, account)
