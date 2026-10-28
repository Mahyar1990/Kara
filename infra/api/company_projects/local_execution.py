"""Central authorization/ledger only. Graphs, model calls and tools run on a device."""
from copy import deepcopy
from datetime import timedelta, timezone
import hashlib
import json
import time
from uuid import uuid4
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound
from company_projects import agents, access, team, source_code as source, personal_models
from models.account import Account
from models.model import App
from models.workflow import Workflow, WorkflowRun

TERMINAL=('succeeded','failed','cancelled','interrupted','blocked')
PROTOCOL=2

def table(s,name): return agents.reflected(s,'company_'+name)
def utc_naive(value): return value.astimezone(timezone.utc).replace(tzinfo=None) if value else None

def execution(s,identity,runner=None,actor=None,lock=False):
    t=table(s,'local_executions'); q=sa.select(t).where(t.c.id==source.uid(identity))
    if runner: q=q.where(t.c.device_id==str(runner['id']),t.c.account_id==str(runner['account_id']))
    if actor: q=q.where(t.c.account_id==str(actor))
    row=s.execute(q.with_for_update() if lock else q).mappings().first()
    if not row: raise NotFound('اجرای محلی در دسترس نیست.')
    return dict(row)

def binding(s,project,workspace,actor):
    team.scope(s,project,workspace,actor); t=table(s,'execution_bindings')
    row=s.execute(sa.select(t).where(t.c.project_id==str(project),t.c.account_id==str(actor))).mappings().first()
    return dict(row) if row else None

def settings(s,project,workspace,actor):
    selected=binding(s,project,workspace,actor); expire(s)
    t=table(s,'local_executions')
    jobs=s.execute(sa.select(t).where(t.c.project_id==str(project),t.c.workspace_id==str(workspace),t.c.account_id==str(actor)).order_by(t.c.created_at.desc()).limit(50)).mappings()
    result=[dict(public(r),kind='workflow') for r in jobs]
    from company_projects.local_rpc import table as rpc_table
    rpc=rpc_table(s)
    for r in s.execute(sa.select(rpc).where(rpc.c.project_id==str(project),rpc.c.account_id==str(actor)).order_by(rpc.c.created_at.desc()).limit(50)).mappings():
        result.append(dict(id=str(r['id']),kind='rpc',device_id=str(r['device_id']) if r['device_id'] else None,state=r['state'],created_at=r['created_at'].isoformat(),result={'error':(r['result'] or {}).get('error')}))
    result.sort(key=lambda r:r['created_at'],reverse=True)
    return dict(binding=source.public(selected) if selected else None,executions=result[:50])

def set_binding(s,project,workspace,actor,data):
    agents.body(data,('device_id','source_job_id','expected_revision')); key=team.scope(s,project,workspace,actor)
    # Account lock serializes first binding and concurrent device changes.
    from company_projects.gitlab_connections import account
    account(s,actor,lock=True); source.device(s,actor,data['device_id'],True)
    previous=binding(s,project,workspace,actor); source.check_revision(data,previous)
    source_job=None
    if data['source_job_id']:
        source_job=source.row(s,'jobs',data['source_job_id'],key|dict(account_id=str(actor),device_id=str(data['device_id'])))
        if source_job['state']!='succeeded': raise BadRequest('ابتدا سورس را روی همین دستگاه آماده کنید.')
    values=dict(**key,account_id=str(actor),device_id=source.uid(data['device_id']),source_job_id=str(source_job['id']) if source_job else None,revision=(previous['revision']+1) if previous else 1,updated_at=agents.now())
    t=table(s,'execution_bindings')
    if previous: s.execute(t.update().where(t.c.project_id==str(project),t.c.account_id==str(actor)).values(**values))
    else: s.execute(t.insert().values(**values))
    from company_projects.local_rpc import table as rpc_table
    rpc=rpc_table(s);s.execute(rpc.update().where(rpc.c.project_id==str(project),rpc.c.account_id==str(actor),rpc.c.state=='pending',rpc.c.device_id.is_(None)).values(device_id=values['device_id']))
    # Only unassigned jobs can be assigned here. Jobs already targeted never move silently.
    jobs=table(s,'local_executions'); s.execute(jobs.update().where(jobs.c.project_id==str(project),jobs.c.account_id==str(actor),jobs.c.state=='pending',jobs.c.device_id.is_(None)).values(device_id=values['device_id'],source_job_id=values['source_job_id']))
    return source.public(values)

