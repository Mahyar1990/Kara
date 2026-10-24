"""Product authority and project boundaries backed by native Dify memberships."""
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from company_projects import store
from models.account import Account, AccountStatus, Tenant, TenantAccountJoin, TenantAccountRole


def initialize(connection):
    """Pin the initial installation owner once; never elect an owner on a request."""
    if connection.dialect.name == 'postgresql':
        connection.execute(sa.text('SELECT pg_advisory_xact_lock(210610002)'))
    if connection.execute(sa.select(store.product)).first():
        initialize_product_access(connection)
        return
    first = connection.execute(sa.select(TenantAccountJoin.account_id, TenantAccountJoin.tenant_id)
        .join(Tenant, Tenant.id == TenantAccountJoin.tenant_id)
        .join(Account, Account.id == TenantAccountJoin.account_id)
        .where(TenantAccountJoin.role == TenantAccountRole.OWNER, Account.status == AccountStatus.ACTIVE)
        .order_by(Tenant.created_at, Tenant.id).limit(1)).first()
    if first:
        connection.execute(store.product.insert().values(id=1, account_id=first.account_id, tenant_id=first.tenant_id))
        initialize_product_access(connection)


def initialize_product_access(connection):
    # Legacy central invitations had project roles, never product authority.
    # Normalize once so old "admin" invitations do not gain new privileges.
    if connection.execute(sa.select(store.product_access_schema)).first():
        return
    root = connection.execute(sa.select(store.product)).mappings().one()
    connection.execute(sa.update(TenantAccountJoin).where(
        TenantAccountJoin.tenant_id == str(root['tenant_id']),
        TenantAccountJoin.account_id != str(root['account_id'])).values(role=TenantAccountRole.NORMAL))
    connection.execute(store.product_access_schema.insert().values(version=1))


def authority(session):
    row = session.execute(sa.select(store.product).where(store.product.c.id == 1)).mappings().first()
    if row is None:
        raise Forbidden('ادمین کل Kara هنوز در راه‌اندازی اولیه تعیین نشده است.')
    return row


def is_product_owner(session, account_id):
    return str(authority(session)['account_id']) == str(account_id)


def is_product_admin(session, account_id):
    if is_product_owner(session, account_id):
        return True
    member = membership(session, authority(session)['tenant_id'], account_id)
    return bool(member and member.role == TenantAccountRole.ADMIN)


def require_product_admin(session, account_id):
    if not is_product_admin(session, account_id):
        raise Forbidden('ساخت پروژه و مدیریت کاربران محصول فقط با مدیر کارا است.')


def require_product_owner(session, account_id):
    if not is_product_owner(session, account_id):
        raise Forbidden('ویرایش پروژه و تغییر مالک آن فقط با ادمین کل Kara است.')


def workspace_project(session, workspace_id):
    return session.execute(sa.select(store.projects, store.workspaces.c.workspace_id)
        .join(store.workspaces, store.workspaces.c.project_id == store.projects.c.id)
        .where(store.workspaces.c.workspace_id == store.uid(workspace_id))).mappings().first()


def membership(session, workspace_id, account_id):
    return session.scalar(sa.select(TenantAccountJoin).where(
        TenantAccountJoin.tenant_id == str(workspace_id), TenantAccountJoin.account_id == str(account_id)))


def project_for_account(session, project_id, account_id):
    root = authority(session)
    row = session.execute(sa.select(store.projects, store.workspaces.c.workspace_id)
        .outerjoin(store.workspaces, store.workspaces.c.project_id == store.projects.c.id)
        .where(store.projects.c.id == store.uid(project_id), store.projects.c.tenant_id == root['tenant_id'])).mappings().first()
    if row is None or (not is_product_owner(session, account_id) and (
            not row['workspace_id'] or membership(session, row['workspace_id'], account_id) is None)):
        raise NotFound('پروژه پیدا نشد یا به آن دسترسی ندارید.')
    return dict(row)


def list_for_account(session, account_id):
    root = authority(session)
    query = sa.select(store.projects.c.id).where(store.projects.c.tenant_id == root['tenant_id'])
    if not is_product_owner(session, account_id):
        query = query.join(store.workspaces, store.workspaces.c.project_id == store.projects.c.id).join(
            TenantAccountJoin, TenantAccountJoin.tenant_id == store.workspaces.c.workspace_id).where(
            TenantAccountJoin.account_id == str(account_id))
    return [project_for_account(session, pid, account_id) for pid in session.scalars(query.order_by(store.projects.c.created_at))]


def owner_of(session, workspace_id):
    return session.scalar(sa.select(Account).join(TenantAccountJoin, TenantAccountJoin.account_id == Account.id)
        .where(TenantAccountJoin.tenant_id == str(workspace_id), TenantAccountJoin.role == TenantAccountRole.OWNER))


