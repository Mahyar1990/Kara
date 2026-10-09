"""Console endpoints using Dify authentication and application visibility."""
from functools import wraps

import sqlalchemy as sa
from flask import request
from flask_restx import Resource
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from company_projects import store
from configs import dify_config
from controllers.common.app_access import resolve_app_access_filter
from controllers.common.rbac import RBACCheck, Workspace
from controllers.console import console_ns
from controllers.console.wraps import (RBACPermission, account_initialization_required,
    cloud_edition_billing_resource_check, edit_permission_required, rbac_permission_required, setup_required)
from extensions.ext_database import db
from libs.login import current_account_with_tenant, login_required
from models.model import App
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
        store.get_project(session.connection(), tenant_id, project_id)
        conditions.append(App.id.in_(store.app_ids(project_id, tenant_id)))
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
        _, tenant_id = identity()
        with db.engine.connect() as connection:
            return dict(data=[store.public_project(row) for row in store.list_projects(connection, tenant_id)])

    @guarded(write=True)
    def post(self):
        account, tenant_id = identity()
        data = payload()
        with db.engine.begin() as connection:
            row = store.create_project(connection, tenant_id, account.id, data.get('name'), data.get('description', ''))
        return store.public_project(row), 201


@console_ns.route('/company/projects/<uuid:project_id>')
class ProjectApi(Resource):
    @guarded()
    def get(self, project_id):
        _, tenant_id = identity()
        with db.engine.connect() as connection:
            return store.public_project(store.get_project(connection, tenant_id, project_id))

    @guarded(write=True)
    def patch(self, project_id):
        _, tenant_id = identity()
        data = payload()
        with db.engine.begin() as connection:
            row = store.update_project(connection, tenant_id, project_id, data.get('name'), data.get('description', ''))
        return store.public_project(row)


@console_ns.route('/company/projects/resources')
class ProjectResourcesApi(Resource):
    @guarded()
    def get(self):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            return list_apps(session, tenant_id, account.id)


@console_ns.route('/company/projects/<uuid:project_id>/apps')
class ProjectAppsApi(Resource):
    @guarded()
    def get(self, project_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
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
            app = AppService().create_app(tenant_id, params, account, session=session)
            return dict(id=app.id, name=app.name, mode=app.mode), 201


@console_ns.route('/company/projects/<uuid:project_id>/apps/<uuid:app_id>')
class ProjectAppBindingApi(Resource):
    @guarded(write=True)
    def put(self, project_id, app_id):
        account, tenant_id = identity()
        with Session(db.engine) as session, session.begin():
            visible_app(session, tenant_id, account.id, app_id)
            store.assign(session.connection(), tenant_id, project_id, app_id)
        return dict(result='success')

    @guarded(write=True)
    def delete(self, project_id, app_id):
        account, tenant_id = identity()
        with Session(db.engine) as session, session.begin():
            visible_app(session, tenant_id, account.id, app_id)
            store.unassign(session.connection(), tenant_id, project_id, app_id)
        return dict(result='success')
