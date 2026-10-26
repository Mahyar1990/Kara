"""Console CRUD and a separate device-scoped Runner protocol."""
from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session
from werkzeug.exceptions import Unauthorized
from company_projects import source_code as source
from company_projects.controller import guarded, identity, payload
from controllers.console import console_ns
from extensions.ext_database import db

NO_STORE={'Cache-Control':'private, no-store'}

def source_payload():
    request.max_content_length=400000
    return payload()

def console(operation,*args,project=None):
    actor,workspace=identity(); request.max_content_length=400000
    with Session(db.engine) as s, s.begin():
        result=operation(s,project,workspace,actor.id,*args) if project else operation(s,actor.id,*args)
    return result,200,NO_STORE

def device_call(operation,*args,anonymous=False):
    request.max_content_length=16384
    with Session(db.engine) as s,s.begin():
        if anonymous: result=operation(s,*args)
        else:
            header=request.headers.get('Authorization','')
            if not header.startswith('Bearer '): raise Unauthorized('توکن Runner لازم است.')
            result=operation(s,source.authenticate(s,header[7:]),*args)
    return result,200,NO_STORE

@console_ns.route('/company/projects/<uuid:project_id>/source-code')
class SourceCode(Resource):
    @guarded()
    def get(self,project_id): return console(source.listing,project=project_id)

@console_ns.route('/company/projects/<uuid:project_id>/source-code/repositories')
class Repositories(Resource):
    @guarded()
    def post(self,project_id): return console(source.save_repository,source_payload(),project=project_id)

@console_ns.route('/company/projects/<uuid:project_id>/source-code/repositories/<uuid:entity_id>')
class Repository(Resource):
    @guarded()
    def put(self,project_id,entity_id): return console(source.save_repository,source_payload(),entity_id,project=project_id)
    @guarded()
    def delete(self,project_id,entity_id): return console(source.retire,'repositories',entity_id,source_payload(),project=project_id)

@console_ns.route('/company/projects/<uuid:project_id>/source-code/workspaces')
class Workspaces(Resource):
    @guarded()
    def post(self,project_id): return console(source.save_workspace,source_payload(),project=project_id)

@console_ns.route('/company/projects/<uuid:project_id>/source-code/workspaces/<uuid:entity_id>')
class Workspace(Resource):
    @guarded()
    def put(self,project_id,entity_id): return console(source.save_workspace,source_payload(),entity_id,project=project_id)
    @guarded()
    def delete(self,project_id,entity_id): return console(source.retire,'workspaces',entity_id,source_payload(),project=project_id)

@console_ns.route('/company/projects/<uuid:project_id>/source-code/workspaces/<uuid:entity_id>/prepare')
class Prepare(Resource):
    @guarded()
    def post(self,project_id,entity_id): return console(source.enqueue,entity_id,source_payload(),project=project_id)

@console_ns.route('/company/projects/<uuid:project_id>/source-code/jobs/<uuid:job_id>/cancel')
class Cancel(Resource):
    @guarded()
    def post(self,project_id,job_id): return console(source.cancel,job_id,project=project_id)

@console_ns.route('/company/me/source-runners')
class Devices(Resource):
    @guarded()
    def get(self): return console(source.devices)

@console_ns.route('/company/me/source-runners/pairing')
class Pairing(Resource):
    @guarded()
    def post(self): return console(source.pairing,source_payload())

@console_ns.route('/company/me/source-runners/<uuid:device_id>/revoke')
class Revoke(Resource):
    @guarded()
    def post(self,device_id): return console(source.revoke,device_id)

@console_ns.route('/company/me/source-runners/download')
class Download(Resource):
    @guarded()
    def get(self):
        # Archive generated from the same version as the server; no credentials inside.
        import io, zipfile
        from pathlib import Path
        import kara_source_runner
        buffer=io.BytesIO(); root=Path(kara_source_runner.__file__).parent
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(root.glob('*.py')): archive.writestr('kara_source_runner/'+file.name,file.read_bytes())
            from kara_source_runner.package import extras
            for name,content in extras().items():archive.writestr(name,content)
        import base64
        return dict(filename='kara-source-runner.zip', content=base64.b64encode(buffer.getvalue()).decode()),200,NO_STORE