def register(s,runner,data):
    agents.body(data,('protocol','capabilities'))
    if data['protocol']!=PROTOCOL or not isinstance(data['capabilities'],list) or set(data['capabilities'])-{'workflow-v2','python3','javascript','http','source-v1'}: raise BadRequest('نسخه یا قابلیت Runner معتبر نیست.')
    t=table(s,'runner_capabilities'); values=dict(device_id=str(runner['id']),protocol=PROTOCOL,capabilities=sorted(set(data['capabilities'])),updated_at=agents.now())
    if s.scalar(sa.select(t.c.device_id).where(t.c.device_id==str(runner['id']))): s.execute(t.update().where(t.c.device_id==str(runner['id'])).values(**values))
    else: s.execute(t.insert().values(**values))
    return dict(registered=True,protocol=PROTOCOL)

def public(row):
    return {k: row[k].isoformat() if hasattr(row[k],'isoformat') else row[k] for k in ('id','project_id','device_id','source_job_id','app_id','workflow_id','team_attempt_id','state','created_at','started_at','finished_at','result') if k in row}

def project_key(s,workspace,actor):
    project=access.workspace_project(s,workspace)
    if not project: raise Forbidden('اجرای محلی به پروژهٔ مستقل نیاز دارد.')
    return team.scope(s,project['id'],workspace,actor)

def build_snapshot(s,workflow,actor,inputs):
    from company_projects import runtime_models
    from kara_source_runner.workflow_contract import validate_graph
    from company_projects.personal_agent_sources import validate
    validate(s,workflow,actor)
    graph=deepcopy(workflow.graph_dict)
    # Selection resolves only metadata and the actor's connection. No model inference here.
    selection=runtime_models.select(s,workflow,actor,inputs.get(runtime_models.INPUT))
    models={}
    for node in graph.get('nodes',[]):
        d=node.get('data',{})
        if d.get('type')=='llm':
            m=d['model']
            row=personal_models.load(s,actor,selection['connection_id']) if selection else personal_models.resolve(s,actor,m['provider'],m['name'],'llm')
            models[node['id']]=dict(id=str(row['id']),revision=row['revision'],provider=row['provider'],model_name=row['model_name'],model_type='llm')
            d['model']=dict(m,provider=row['provider'],name=row['model_name'])
        if d.get('type')=='start':
            d['variables']=[v for v in d.get('variables',[]) if v.get('variable')!=runtime_models.INPUT]
            if selection:d['kara_runtime_model_used']=deepcopy(selection)
    try: requirements=validate_graph(graph)
    except ValueError as exc: raise BadRequest('این نسخهٔ Runner تعریف برنامه را پشتیبانی نمی‌کند: '+str(exc)) from None
    knowledge=knowledge_spec(s,workflow,actor,graph,models)
    return dict(protocol=PROTOCOL,graph=graph,models=models,knowledge=knowledge,requirements=requirements,workflow_digest=agents.fingerprint(workflow))

def enqueue(s,app,workflow,actor,inputs,*,identity=None,attempt=None,root_node_id=None,trigger_log_id=None,preview=None,triggered_from='app-run'):
    key=project_key(s,app.tenant_id,actor.id); join=team.member(s,app.tenant_id,actor.id)
    identity=identity or str(uuid4()); t=table(s,'local_executions')
    old=s.execute(sa.select(t).where(t.c.id==str(identity))).mappings().first()
    if old:
        if str(old['account_id'])!=str(actor.id) or str(old['workflow_id'])!=str(workflow.id): raise Conflict('شناسهٔ اجرا قبلاً استفاده شده است.')
        return dict(old)
    snapshot=build_snapshot(s,workflow,actor.id,inputs)
    if len(json.dumps(snapshot,ensure_ascii=False).encode())>8388608:raise BadRequest('تعریف و دانش این اجرا بیش از بودجهٔ واگذاری است.')
    snapshot['root_node_id']=root_node_id
    snapshot['triggered_from']=triggered_from
    if preview:snapshot['preview']=preview
    selected=binding(s,key['project_id'],key['workspace_id'],actor.id)
    now=agents.now(); values=dict(id=str(identity),**key,account_id=str(actor.id),membership_id=join.id,device_id=selected['device_id'] if selected else None,source_job_id=selected['source_job_id'] if selected else None,app_id=app.id,workflow_id=workflow.id,team_attempt_id=attempt['id'] if attempt else None,trigger_log_id=trigger_log_id,snapshot=snapshot,snapshot_digest=agents.digest(snapshot),inputs={k:v for k,v in inputs.items() if k!='__kara_model_connection'},state='pending',created_at=now,event_sequence=0)
    s.execute(t.insert().values(**values))
    return values

