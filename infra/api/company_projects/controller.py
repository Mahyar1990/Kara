"""Console endpoints using Dify authentication and application visibility."""
from functools import wraps

import sqlalchemy as sa
from flask import request
from flask_restx import Resource
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Conflict, NotFound, Forbidden

from company_projects import store, access, ownership
from configs import dify_config
from controllers.common.app_access import resolve_app_access_filter
from controllers.common.rbac import RBACCheck, Workspace
from controllers.console import console_ns
from controllers.console.wraps import (RBACPermission, account_initialization_required,
    cloud_edition_billing_resource_check, edit_permission_required, rbac_permission_required, setup_required)
from extensions.ext_database import db
from libs.login import current_account_with_tenant, login_required
from models.model import App
from models.account import Account, AccountStatus, TenantAccountRole
from services.account_service import TenantService
from services.app_service import AppListParams, AppService, CreateAppParams


def guarded(write=False):
    def decorate(method):
        @wraps(method)
        def checked(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except store.MissingProject as exc:
                raise NotFound(str(exc)) from None
            except store.ProjectError as exc:
                raise BadRequest(str(exc)) from None
            except IntegrityError:
                raise Conflict('این نام پروژه قبلاً استفاده شده است.') from None
        if write:
            checked = edit_permission_required(checked)
            checked = rbac_permission_required(RBACCheck(RBACPermission.APP_CREATE_AND_MANAGEMENT, Workspace()))(checked)
        return setup_required(login_required(account_initialization_required(checked)))
    return decorate


def identity():
    account, tenant_id = current_account_with_tenant()
    return account, str(tenant_id)


def payload():
    result = request.get_json(silent=True)
    if not isinstance(result, dict):
        raise BadRequest('ورودی باید یک شیء معتبر باشد.')
    return result


def visible_filters(session, tenant_id, account_id, **values):
    params = AppListParams(**values)
    if dify_config.RBAC_ENABLED:
        resolve_app_access_filter(tenant_id, account_id, session=session).apply_to_params(params)
    legacy = AppService._build_app_list_filters(account_id, tenant_id, params, session)
    # Studio's "all" intentionally excludes new agent apps; projects include both
    # catalogs while retaining Dify's permission and backing-agent checks.
    params.mode = 'agent'
    agents = AppService._build_app_list_filters(account_id, tenant_id, params, session)
    return [sa.or_(sa.and_(*legacy), sa.and_(*agents))] if legacy and agents else []


def visible_app(session, tenant_id, account_id, app_id):
    conditions = visible_filters(session, tenant_id, account_id)
    app = session.scalar(sa.select(App).where(*conditions, App.id == store.uid(app_id))) if conditions else None
    if app is None:
        raise NotFound('برنامه پیدا نشد.')
    return app


def list_apps(session, tenant_id, account_id, project_id=None):
    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 30))))
    except ValueError:
        raise BadRequest('شمارهٔ صفحه معتبر نیست.') from None
    kind = request.args.get('kind', 'all')
    if kind not in ('all', 'workflow', 'agent', 'other'):
        raise BadRequest('نوع برنامه معتبر نیست.')
    conditions = visible_filters(session, tenant_id, account_id, name=request.args.get('name'))
    if not conditions:
        return dict(data=[], total=0, page=page, has_more=False)
    if project_id:
        row = access.project_for_account(session, project_id, account_id)
        if str(row['workspace_id']) != str(tenant_id):
            raise Forbidden('ابتدا وارد فضای مستقل همین پروژه شوید.')
    if kind == 'workflow':
        conditions.append(App.mode.in_(['workflow', 'advanced-chat']))
    elif kind == 'agent':
        conditions.append(App.mode.in_(['agent', 'agent-chat']))
    elif kind == 'other':
        conditions.append(App.mode.not_in(['workflow', 'advanced-chat', 'agent', 'agent-chat']))
    total = session.scalar(sa.select(sa.func.count()).select_from(App).where(*conditions))
    apps = session.scalars(sa.select(App).where(*conditions).order_by(App.updated_at.desc(), App.id)
                          .offset((page - 1) * limit).limit(limit)).all()
    assignments = session.execute(sa.select(store.bindings.c.app_id, store.projects.c.id, store.projects.c.name)
        .join(store.projects, sa.and_(store.projects.c.id == store.bindings.c.project_id,
                                     store.projects.c.tenant_id == store.bindings.c.tenant_id))
        .where(store.bindings.c.tenant_id == tenant_id, store.bindings.c.app_id.in_([app.id for app in apps]))).all()
    owners = {app_id: dict(id=owner_id, name=name) for app_id, owner_id, name in assignments}
    return dict(data=[dict(id=app.id, name=app.name, description=app.description, mode=app.mode,
                          project=owners.get(app.id)) for app in apps], total=total, page=page,
                has_more=page * limit < total)


@console_ns.route('/company/projects')
class ProjectsApi(Resource):
    @guarded()
    def get(self):
        account, _ = identity()
        with Session(db.engine) as session:
            return dict(data=[access.public_project(session, row, account.id) for row in access.list_for_account(session, account.id)],
                is_product_owner=access.is_product_owner(session, account.id),
                can_create_projects=access.is_product_admin(session, account.id))

    @guarded()
    def post(self):
        account, _ = identity()
        data = payload()
        with db.engine.begin() as connection, Session(bind=connection, join_transaction_mode='create_savepoint') as session:
            row = ownership.create_project(session, account.id, data.get('name'), data.get('description', ''), data.get('owner_id'))
            session.commit()
            return access.public_project(session, row, account.id), 201


