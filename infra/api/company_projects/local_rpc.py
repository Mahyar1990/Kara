"""Scoped local calls for model validation, indexing and connection requests; no server I/O."""
import json
import time
from datetime import timedelta
from uuid import uuid4
import sqlalchemy as sa
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadGateway,BadRequest,Conflict,Forbidden,NotFound,ServiceUnavailable
from extensions.ext_database import db
from company_projects import agents,local_execution as local,personal_models,source_code as source,team

MODEL_METHODS={'invoke_llm','invoke_text_embedding','invoke_rerank','get_llm_num_tokens','get_text_embedding_num_tokens','validate_model_credentials','validate_provider_credentials'}

def table(s):return local.table(s,'local_rpc')
def plain(value):
    if hasattr(value,'model_dump'):return value.model_dump(mode='json')
    if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [plain(v) for v in value]
    return value

def enqueue(s,workspace,actor,method,payload,kind=None,connection=None):
    key=local.project_key(s,workspace,actor); join=team.member(s,workspace,actor); chosen=local.binding(s,key['project_id'],workspace,actor)
    if len(json.dumps(payload,ensure_ascii=False).encode())>2097152:raise BadRequest('درخواست محلی بیش از حد بزرگ است.')
    row=dict(id=str(uuid4()),**key,account_id=str(actor),membership_id=join.id,device_id=chosen['device_id'] if chosen else None,method=method,connection_kind=kind,connection_id=connection['id'] if connection else None,connection_revision=connection['revision'] if connection else None,payload=payload,state='pending',created_at=agents.now())
    s.execute(table(s).insert().values(**row));return row

def wait(identity,actor):
    deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        with Session(db.engine) as s,s.begin():
            expire(s); row=load(s,identity,actor=actor)
            team.scope(s,row['project_id'],row['workspace_id'],actor)
        if row['state']=='succeeded':return row['result']['value']
        if row['state'] in ('failed','cancelled','interrupted'):raise BadGateway('فراخوانی روی Runner انجام نشد؛ دستگاه، شبکه و اتصال شخصی را بررسی کنید.')
        time.sleep(1)
    raise ServiceUnavailable('درخواست منتظر Runner است؛ دستگاه مقصد پروژه را در تنظیمات Runner انتخاب و اجرا کنید. شناسه: '+str(identity))

def model_call(method,arguments):
    if method not in MODEL_METHODS:raise Forbidden('این نوع فراخوانی مدل در Runner فعلی پشتیبانی نشده است؛ اجرای سروری مسدود است.')
    from company_projects.personal_model_runtime import require_actor,_validation
    from company_projects.model_client_boundary import MODEL_METHODS as TYPES
    actor=require_actor(arguments['tenant_id'],arguments.get('user_id'))
    with Session(db.engine) as s,s.begin():
        if method.startswith('validate_') and _validation.get(): connection=personal_models.load(s,actor,_validation.get())
        else:connection=personal_models.resolve(s,actor,arguments['plugin_id']+'/'+arguments['provider'],arguments['model'],arguments.get('model_type') or TYPES[method])
        payload={k:plain(v) for k,v in arguments.items() if k in ('model','prompt_messages','model_parameters','tools','stop','texts','input_type','query','docs','top_n','score_threshold')}
        job=enqueue(s,arguments['tenant_id'],actor,method,payload,'model',connection)
    value=wait(job['id'],actor)
    if method=='invoke_llm':
        from graphon.model_runtime.entities.llm_entities import LLMResultChunk
        return [LLMResultChunk.model_validate(v) for v in value]
    if method=='invoke_text_embedding':
        from graphon.model_runtime.entities.text_embedding_entities import EmbeddingResult
        return EmbeddingResult.model_validate(value)
    if method=='invoke_rerank':
        from graphon.model_runtime.entities.rerank_entities import RerankResult
        return RerankResult.model_validate(value)
    return value

def connection_request(kind,row,path,body=None):
    # Callers supply a fixed endpoint and the already account-scoped connection.
    from company_projects.personal_model_runtime import require_actor
    from company_projects.controller import identity
    actor,workspace=identity();require_actor(workspace,actor.id)
    if str(row['account_id'])!=str(actor.id):raise Forbidden('اتصال متعلق به کاربر اجراکننده نیست.')
    allowed={'jira':{'/rest/api/2/search','/rest/api/2/myself'},'gitlab':{'/api/v4/user'}}
    if path not in allowed.get(kind,set()):raise Forbidden('مسیر اتصال مجاز نیست.')
    with Session(db.engine) as s,s.begin():job=enqueue(s,workspace,actor.id,'connection-http',dict(path=path,body=body),'jira' if kind=='jira' else 'gitlab',row)
    result=wait(job['id'],actor.id)
    if result.get('status')!=200:raise BadGateway('سرویس اتصال پاسخ HTTP '+str(result.get('status'))+' داد؛ تنظیمات و مجوز خودتان را بررسی کنید.')
    if not isinstance(result.get('body'),dict):raise BadGateway('پاسخ سرویس JSON معتبر نیست.')
    return result['body']

def raw_code(language,preload,code):
    from company_projects.personal_model_runtime import require_actor
    from company_projects.controller import identity
    actor,workspace=identity();require_actor(workspace,actor.id)
    with Session(db.engine) as s,s.begin():job=enqueue(s,workspace,actor.id,'raw-code',dict(language='python3' if str(language)=='jinja2' else str(language),preload=preload,code=code))
    return wait(job['id'],actor.id)

def load(s,identity,runner=None,actor=None,lock=False):
    t=table(s);q=sa.select(t).where(t.c.id==source.uid(identity))
    if runner:q=q.where(t.c.device_id==str(runner['id']),t.c.account_id==str(runner['account_id']))
    if actor:q=q.where(t.c.account_id==str(actor))
    row=s.execute(q.with_for_update() if lock else q).mappings().first()
    if not row:raise NotFound('درخواست محلی پیدا نشد.')
    return dict(row)

