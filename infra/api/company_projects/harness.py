"""Personal harness jobs: authorization, immutable context and human handoff only."""
import json
import re
from datetime import timedelta
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, HTTPException
from company_projects import agents, source_code as source, team, local_execution as local
from models.workflow import Workflow

ACTIVE=('pending','running','awaiting_user')
TERMINAL=('succeeded','failed','cancelled','interrupted','blocked')
KEY=re.compile(r'[a-z][a-z0-9_-]{0,63}')

def table(s,name='attempts'):
    cache=s.info.setdefault('company_harness_tables',{})
    if name not in cache:cache[name]=agents.reflected(s,'company_harness_'+name)
    return cache[name]
def is_attempt(s,identity): return s.scalar(sa.select(table(s).c.attempt_id).where(table(s).c.attempt_id==str(identity))) is not None

def load(s,identity,actor=None,runner=None,lock=False):
    t=table(s); q=sa.select(t).where(t.c.attempt_id==source.uid(identity))
    if actor: q=q.where(t.c.account_id==str(actor))
    if runner: q=q.where(t.c.device_id==str(runner['id']),t.c.account_id==str(runner['account_id']))
    row=s.execute(q.with_for_update() if lock else q).mappings().first()
    if not row: raise NotFound('تلاش هارنس در دسترس نیست.')
    return dict(row)

def compatible(s,agent):
    from company_projects.output_validation import definition
    workflow=s.get(Workflow,agent['workflow_id'])
    if not workflow or agents.fingerprint(workflow)!=agent['workflow_digest']: return 'نسخهٔ برنامه تغییر کرده است.'
    if definition(workflow): return 'این نسخه اعتبارسنج اختصاصی اجرای برنامه دارد؛ اتصال هارنس به قرارداد سازگار نیاز دارد.'
    return None

def policy(s,agent):
    t=table(s,'policies')
    row=s.execute(sa.select(t).where(t.c.agent_id==agent['id'],t.c.workflow_digest==agent['workflow_digest'])).mappings().first()
    return dict(row) if row else dict(revision=1,enabled=False,instructions='',requires_source=True)

def settings(s,project,workspace,actor,agent_id):
    key=team.scope(s,project,workspace,actor); agent=agents.load(s,key,agent_id)
    actions=agents.permissions(s,agent,actor)
    if not set(actions)&{'view','run','edit_definition','publish_definition'}: raise Forbidden('مجوز مشاهدهٔ تنظیم اجرا لازم است.')
    value=policy(s,agent); reason=compatible(s,agent)
    return dict(policy={k:value[k] for k in ('revision','enabled','instructions','requires_source')},compatible=reason is None,reason=reason,
                can_manage='publish_definition' in actions,output_contract=agent['output_contract'],workflow_digest=agent['workflow_digest'])

def save_policy(s,project,workspace,actor,agent_id,data):
    agents.body(data,('expected_revision','enabled','instructions','requires_source'))
    key=team.scope(s,project,workspace,actor); agent=agents.load(s,key,agent_id,lock=True)
    agents.require(s,agent,actor,'publish_definition')
    from company_projects.agent_execution import native_permission
    native_permission(s,agent['app_id'],actor,'publish_definition')
    old=policy(s,agent);source.check_revision(data,old)
    if type(data['enabled']) is not bool or type(data['requires_source']) is not bool or not isinstance(data['instructions'],str) or len(data['instructions'])>32000: raise BadRequest('تنظیم هارنس معتبر نیست.')
    if data['enabled'] and (not data['instructions'].strip() or compatible(s,agent)): raise BadRequest(compatible(s,agent) or 'مأموریت و معیار پذیرش هارنس را بنویسید.')
    t=table(s,'policies'); values=dict(agent_id=agent['id'],workflow_digest=agent['workflow_digest'],revision=old['revision']+1,enabled=data['enabled'],instructions=data['instructions'].strip(),requires_source=data['requires_source'],updated_by=str(actor),updated_at=agents.now())
    if 'agent_id' in old: s.execute(t.update().where(t.c.agent_id==agent['id'],t.c.workflow_digest==agent['workflow_digest']).values(**values))
    else:s.execute(t.insert().values(**values))
    return settings(s,project,workspace,actor,agent_id)