def dispatch_team(s,attempt_id):
    from company_projects import agent_execution
    # Reuse existing business permission/version validation without starting execution.
    claimed=agent_execution.claim(s,attempt_id,start=False)
    if claimed is None: return None
    attempt,agent=claimed
    actor=s.get(Account,attempt['actor_id']); app=s.get(App,agent['app_id']); workflow=s.get(Workflow,attempt['workflow_id'])
    try: return enqueue(s,app,workflow,actor,attempt['inputs'],identity=attempt['id'],attempt=attempt)
    except (BadRequest,Forbidden,Conflict,NotFound) as exc:
        t=agents.tables(s)[2]; s.execute(t.update().where(t.c.id==attempt['id'],t.c.status=='pending').values(status='blocked',finished_at=agents.now(),result={'error':exc.description}))
        from company_projects.stages import complete_attempt
        complete_attempt(s,attempt['id']); return None

def validate_access(s,job):
    team.scope(s,job['project_id'],job['workspace_id'],job['account_id'])
    join=team.member(s,job['workspace_id'],job['account_id'])
    if str(join.id)!=str(job['membership_id']): raise Forbidden('عضویت اجرا تغییر کرده است.')
    workflow=s.get(Workflow,job['workflow_id']); app=s.get(App,job['app_id'])
    if not app or app.status!='normal' or not workflow or workflow.app_id!=app.id or workflow.tenant_id!=job['workspace_id'] or agents.fingerprint(workflow)!=job['snapshot']['workflow_digest']: raise Conflict('نسخه یا دسترسی برنامه تغییر کرده است.')
    from company_projects.personal_agent_sources import validate
    validate(s,workflow,job['account_id'])
    if job['team_attempt_id']:
        attempts=agents.tables(s)[2]
        attempt=s.execute(sa.select(attempts).where(attempts.c.id==job['team_attempt_id'])).mappings().first()
        if not attempt or attempt['status'] not in ('pending','running'): raise Conflict('این تلاش تیمی فعال نیست.')
        agent=agents.load(s,{'project_id':job['project_id'],'workspace_id':job['workspace_id']},attempt['agent_id'], _stage=True)
        from company_projects.stage_config import attempt_join
        attempt_join(s,agent,attempt)
        from company_projects.stages import validate_attempt
        validate_attempt(s,attempt)
    else:
        from company_projects.controller import visible_filters
        filters=visible_filters(s,job['workspace_id'],job['account_id'])
        if not filters or not s.scalar(sa.select(App.id).where(App.id==app.id,*filters)): raise Forbidden('مجوز برنامه لغو شده است.')
    for selected in job['snapshot']['models'].values():
        row=personal_models.load(s,job['account_id'],selected['id'])
        if row['revision']!=selected['revision']: raise Conflict('اتصال مدل تغییر کرده است؛ اجرای تازه بسازید.')
    from models.dataset import Dataset
    for spec in job['snapshot'].get('knowledge',{}).values():
        for item in spec['datasets']:
            dataset=s.get(Dataset,item['id'])
            if not dataset:raise Conflict('دانش حذف شده است.')
            check_dataset(s,dataset,job['account_id'],job['workspace_id'])
    return workflow