@console_ns.route('/company/projects/<uuid:project_id>')
class ProjectApi(Resource):
    @guarded()
    def get(self, project_id):
        account, _ = identity()
        with Session(db.engine) as session:
            return access.public_project(session, access.project_for_account(session, project_id, account.id), account.id)

    @guarded()
    def patch(self, project_id):
        account, _ = identity()
        data = payload()
        with Session(db.engine) as session, session.begin():
            access.require_product_owner(session, account.id)
            row = access.project_for_account(session, project_id, account.id)
            store.update_project(session.connection(), row['tenant_id'], project_id, data.get('name'), data.get('description', ''))
            if row['workspace_id']:
                from models.account import Tenant
                session.get(Tenant, row['workspace_id']).name = store.details(data.get('name'))['name']
            return access.public_project(session, access.project_for_account(session, project_id, account.id), account.id)


@console_ns.route('/company/context')
class CompanyContextApi(Resource):
    @guarded()
    def get(self):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            root = access.authority(session)
            row = access.workspace_project(session, tenant_id)
            return dict(is_product_owner=access.is_product_owner(session, account.id),
                is_product_admin=access.is_product_admin(session, account.id),
                product_owner_id=str(root['account_id']),
                root_workspace_id=str(root['tenant_id']),
                current_project=access.public_project(session, row, account.id) if row else None,
                can_manage_members=access.can_manage_members(session, tenant_id, account.id))


@console_ns.route('/company/projects/owners')
class ProjectOwnersApi(Resource):
    @guarded()
    def get(self):
        account, _ = identity()
        with Session(db.engine) as session:
            access.require_product_admin(session, account.id)
            return dict(data=[dict(id=user.id, name=user.name, email=user.email) for user in
                session.scalars(sa.select(Account).where(Account.status == AccountStatus.ACTIVE).order_by(Account.name))])


@console_ns.route('/company/projects/<uuid:project_id>/owner')
class ProjectOwnerApi(Resource):
    @guarded()
    def put(self, project_id):
        account, _ = identity()
        with Session(db.engine) as session, session.begin():
            row = ownership.set_owner(session, project_id, account.id, payload().get('owner_id'))
            return access.public_project(session, row, account.id)


@console_ns.route('/company/projects/<uuid:project_id>/enter')
class ProjectEnterApi(Resource):
    @guarded()
    def post(self, project_id):
        account, _ = identity()
        with Session(db.engine) as session:
            row = access.project_for_account(session, project_id, account.id)
            if not row['workspace_id']:
                raise Conflict('فضای مستقل پروژه هنوز آماده نشده است.')
            TenantService.switch_tenant(account, row['workspace_id'], session=session)
            return dict(result='success', workspace_id=row['workspace_id'])


@console_ns.route('/company/projects/resources')
class ProjectResourcesApi(Resource):
    @guarded()
    def get(self):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            if not access.workspace_project(session, tenant_id) and not access.is_product_owner(session, account.id):
                raise Forbidden('ابتدا وارد پروژهٔ خود شوید.')
            return list_apps(session, tenant_id, account.id)


@console_ns.route('/company/projects/<uuid:project_id>/apps')
class ProjectAppsApi(Resource):
    @guarded()
    def get(self, project_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            access.validate_app_project(session, tenant_id, project_id, account.id)
            return list_apps(session, tenant_id, account.id, str(project_id))

    @guarded(write=True)
    @cloud_edition_billing_resource_check('apps')
    def post(self, project_id):
        account, tenant_id = identity()
        data = payload()
        if data.get('mode') not in ('workflow', 'agent-chat', 'agent', 'advanced-chat', 'chat', 'completion'):
            raise BadRequest('نوع برنامه معتبر نیست.')
        if not isinstance(data.get('name'), str) or not data['name'].strip() or len(data['name']) > 120:
            raise BadRequest('نام برنامه الزامی و حداکثر ۱۲۰ نویسه است.')
        if not isinstance(data.get('description', ''), str) or len(data.get('description', '')) > 400:
            raise BadRequest('توضیح برنامه حداکثر ۴۰۰ نویسه است.')
        try:
            params = CreateAppParams(name=data.get('name', '').strip(), description=data.get('description', ''),
                mode=data['mode'], icon_type='emoji', icon='🧩', icon_background='#E0F2FE', project_id=str(project_id))
        except (ValueError, TypeError):
            raise BadRequest('نام برنامه الزامی است.') from None
        with Session(db.engine, expire_on_commit=False) as session:
            access.validate_app_project(session, tenant_id, project_id, account.id)
            app = AppService().create_app(tenant_id, params, account, session=session)
            return dict(id=app.id, name=app.name, mode=app.mode), 201


@console_ns.route('/company/projects/<uuid:project_id>/apps/<uuid:app_id>')
class ProjectAppBindingApi(Resource):
    @guarded(write=True)
    def put(self, project_id, app_id):
        raise Conflict('برنامه‌ها در فضای مستقل پروژه ساخته می‌شوند؛ انتقال بین پروژه‌ها نیازمند انتقال وابستگی‌هاست.')

    @guarded(write=True)
    def delete(self, project_id, app_id):
        raise Conflict('برنامه متعلق به فضای مستقل پروژه است. برای حذف برنامه از ابزار حذف Dify استفاده کنید.')