def profiles(s,actor):
    devices=source.devices(s,actor)['data']; t=table(s,'profiles')
    rows=s.execute(sa.select(t).where(t.c.device_id.in_([d['id'] for d in devices]))).mappings()
    grouped={}
    for row in rows: grouped.setdefault(str(row['device_id']),[]).append(dict(key=row['profile_key'],digest=row['digest'],**row['metadata']))
    return dict(devices=[dict(**d,harnesses=grouped.get(str(d['id']),[])) for d in devices if not d['revoked_at']])

def register(s,runner,data):
    agents.body(data,('profiles',))
    if not isinstance(data['profiles'],list) or len(data['profiles'])>10: raise BadRequest('فهرست هارنس معتبر نیست.')
    values=[]; keys=set()
    for p in data['profiles']:
        agents.body(p,('key','name','kind','version','digest'))
        if not isinstance(p['key'],str) or not KEY.fullmatch(p['key']) or p['key'] in keys or p['kind'] not in ('codex','opencode','custom') or not isinstance(p['digest'],str) or not re.fullmatch('[a-f0-9]{64}',p['digest']): raise BadRequest('پروفایل هارنس معتبر نیست.')
        keys.add(p['key']); name=source.name(p['name'])
        if not isinstance(p['version'],str) or len(p['version'])>120:raise BadRequest('نسخهٔ هارنس معتبر نیست.')
        values.append(dict(device_id=str(runner['id']),profile_key=p['key'],metadata=dict(name=name,kind=p['kind'],version=p['version']),digest=p['digest'],updated_at=agents.now()))
    t=table(s,'profiles');s.execute(t.delete().where(t.c.device_id==str(runner['id'])))
    if values:s.execute(t.insert(),values)
    return dict(registered=True)

def knowledge(s,workflow,actor):
    from models.dataset import Dataset,Document,DocumentSegment
    ids=sorted({source.uid(i) for n in workflow.graph_dict['nodes'] if n['data']['type']=='knowledge-retrieval' for i in n['data'].get('dataset_ids',[])})
    for identity in ids:
        dataset=s.get(Dataset,identity)
        if not dataset or dataset.tenant_id!=workflow.tenant_id or dataset.provider=='external':raise Forbidden('دانش مجاز پروژه برای هارنس لازم است.')
        local.check_dataset(s,dataset,actor,workflow.tenant_id)
    q=sa.select(DocumentSegment.id,DocumentSegment.content,DocumentSegment.answer,DocumentSegment.dataset_id,Document.name).join(Document,Document.id==DocumentSegment.document_id).where(DocumentSegment.tenant_id==workflow.tenant_id,DocumentSegment.dataset_id.in_(ids),DocumentSegment.enabled.is_(True),DocumentSegment.status=='completed',Document.enabled.is_(True),Document.archived.is_(False),Document.indexing_status=='completed').order_by(DocumentSegment.id)
    rows=[dict(r) for r in s.execute(q.limit(501)).mappings()]
    if len(rows)>500 or len(json.dumps(rows,default=str).encode())>2097152:raise BadRequest('دانش این برنامه برای بستهٔ هارنس بزرگ است؛ مجموعهٔ دانش را محدود کنید.')
    return [dict(id=str(r['id']),dataset_id=str(r['dataset_id']),name=r['name'],content=r['content'],answer=r['answer'],digest=agents.digest([r['content'],r['answer']])) for r in rows]