def finish(s,job,state,result):
    t=table(s,'local_executions'); now=agents.now()
    s.execute(t.update().where(t.c.id==job['id']).values(state=state,result=result,finished_at=now,lease_until=None))
    run=s.get(WorkflowRun,job['id'])
    if run:
        run.status='succeeded' if state=='succeeded' else 'stopped' if state in ('cancelled','interrupted') else 'failed'
        run.outputs=json.dumps(result.get('outputs',{}),ensure_ascii=False); run.error=result.get('error'); run.finished_at=utc_naive(now)
        run.elapsed_time=max(0,(now-job['started_at']).total_seconds()) if job.get('started_at') else 0
        run.total_steps=result.get('total_steps',0); run.total_tokens=result.get('total_tokens',0)
    from models.workflow import WorkflowNodeExecutionModel
    if state!='succeeded':
        for node in s.scalars(sa.select(WorkflowNodeExecutionModel).where(WorkflowNodeExecutionModel.workflow_run_id==job['id'],WorkflowNodeExecutionModel.status=='running')):
            node.status='failed';node.error=result.get('error','اجرای محلی متوقف شد.');node.finished_at=utc_naive(now)
    if job['snapshot'].get('preview'):
        from models.workflow import WorkflowNodeExecutionModel
        node_id=job['snapshot']['preview'];data=next(n['data'] for n in job['snapshot']['graph']['nodes'] if n['id']==node_id)
        s.add(WorkflowNodeExecutionModel(id=job['id'],tenant_id=job['workspace_id'],app_id=job['app_id'],workflow_id=job['workflow_id'],workflow_run_id=job['id'],triggered_from='single-step',index=1,node_execution_id=job['id'],node_id=node_id,node_type=data['type'],title=data.get('title',node_id),inputs=json.dumps(job['inputs'],ensure_ascii=False),process_data='{}',outputs=json.dumps(result.get('outputs',{}),ensure_ascii=False),status='succeeded' if state=='succeeded' else 'failed',error=result.get('error'),created_at=utc_naive(job['created_at']),created_by_role='account',created_by=job['account_id'],finished_at=utc_naive(now)))
    if job['team_attempt_id']:
        from company_projects.agent_execution import finish as finish_attempt
        mapped='succeeded' if state=='succeeded' else 'interrupted' if state in ('cancelled','interrupted') else 'failed'
        attempts=agents.tables(s)[2]
        pending=s.execute(sa.select(attempts).where(attempts.c.id==job['team_attempt_id'])).mappings().first()
        if pending and pending['status']=='pending':
            s.execute(attempts.update().where(attempts.c.id==pending['id'],attempts.c.status=='pending').values(status='blocked' if state=='blocked' else mapped,result=result,finished_at=now))
            from company_projects.stages import complete_attempt
            complete_attempt(s,pending['id'])
        else: finish_attempt(s,job['team_attempt_id'],mapped,result)
    if job.get('trigger_log_id'):
        from models.trigger import WorkflowTriggerLog
        log=s.get(WorkflowTriggerLog,job['trigger_log_id'])
        if log:
            log.workflow_run_id=job['id']; log.status='succeeded' if state=='succeeded' else 'failed'
            log.outputs=json.dumps(result.get('outputs',{}),ensure_ascii=False)
    return dict(recorded=True)

def expire(s):
    t=table(s,'local_executions'); now=agents.now()
    rows=s.execute(sa.select(t).where(t.c.state=='running',t.c.lease_until<now).with_for_update(skip_locked=True)).mappings().all()
    for row in rows: finish(s,dict(row),'interrupted',{'error':'ارتباط Runner قطع شد؛ برای جلوگیری از اجرای تکراری، ادامهٔ خودکار انجام نمی‌شود.'})

