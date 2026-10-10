"""Transactional native workspace provisioning and owner assignment."""
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict

from company_projects import access, store
from models.account import Account, AccountStatus, Tenant, TenantAccountJoin, TenantAccountRole
from services.account_service import TenantService


def resolve_owner(session, owner_id):
    try:
        owner = session.get(Account, store.uid(owner_id))
    except store.ProjectError:
        raise BadRequest('مالک پروژه را از کاربران فعال انتخاب کنید.') from None
    if owner is None or owner.status != AccountStatus.ACTIVE:
        raise BadRequest('مالک پروژه باید یک کاربر فعال محصول باشد.')
    return owner


def provision(session, row, owner_id, product_owner_id):
    owner = resolve_owner(session, owner_id)
    tenant = TenantService.create_tenant(name=row['name'], is_from_dashboard=True, session=session)
    TenantService.create_tenant_member(tenant, owner, session, role='owner')
    if owner.id != str(product_owner_id):
        TenantService.create_tenant_member(tenant, session.get(Account, str(product_owner_id)), session, role='admin')
    session.execute(store.workspaces.insert().values(project_id=row['id'], workspace_id=tenant.id))
    session.flush()
    return tenant


def create_project(session, actor_id, name, description, owner_id):
    access.require_product_owner(session, actor_id)
    resolve_owner(session, owner_id)
    root = access.authority(session)
    row = store.create_project(session.connection(), root['tenant_id'], actor_id, name, description)
    provision(session, row, owner_id, root['account_id'])
    return access.project_for_account(session, row['id'], actor_id)


def set_owner(session, project_id, actor_id, owner_id):
    access.require_product_owner(session, actor_id)
    row = access.project_for_account(session, project_id, actor_id)
    if not row['workspace_id']:
        raise Conflict('ابتدا فضای مستقل این پروژه را آماده کنید.')
    target = resolve_owner(session, owner_id)
    # Serialize concurrent assignments; one native owner remains at all times.
    session.scalar(sa.select(Tenant).where(Tenant.id == row['workspace_id']).with_for_update())
    joins = session.scalars(sa.select(TenantAccountJoin).where(TenantAccountJoin.tenant_id == row['workspace_id']).with_for_update()).all()
    root = access.authority(session)
    for join in joins:
        if join.role == TenantAccountRole.OWNER:
            join.role = TenantAccountRole.ADMIN if join.account_id == str(root['account_id']) else TenantAccountRole.EDITOR
    member = next((join for join in joins if join.account_id == target.id), None)
    if member:
        member.role = TenantAccountRole.OWNER
    else:
        session.add(TenantAccountJoin(tenant_id=row['workspace_id'], account_id=target.id, role=TenantAccountRole.OWNER))
    session.flush()
    return access.project_for_account(session, project_id, actor_id)
