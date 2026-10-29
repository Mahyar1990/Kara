"""Project repository metadata and personal local workspaces, isolated from programs."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from uuid import uuid4
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, Unauthorized
from company_projects import agents, team, access, gitlab_connections as gitlab
from kara_source_runner import contracts

ACTIVE = ('pending', 'running')

def table(s, name): return agents.reflected(s, 'company_source_' + name)
def uid(value): return str(agents.store.uid(value))
def scope(s, project, workspace, actor): return team.scope(s, project, workspace, actor)
def name(value):
    if not isinstance(value, str) or not value.strip() or len(value)>120: raise BadRequest('نام باید بین ۱ تا ۱۲۰ نویسه باشد.')
    return value.strip()
def validated(fn, *args):
    try: return fn(*args)
    except ValueError as exc: raise BadRequest('اطلاعات سورس کد معتبر نیست: ' + str(exc)) from None

def row(s, kind, row_id, key, *, lock=False, live=True):
    t=table(s,kind); q=sa.select(t).where(t.c.id==uid(row_id), *(t.c[k]==str(v) for k,v in key.items()))
    if live and 'deleted_at' in t.c: q=q.where(t.c.deleted_at.is_(None))
    found=s.execute(q.with_for_update() if lock else q).mappings().first()
    if found is None: raise NotFound('مورد در محدودهٔ دسترسی شما پیدا نشد.')
    return dict(found)

def public(value):
    return {k: v.isoformat() if hasattr(v,'isoformat') else v for k,v in value.items() if k not in ('secret_hash','code_hash','definition','snapshot','deleted_at')}

def check_revision(data, old):
    if agents.revision(data['expected_revision']) != (old['revision'] if old else 1): raise Conflict('اطلاعات تغییر کرده است؛ فهرست را تازه کنید.')

def save_repository(s, project, workspace, actor, data, entity_id=None):
    agents.body(data, ('name','url','branch','expected_revision'))
    key=scope(s,project,workspace,actor); t=table(s,'repositories')
    old=row(s,'repositories',entity_id,key,lock=True) if entity_id else None
    if old and str(old['created_by'])!=str(actor) and not access.can_manage_members(s,workspace,actor): raise Forbidden('ویرایش مخزن فقط با سازنده یا مدیر پروژه است.')
    check_revision(data,old); now=agents.now()
    values=dict(name=name(data['name']),url=validated(contracts.repository_url,data['url']),branch=validated(contracts.branch_name,data['branch']),revision=old['revision']+1 if old else 1,updated_at=now)
    if old: s.execute(t.update().where(t.c.id==old['id']).values(**values))
    else:
        old=dict(id=str(uuid4()),**key,created_by=str(actor),created_at=now,deleted_at=None)
        s.execute(t.insert().values(**old,**values))
    return public(old|values)

def definition(s,key,actor,data):
    components,docs=data['components'],data['documents']
    validated(contracts.workspace_files,components,docs)
    result=[]
    for part in components:
        agents.body(part,('key','path','repository_id','connection_id'))
        repo=row(s,'repositories',part['repository_id'],key)
        connection=gitlab.load(s,actor,part['connection_id'])
        validated(contracts.repository_on_connection,repo['url'],connection['base_url'])
        result.append(dict(key=part['key'],path=part['path'],repository_id=str(repo['id']),repository_revision=repo['revision'],url=repo['url'],branch=repo['branch'],connection_id=str(connection['id']),connection_revision=connection['revision']))
    return dict(components=result,documents=docs)

def save_workspace(s,project,workspace,actor,data,entity_id=None):
    agents.body(data,('name','components','documents','expected_revision'))
    key=scope(s,project,workspace,actor); own=key|dict(account_id=str(actor)); t=table(s,'workspaces')
    old=row(s,'workspaces',entity_id,own,lock=True) if entity_id else None
    check_revision(data,old)
    if old: no_active(s,old['id'])
    values=dict(name=name(data['name']),definition=definition(s,key,actor,data),revision=old['revision']+1 if old else 1,updated_at=agents.now())
    if old: s.execute(t.update().where(t.c.id==old['id']).values(**values))
    else:
        old=dict(id=str(uuid4()),**own,created_at=agents.now(),deleted_at=None)
        s.execute(t.insert().values(**old,**values))
    return public(old|values)|dict(**values['definition'])

def expire(s):
    t=table(s,'jobs'); now=agents.now()
    s.execute(t.update().where(t.c.state=='running',t.c.lease_until<now).values(state='interrupted',finished_at=now,result={'error':'runner_disconnected'}))

def no_active(s,workspace_id):
    expire(s); t=table(s,'jobs')
    if s.scalar(sa.select(t.c.id).where(t.c.source_workspace_id==workspace_id,t.c.state.in_(ACTIVE)).limit(1)): raise Conflict('ابتدا آماده‌سازی در حال اجرا را لغو کنید.')

def listing(s,project,workspace,actor):
    key=scope(s,project,workspace,actor); expire(s)
    def query(kind,private=False):
        t=table(s,kind); q=sa.select(t).where(*(t.c[k]==v for k,v in key.items()))
        if private: q=q.where(t.c.account_id==str(actor))
        if 'deleted_at' in t.c: q=q.where(t.c.deleted_at.is_(None))
        return [dict(r) for r in s.execute(q.order_by(t.c.created_at.desc()).limit(100)).mappings()]
    # Keep the current preparation for every workspace/device visible even when
    # unrelated jobs have pushed it outside the bounded history window.
    t=table(s,'jobs'); job_key=key|dict(account_id=str(actor))
    latest=s.execute(sa.select(t).where(*(t.c[k]==v for k,v in job_key.items()),sa.or_(t.c.state=='succeeded',t.c.snapshot['update_of'].as_string().is_not(None))).distinct(t.c.source_workspace_id,t.c.device_id).order_by(t.c.source_workspace_id,t.c.device_id,t.c.created_at.desc(),t.c.id.desc())).mappings()
    jobs={str(r['id']):dict(r) for r in query('jobs',True)}
    jobs.update({str(r['id']):dict(r) for r in latest})
    return dict(repositories=[public(r)|dict(can_edit=str(r['created_by'])==str(actor) or access.can_manage_members(s,workspace,actor)) for r in query('repositories')],
        workspaces=[public(r)|r['definition'] for r in query('workspaces',True)], jobs=[public(r)|dict(snapshot_revision=r['snapshot']['revision'],update_of=r['snapshot'].get('update_of'),local_directory=directory(r)) for r in sorted(jobs.values(),key=lambda r:(r['created_at'],str(r['id'])),reverse=True)])

def retire(s,project,workspace,actor,kind,entity_id,data):
    agents.body(data,('expected_revision',))
    key=scope(s,project,workspace,actor)
    if kind=='workspaces': key['account_id']=str(actor)
    value=row(s,kind,entity_id,key,lock=True); check_revision(data,value)
    if kind=='repositories' and str(value['created_by'])!=str(actor) and not access.can_manage_members(s,workspace,actor): raise Forbidden('حذف مخزن فقط با سازنده یا مدیر پروژه است.')
    if kind=='workspaces': no_active(s,value['id'])
    t=table(s,kind); s.execute(t.update().where(t.c.id==value['id']).values(deleted_at=agents.now(),revision=value['revision']+1))
    return dict(deleted=True)

def device(s,actor,device_id,lock=False):
    value=row(s,'devices',device_id,dict(account_id=str(actor)),lock=lock)
    if value['revoked_at']: raise Forbidden('دسترسی Runner لغو شده است.')
    return value

def devices(s,actor):
    gitlab.account(s,actor); t=table(s,'devices')
    caps=agents.reflected(s,'company_runner_capabilities')
    capabilities={str(r['device_id']):dict(protocol=r['protocol'],capabilities=r['capabilities']) for r in s.execute(sa.select(caps).join(t,t.c.id==caps.c.device_id).where(t.c.account_id==str(actor))).mappings()}
    return dict(data=[public(r)|capabilities.get(str(r['id']),dict(protocol=1,capabilities=['source-v1'])) for r in s.execute(sa.select(t).where(t.c.account_id==str(actor)).order_by(t.c.created_at.desc())).mappings()])

def digest(secret): return hashlib.sha256(secret.encode()).hexdigest()

def pairing(s,actor,data):
    agents.body(data,('name',)); gitlab.account(s,actor,lock=True)
    # Revoke unconsumed codes before issuing a new one.
    t=table(s,'pairings'); now=agents.now()
    s.execute(t.update().where(t.c.account_id==str(actor),t.c.consumed_at.is_(None)).values(consumed_at=now))
    entity_id=str(uuid4()); secret=secrets.token_urlsafe(32)
    s.execute(t.insert().values(id=entity_id,account_id=str(actor),name=name(data['name']),code_hash=digest(secret),expires_at=now+timedelta(minutes=10)))
    return dict(code=entity_id+'.'+secret,expires_at=(now+timedelta(minutes=10)).isoformat())

def split_secret(value):
    try:
        if not isinstance(value,str) or len(value)>160: raise ValueError()
        entity_id,secret=value.split('.',1)
        if len(secret)<32: raise ValueError()
        return uid(entity_id),secret
    except (ValueError,agents.store.ProjectError): raise Unauthorized('اعتبار Runner معتبر نیست.') from None

def pair(s,data):
    agents.body(data,('code',)); entity_id,secret=split_secret(data['code']); t=table(s,'pairings')
    value=s.execute(sa.select(t).where(t.c.id==entity_id).with_for_update()).mappings().first(); now=agents.now()
    if value is None or value['consumed_at'] or value['expires_at']<now or not hmac.compare_digest(value['code_hash'],digest(secret)): raise Unauthorized('کد اتصال نامعتبر، مصرف‌شده یا منقضی است.')
    gitlab.account(s,value['account_id']); s.execute(t.update().where(t.c.id==entity_id).values(consumed_at=now))
    device_id=str(uuid4()); token=secrets.token_urlsafe(48)
    s.execute(table(s,'devices').insert().values(id=device_id,account_id=value['account_id'],name=value['name'],secret_hash=digest(token),created_at=now))
    return dict(device_id=device_id,secret=device_id+'.'+token)

def authenticate(s,bearer):
    entity_id,secret=split_secret(bearer); t=table(s,'devices')
    value=s.execute(sa.select(t).where(t.c.id==entity_id).with_for_update()).mappings().first()
    if value is None or value['revoked_at'] or not hmac.compare_digest(value['secret_hash'],digest(secret)): raise Unauthorized('اعتبار Runner معتبر نیست.')
    gitlab.account(s,value['account_id']); s.execute(t.update().where(t.c.id==entity_id).values(last_seen_at=agents.now()))
    return dict(value)

def revoke(s,actor,device_id):
    gitlab.account(s,actor,lock=True); value=device(s,actor,device_id,True); now=agents.now(); t=table(s,'devices')
    s.execute(t.update().where(t.c.id==value['id']).values(revoked_at=now))
    jobs=table(s,'jobs'); s.execute(jobs.update().where(jobs.c.device_id==value['id'],jobs.c.state.in_(ACTIVE)).values(state='cancelled',finished_at=now))
    from company_projects.local_execution import revoke_device
    revoke_device(s,value['id'])
    from company_projects.harness import revoke_device as revoke_harness
    revoke_harness(s,value['id'])
    return dict(revoked=True)

def validate_snapshot(s,job):
    if (job.get('result') or {}).get('superseded_by'): raise Conflict('این نسخه با به‌روزرسانی جدید جایگزین شده است.')
    key=scope(s,job['project_id'],job['workspace_id'],job['account_id'])
    current=row(s,'workspaces',job['source_workspace_id'],key|dict(account_id=str(job['account_id'])))
    if current['revision']!=job['snapshot']['revision']: raise Conflict('تعریف worktree تغییر کرده است.')
    for part in job['snapshot']['components']:
        repo=row(s,'repositories',part['repository_id'],key)
        connection=gitlab.load(s,job['account_id'],part['connection_id'])
        if repo['revision']!=part['repository_revision'] or connection['revision']!=part['connection_revision']: raise Conflict('مخزن یا اتصال تغییر کرده است؛ تعریف worktree را بازبینی و ذخیره کنید.')
        validated(contracts.repository_on_connection,part['url'],connection['base_url'])

def directory(job):
    return str(uid((job.get('result') or {}).get('local_directory') or job['snapshot'].get('local_directory') or job['id']))

def usable(s,job):
    if job['state']!='succeeded' or (job.get('result') or {}).get('superseded_by'):
        raise Conflict('این نسخهٔ سورس قابل استفاده نیست؛ آخرین به‌روزرسانی موفق را انتخاب کنید.')
    t=table(s,'jobs'); path=directory(job)
    if s.scalar(sa.select(t.c.id).where(t.c.account_id==str(job['account_id']),t.c.device_id==str(job['device_id']),t.c.state.in_(ACTIVE),t.c.snapshot['local_directory'].as_string()==path).limit(1)):
        raise Conflict('به‌روزرسانی سورس در صف یا در حال اجراست؛ تا پایان آن صبر کنید.')

def enqueue_update(s,project,workspace,actor,entity_id,data):
    agents.body(data,('device_id','expected_revision','action_key','update_of'))
    return enqueue(s,project,workspace,actor,entity_id,{k:v for k,v in data.items() if k!='update_of'},update_of=uid(data['update_of']))

def enqueue(s,project,workspace,actor,entity_id,data,*,update_of=None):
    from company_projects import local_execution as local, harness
    local.admission_lock(s,actor)
    agents.body(data,('device_id','expected_revision','action_key')); key=scope(s,project,workspace,actor)
    current=row(s,'workspaces',entity_id,key|dict(account_id=str(actor)),lock=True); check_revision(data,current)
    target=device(s,actor,data['device_id'],True); t=table(s,'jobs'); action_key=uid(data['action_key'])
    previous=s.execute(sa.select(t).where(t.c.account_id==str(actor),t.c.action_key==action_key)).mappings().first()
    if previous:
        if str(previous['source_workspace_id'])!=str(entity_id) or str(previous['device_id'])!=str(target['id']) or previous['snapshot']['revision']!=current['revision'] or previous['snapshot'].get('update_of')!=(str(uid(update_of)) if update_of else None): raise Conflict('شناسهٔ اقدام قبلاً برای درخواست دیگری استفاده شده است.')
        return public(previous)
    no_active(s,current['id'])
    if not update_of:
        existing=s.scalar(sa.select(t.c.id).where(t.c.source_workspace_id==str(current['id']),t.c.device_id==str(target['id']),t.c.account_id==str(actor),sa.or_(t.c.state=='succeeded',t.c.snapshot['update_of'].as_string().is_not(None))).limit(1))
        if existing: raise Conflict('این worktree روی همین Runner قبلاً آماده شده است؛ فهرست را تازه و «به‌روزرسانی در همین پوشه» را انتخاب کنید.')
    value=dict(id=str(uuid4()),**key,account_id=str(actor),source_workspace_id=current['id'],device_id=target['id'],action_key=action_key,
        snapshot=current['definition']|dict(revision=current['revision'],name=current['name']),state='pending',created_at=agents.now())
    if update_of:
        cap=local.table(s,'runner_capabilities')
        capabilities=s.scalar(sa.select(cap.c.capabilities).where(cap.c.device_id==str(target['id']))) or []
        if 'source-update-v1' not in capabilities: raise Conflict('بستهٔ جدید Runner را دریافت و Runner را دوباره اجرا کنید تا به‌روزرسانی درجا فعال شود.')
        base=row(s,'jobs',update_of,key|dict(account_id=str(actor),device_id=str(target['id'])),lock=True)
        if str(base['source_workspace_id'])!=str(entity_id) or base['state'] in ACTIVE: raise Conflict('آماده‌سازی پایه معتبر نیست.')
        if base['state']!='succeeded' and not base['snapshot'].get('update_of'): raise Conflict('ابتدا آماده‌سازی اولیه باید موفق شود.')
        path=directory(base)
        family=list(s.execute(sa.select(t).where(t.c.account_id==str(actor),t.c.device_id==str(target['id']),sa.or_(t.c.id==path,t.c.snapshot['local_directory'].as_string()==path))).mappings())
        if any(str(r['id'])!=str(base['id']) and (r['result'] or {}).get('superseded_by') is None and r['created_at']>base['created_at'] for r in family): raise Conflict('نسخهٔ جدیدتری وجود دارد؛ فهرست را تازه کنید.')
        ids=[str(r['id']) for r in family]
        for active_table, field, states in [(local.table(s,'local_executions'),'source_job_id',('pending','running')), (harness.table(s),'source_job_id',harness.ACTIVE)]:
            if s.scalar(sa.select(getattr(active_table.c,field)).where(getattr(active_table.c,field).in_(ids),active_table.c.state.in_(states)).limit(1)):
                raise Conflict('یک اجرا یا مأموریت فعال به این سورس وابسته است؛ ابتدا آن را تمام یا لغو کنید.')
        executions=local.table(s,'local_executions')
        for execution in s.execute(sa.select(executions.c.snapshot).where(executions.c.account_id==str(actor),executions.c.state.in_(('pending','running')))).mappings():
            if any(route.get('source_job_id') in ids for route in execution['snapshot'].get('routes',{}).values()): raise Conflict('یک گام فعال به این سورس وابسته است؛ ابتدا اجرا را تمام یا لغو کنید.')
        layout=lambda parts:[(p['key'],p['path'],p['url']) for p in parts]
        if layout(base['snapshot']['components'])!=layout(value['snapshot']['components']) or base['snapshot']['documents']!=value['snapshot']['documents']: raise Conflict('ساختار بخش‌ها یا مستندات تغییر کرده است؛ به‌روزرسانی درجا فقط با ساختار قبلی ممکن است.')
        value['snapshot'].update(update_of=str(base['id']),local_directory=path,previous_job_ids=ids)
    validate_snapshot(s,value); s.execute(t.insert().values(**value)); return public(value)

def cancel(s,project,workspace,actor,job_id):
    key=scope(s,project,workspace,actor)|dict(account_id=str(actor)); job=row(s,'jobs',job_id,key,lock=True); t=table(s,'jobs')
    if job['state'] in ACTIVE: s.execute(t.update().where(t.c.id==job['id']).values(state='cancelled',finished_at=agents.now()))
    return dict(cancelled=True)

def claim(s,runner):
    from company_projects.harness import busy
    from company_projects import local_execution as local
    local.admission_lock(s,runner['account_id'])
    if busy(s,runner['id']):return dict(job=None)
    if str(runner['id']) in local.reserved_devices(s,runner['account_id']):return dict(job=None)
    rpc=local.table(s,'local_rpc')
    if s.scalar(sa.select(rpc.c.id).where(rpc.c.device_id==str(runner['id']),rpc.c.state=='running').limit(1)):return dict(job=None)
    expire(s); t=table(s,'jobs')
    if s.scalar(sa.select(t.c.id).where(t.c.device_id==str(runner['id']),t.c.state=='running').limit(1)):return dict(job=None)
    candidates=s.execute(sa.select(t).where(t.c.device_id==runner['id'],t.c.account_id==runner['account_id'],t.c.state=='pending').order_by(t.c.created_at).with_for_update(skip_locked=True).limit(1)).mappings().first()
    if not candidates: return dict(job=None)
    job=dict(candidates)
    if job['snapshot'].get('update_of'):
        cap=local.table(s,'runner_capabilities')
        if 'source-update-v1' not in (s.scalar(sa.select(cap.c.capabilities).where(cap.c.device_id==str(runner['id']))) or []):
            s.execute(t.update().where(t.c.id==job['id']).values(state='failed',finished_at=agents.now(),result={'error':'runner_update_required'})); return dict(job=None)
    try: validate_snapshot(s,job)
    except (Forbidden,NotFound,Conflict):
        s.execute(t.update().where(t.c.id==job['id']).values(state='failed',finished_at=agents.now(),result={'error':'source_access_or_revision_changed'})); return dict(job=None)
    if job['snapshot'].get('update_of'):
        for old in s.execute(sa.select(t).where(t.c.account_id==str(job['account_id']),t.c.device_id==str(job['device_id']),t.c.state=='succeeded')).mappings():
            if directory(old)==directory(job): s.execute(t.update().where(t.c.id==old['id']).values(result=dict(old['result'] or {},superseded_by=str(job['id']))))
    now=agents.now(); s.execute(t.update().where(t.c.id==job['id']).values(state='running',started_at=now,lease_until=now+timedelta(seconds=90)))
    return dict(job=dict(id=str(job['id']),**job['snapshot']))

def running(s,runner,job_id):
    expire(s); job=row(s,'jobs',job_id,dict(device_id=str(runner['id']),account_id=str(runner['account_id'])),lock=True)
    if job['state']!='running': raise Conflict('آماده‌سازی فعال نیست؛ اجرای محلی باید متوقف شود.')
    validate_snapshot(s,job); return job

def heartbeat(s,runner,job_id):
    job=running(s,runner,job_id); t=table(s,'jobs'); s.execute(t.update().where(t.c.id==job['id']).values(lease_until=agents.now()+timedelta(seconds=90)))
    return dict(active=True)

def credentials(s,runner,job_id):
    job=running(s,runner,job_id)
    return dict(connections=[dict(key=p['key'],token=gitlab.decrypt(gitlab.load(s,runner['account_id'],p['connection_id']))) for p in job['snapshot']['components']])

def complete(s,runner,job_id,data):
    agents.body(data,('state','components','error'))
    previous=row(s,'jobs',job_id,dict(device_id=str(runner['id']),account_id=str(runner['account_id'])),lock=True)
    if previous['state']==data['state'] and previous['state'] in ('succeeded','failed'):
        expected=previous['result'] or {}
        if (data['state']=='succeeded' and data['components']==expected.get('components') and data['error'] is None) or (data['state']=='failed' and data['components']==[] and data['error']==expected.get('error')):
            return dict(recorded=True)
        raise Conflict('نتیجهٔ ثبت‌شده با این درخواست متفاوت است.')
    job=running(s,runner,job_id)
    if data['state'] not in ('succeeded','failed'): raise BadRequest('وضعیت معتبر نیست.')
    if (data['state']=='succeeded' and data['error'] is not None) or (data['state']=='failed' and data['components']!=[]): raise BadRequest('نتیجه با وضعیت سازگار نیست.')
    result={}
    if data['state']=='succeeded':
        import re
        parts=data['components']
        if not isinstance(parts,list) or len(parts)!=len(job['snapshot']['components']): raise BadRequest('نتیجهٔ مخزن‌ها کامل نیست.')
        for actual,expected in zip(parts,job['snapshot']['components']):
            agents.body(actual,('key','commit'))
            if actual['key']!=expected['key'] or not isinstance(actual['commit'],str) or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',actual['commit']): raise BadRequest('شناسهٔ commit معتبر نیست.')
        result=dict(components=parts,local_directory=directory(job))
    else:
        if data['error'] not in ('git_failed','disk_error','invalid_job','runner_error','merge_conflict','workspace_update_failed'): raise BadRequest('کد خطا معتبر نیست.')
        result=dict(error=data['error'])
    if job['snapshot'].get('update_of'):
        result.update(local_directory=directory(job),update_of=job['snapshot']['update_of'])
        if data['state']=='succeeded':
            from company_projects import local_execution as local
            bindings=local.table(s,'execution_bindings')
            s.execute(bindings.update().where(bindings.c.account_id==str(job['account_id']),bindings.c.device_id==str(job['device_id']),bindings.c.source_job_id.in_(job['snapshot']['previous_job_ids'])).values(source_job_id=str(job['id']),revision=bindings.c.revision+1,updated_at=agents.now()))
    t=table(s,'jobs'); s.execute(t.update().where(t.c.id==job['id']).values(state=data['state'],finished_at=agents.now(),result=result,lease_until=None))
    return dict(recorded=True)