def claim(s,runner):
    from company_projects.harness import busy
    if busy(s,runner['id']):return dict(job=None)
    expire(s); cap=table(s,'runner_capabilities'); capabilities=s.execute(sa.select(cap).where(cap.c.device_id==str(runner['id']))).mappings().first()
    if not capabilities or capabilities['protocol']!=PROTOCOL: return dict(job=None)
    t=table(s,'local_executions')
    rpc=table(s,'local_rpc')
    if s.scalar(sa.select(rpc.c.id).where(rpc.c.device_id==str(runner['id']),rpc.c.state=='running').limit(1)):return dict(job=None)
    if s.scalar(sa.select(t.c.id).where(t.c.device_id==str(runner['id']),t.c.state=='running').limit(1)): return dict(job=None)
    rows=s.execute(sa.select(t).where(t.c.device_id==str(runner['id']),t.c.account_id==str(runner['account_id']),t.c.state=='pending').order_by(t.c.created_at).with_for_update(skip_locked=True).limit(20)).mappings().all()
    for original in rows:
        job=dict(original)
        if set(job['snapshot']['requirements'])-set(capabilities['capabilities']): continue
        try: validate_access(s,job)
        except (BadRequest,Forbidden,NotFound,Conflict):
            finish(s,job,'blocked',{'error':'مجوز، عضویت یا نسخهٔ اجرا تغییر کرده است.'}); continue
        now=agents.now(); s.execute(t.update().where(t.c.id==job['id']).values(state='running',started_at=now,lease_until=now+timedelta(seconds=90)))
        if job['team_attempt_id']:
            attempts=agents.tables(s)[2]; s.execute(attempts.update().where(attempts.c.id==job['team_attempt_id'],attempts.c.status=='pending').values(status='running',started_at=now))
        workflow=s.get(Workflow,job['workflow_id'])
        s.add(WorkflowRun(id=job['id'],tenant_id=job['workspace_id'],app_id=job['app_id'],workflow_id=workflow.id,type=workflow.type,triggered_from=job['snapshot'].get('triggered_from','app-run'),version=workflow.version,graph=json.dumps(job['snapshot']['graph'],ensure_ascii=False),inputs=json.dumps(job['inputs'],ensure_ascii=False),status='running',created_by_role='account',created_by=job['account_id'],created_at=utc_naive(now)))
        return dict(job=dict(id=job['id'],actor_id=job['account_id'],app_id=job['app_id'],workflow_id=job['workflow_id'],project_id=job['project_id'],source_job_id=job['source_job_id'],snapshot_digest=job['snapshot_digest'],inputs=job['inputs'],**job['snapshot']))
    return dict(job=None)

def running(s,runner,identity):
    expire(s); job=execution(s,identity,runner,lock=True)
    if job['state']!='running': raise Conflict('این اجرا فعال نیست؛ Runner باید متوقف شود.')
    validate_access(s,job); return job

def heartbeat(s,runner,identity):
    job=running(s,runner,identity); t=table(s,'local_executions'); s.execute(t.update().where(t.c.id==job['id']).values(lease_until=agents.now()+timedelta(seconds=90)))
    return dict(active=True)

def credentials(s,runner,identity):
    job=running(s,runner,identity)
    workflow=s.get(Workflow,job['workflow_id'])
    return dict(models={key: dict(**selected,credentials=personal_models.decrypt(personal_models.load(s,job['account_id'],selected['id']))) for key,selected in job['snapshot']['models'].items()},environment={v.name:v.value for v in workflow.environment_variables})