def create(s,attempt,agent,selection):
    agents.body(selection,('method','mode','device_id','source_job_id','profile_key'))
    if selection['method']!='harness' or selection['mode'] not in ('manual','managed'):raise BadRequest('روش اجرای تسک معتبر نیست.')
    actor=attempt['actor_id']; cfg=policy(s,agent);reason=compatible(s,agent)
    if not cfg['enabled'] or reason:raise Forbidden(reason or 'استفاده از هارنس برای این نسخه فعال نشده است.')
    device=source.device(s,actor,selection['device_id'],True); prepared=None
    if selection['source_job_id']:
        prepared=source.row(s,'jobs',selection['source_job_id'],{k:attempt[k] for k in ('project_id','workspace_id')}|dict(account_id=actor,device_id=str(device['id'])))
        if prepared['state']!='succeeded':raise BadRequest('سورس موفق روی همین دستگاه را انتخاب کنید.')
        source.validate_snapshot(s,prepared)
    if cfg['requires_source'] and not prepared:raise BadRequest('برای این مأموریت سورس آماده‌شده لازم است.')
    profile=None
    if selection['mode']=='managed':
        t=table(s,'profiles');profile=s.execute(sa.select(t).where(t.c.device_id==device['id'],t.c.profile_key==selection['profile_key'])).mappings().first()
        if not profile:raise BadRequest('هارنس ثبت‌شدهٔ همین دستگاه را انتخاب کنید.')
    elif selection['profile_key'] is not None:raise BadRequest('تحویل تعاملی پروفایل اجرایی خودکار ندارد.')
    workflow=s.get(Workflow,agent['workflow_id'])
    snapshot=dict(device_name=device['name'],harness_profile=dict(profile['metadata']) if profile else None,version=1,attempt_id=attempt['id'],agent_id=agent['id'],workflow_id=workflow.id,workflow_digest=agent['workflow_digest'],instructions=cfg['instructions'],requires_source=cfg['requires_source'],inputs=attempt['inputs'],output_contract=agent['output_contract'],knowledge=knowledge(s,workflow,actor),program_instructions=[n['data'].get('prompt_template',[]) for n in workflow.graph_dict['nodes'] if n['data']['type']=='llm'],source=dict(id=str(prepared['id']),**prepared['snapshot'],result=prepared['result']) if prepared else None)
    if len(json.dumps(snapshot,ensure_ascii=False).encode())>8388608:raise BadRequest('بستهٔ مأموریت بیش از حد بزرگ است.')
    now=agents.now();state='pending' if profile else 'awaiting_user'
    s.execute(table(s).insert().values(attempt_id=attempt['id'],**{k:attempt[k] for k in ('project_id','workspace_id')},account_id=actor,device_id=str(device['id']),source_job_id=str(prepared['id']) if prepared else None,mode=selection['mode'],profile_key=selection['profile_key'],profile_digest=profile['digest'] if profile else None,policy_revision=cfg['revision'],snapshot=snapshot,snapshot_digest=agents.digest(snapshot),state=state,created_at=now,updated_at=now))
    if not profile:
        native=agents.tables(s)[2]
        s.execute(native.update().where(native.c.id==attempt['id']).values(status='running',started_at=now))

