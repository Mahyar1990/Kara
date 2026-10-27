"""Authenticated program composition; transaction commits contain no execution."""
from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session
from company_projects import program_agents as programs
from company_projects.controller import guarded, identity, payload
from controllers.console import console_ns
from extensions.ext_database import db


def invoke(operation, project, *args, **kwargs):
    actor, workspace = identity()
    with Session(db.engine) as s, s.begin():
        return operation(s, project, workspace, actor.id, *args, **kwargs)


@console_ns.route('/company/projects/<uuid:project_id>/program-agents')
class ProgramLibraryApi(Resource):
    @guarded()
    def get(self, project_id):
        return invoke(programs.catalog, project_id)

    @guarded()
    def post(self, project_id):
        result = invoke(programs.create, project_id, payload(), request.headers.get('Idempotency-Key'))
        from tasks.initialize_created_app_rbac_access_task import initialize_created_app_rbac_access_task
        from configs import dify_config
        if dify_config.RBAC_ENABLED:
            actor, workspace = identity()
            from services.app_service import _CreatedApp, _initialize_created_app_access
            _initialize_created_app_access(_CreatedApp(tenant_id=workspace, creator_account_id=actor.id, app_id=result['app_id'], backing_agent_id=None))
            try:
                initialize_created_app_rbac_access_task.delay(workspace, actor.id, app_id=result['app_id'])
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Program library access synchronization deferred')
        return result, 201


@console_ns.route('/company/projects/<uuid:project_id>/program-agents/sources/<uuid:source_id>')
class ProgramRolePreviewApi(Resource):
    @guarded()
    def get(self, project_id, source_id):
        return invoke(programs.preview, project_id, source_id, request.args.get('snapshot_id'))


@console_ns.route('/company/projects/<uuid:project_id>/program-agents/programs/<uuid:app_id>')
class ProgramRoleDetailApi(Resource):
    @guarded()
    def get(self, project_id, app_id):
        return invoke(programs.detail, project_id, app_id)


@console_ns.route('/company/projects/<uuid:project_id>/program-agents/programs/<uuid:app_id>/nodes/<string:node_id>')
class ProgramRoleAttachApi(Resource):
    @guarded()
    def post(self, project_id, app_id, node_id):
        return invoke(programs.modify, project_id, app_id, node_id, payload(), request.headers.get('Idempotency-Key'))


@console_ns.route('/company/projects/<uuid:project_id>/program-agents/programs/<uuid:app_id>/nodes/<string:node_id>/detach')
class ProgramRoleDetachApi(Resource):
    @guarded()
    def post(self, project_id, app_id, node_id):
        return invoke(programs.modify, project_id, app_id, node_id, payload(), request.headers.get('Idempotency-Key'), detach=True)