@console_ns.route('/company/source-runner/pair')
class RunnerPair(Resource):
    def post(self): return device_call(source.pair,source_payload(),anonymous=True)

@console_ns.route('/company/source-runner/claim')
class RunnerClaim(Resource):
    def post(self): return device_call(source.claim)

@console_ns.route('/company/source-runner/jobs/<uuid:job_id>/heartbeat')
class RunnerHeartbeat(Resource):
    def post(self,job_id): return device_call(source.heartbeat,job_id)

@console_ns.route('/company/source-runner/jobs/<uuid:job_id>/credentials')
class RunnerCredentials(Resource):
    def post(self,job_id): return device_call(source.credentials,job_id)

@console_ns.route('/company/source-runner/jobs/<uuid:job_id>/complete')
class RunnerComplete(Resource):
    def post(self,job_id): return device_call(source.complete,job_id,source_payload())

# Execution jobs share device identity, never console session authority.
from company_projects import local_execution

@console_ns.route('/company/projects/<uuid:project_id>/local-execution')
class LocalExecutionSettings(Resource):
    @guarded()
    def get(self,project_id): return console(local_execution.settings,project=project_id)
    @guarded()
    def put(self,project_id): return console(local_execution.set_binding,source_payload(),project=project_id)

@console_ns.route('/company/projects/<uuid:project_id>/local-execution/<uuid:execution_id>/cancel')
class LocalExecutionCancel(Resource):
    @guarded()
    def post(self,project_id,execution_id): return console(local_execution.cancel,execution_id,project=project_id)

@console_ns.route('/company/source-runner/execution/register')
class LocalExecutionRegister(Resource):
    def post(self): return device_call(local_execution.register,source_payload())

@console_ns.route('/company/source-runner/execution/claim')
class LocalExecutionClaim(Resource):
    def post(self): return device_call(local_execution.claim)

@console_ns.route('/company/source-runner/execution/<uuid:execution_id>/heartbeat')
class LocalExecutionHeartbeat(Resource):
    def post(self,execution_id): return device_call(local_execution.heartbeat,execution_id)

@console_ns.route('/company/source-runner/execution/<uuid:execution_id>/credentials')
class LocalExecutionCredentials(Resource):
    def post(self,execution_id): return device_call(local_execution.credentials,execution_id)

@console_ns.route('/company/source-runner/execution/<uuid:execution_id>/events')
class LocalExecutionEvents(Resource):
    def post(self,execution_id): return device_call(local_execution.events,execution_id,source_payload())

@console_ns.route('/company/source-runner/execution/<uuid:execution_id>/complete')
class LocalExecutionComplete(Resource):
    def post(self,execution_id): return device_call(local_execution.complete,execution_id,execution_payload())

@console_ns.route('/company/source-runner/execution/<uuid:execution_id>/knowledge')
class LocalExecutionKnowledge(Resource):
    def post(self,execution_id): return device_call(local_execution.knowledge_page,execution_id,source_payload())

from company_projects import local_rpc

def execution_payload():
    request.max_content_length=18000000
    return payload()

@console_ns.route('/company/source-runner/rpc/claim')
class LocalRpcClaim(Resource):
    def post(self): return device_call(local_rpc.claim)

@console_ns.route('/company/source-runner/rpc/<uuid:execution_id>/credentials')
class LocalRpcCredentials(Resource):
    def post(self,execution_id): return device_call(local_rpc.credentials,execution_id)

@console_ns.route('/company/source-runner/rpc/<uuid:execution_id>/heartbeat')
class LocalRpcHeartbeat(Resource):
    def post(self,execution_id): return device_call(local_rpc.heartbeat,execution_id)

@console_ns.route('/company/source-runner/rpc/<uuid:execution_id>/complete')
class LocalRpcComplete(Resource):
    def post(self,execution_id): return device_call(local_rpc.complete,execution_id,execution_payload())
