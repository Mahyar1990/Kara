"""Protect the community member-role compatibility endpoint on the server."""
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from models.account import Account, Tenant, TenantAccountJoin, TenantAccountRole
from services.account_service import TenantService
from services.errors.account import CannotOperateSelfError, NoPermissionError


def require_role_change(tenant_id, operator_id, member_id, role_ids, *, session):
    if len(role_ids) != 1 or not TenantAccountRole.is_valid_role(role_ids[0]):
        raise BadRequest('یک نقش معتبر انتخاب کنید.')
    from company_members.product import validate_role
    validate_role(session, tenant_id, role_ids[0])
    if role_ids[0] == TenantAccountRole.OWNER:
        raise BadRequest('تغییر مالکیت از بخش انتقال مالکیت انجام می‌شود.')
    tenant = session.get(Tenant, tenant_id)
    operator = session.get(Account, operator_id) if operator_id else None
    member = session.get(Account, member_id)
    if tenant is None or operator is None:
        raise Forbidden('اجازهٔ مدیریت کاربران این فضای کاری را ندارید.')
    if member is None:
        raise NotFound('کاربر پیدا نشد.')
    try:
        TenantService.check_member_permission(tenant, operator, member, 'update', session=session)
    except CannotOperateSelfError:
        raise BadRequest('نقش خودتان از این بخش قابل تغییر نیست.') from None
    except NoPermissionError:
        raise Forbidden('اجازهٔ تغییر نقش کاربران را ندارید.') from None
    membership = session.scalar(sa.select(TenantAccountJoin).where(
        TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.account_id == member_id))
    if membership is None:
        raise NotFound('کاربر عضو این فضای کاری نیست.')
    if membership.role == TenantAccountRole.OWNER:
        raise Forbidden('نقش مالک فضای کاری از این بخش قابل تغییر نیست.')
