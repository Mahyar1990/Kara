"""HTTP boundary for reviewed, project-scoped Agency template adoption."""
import sqlalchemy as sa
from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session
from company_projects import agency_catalog as agency, agents
from company_projects.controller import guarded, identity, payload
from controllers.console import console_ns
from extensions.ext_database import db
from extensions.ext_storage import storage


@console_ns.route('/company/projects/<uuid:project_id>/agency-agents')
class AgencyCatalogApi(Resource):
    @guarded()
    def get(self, project_id):
        actor, workspace = identity()
        with Session(db.engine) as s:
            return agency.listing(s, project_id, workspace, actor.id)


@console_ns.route('/company/projects/<uuid:project_id>/agency-agents/<string:template_id>')
class AgencyPreviewApi(Resource):
    @guarded()
    def get(self, project_id, template_id):
        actor, workspace = identity()
        with Session(db.engine) as s:
            return agency.preview(s, project_id, workspace, actor.id, template_id)


@console_ns.route('/company/projects/<uuid:project_id>/agency-agents/<string:template_id>/copies')
class AgencyCopyApi(Resource):
    @guarded()
    def post(self, project_id, template_id):
        actor, workspace = identity(); written = []
        try:
            with Session(db.engine) as s, s.begin():
                result = agency.adopt(s, project_id, workspace, actor.id, template_id, payload(), request.headers.get('Idempotency-Key'), written)
        except Exception:
            # A lost commit acknowledgement must not delete a file belonging to a committed copy.
            if written:
                try:
                    with Session(db.engine) as check:
                        t = agency.adoptions(check)
                        committed = check.scalar(sa.select(t.c.id).where(t.c.project_id == str(project_id), t.c.workspace_id == str(workspace),
                            t.c.actor_id == actor.id, t.c.correlation_id == agents.action_key(request.headers.get('Idempotency-Key'))).limit(1))
                    if not committed:
                        for key in written: storage.delete(key)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception('Agency adoption file retained pending commit reconciliation')
            raise
        if result.get('created'):
            from services.rbac_agent_access_service import initialize_agent_rbac_access
            initialize_agent_rbac_access(tenant_id=str(workspace), agent_id=result['agent_id'], creator_account_id=actor.id)
        return result, 201
