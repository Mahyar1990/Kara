"""Native session/CSRF routes; publication and intake never dispatch a stage."""
import logging

from flask import request
from flask_restx import Resource

from company_projects import stages
from company_projects.agent_controller import invoke
from company_projects.agent_execution import execute_task
from company_projects.controller import guarded, payload
from controllers.console import console_ns


@console_ns.route('/company/projects/<uuid:project_id>/team/instances')
class InstancesApi(Resource):
    @guarded()
    def get(self, project_id):
        return invoke(stages.list_instances, project_id)

    @guarded()
    def post(self, project_id):
        return invoke(stages.create, project_id, payload(), request.headers.get('Idempotency-Key')), 201


@console_ns.route('/company/projects/<uuid:project_id>/team/instances/<uuid:instance_id>/stages/<uuid:stage_id>')
class StageApi(Resource):
    @guarded()
    def get(self, project_id, instance_id, stage_id):
        return invoke(stages.get_stage, project_id, instance_id, stage_id)


@console_ns.route('/company/projects/<uuid:project_id>/team/instances/<uuid:instance_id>/stages/<uuid:stage_id>/<string:action>')
class StageActionApi(Resource):
    @guarded()
    def post(self, project_id, instance_id, stage_id, action):
        result = invoke(stages.mutate, project_id, instance_id, stage_id, action, payload(), request.headers.get('Idempotency-Key'))
        if action == 'run' and result['active_attempt_id']:
            try:
                # Same committed outbox and recovery dispatcher as standalone agents.
                execute_task.delay(result['active_attempt_id'])
            except Exception:
                logging.getLogger(__name__).exception('Stage dispatch deferred: %s', result['active_attempt_id'])
        return result, 202 if action == 'run' else 200
