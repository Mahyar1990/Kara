"""Session/CSRF-protected team role endpoints; server derives the actor and scope."""
from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session

from company_projects import team
from company_projects.controller import guarded, identity, payload
from controllers.console import console_ns
from extensions.ext_database import db


@console_ns.route('/company/projects/<uuid:project_id>/team/members')
class TeamMembersApi(Resource):
    @guarded()
    def get(self, project_id):
        actor, workspace_id = identity()
        with Session(db.engine) as session:
            return dict(data=team.list_roles(session, project_id, workspace_id, actor.id))


@console_ns.route('/company/projects/<uuid:project_id>/team/members/<uuid:account_id>/roles')
class TeamMemberRolesApi(Resource):
    @guarded()
    def get(self, project_id, account_id):
        actor, workspace_id = identity()
        with Session(db.engine) as session:
            return team.get_roles(session, project_id, workspace_id, actor.id, account_id)

    @guarded()
    def put(self, project_id, account_id):
        actor, workspace_id = identity()
        with Session(db.engine) as session, session.begin():
            return team.set_roles(session, project_id, workspace_id, actor.id, account_id,
                payload(), request.headers.get('Idempotency-Key'))
