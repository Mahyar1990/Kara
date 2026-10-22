"""Same-session, CSRF-protected manual request and intake endpoints."""
import json
from io import BytesIO

from flask import request, send_file
from flask_restx import Resource
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from company_projects import requests
from company_projects.agent_controller import invoke
from company_projects.controller import guarded, payload
from controllers.console import console_ns


def save(project_id, request_id=None):
    files = []
    if request.mimetype == 'multipart/form-data':
        # Bound multipart parsing as well as each individual file read.
        request.max_content_length = 6 * 1024 * 1024
        if set(request.form) != {'data'} or set(request.files) - {'files'}:
            raise BadRequest('فیلدهای فرم معتبر نیستند.')
        try:
            data = json.loads(request.form['data'])
        except (ValueError, TypeError):
            raise BadRequest('متن فرم معتبر نیست.') from None
        uploads = request.files.getlist('files')
        if len(uploads) > requests.MAX_FILES:
            raise RequestEntityTooLarge('حداکثر پنج پیوست مجاز است.')
        files = [(value.filename, value.stream.read(requests.MAX_FILE + 1)) for value in uploads]
    else:
        data = payload()
    return invoke(requests.save, project_id, data, request.headers.get('Idempotency-Key'), request_id, files)


@console_ns.route('/company/projects/<uuid:project_id>/team/requests')
class RequestsApi(Resource):
    @guarded()
    def get(self, project_id):
        return invoke(requests.list_requests, project_id)

    @guarded()
    def post(self, project_id):
        return save(project_id), 201


@console_ns.route('/company/projects/<uuid:project_id>/team/requests/<uuid:request_id>')
class RequestApi(Resource):
    @guarded()
    def get(self, project_id, request_id):
        return invoke(requests.get_request, project_id, request_id)


@console_ns.route('/company/projects/<uuid:project_id>/team/requests/<uuid:request_id>/revisions')
class RequestRevisionsApi(Resource):
    @guarded()
    def get(self, project_id, request_id):
        return {'data': invoke(requests.get_request, project_id, request_id)['revisions']}

    @guarded()
    def post(self, project_id, request_id):
        return save(project_id, request_id), 201


@console_ns.route('/company/projects/<uuid:project_id>/team/requests/<uuid:request_id>/intake-decisions')
class IntakeDecisionsApi(Resource):
    @guarded()
    def get(self, project_id, request_id):
        return {'data': invoke(requests.get_request, project_id, request_id)['decisions']}

    @guarded()
    def post(self, project_id, request_id):
        return invoke(requests.decide, project_id, request_id, payload(), request.headers.get('Idempotency-Key')), 201


@console_ns.route('/company/projects/<uuid:project_id>/team/requests/<uuid:request_id>/intake-decisions/<uuid:decision_id>/revocations')
class IntakeRevocationsApi(Resource):
    @guarded()
    def post(self, project_id, request_id, decision_id):
        return invoke(requests.decide, project_id, request_id, payload(), request.headers.get('Idempotency-Key'), decision_id), 201


@console_ns.route('/company/projects/<uuid:project_id>/team/requests/<uuid:request_id>/attachments/<uuid:attachment_id>')
class RequestAttachmentApi(Resource):
    @guarded()
    def get(self, project_id, request_id, attachment_id):
        value = invoke(requests.download, project_id, request_id, attachment_id)
        response = send_file(BytesIO(value['content']), mimetype='application/octet-stream', as_attachment=True,
            download_name=value['name'], max_age=0)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
