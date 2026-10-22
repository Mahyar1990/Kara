"""Native session/CSRF endpoints for versioned human team flows."""
from flask import request
from flask_restx import Resource

from company_projects import flows
from company_projects.agent_controller import invoke
from company_projects.controller import guarded, payload
from controllers.console import console_ns


def mutate(project_id, flow_id=None, action='save'):
    return invoke(flows.mutate, project_id, payload(), request.headers.get('Idempotency-Key'), flow_id, action)


@console_ns.route('/company/projects/<uuid:project_id>/team/flows')
class FlowsApi(Resource):
    @guarded()
    def get(self, project_id):
        return invoke(flows.list_flows, project_id)

    @guarded()
    def post(self, project_id):
        return mutate(project_id), 201


@console_ns.route('/company/projects/<uuid:project_id>/team/flows/options')
class FlowOptionsApi(Resource):
    @guarded()
    def get(self, project_id):
        return invoke(flows.options, project_id)


@console_ns.route('/company/projects/<uuid:project_id>/team/flows/<uuid:flow_id>')
class FlowApi(Resource):
    @guarded()
    def get(self, project_id, flow_id):
        return invoke(flows.get_flow, project_id, flow_id)

    @guarded()
    def put(self, project_id, flow_id):
        return mutate(project_id, flow_id)


@console_ns.route('/company/projects/<uuid:project_id>/team/flows/<uuid:flow_id>/publish')
class FlowPublishApi(Resource):
    @guarded()
    def post(self, project_id, flow_id):
        return mutate(project_id, flow_id, 'publish')


@console_ns.route('/company/projects/<uuid:project_id>/team/flows/<uuid:flow_id>/archive')
class FlowArchiveApi(Resource):
    @guarded()
    def post(self, project_id, flow_id):
        return mutate(project_id, flow_id, 'archive')


@console_ns.route('/company/projects/<uuid:project_id>/team/flows/<uuid:flow_id>/versions')
class FlowVersionsApi(Resource):
    @guarded()
    def get(self, project_id, flow_id):
        return invoke(flows.list_versions, project_id, flow_id)


@console_ns.route('/company/projects/<uuid:project_id>/team/flows/<uuid:flow_id>/versions/<uuid:version_id>')
class FlowVersionApi(Resource):
    @guarded()
    def get(self, project_id, flow_id, version_id):
        return invoke(flows.get_version, project_id, flow_id, version_id)