def events(s,runner,identity,data):
    agents.body(data,('sequence','event')); job=running(s,runner,identity)
    seq=data['sequence']; event=data['event']
    if type(seq) is not int or seq<1 or not isinstance(event,dict) or len(json.dumps(event,ensure_ascii=False).encode())>131072: raise BadRequest('رویداد اجرا معتبر نیست.')
    # Only bounded node status/output metadata, never arbitrary provider exceptions/credentials.
    if set(event)-{'event','node_id','title','node_type','status','outputs','elapsed_time','total_tokens'} or event.get('event') not in ('node_started','node_finished','text_chunk'): raise BadRequest('نوع رویداد مجاز نیست.')
    if str(event.get('node_id')) not in {str(n['id']) for n in job['snapshot']['graph']['nodes']}: raise BadRequest('گره در این اجرا وجود ندارد.')
    data=next(n['data'] for n in job['snapshot']['graph']['nodes'] if n['id']==event['node_id'])
    if event.get('node_type')!=data['type'] or event.get('status')!=('running' if event['event']=='node_started' else 'succeeded'):
        raise BadRequest('وضعیت یا نوع گره معتبر نیست.')
    if event['event']=='node_finished' and not isinstance(event.get('outputs'),dict):raise BadRequest('خروجی گره معتبر نیست.')
    digest=agents.digest(event); t=table(s,'local_execution_events')
    previous=s.execute(sa.select(t).where(t.c.execution_id==job['id'],t.c.sequence==seq)).mappings().first()
    if previous:
        if previous['digest']!=digest: raise Conflict('رویداد تکراری با محتوای متفاوت دریافت شد.')
        return dict(recorded=True,sequence=seq)
    if seq!=job['event_sequence']+1: raise Conflict('ترتیب رویداد معتبر نیست.')
    s.execute(t.insert().values(execution_id=job['id'],sequence=seq,event=event,digest=digest,created_at=agents.now()))
    # Native history records are metadata mirrors of the device events.
    if not job['snapshot'].get('preview'):
        from models.workflow import WorkflowNodeExecutionModel
        from uuid import UUID,uuid5
        node_identity=str(uuid5(UUID(str(job['id'])),event['node_id']))
        native=s.get(WorkflowNodeExecutionModel,node_identity)
        if event['event']=='node_started' and native is None:
            native=WorkflowNodeExecutionModel(id=node_identity,tenant_id=job['workspace_id'],app_id=job['app_id'],workflow_id=job['workflow_id'],workflow_run_id=job['id'],triggered_from='workflow-run',index=seq,node_execution_id=node_identity,node_id=event['node_id'],node_type=data['type'],title=data.get('title',event['node_id']),inputs='{}',process_data='{}',status='running',created_at=utc_naive(agents.now()),created_by_role='account',created_by=job['account_id'])
            s.add(native)
        elif event['event']=='node_finished':
            if native is None:raise Conflict('شروع گره ثبت نشده است.')
            native.status='succeeded';native.outputs=json.dumps(event['outputs'],ensure_ascii=False);native.elapsed_time=event.get('elapsed_time',0);native.finished_at=utc_naive(agents.now())

    jobs=table(s,'local_executions'); s.execute(jobs.update().where(jobs.c.id==job['id']).values(event_sequence=seq))
    return dict(recorded=True,sequence=seq)

def complete(s,runner,identity,data):
    agents.body(data,('state','outputs','error','total_steps','total_tokens','snapshot_digest'))
    job=execution(s,identity,runner,lock=True)
    if data['snapshot_digest']!=job['snapshot_digest']: raise Conflict('نسخهٔ نتیجه با اجرای واگذارشده یکسان نیست.')
    if data['state'] not in ('succeeded','failed') or not isinstance(data['outputs'],dict) or any(type(data[k]) is not int or not 0<=data[k]<=100000000 for k in ('total_steps','total_tokens')): raise BadRequest('نتیجهٔ اجرا معتبر نیست.')
    allowed_errors={'model_request_failed','code_failed','invalid_output','unsupported_definition','knowledge_failed','network_failed','execution_failed'}
    if data['state']=='failed' and data['error'] not in allowed_errors: raise BadRequest('کد خطا معتبر نیست.')
    if data['state']=='succeeded' and data['error'] is not None: raise BadRequest('خطا با وضعیت موفق سازگار نیست.')
    if len(json.dumps(data,ensure_ascii=False).encode())>1048576: raise BadRequest('حجم نتیجه بیش از حد مجاز است.')
    result=dict(outputs=data['outputs'],total_steps=data['total_steps'],total_tokens=data['total_tokens'])
    if data['error']: result['error']='اجرای محلی ناموفق بود: '+data['error']
    if job['state'] in TERMINAL:
        if job['state']==data['state'] and job['result']==result: return dict(recorded=True)
        raise Conflict('وضعیت نهایی اجرا قبلاً ثبت شده است.')
    running(s,runner,identity)
    if data['state']=='succeeded':
        from models.workflow import WorkflowNodeExecutionModel
        open_nodes=s.scalar(sa.select(sa.func.count()).select_from(WorkflowNodeExecutionModel).where(WorkflowNodeExecutionModel.workflow_run_id==job['id'],WorkflowNodeExecutionModel.status=='running'))
        if open_nodes:raise Conflict('پایان بعضی گره‌ها هنوز ثبت نشده است.')
    if job['team_attempt_id']:
        attempts=agents.tables(s)[2]
        attempt=s.execute(sa.select(attempts).where(attempts.c.id==job['team_attempt_id'])).mappings().one()
        agent=agents.load(s,{'project_id':job['project_id'],'workspace_id':job['workspace_id']},attempt['agent_id'], _stage=True)
        result['outputs']={k:v for k,v in result['outputs'].items() if k in agent['output_contract']}
    return finish(s,job,data['state'],result)