def can_manage_members(session, workspace_id, account_id):
    if str(workspace_id) == str(authority(session)['tenant_id']):
        return is_product_admin(session, account_id)
    owner = owner_of(session, workspace_id)
    return is_product_owner(session, account_id) or bool(owner and owner.id == str(account_id))


def require_member_management(session, workspace_id, operator_id, target_id=None, action='add'):
    root = authority(session)
    managed = str(workspace_id) == str(root['tenant_id']) or workspace_project(session, workspace_id)
    if not managed:
        return  # Leave unrelated legacy workspaces to their native policy.
    if not can_manage_members(session, workspace_id, operator_id):
        raise Forbidden('مدیریت اعضای پروژه فقط با مالک پروژه یا ادمین کل Kara است.')
    if target_id and action in ('remove', 'update'):
        owner = owner_of(session, workspace_id)
        if str(target_id) == str(root['account_id']) or (owner and owner.id == str(target_id)):
            raise Forbidden('ادمین کل Kara و مالک پروژه از این مسیر قابل حذف یا تغییر نیستند.')


def filter_permissions(session, workspace_id, account_id, keys):
    # Native editors retain agent, dataset and skill permissions; admins cannot
    # acquire project ownership or delegate membership without the owner.
    root = authority(session)
    managed = str(workspace_id) == str(root['tenant_id']) or workspace_project(session, workspace_id)
    if managed and not can_manage_members(session, workspace_id, account_id):
        return [key for key in keys if key not in ('workspace.member.manage', 'workspace.role.manage')]
    return list(keys)


def validate_app_project(session, workspace_id, project_id, account_id):
    row = project_for_account(session, project_id, account_id)
    if not row['workspace_id'] or str(row['workspace_id']) != str(workspace_id):
        raise Forbidden('ابتدا وارد فضای مستقل همین پروژه شوید.')


def forbid_native_owner_transfer(session, tenant_id, new_role):
    root = authority(session)
    if new_role == 'owner' and (str(tenant_id) == str(root['tenant_id']) or workspace_project(session, tenant_id)):
        raise Forbidden('مالک پروژه را ادمین کل Kara از صفحهٔ پروژه تعیین می‌کند.')


def public_project(session, row, account_id):
    owner = owner_of(session, row['workspace_id']) if row['workspace_id'] else None
    member = membership(session, row['workspace_id'], account_id) if row['workspace_id'] else None
    return {**store.public_project(row), 'workspace_id': row['workspace_id'],
        'owner': {'id': owner.id, 'name': owner.name, 'email': owner.email} if owner else None,
        'role': str(member.role) if member else None,
        'can_manage_members': bool(row['workspace_id'] and can_manage_members(session, row['workspace_id'], account_id)),
        'can_edit': bool(member and TenantAccountRole.is_editing_role(member.role)),
        'is_product_owner': is_product_owner(session, account_id)}


def restrict_central_workspace(app):
    """Protect central workspace content without blocking account authentication."""
    from flask import request
    from libs.login import current_account_with_tenant_optional
    from extensions.ext_database import db
    from sqlalchemy.orm import Session

    @app.before_request
    def company_workspace_boundary():
        if request.blueprint != 'console' or request.method == 'OPTIONS':
            return
        # These endpoints are account/global context, not workspace content.
        path = request.path.removeprefix('/console/api')
        # An invitation check can run again after login has set the regular
        # user's session cookie. Leave credential/token validation to the native
        # auth endpoints, even when the active workspace is still central.
        if path in ('/login', '/activate', '/activate/check', '/reset-password',
                '/email-code-login', '/email-code-login/validity',
                '/email-register', '/email-register/send-email', '/email-register/validity',
                '/forgot-password', '/forgot-password/validity', '/forgot-password/resets') \
                or path.startswith(('/oauth/login/', '/oauth/authorize/')):
            return
        if path.startswith(('/company/projects', '/company/context', '/account/', '/system-features', '/logout', '/refresh-token', '/workspaces/switch')) or path in ('/workspaces', '/features', '/workspaces/current/summary', '/workspaces/current/rbac/my-permissions'):
            return
        account, tenant_id = current_account_with_tenant_optional()
        if account and tenant_id:
            with Session(db.engine) as session:
                root = authority(session)
                if path == '/workspaces/info' and request.method == 'POST' and workspace_project(session, tenant_id):
                    raise Forbidden('نام پروژه را ادمین کل Kara از صفحهٔ پروژه ویرایش می‌کند.')
                if str(tenant_id) == str(root['tenant_id']) and not is_product_admin(session, account.id):
                    raise Forbidden('این بخش مخصوص مدیر کارا است؛ از صفحهٔ پروژه‌ها وارد پروژهٔ خود شوید.')
