"""Product invitations use central membership, separate from every project."""
from werkzeug.exceptions import BadRequest

from company_projects import access

PRODUCT_ROLES = ('admin', 'normal')


def is_product_workspace(session, tenant_id):
    return str(tenant_id) == str(access.authority(session)['tenant_id'])


def validate_role(session, tenant_id, role):
    if is_product_workspace(session, tenant_id) and role not in PRODUCT_ROLES:
        raise BadRequest('نقش محصول باید مدیر یا کاربر عادی باشد.')


def available_roles(session, tenant_id):
    return PRODUCT_ROLES if is_product_workspace(session, tenant_id) else (
        'owner', 'admin', 'editor', 'normal', 'dataset_operator')


def validate_invitation(session, tenant_id, role):
    validate_role(session, tenant_id, role)
    if access.workspace_project(session, tenant_id):
        raise BadRequest('برای پروژه، کاربر موجود کارا را از فهرست کاربران انتخاب کنید؛ دعوت ایمیلی پروژه غیرفعال است.')
