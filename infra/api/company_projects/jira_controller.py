"""Personal connection endpoints use only the authenticated account identity."""
from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session

from company_projects import jira_connections
from company_projects.controller import guarded, identity, payload
from controllers.console import console_ns
from extensions.ext_database import db


def personal(operation, *args):
    actor, _ = identity()
    with Session(db.engine) as session, session.begin():
        return operation(session, actor.id, *args)


@console_ns.route('/company/me/jira-connections')
class JiraConnectionsApi(Resource):
    @guarded()
    def get(self):
        response = personal(jira_connections.list_connections)
        return response, 200, {'Cache-Control': 'private, no-store'}

    @guarded()
    def post(self):
        request.max_content_length = 16384
        return personal(jira_connections.save, payload()), 201


@console_ns.route('/company/me/jira-connections/<uuid:connection_id>')
class JiraConnectionApi(Resource):
    @guarded()
    def put(self, connection_id):
        request.max_content_length = 16384
        return personal(jira_connections.save, payload(), connection_id)

    @guarded()
    def delete(self, connection_id):
        return personal(jira_connections.delete, connection_id, payload())


@console_ns.route('/company/me/jira-connections/<uuid:connection_id>/test')
class JiraConnectionTestApi(Resource):
    @guarded()
    def post(self, connection_id):
        return personal(jira_connections.test_connection, connection_id)
