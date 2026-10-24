"""Direct project membership for existing, activated Kara users."""
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest

from company_projects import access, store
from configs import dify_config
from models.account import Account, AccountStatus, Tenant, TenantAccountJoin
from services.account_service import TenantService


def managed_project(session, project_id, workspace_id, actor_id):
    row = access.project_for_account(session, project_id, actor_id)
    access.validate_app_project(session, workspace_id, project_id, actor_id)
    access.require_member_management(session, workspace_id, actor_id)
    return row


def roles():
    result = [('admin', 'مدیر فنی'), ('editor', 'توسعه‌دهنده'), ('normal', 'کاربر')]
    if dify_config.DATASET_OPERATOR_ENABLED:
        result.append(('dataset_operator', 'مدیر دانش'))
    return [dict(id=key, name=name) for key, name in result]


def candidates(session, project_id, workspace_id, actor_id):
    managed_project(session, project_id, workspace_id, actor_id)
    central = access.authority(session)['tenant_id']
    already_member = sa.exists(sa.select(TenantAccountJoin.id).where(
        TenantAccountJoin.tenant_id == str(workspace_id), TenantAccountJoin.account_id == Account.id))
    accounts = session.scalars(sa.select(Account).join(TenantAccountJoin,
        TenantAccountJoin.account_id == Account.id).where(
        TenantAccountJoin.tenant_id == str(central), Account.status == AccountStatus.ACTIVE,
        ~already_member.correlate(Account)).order_by(Account.name, Account.email))
    return dict(data=[dict(id=user.id, name=user.name, email=user.email) for user in accounts], roles=roles())


def add(session, project_id, workspace_id, actor_id, account_id, role):
    managed_project(session, project_id, workspace_id, actor_id)
    if role not in [item['id'] for item in roles()]:
        raise BadRequest('یک نقش معتبر پروژه انتخاب کنید.')
    target = session.get(Account, store.uid(account_id))
    if target is None or target.status != AccountStatus.ACTIVE or not access.membership(
            session, access.authority(session)['tenant_id'], target.id):
        raise BadRequest('کاربر باید ابتدا در مدیریت کاربران کارا ثبت و فعال شده باشد.')
    session.scalar(sa.select(Tenant).where(Tenant.id == str(workspace_id)).with_for_update())
    member = access.membership(session, workspace_id, target.id)
    if member is None:
        member = TenantService.create_tenant_member(session.get(Tenant, str(workspace_id)), target,
            session, role=role, operator_account_id=str(actor_id))
    return dict(account_id=target.id, role=str(member.role), result='success')