def authorize(s,row):
    key=team.scope(s,row['project_id'],row['workspace_id'],row['account_id']);agent=agents.load(s,key,row['snapshot']['agent_id'])
    join=agents.require(s,agent,row['account_id'],'run');native=agents.tables(s)[2]
    attempt=s.execute(sa.select(native).where(native.c.id==row['attempt_id'])).mappings().one()
    if join.id!=attempt['membership_id'] or attempt['status'] not in ('pending','running') or agent['workflow_digest']!=row['snapshot']['workflow_digest']:raise Conflict('مجوز، عضویت یا نسخهٔ تلاش تغییر کرده است.')
    cfg=policy(s,agent)
    if not cfg['enabled'] or cfg['revision']!=row['policy_revision'] or compatible(s,agent):raise Conflict('قرارداد هارنس تغییر کرده است.')
    source.device(s,row['account_id'],row['device_id'])
    from company_projects.stages import validate_attempt
    validate_attempt(s,attempt)
    workflow=s.get(Workflow,agent['workflow_id'])
    if agents.digest(knowledge(s,workflow,row['account_id']))!=agents.digest(row['snapshot']['knowledge']):raise Conflict('دانش مأموریت تغییر کرده است؛ تلاش تازه بسازید.')
    if row['source_job_id']:
        prepared=source.row(s,'jobs',row['source_job_id'],key|dict(account_id=row['account_id'],device_id=row['device_id']))
        source.validate_snapshot(s,prepared)
    if row['mode']=='managed':
        t=table(s,'profiles');digest=s.scalar(sa.select(t.c.digest).where(t.c.device_id==row['device_id'],t.c.profile_key==row['profile_key']))
        if digest!=row['profile_digest']:raise Conflict('پروفایل محلی تغییر کرده است.')
    return dict(attempt)

def public(row):
    return {k:row[k] for k in ('attempt_id','mode','device_id','source_job_id','profile_key','state','snapshot_digest','prepared','result')} | dict(device_name=row['snapshot'].get('device_name',''),profile_name=(row['snapshot'].get('harness_profile') or {}).get('name'))

def console_detail(s,project,workspace,actor,agent_id,identity):
    from company_projects.agents import get_attempt
    get_attempt(s,project,workspace,actor,agent_id,identity)
    row=load(s,identity,actor=actor)
    return public(row)

def bundle(s,row):
    authorize(s,row)
    return dict(id=row['attempt_id'],snapshot_digest=row['snapshot_digest'],profile_key=row['profile_key'],profile_digest=row['profile_digest'],mode=row['mode'],**row['snapshot'])

def prepared(s,runner,identity,data):
    agents.body(data,('snapshot_digest',))
    row=load(s,identity,runner=runner,lock=True);authorize(s,row)
    if row['state'] not in ('running','awaiting_user') or row['snapshot_digest']!=data['snapshot_digest']:raise Conflict('تلاش آماده‌سازی فعال نیست.')
    value=dict(snapshot_digest=data['snapshot_digest'],directory=str(row['attempt_id']))
    s.execute(table(s).update().where(table(s).c.attempt_id==row['attempt_id']).values(prepared=value,updated_at=agents.now()))
    return dict(recorded=True)

def validate_result(row,outputs,evidence):
    from company_projects.stages import validate_output
    validate_output(dict(output_contract=row['snapshot']['output_contract']),outputs)
    agents.body(evidence,('summary','changes','tests','references','diff'))
    if not isinstance(evidence['summary'],str) or not evidence['summary'].strip() or len(evidence['summary'])>8000 or not isinstance(evidence['diff'],str) or len(evidence['diff'])>131072:raise BadRequest('خلاصه یا diff معتبر نیست.')
    if not isinstance(evidence['changes'],list) or len(evidence['changes'])>500 or any(not isinstance(v,str) or len(v)>512 for v in evidence['changes']):raise BadRequest('فهرست تغییرات معتبر نیست.')
    agents.body(evidence['tests'],('status','summary'))
    if evidence['tests']['status'] not in ('not_run','passed','failed','mixed') or not isinstance(evidence['tests']['summary'],str) or len(evidence['tests']['summary'])>8000:raise BadRequest('وضعیت واقعی تست را مشخص کنید.')
    if not isinstance(evidence['references'],list) or len(evidence['references'])>20 or any(not isinstance(v,str) or len(v)>2000 for v in evidence['references']):raise BadRequest('مراجع نتیجه معتبر نیست.')
    if len(json.dumps(dict(outputs=outputs,evidence=evidence),ensure_ascii=False).encode())>524288:raise BadRequest('نتیجه بیش از حد مجاز است.')
    if row['snapshot']['requires_source'] and not row['prepared']:raise Conflict('ابتدا پوشهٔ مستقل این تسک را روی دستگاه آماده کنید.')

