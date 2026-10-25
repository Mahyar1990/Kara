"""Same-session personal model management; credentials are never returned."""
from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session

from company_projects import personal_models
from company_projects.controller import guarded, identity, payload
from controllers.console import console_ns
from extensions.ext_database import db


def invoke(operation, *args, workspace=False):
    user, tenant = identity()
    with Session(db.engine) as session, session.begin():
        if workspace:
            return operation(session, tenant, user.id, *args)
        return operation(session, user.id, *args)


@console_ns.route('/company/me/model-connections')
class ModelConnectionsApi(Resource):
    @guarded()
    def get(self):
        return invoke(personal_models.list_connections), 200, {'Cache-Control': 'private, no-store'}

    @guarded()
    def post(self):
        request.max_content_length = 65536
        return invoke(personal_models.save, payload(), workspace=True), 201


@console_ns.route('/company/me/model-connections/providers')
class PersonalModelProvidersApi(Resource):
    @guarded()
    def get(self):
        user, tenant = identity()
        return personal_models.catalog(tenant, user.id), 200, {'Cache-Control': 'private, no-store'}


@console_ns.route('/company/me/model-connections/<uuid:connection_id>')
class ModelConnectionApi(Resource):
    @guarded()
    def get(self, connection_id):
        return invoke(personal_models.detail, connection_id, workspace=True), 200, {'Cache-Control': 'private, no-store'}

    @guarded()
    def put(self, connection_id):
        request.max_content_length = 65536
        return invoke(personal_models.save, payload(), connection_id, workspace=True)

    @guarded()
    def delete(self, connection_id):
        return invoke(personal_models.delete, connection_id, payload())


@console_ns.route('/company/me/model-connections/<uuid:connection_id>/test')
class ModelConnectionTestApi(Resource):
    @guarded()
    def post(self, connection_id):
        return invoke(personal_models.test_connection, connection_id, workspace=True)
