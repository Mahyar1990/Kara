"""Native-console adapter: enqueue locally, relay persisted device events only."""
import inspect
import json
import time
from functools import wraps
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Forbidden, ServiceUnavailable
from company_projects import local_execution as local, agents
from extensions.ext_database import db
from models.account import Account


def submit(app,user,args,invoke_from,session,*,workflow=None,identity=None,root_node_id=None):
    from company_projects.personal_model_runtime import require_account_execution
    require_account_execution(app.tenant_id,user)
    if app.mode!='workflow': raise BadRequest('این نوع برنامه هنوز در پروتکل اجرای محلی پشتیبانی نشده است؛ اجرای سروری مسدود است.')
    if args.get('files'): raise BadRequest('پیوست فایل برای این نسخهٔ اجرای محلی پشتیبانی نشده است؛ ورودی متنی استفاده کنید.')
    if workflow is None:
        from services.app_generate_service import AppGenerateService
        workflow=AppGenerateService._get_workflow(app,invoke_from,args.get('workflow_id'),session=session)
    inputs=args.get('inputs',{})
    if not isinstance(inputs,dict): raise BadRequest('ورودی اجرا معتبر نیست.')
    if not root_node_id:
        from company_projects.runtime_models import business_inputs
        fields,_=agents.contracts(workflow)
        agents.validate_inputs(fields,business_inputs(inputs))
    job=local.enqueue(session,app,workflow,user,inputs,identity=identity,root_node_id=root_node_id,triggered_from='debugging' if str(invoke_from)=='debugger' else 'app-run')
    session.commit()
    return job


def response(job):
    result=job.get('result') or {}; created=job['created_at']; finished=job.get('finished_at')
    return dict(task_id=str(job['id']),workflow_run_id=str(job['id']),data=dict(id=str(job['id']),workflow_id=str(job['workflow_id']),status='succeeded' if job['state']=='succeeded' else 'stopped' if job['state'] in ('cancelled','interrupted') else 'failed',outputs=result.get('outputs',{}),error=result.get('error'),elapsed_time=max(0,(finished-job['started_at']).total_seconds()) if finished and job.get('started_at') else 0,total_tokens=result.get('total_tokens',0),total_steps=result.get('total_steps',0),created_at=int(created.timestamp()),finished_at=int(finished.timestamp()) if finished else None))


def chunks(identity,actor):
    sequence=0; announced=False
    while True:
        with Session(db.engine) as s,s.begin():
            local.expire(s); job=local.execution(s,identity,actor=actor)
            # Auth is fresh even on an already open stream.
            local.team.scope(s,job['project_id'],job['workspace_id'],actor)
            events=local.table(s,'local_execution_events')
            rows=s.execute(events.select().where(events.c.execution_id==str(identity),events.c.sequence>sequence).order_by(events.c.sequence).limit(100)).mappings().all()
        if not announced:
            announced=True
            yield dict(event='workflow_started',task_id=str(identity),workflow_run_id=str(identity),data=dict(id=str(identity),workflow_id=str(job['workflow_id']),inputs=job['inputs'],created_at=int(job['created_at'].timestamp())))
        for row in rows:
            sequence=row['sequence']; event=dict(row['event']); kind=event.pop('event')
            event=dict(event,id=str(identity)+':'+str(sequence),execution_id=str(identity),index=sequence,created_at=int(row['created_at'].timestamp()),finished_at=int(row['created_at'].timestamp()) if kind=='node_finished' else None)
            yield dict(event=kind,task_id=str(identity),workflow_run_id=str(identity),data=event)
        if job['state'] in local.TERMINAL:
            yield dict(event='workflow_finished',**response(job)); return
        yield dict(event='ping',task_id=str(identity),local_state=job['state'])
        time.sleep(2)


def relay(job,*,streaming=True,typed=False):
    if streaming:
        def stream():
            for event in chunks(job['id'],job['account_id']):
                yield 'data: '+json.dumps(event,ensure_ascii=False)+'\n\n'
        return stream()
    deadline=time.monotonic()+1800
    while time.monotonic()<deadline:
        with Session(db.engine) as s,s.begin():
            local.expire(s); value=local.execution(s,job['id'],actor=job['account_id'])
            local.team.scope(s,value['project_id'],value['workspace_id'],value['account_id'])
        if value['state'] in local.TERMINAL:
            value=response(value)
            if typed:
                from core.app.entities.task_entities import WorkflowAppBlockingResponse
                return WorkflowAppBlockingResponse.model_validate(value)
            return value
        time.sleep(2)
    raise ServiceUnavailable('اجرا هنوز در صف یا روی Runner است؛ وضعیت را در کارا پیگیری کنید. شناسه: '+str(job['id']))