def finish(s,row,state,result,completion_digest=None):
    from models.account import Tenant
    s.scalar(sa.select(Tenant).where(Tenant.id==row['workspace_id']).with_for_update())
    if state=='succeeded':authorize(s,row)
    native=agents.tables(s)[2]; status='succeeded' if state=='succeeded' else 'interrupted' if state in ('interrupted','cancelled') else 'blocked' if state=='blocked' else 'failed'
    s.execute(table(s).update().where(table(s).c.attempt_id==row['attempt_id']).values(state=state,result=result,completion_digest=completion_digest,lease_until=None,updated_at=agents.now()))
    updated=s.execute(native.update().where(native.c.id==row['attempt_id'],native.c.status.in_(('pending','running'))).values(status=status,result=result,finished_at=agents.now()))
    if state=='succeeded' and updated.rowcount!=1:raise Conflict('تلاش قبلاً متوقف شده است؛ نتیجهٔ دیررس پذیرفته نیست.')
    from company_projects.stages import complete_attempt
    complete_attempt(s,row['attempt_id'])
    return dict(recorded=True)

def submit(s,row,data,*,observed=False):
    agents.body(data,('snapshot_digest','outputs','evidence','session_id'))
    if data['snapshot_digest']!=row['snapshot_digest']:raise Conflict('نسخهٔ بستهٔ نتیجه یکسان نیست.')
    if data['session_id'] is not None and (not isinstance(data['session_id'],str) or len(data['session_id'])>200):raise BadRequest('شناسهٔ جلسه معتبر نیست.')
    digest=agents.digest(data)
    if row['state'] in TERMINAL:
        if row['state']=='succeeded' and row['completion_digest']==digest:return dict(recorded=True)
        raise Conflict('نتیجهٔ نهایی قبلاً ثبت شده است.')
    authorize(s,row)
    if row['state'] not in ('awaiting_user','running') or (observed and row['mode']!='managed') or (not observed and row['mode']!='manual'):raise Conflict('تلاش قابل تحویل نیست.')
    validate_result(row,data['outputs'],data['evidence'])
    result=dict(outputs=data['outputs'],evidence=data['evidence'],origin='managed_harness' if observed else 'user_submission',session_id=data['session_id'],snapshot_digest=row['snapshot_digest'])
    return finish(s,row,'succeeded',result,digest)

def expire(s):
    t=table(s);native=agents.tables(s)[2]
    for value in s.execute(sa.select(t,native.c.status.label('native_status')).join(native,native.c.id==t.c.attempt_id).where(t.c.state.in_(ACTIVE))).mappings():
        row=dict(value)
        if row['native_status'] not in ('pending','running'):finish(s,row,'interrupted',{'error':'تلاش متوقف شده است.'})
        elif row['state']=='running' and row['lease_until'] and row['lease_until']<agents.now():finish(s,row,'interrupted',{'error':'ارتباط Runner قطع شد؛ اجرای مجدد نیازمند اقدام صریح است.'})

def claim(s,runner):
    expire(s);t=table(s)
    for name in ('local_executions','local_rpc'):
        q=local.table(s,name)
        if s.scalar(sa.select(q.c.id).where(q.c.device_id==runner['id'],q.c.state=='running').limit(1)):return dict(job=None)
    q=source.table(s,'jobs')
    if s.scalar(sa.select(q.c.id).where(q.c.device_id==runner['id'],q.c.state=='running').limit(1)) or busy(s,runner['id']):return dict(job=None)
    for value in s.execute(sa.select(t).where(t.c.device_id==runner['id'],t.c.account_id==runner['account_id'],t.c.state=='pending',t.c.mode=='managed').order_by(t.c.created_at).with_for_update(skip_locked=True).limit(10)).mappings():
        row=dict(value)
        try:
            authorize(s,row)
            from company_projects.agent_execution import claim as native_claim
            if not native_claim(s,row['attempt_id']):continue
        except HTTPException:
            finish(s,row,'blocked',{'error':'مجوز یا قرارداد هارنس تغییر کرده است.'});continue
        s.execute(t.update().where(t.c.attempt_id==row['attempt_id']).values(state='running',lease_until=agents.now()+timedelta(seconds=90),updated_at=agents.now()))
        return dict(job=bundle(s,row))
    return dict(job=None)