def access(s,row):
    team.scope(s,row['project_id'],row['workspace_id'],row['account_id'])
    if str(team.member(s,row['workspace_id'],row['account_id']).id)!=str(row['membership_id']):raise Forbidden('عضویت اجرا تغییر کرده است.')
    if row['method']=='workflow-node':
        from company_projects.node_routing import parent
        parent(s,row)
    if not row['connection_id']:return None
    if row['connection_kind']=='model':connection=personal_models.load(s,row['account_id'],row['connection_id'])
    else:
        from company_projects import jira_connections,gitlab_connections
        service=jira_connections if row['connection_kind']=='jira' else gitlab_connections
        connection=service.load(s,row['account_id'],row['connection_id'])
    if connection['revision']!=row['connection_revision']:raise Conflict('اتصال درخواست تغییر کرده است.')
    return connection

def expire(s):
    t=table(s);now=agents.now()
    s.execute(t.update().where(t.c.state=='running',t.c.lease_until<now).values(state='interrupted',finished_at=now,result={'error':'runner_disconnected'}))

def claim(s,runner):
    from company_projects.harness import busy
    if busy(s,runner['id']):return dict(job=None)
    expire(s);cap=local.table(s,'runner_capabilities');current=s.execute(sa.select(cap).where(cap.c.device_id==str(runner['id']))).mappings().first()
    if not current or current['protocol']!=2:return dict(job=None)
    t=table(s)
    jobs=local.table(s,'local_executions')
    if s.scalar(sa.select(jobs.c.id).where(jobs.c.device_id==str(runner['id']),jobs.c.state=='running').limit(1)):return dict(job=None)
    if s.scalar(sa.select(t.c.id).where(t.c.device_id==str(runner['id']),t.c.state=='running').limit(1)):return dict(job=None)
    rows=s.execute(sa.select(t).where(t.c.device_id==str(runner['id']),t.c.account_id==str(runner['account_id']),t.c.state=='pending').order_by(t.c.created_at).with_for_update(skip_locked=True).limit(20)).mappings().all()
    for original in rows:
        row=dict(original)
        if row['method']=='workflow-node' and 'node-routing-v1' not in current['capabilities']:continue
        if row['method']=='raw-code' and row['payload']['language'] not in current['capabilities']:continue
        try:access(s,row)
        except (Forbidden,Conflict,NotFound):
            s.execute(t.update().where(t.c.id==row['id']).values(state='failed',finished_at=agents.now(),result={'error':'access_changed'}));continue
        now=agents.now();s.execute(t.update().where(t.c.id==row['id']).values(state='running',started_at=now,lease_until=now+timedelta(seconds=90)))
        job=dict(id=row['id'],kind='rpc',method=row['method'],payload=row['payload'],project_id=row['project_id'])
        if row['method']=='workflow-node':
            from company_projects.node_routing import claim_payload
            job.update(claim_payload(s,row))
        return dict(job=job)
    return dict(job=None)

def running(s,runner,identity):
    expire(s);row=load(s,identity,runner,lock=True)
    if row['state']!='running':raise Conflict('این درخواست فعال نیست.')
    access(s,row);return row

def credentials(s,runner,identity):
    row=running(s,runner,identity);connection=access(s,row)
    if row['method']=='workflow-node':
        from company_projects.node_routing import secrets
        return secrets(s,row)
    if not connection:return dict(connection=None)
    if row['connection_kind']=='model':return dict(connection=dict(id=str(connection['id']),revision=connection['revision'],provider=connection['provider'],model_name=connection['model_name'],model_type=connection['model_type'],credentials=personal_models.decrypt(connection)))
    from company_projects import jira_connections,gitlab_connections
    service=jira_connections if row['connection_kind']=='jira' else gitlab_connections
    return dict(connection=dict(kind=row['connection_kind'],base_url=connection['base_url'],token=service.decrypt(connection)))

def heartbeat(s,runner,identity):
    row=running(s,runner,identity);t=table(s);s.execute(t.update().where(t.c.id==row['id']).values(lease_until=agents.now()+timedelta(seconds=90)));return dict(active=True)

def complete(s,runner,identity,data):
    agents.body(data,('state','value','error'));row=load(s,identity,runner,lock=True)
    if data['state'] not in ('succeeded','failed') or data['error'] not in (None,'execution_failed','model_request_failed','unsupported_definition','code_failed','network_failed','invalid_output','knowledge_failed'):raise BadRequest('نتیجهٔ درخواست معتبر نیست.')
    if row['method']=='workflow-node' and data['state']=='succeeded':
        value=data['value']
        if data['error'] is not None or not isinstance(value,dict) or set(value)!={'output','branch','total_tokens'} or not isinstance(value['output'],dict) or value['branch'] is not None or type(value['total_tokens']) is not int or not 0<=value['total_tokens']<=100000000:
            raise BadRequest('نتیجهٔ گام معتبر نیست.')
    if len(json.dumps(data,ensure_ascii=False).encode())>16777216:raise BadRequest('حجم نتیجه بیش از حد مجاز است.')
    if row['state'] in ('succeeded','failed'):
        if row['state']==data['state'] and row['result']==dict(value=data['value'],error=data['error']):return dict(recorded=True)
        raise Conflict('نتیجهٔ نهایی قبلاً ثبت شده است.')
    running(s,runner,identity);t=table(s);s.execute(t.update().where(t.c.id==row['id']).values(state=data['state'],result=dict(value=data['value'],error=data['error']),finished_at=agents.now(),lease_until=None));return dict(recorded=True)
