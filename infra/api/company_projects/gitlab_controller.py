"""Personal connection endpoints use only the authenticated account identity."""
from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session

from company_projects import gitlab_connections
from company_projects.controller import guarded, identity, payload
from controllers.console import console_ns
from extensions.ext_database import db


def personal(operation, *args):
    actor, _ = identity()
    with Session(db.engine) as session, session.begin():
        return operation(session, actor.id, *args)


@console_ns.route('/company/me/gitlab-connections')
class GitLabConnectionsApi(Resource):
    @guarded()
    def get(self):
        response = personal(gitlab_connections.list_connections)
        return response, 200, {'Cache-Control': 'private, no-store'}

    @guarded()
    def post(self):
        request.max_content_length = 16384
        return personal(gitlab_connections.save, payload()), 201


@console_ns.route('/company/me/gitlab-connections/<uuid:connection_id>')
class GitLabConnectionApi(Resource):
    @guarded()
    def put(self, connection_id):
        request.max_content_length = 16384
        return personal(gitlab_connections.save, payload(), connection_id)

    @guarded()
    def delete(self, connection_id):
        return personal(gitlab_connections.delete, connection_id, payload())


@console_ns.route('/company/me/gitlab-connections/<uuid:connection_id>/test')
class GitLabConnectionTestApi(Resource):
    @guarded()
    def post(self, connection_id):
        return personal(gitlab_connections.test_connection, connection_id)