def generate(app,user,args,invoke_from,session,streaming=True,root_node_id=None):
    return relay(submit(app,user,args,invoke_from,session,root_node_id=root_node_id),streaming=streaming)


def generator_boundary(generator):
    method=generator.generate; signature=inspect.signature(method)
    @wraps(method)
    def call(*args,**kwargs):
        values=signature.bind(*args,**kwargs); values.apply_defaults(); p=values.arguments
        from company_projects.agent_execution import deny_native
        deny_native(p['app_model'].id)
        with Session(db.engine) as s:
            job=submit(p['app_model'],p['user'],p['args'],p['invoke_from'],s,workflow=p['workflow'],identity=p.get('workflow_run_id'),root_node_id=p.get('root_node_id'))
        if p.get('streaming',True):
            from core.app.entities.task_entities import WorkflowAppStreamResponse, WorkflowStartStreamResponse, WorkflowFinishStreamResponse
            # Scheduled/legacy native callers expect typed workflow events.
            def typed_stream():
                for event in chunks(job['id'],job['account_id']):
                    kind=event['event']
                    if kind in ('workflow_started','workflow_finished'):
                        cls=WorkflowStartStreamResponse if kind=='workflow_started' else WorkflowFinishStreamResponse
                        yield WorkflowAppStreamResponse(task_id=job['id'],workflow_run_id=job['id'],stream_response=cls.model_validate(event))
            return typed_stream()
        return relay(job,streaming=False,typed=True)
    generator.generate=call
    for name in ('single_iteration_generate','single_loop_generate'):
        if hasattr(generator,name): setattr(generator,name,blocked)
    return generator


def blocked(*args,**kwargs):
    raise Forbidden('اجرای مستقیم گره یا موتور روی سرور غیرفعال است؛ اجرا باید به Runner واگذار شود.')


def enqueue_trigger(s,user,app,workflow,trigger_data,trigger_log):
    if not isinstance(user,Account): raise Forbidden('اتوماسیون به حساب شخصی و Runner آن نیاز دارد.')
    from company_projects.personal_model_runtime import require_account_execution
    require_account_execution(app.tenant_id,user)
    job=local.enqueue(s,app,workflow,user,dict(trigger_data.inputs),root_node_id=trigger_data.root_node_id,trigger_log_id=trigger_log.id,automatic=True)
    trigger_log.celery_task_id=job['id']; trigger_log.workflow_run_id=job['id']; s.commit()
    from services.workflow.entities import AsyncTriggerResponse
    return AsyncTriggerResponse(workflow_trigger_log_id=trigger_log.id,task_id=job['id'],status='queued',queue='local-runner')


def block_generator(generator):
    """Fail closed for native engines outside the advertised local graph protocol."""
    for name in ('generate','_generate_worker','generate_more_like_this','single_iteration_generate','single_loop_generate'):
        if hasattr(generator,name):setattr(generator,name,blocked)
    return generator


def stop(identity,actor):
    with Session(db.engine) as s,s.begin():
        try:job=local.execution(s,identity,actor=actor,lock=True)
        except local.NotFound:return False
        local.team.scope(s,job['project_id'],job['workspace_id'],actor)
        if job['state'] not in local.TERMINAL:local.finish(s,job,'cancelled',{'error':'اجرا به درخواست کاربر متوقف شد.'})
    return True


def resume(app,run):
    from libs.login import current_account_with_tenant
    with Session(db.engine) as s:
        try:job=local.execution(s,run.id)
        except local.NotFound:return None
        actor,workspace=current_account_with_tenant()
        if str(actor.id)!=str(job['account_id']) or str(workspace)!=str(job['workspace_id']) or app.id!=job['app_id']:raise Forbidden('جریان اجرا متعلق به حساب و پروژهٔ جاری نیست.')
    return relay(job,streaming=True)