def cancel(s,project,workspace,actor,identity):
    team.scope(s,project,workspace,actor)
    try:job=execution(s,identity,actor=actor,lock=True)
    except NotFound:
        from company_projects import local_rpc
        job=local_rpc.load(s,identity,actor=actor,lock=True)
        if (job['project_id'],job['workspace_id'])!=(str(project),str(workspace)):raise NotFound('اجرا پیدا نشد.')
        if job['state'] not in TERMINAL:
            rpc=local_rpc.table(s);s.execute(rpc.update().where(rpc.c.id==job['id']).values(state='cancelled',finished_at=agents.now(),result={'error':'cancelled'}))
        return dict(cancelled=True)
    if (job['project_id'],job['workspace_id'])!=(str(project),str(workspace)): raise NotFound('اجرا پیدا نشد.')
    if job['state'] not in TERMINAL: finish(s,job,'cancelled',{'error':'اجرا به درخواست کاربر متوقف شد.'})
    return dict(cancelled=True)


def knowledge_signature(s,workspace,dataset_ids):
    """Hash content identities and visibility; exporting changed knowledge fails closed."""
    from models.dataset import Dataset, Document, DocumentSegment
    values=s.execute(sa.select(DocumentSegment.id,DocumentSegment.content,DocumentSegment.answer,DocumentSegment.dataset_id,DocumentSegment.document_id,Document.name).join(Document,Document.id==DocumentSegment.document_id).where(DocumentSegment.tenant_id==str(workspace),DocumentSegment.dataset_id.in_(dataset_ids),DocumentSegment.enabled.is_(True),DocumentSegment.status=='completed',Document.enabled.is_(True),Document.archived.is_(False),Document.indexing_status=='completed').order_by(DocumentSegment.id)).all()
    if len(values)>20000 or sum(len(r.content.encode()) for r in values)>33554432: raise BadRequest('دانش این اجرا بیش از بودجهٔ انتقال محلی است؛ مجموعهٔ دانش برنامه را محدود کنید.')
    segments=[dict(id=str(r.id),digest=agents.digest(list(r))) for r in values]
    return dict(digest=agents.digest(segments),segments=segments)


def knowledge_spec(s,workflow,actor,graph,models):
    from models.dataset import Dataset, DatasetPermission, DocumentSegment
    datasets={}
    for node in graph['nodes']:
        data=node['data']
        if data['type']!='knowledge-retrieval': continue
        selected=[]
        for identity in data.get('dataset_ids',[]):
            dataset=s.get(Dataset,source.uid(identity))
            if not dataset or dataset.tenant_id!=workflow.tenant_id: raise Forbidden('دانش برنامه متعلق به این پروژه نیست.')
            check_dataset(s,dataset,actor,workflow.tenant_id)
            if dataset.provider=='external': raise BadRequest('دانش خارجی به آداپتور محلی نیاز دارد؛ اجرای سروری مجاز نیست.')
            info=dict(id=dataset.id,name=dataset.name,technique=str(dataset.indexing_technique or 'economy'))
            exists=s.scalar(sa.select(DocumentSegment.id).where(DocumentSegment.dataset_id==dataset.id,DocumentSegment.enabled.is_(True),DocumentSegment.status=='completed').limit(1))
            if exists and str(dataset.indexing_technique)=='high_quality':
                row=personal_models.resolve(s,actor,dataset.embedding_model_provider,dataset.embedding_model,'text-embedding')
                key=node['id']+':embedding:'+dataset.id; models[key]=dict(id=str(row['id']),revision=row['revision'],provider=row['provider'],model_name=row['model_name'],model_type='text-embedding');info['embedding_key']=key
            selected.append(info)
        rerank=data.get('multiple_retrieval_config',{})
        if rerank.get('reranking_enable'):
            model=rerank.get('reranking_model',{})
            row=personal_models.resolve(s,actor,model.get('reranking_provider_name'),model.get('reranking_model_name'),'rerank')
            models[node['id']+':rerank']=dict(id=str(row['id']),revision=row['revision'],provider=row['provider'],model_name=row['model_name'],model_type='rerank')
        ids=[r['id'] for r in selected]
        datasets[node['id']]=dict(datasets=selected,**knowledge_signature(s,workflow.tenant_id,ids))
    return datasets