def busy(s,device_id):
    t=table(s);return s.scalar(sa.select(t.c.attempt_id).where(t.c.device_id==str(device_id),t.c.state=='running').limit(1)) is not None

def heartbeat(s,runner,identity):
    expire(s);row=load(s,identity,runner=runner,lock=True)
    if row['state']!='running':raise Conflict('هارنس باید متوقف شود.')
    authorize(s,row);s.execute(table(s).update().where(table(s).c.attempt_id==row['attempt_id']).values(lease_until=agents.now()+timedelta(seconds=90)))
    return dict(active=True)

def complete(s,runner,identity,data):
    row=load(s,identity,runner=runner,lock=True)
    if row['state']=='running':heartbeat(s,runner,identity)
    return submit(s,row,data,observed=True)

def fail(s,runner,identity,data):
    agents.body(data,('snapshot_digest','error'))
    row=load(s,identity,runner=runner,lock=True)
    if data['snapshot_digest']!=row['snapshot_digest'] or data['error'] not in ('harness_failed','invalid_result','interaction_required','workspace_failed'):raise BadRequest('گزارش خطا معتبر نیست.')
    result={'error':'اجرای هارنس ناموفق بود: '+data['error']}
    if row['state']=='failed' and row['result']==result:return dict(recorded=True)
    if row['state'] not in ACTIVE:raise Conflict('تلاش پایان یافته است.')
    return finish(s,row,'failed',result)

def revoke_device(s,identity):
    t=table(s)
    for row in s.execute(sa.select(t).where(t.c.device_id==str(identity),t.c.state.in_(ACTIVE))).mappings():finish(s,dict(row),'cancelled',{'error':'دسترسی دستگاه لغو شد.'})

def validate_artifact(s,stage,selected,content):
    from company_projects.stages import validate_output
    row=load(s,selected['attempt_id']);native=agents.tables(s)[2]
    attempt=s.execute(sa.select(native).where(native.c.id==row['attempt_id'])).mappings().one()
    from company_projects import stages
    bridge=stages.tables(s)[2]
    link=s.execute(sa.select(bridge).where(bridge.c.attempt_id==row['attempt_id'],bridge.c.stage_id==stage['id'])).mappings().first()
    agent=agents.load(s,{k:stage[k] for k in ('project_id','workspace_id')},stage['binding']['agent_id'])
    if row['state']!='succeeded' or attempt['status']!='succeeded' or not link or link['round']!=stage['round'] or link['input_digest']!=stage['input_digest'] or stage['inputs']!=row['snapshot']['inputs'] or compatible(s,agent):raise Conflict('منشأ خروجی هارنس با مرحله یکسان نیست.')
    validate_output(stage['binding'],content)
    return content,dict(kind='harness',attempt_id=row['attempt_id'],artifact_id=selected['id'],snapshot_digest=row['snapshot_digest'],input_digest=stage['input_digest'],content_digest=agents.digest(content),outcome='structural_passed',origin=row['result']['origin'])

def bind_stage(s,identity,stage,instance,input_digest,dependencies):
    if not is_attempt(s,identity):return
    row=load(s,identity);snapshot=dict(row['snapshot'],stage_context=dict(instance_id=instance['id'],stage_id=stage['id'],round=stage['round'],input_digest=input_digest,request_id=instance['request_id'],request_revision_id=instance['request_revision_id'],flow_version_id=instance['flow_version_id'],dependencies=dependencies))
    s.execute(table(s).update().where(table(s).c.attempt_id==str(identity)).values(snapshot=snapshot,snapshot_digest=agents.digest(snapshot)))

