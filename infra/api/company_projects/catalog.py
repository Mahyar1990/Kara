"""Trusted, versioned starter assets; native DSL import creates private drafts."""
import json
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from flask_restx import Resource
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from company_projects import access, store
from company_projects.controller import guarded, identity, payload
from controllers.console import console_ns
from controllers.console.wraps import cloud_edition_billing_resource_check
from configs import dify_config
from core.rbac import RBACPermission
from extensions.ext_database import db
from models.dataset import Dataset, Document
from models.model import App
from services.app_dsl_service import AppDslService, ImportStatus
from services.dataset_service import DatasetService
from services.enterprise.rbac_service import RBACService
from services.errors.account import NoPermissionError
from services.model_provider_service import ModelProviderService

ASSETS = Path('/app/api/company_templates')


def templates():
    return json.loads((ASSETS / 'catalog.json').read_text())['templates']


def dataset_allowed(session, dataset, account):
    try:
        DatasetService.check_dataset_permission(dataset, account, session)
    except NoPermissionError:
        return False
    return not dify_config.RBAC_ENABLED or RBACService.CheckAccess.check(
        dataset.tenant_id, account.id, scene=RBACPermission.DATASET_READONLY,
        resource_type='dataset', resource_id=dataset.id)


def ready_dataset(session, tenant_id, account, dataset_id):
    dataset = session.scalar(sa.select(Dataset).where(Dataset.id == store.uid(dataset_id), Dataset.tenant_id == tenant_id))
    if dataset is None or not dataset_allowed(session, dataset, account):
        raise NotFound('دانش پیدا نشد یا اجازهٔ استفاده از آن را ندارید.')
    if dataset.provider != 'external' and not session.scalar(sa.select(Document.id).where(
        Document.dataset_id == dataset.id, Document.tenant_id == tenant_id,
        Document.indexing_status == 'completed', Document.enabled.is_(True), Document.archived.is_(False)).limit(1)):
        raise Conflict('ابتدا اسناد دانش را اضافه کنید و منتظر پایان پردازش بمانید.')
    return dataset


def instantiate(session, project_id, tenant_id, account, template_id, name, dataset_id=None):
    access.validate_app_project(session, tenant_id, project_id, account.id)
    spec = next((item for item in templates() if item['id'] == template_id), None)
    if not spec:
        raise NotFound('قالب پیدا نشد.')
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise BadRequest('نام برنامه الزامی و حداکثر ۱۲۰ نویسه است.')
    model = ModelProviderService().get_default_model_of_model_type(tenant_id, 'llm')
    if model is None:
        raise Conflict('ابتدا مدل پیش‌فرض شخصی خودتان را تنظیم کنید.')
    dataset = ready_dataset(session, tenant_id, account, dataset_id) if spec['requires_knowledge'] else None
    dsl = json.loads((ASSETS / spec['file']).read_text())
    for node in dsl['workflow']['graph']['nodes']:
        data = node['data']
        if data['type'] == 'llm':
            data['model'].update(provider=model.provider.provider, name=model.model)
        elif data['type'] == 'knowledge-retrieval':
            data['dataset_ids'] = [dataset.id]
    result = AppDslService(session).import_app(account=account, import_mode='yaml-content',
        yaml_content=json.dumps(dsl, ensure_ascii=False), name=name.strip(), description=spec['description'])
    if result.status not in {ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_WARNINGS} or not result.app_id:
        raise Conflict('ساخت برنامه از قالب انجام نشد. تنظیم مدل و سازگاری قالب را بررسی کنید.')
    app = session.get(App, result.app_id)
    if app.tenant_id != tenant_id:
        raise Conflict('فضای برنامه با پروژه یکسان نیست.')
    # Publishing is an explicit later decision by the team.
    app.enable_api = False
    app.enable_site = False
    root = access.authority(session)
    store.assign(session.connection(), root['tenant_id'], project_id, app.id)
    session.execute(store.template_copies.insert().values(app_id=app.id, tenant_id=tenant_id,
        template_id=spec['id'], template_version=spec['version'],
        source_commit=json.loads((ASSETS / 'source.json').read_text())['commit'],
        created_by=account.id, created_at=datetime.now(timezone.utc)))
    session.commit()
    return dict(id=app.id, name=app.name, mode=app.mode, template_id=spec['id'], template_version=spec['version'])


@console_ns.route('/company/projects/<uuid:project_id>/templates')
class ProjectTemplatesApi(Resource):
    @guarded()
    def get(self, project_id):
        account, tenant_id = identity()
        with Session(db.engine) as session:
            access.validate_app_project(session, tenant_id, project_id, account.id)
            model = ModelProviderService().get_default_model_of_model_type(tenant_id, 'llm')
            datasets = []
            for dataset in session.scalars(sa.select(Dataset).where(Dataset.tenant_id == tenant_id).order_by(Dataset.name)):
                if not dataset_allowed(session, dataset, account):
                    continue
                try:
                    ready_dataset(session, tenant_id, account, dataset.id)
                except Conflict:
                    continue
                datasets.append(dict(id=dataset.id, name=dataset.name))
            return dict(data=[{key: value for key, value in item.items() if key != 'file'} for item in templates()],
                model_name=model.model if model else None, datasets=datasets)


@console_ns.route('/company/projects/<uuid:project_id>/templates/<string:template_id>/copies')
class ProjectTemplateCopyApi(Resource):
    @guarded(write=True)
    @cloud_edition_billing_resource_check('apps')
    def post(self, project_id, template_id):
        account, tenant_id = identity()
        data = payload()
        with db.engine.begin() as connection, Session(bind=connection, join_transaction_mode='create_savepoint') as session:
            return instantiate(session, str(project_id), tenant_id, account, template_id,
                data.get('name'), data.get('dataset_id')), 201
