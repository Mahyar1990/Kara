"""Authenticated team agent management and controlled execution API."""
import logging

from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session

from company_projects import agents
from company_projects.agent_execution import execute_task
from company_projects.controller import guarded, identity, payload
from controllers.console import console_ns
from extensions.ext_database import db


def invoke(operation, *args):
    actor, workspace = identity()
    with Session(db.engine) as session:
        with session.begin():
            return operation(session, args[0], workspace, actor.id, *args[1:])


@console_ns.route('/company/projects/<uuid:project_id>/team/agents')
class AgentsApi(Resource):
    @guarded()
    def get(self, project_id):
        return invoke(agents.list_agents, project_id)

    @guarded()
    def post(self, project_id):
        return invoke(agents.register, project_id, payload(), request.headers.get('Idempotency-Key')), 201


@console_ns.route('/company/projects/<uuid:project_id>/team/agents/sources')
class AgentSourcesApi(Resource):
    @guarded()
    def get(self, project_id):
        return invoke(agents.sources, project_id)


@console_ns.route('/company/projects/<uuid:project_id>/team/agents/<uuid:agent_id>/grants')
class AgentGrantsApi(Resource):
    @guarded()
    def get(self, project_id, agent_id):
        return invoke(agents.get_grants, project_id, agent_id)

    @guarded()
    def put(self, project_id, agent_id):
        return invoke(agents.set_grants, project_id, agent_id, payload(), request.headers.get('Idempotency-Key'))


@console_ns.route('/company/projects/<uuid:project_id>/team/agents/<uuid:agent_id>/archive')
class AgentArchiveApi(Resource):
    @guarded()
    def post(self, project_id, agent_id):
        return invoke(agents.archive, project_id, agent_id, payload(), request.headers.get('Idempotency-Key'))


@console_ns.route('/company/projects/<uuid:project_id>/team/agents/<uuid:agent_id>/attempts')
class AgentAttemptsApi(Resource):
    @guarded()
    def post(self, project_id, agent_id):
        result = invoke(agents.start, project_id, agent_id, payload(), request.headers.get('Idempotency-Key'))
        if result['status'] == 'pending':
            try:
                # Only after commit. The periodic outbox dispatcher recovers broker failure.
                execute_task.delay(result['id'])
            except Exception:
                logging.getLogger(__name__).exception('Team agent dispatch deferred: %s', result['id'])
        return result, 202


@console_ns.route('/company/projects/<uuid:project_id>/team/agents/<uuid:agent_id>/attempts/<uuid:attempt_id>')
class AgentAttemptApi(Resource):
    @guarded()
    def get(self, project_id, agent_id, attempt_id):
        return invoke(agents.get_attempt, project_id, agent_id, attempt_id)
