from flask_restx import Resource
from sqlalchemy.orm import Session
from company_projects import program_team
from company_projects.controller import guarded, identity
from controllers.console import console_ns
from extensions.ext_database import db


@console_ns.route('/company/projects/<uuid:project_id>/program-team')
class ProgramTeamApi(Resource):
    @guarded()
    def get(self, project_id):
        actor, workspace = identity()
        with Session(db.engine) as s:
            return program_team.catalog(s, project_id, workspace, actor.id)