def stage_info(s,stage,actor):
    from company_projects import stages
    bridge=stages.tables(s)[2];t=table(s)
    row=s.execute(sa.select(t).join(bridge,bridge.c.attempt_id==t.c.attempt_id).where(bridge.c.stage_id==stage['id'],bridge.c.round==stage['round']).order_by(t.c.created_at.desc()).limit(1)).mappings().first()
    if not row:return None
    mine=str(actor)==str(row['account_id']);actions=[]
    if mine and row['state'] in ACTIVE:
        try:stages.require(s,{k:stage[k] for k in ('project_id','workspace_id')},stage,actor,'run');actions=['cancel']+(['submit','bundle'] if row['mode']=='manual' else [])
        except HTTPException:pass
    can_continue=False
    if 'submit' in actions:
        try:
            stages.require(s,{k:stage[k] for k in ('project_id','workspace_id')},stage,actor,'finalize')
            stages.require(s,{k:stage[k] for k in ('project_id','workspace_id')},stage,actor,'feedback');can_continue=True
        except HTTPException:pass
    return dict(**public(row),actions=actions,can_continue=can_continue)

def stage_submit(s,project,workspace,actor,instance_id,stage_id,data,key):
    from company_projects import stages
    agents.body(data,('expected_revision','attempt_id','snapshot_digest','outputs','evidence','session_id','continue_flow','reason'))
    scope=stages.scoped(s,project,workspace,actor,write=True);instance=stages.instance(s,scope,instance_id)
    stage=stages.load(s,stages.tables(s)[1],scope,stage_id,lock=True)
    if stage['instance_id']!=str(instance_id):raise NotFound('مرحله در این اجرا نیست.')
    stages.require(s,scope,stage,actor,'run');stages.intake(s,instance)
    digest=agents.digest(dict(operation='harness.submit',stage_id=str(stage_id),data=data))
    replay=agents.replay(s,scope,actor,agents.action_key(key),digest)
    if replay:return replay
    if stage['revision']!=agents.revision(data['expected_revision']) or stage['active_attempt_id']!=str(data['attempt_id']) or stage['state']!='running':raise Conflict('این تلاش متعلق به وضعیت فعال مرحله نیست.')
    if type(data['continue_flow']) is not bool:raise BadRequest('روش تحویل معتبر نیست.')
    if data['continue_flow']:
        stages.require(s,scope,stage,actor,'finalize');stages.require(s,scope,stage,actor,'feedback')
        if not isinstance(data['reason'],str) or not data['reason'].strip() or len(data['reason'])>2000:raise BadRequest('علت تحویل و ادامه لازم است.')
    row=load(s,data['attempt_id'],actor=actor,lock=True)
    submit(s,row,{k:data[k] for k in ('snapshot_digest','outputs','evidence','session_id')})
    result=stages.get_stage(s,project,workspace,actor,instance_id,stage_id)
    if data['continue_flow']:
        artifact=result['artifacts'][0]
        from uuid import uuid4
        result=stages.mutate(s,project,workspace,actor,instance_id,stage_id,'request_decision',dict(expected_revision=result['revision'],artifact_id=artifact['id']),str(uuid4()))
        result=stages.mutate(s,project,workspace,actor,instance_id,stage_id,'finalize',dict(expected_revision=result['revision'],artifact_id=artifact['id'],reason=data['reason']),str(uuid4()))
    agents.event(s,scope,actor,key,digest,'harness.submitted',result)
    return result

def cancel_console(s,project,workspace,actor,agent_id,identity):
    console_detail(s,project,workspace,actor,agent_id,identity);row=load(s,identity,actor=actor,lock=True)
    if row['state'] in ACTIVE:
        finish(s,row,'cancelled',{'error':'تلاش به درخواست مجری متوقف شد.'})
    return dict(cancelled=True)