def check_dataset(s,dataset,actor,workspace):
    from models.dataset import DatasetPermission
    join=team.member(s,workspace,actor)
    if str(join.role)=='owner': return
    if str(dataset.permission)=='only_me' and dataset.maintainer!=str(actor): raise Forbidden('دسترسی به این دانش مجاز نیست.')
    if str(dataset.permission)=='partial_team' and dataset.maintainer!=str(actor) and not s.scalar(sa.select(DatasetPermission.id).where(DatasetPermission.dataset_id==dataset.id,DatasetPermission.account_id==str(actor),DatasetPermission.tenant_id==str(workspace)).limit(1)): raise Forbidden('دسترسی به این دانش مجاز نیست.')


def knowledge_page(s,runner,identity,data):
    from models.dataset import Dataset,Document,DocumentSegment
    agents.body(data,('node_id','cursor')); job=running(s,runner,identity)
    spec=job['snapshot'].get('knowledge',{}).get(data['node_id'])
    cursor=data['cursor']
    if spec is None or type(cursor) is not int or cursor<0 or cursor>20000: raise BadRequest('درخواست دانش معتبر نیست.')
    ids=[v['id'] for v in spec['datasets']]
    for identity in ids:
        dataset=s.get(Dataset,identity)
        if not dataset: raise Conflict('دانش تغییر کرده است.')
        check_dataset(s,dataset,job['account_id'],job['workspace_id'])
    frozen=spec['segments'][cursor:cursor+50]; frozen_ids=[v['id'] for v in frozen]; hashes={v['id']:v['digest'] for v in frozen}
    rows=s.execute(sa.select(DocumentSegment,Document.name).join(Document,Document.id==DocumentSegment.document_id).where(DocumentSegment.tenant_id==job['workspace_id'],DocumentSegment.dataset_id.in_(ids),DocumentSegment.id.in_(frozen_ids),DocumentSegment.enabled.is_(True),DocumentSegment.status=='completed',Document.enabled.is_(True),Document.archived.is_(False),Document.indexing_status=='completed').order_by(DocumentSegment.id)).all()
    if len(rows)!=len(frozen):raise Conflict('دسترسی یا نسخهٔ دانش تغییر کرده است.')
    names={v['id']:v['name'] for v in spec['datasets']}
    result=[]; size=0
    for segment,title in rows:
        if agents.digest([segment.id,segment.content,segment.answer,segment.dataset_id,segment.document_id,title])!=hashes[segment.id]:raise Conflict('محتوای دانش تغییر کرده است؛ اجرای تازه بسازید.')
        value=dict(id=segment.id,content=segment.content,answer=segment.answer,title=title,dataset_id=segment.dataset_id,dataset_name=names[segment.dataset_id],document_id=segment.document_id,position=segment.position)
        size+=len(json.dumps(value,ensure_ascii=False).encode())
        if size>1048576:
            if not result: raise BadRequest('قطعهٔ دانش برای انتقال محلی بیش از حد بزرگ است.')
            break
        result.append(value)
    return dict(data=result,next_cursor=cursor+len(result) if result and cursor+len(result)<len(spec['segments']) else None,datasets=spec['datasets'],digest=spec['digest'])


def revoke_device(s,device_id):
    t=table(s,'local_executions'); rows=s.execute(sa.select(t).where(t.c.device_id==str(device_id),t.c.state.in_(('pending','running'))).with_for_update()).mappings().all()
    for row in rows: finish(s,dict(row),'cancelled',{'error':'دسترسی Runner لغو شد.'})
    from company_projects.local_rpc import table as rpc_table
    rpc=rpc_table(s);s.execute(rpc.update().where(rpc.c.device_id==str(device_id),rpc.c.state.in_(('pending','running'))).values(state='cancelled',finished_at=agents.now(),result={'error':'device_revoked'}))
