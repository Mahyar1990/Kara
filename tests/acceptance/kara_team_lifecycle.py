"""KP-08 live HTTP/native-engine acceptance, synthetic data in a restored DB only.

Mount this file read-only at /acceptance.py and a private directory at /proof.
Run seed, exercise, after-restart, controls as documented. Never run on production.
"""
import os
if os.environ.get('DB_DATABASE') != 'kara_kp08_acceptance':
    raise SystemExit('Refusing acceptance writes outside kara_kp08_acceptance')

import base64
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

sys.path.insert(0, '/app/api')
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app_factory import create_app
from company_projects import access, agents, agent_execution, stages
from company_projects.test_stages import feedback_graph as graph
from extensions.ext_database import db
from libs.password import hash_password
from libs.token import generate_csrf_token
from models.account import Account, TenantAccountJoin
from models.model import App
from models.workflow import Workflow, WorkflowRun
from services.account_service import AccountService

PROOF = Path('/proof')
_, app = create_app()
state = {}
tokens = {}
checks = []


def save():
    path = PROOF / 'fixture.json'
    path.write_text(json.dumps(state, ensure_ascii=False))
    path.chmod(0o600)
    (PROOF / 'checks.json').write_text(json.dumps(checks, ensure_ascii=False))


def authenticate():
    for name, person in state['accounts'].items():
        tokens[name] = (AccountService.get_account_jwt_token_for_account_id(person['id']), generate_csrf_token(person['id']))


def call(role, method, path, body=None, key=None, csrf=True):
    token, ct = tokens[role]
    headers = {'Authorization': 'Bearer ' + token, 'Cookie': 'csrf_token=' + ct, 'Content-Type': 'application/json'}
    if csrf:
        headers['X-CSRF-Token'] = ct
    if key:
        headers['Idempotency-Key'] = key
    req = urllib.request.Request('http://nginx/console/api' + path, method=method, headers=headers,
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=45) as result:
            return result.status, json.load(result)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def expect(role, method, path, body=None, code=200, key=None):
    status, value = call(role, method, path, body, key)
    if status != code:
        raise AssertionError((method, path, status, value))
    return value


def base(project='A'):
    return '/company/projects/' + state['projects'][project]['id'] + '/team'


def ip(instance):
    return base() + '/instances/' + instance['id']


def sp(instance, stage):
    return ip(instance) + '/stages/' + stage['id']


def get(instance, stage, actor):
    return expect(actor, 'GET', sp(instance, stage))


def act(instance, stage, action, actor, **body):
    return expect(actor, 'POST', sp(instance, stage) + '/' + action,
        dict(expected_revision=stage['revision'], **body), 202 if action == 'run' else 200, str(uuid4()))


def ctl(instance, stage, action, actor, code=200, **body):
    return expect(actor, 'POST', sp(instance, stage) + '/control/' + action,
        dict(expected_revision=stage['revision'], reason='Synthetic KP08 control', **body), code, str(uuid4()))


def role_set(person, values):
    path = base() + '/members/' + state['accounts'][person]['id'] + '/roles'
    old = expect('manager', 'GET', path)
    return expect('manager', 'PUT', path, dict(roles=values, expected_revision=old['revision'],
        expected_membership_id=old['membership_id']), key=str(uuid4()))


def grant(index, values):
    path = base() + '/agents/' + state['agents'][index]['id'] + '/grants'
    old = expect('manager', 'GET', path)
    expect('manager', 'PUT', path, dict(expected_revision=old['revision'], grants=values), key=str(uuid4()))


def run(instance, stage, actor, *, execute=True):
    before = get(instance, stage, actor)
    key = str(uuid4()); body = dict(expected_revision=before['revision'])
    started = expect(actor, 'POST', sp(instance, stage) + '/run', body, 202, key)
    assert expect(actor, 'POST', sp(instance, stage) + '/run', body, 202, key) == started
    identity = started['active_attempt_id']
    if execute:
        agent_execution.execute(identity)
        agent_execution.execute(identity)  # Broker redelivery: claim must be at most once.
        finished = get(instance, stage, actor)
        assert finished['state'] == 'awaiting_feedback', finished
        with Session(db.engine) as session:
            native = session.get(WorkflowRun, identity)
            assert native and native.status == 'succeeded'
            assert native.created_by == state['accounts'][actor]['id'] and native.workflow_id == before['binding']['workflow_id']
        return finished
    return started


def select(instance, stage, actor, artifact=None):
    return act(instance, stage, 'request_decision', actor, artifact_id=artifact or stage['artifacts'][0]['id'])


def finalize(instance, stage, race=False):
    path = sp(instance, stage) + '/finalize'
    body = dict(expected_revision=stage['revision'], artifact_id=stage['selected_artifact_id'], reason='Synthetic PO finalization')
    if not race:
        return expect('po', 'POST', path, body, key=str(uuid4()))
    keys = [str(uuid4()), str(uuid4())]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda k: call('po', 'POST', path, body, k), keys))
    assert sorted(r[0] for r in results) == [200, 409], results
    index = next(i for i, r in enumerate(results) if r[0] == 200)
    assert call('po', 'POST', path, body, keys[index]) == results[index]
    assert len(get(instance, stage, 'po')['decisions']) == 1
    return results[index][1]


def request(flow, title):
    item = expect('po', 'POST', base() + '/requests', dict(title=title, content='Synthetic KP08 requirement',
        attachment_ids=[], expected_revision=1), 201, str(uuid4()))
    assert call('runner1', 'POST', base() + '/instances', dict(request_id=item['id'],
        intake_decision_id=str(uuid4()), expected_revision=item['revision']), str(uuid4()))[0] == 404
    approved = expect('po', 'POST', base() + '/requests/' + item['id'] + '/intake-decisions', dict(
        expected_revision=item['revision'], request_revision_id=item['current_revision_id'], outcome='approved',
        flow_id=flow['id'], flow_version_id=flow['current_version_id'], reason='Synthetic PO entry', expires_at=None), 201, str(uuid4()))
    instance = expect('po', 'POST', base() + '/instances', dict(request_id=item['id'],
        intake_decision_id=approved['current_decision_id'], expected_revision=approved['revision']), 201, str(uuid4()))
    assert instance['flow_version_id'] == flow['current_version_id']
    return instance


def seed():
    if (PROOF / 'fixture.json').exists():
        raise SystemExit('Seed evidence already exists; preserve it and use a fresh acceptance environment')
    stamp = uuid4().hex[:10]
    with Session(db.engine) as session, session.begin():
        root = access.authority(session)
        state['accounts'] = {'root': {'id': str(root['account_id'])}}
        for name, title in [('manager','مدیر پذیرش KP08'), ('outsider','مدیر پروژه دوم KP08'), ('po','مالک محصول KP08'),
                ('runner1','تحلیلگر پذیرش KP08'), ('runner2','بازبین پذیرش KP08'), ('denied','عضو بدون مجوز KP08')]:
            password, salt = secrets.token_urlsafe(24), os.urandom(16)
            person = Account(name=title, email=f'kp08-{stamp}-{name}@example.test',
                password=base64.b64encode(hash_password(password, salt)).decode(), password_salt=base64.b64encode(salt).decode(),
                interface_language='fa-IR', timezone='Asia/Tehran', initialized_at=datetime.now(timezone.utc).replace(tzinfo=None))
            session.add(person); session.flush()
            state['accounts'][name] = dict(id=person.id, email=person.email, password=password)
    authenticate(); state['projects'] = {}
    for label, owner in [('A','manager'), ('B','outsider')]:
        state['projects'][label] = expect('root', 'POST', '/company/projects', dict(name='پذیرش سراسری KP08 '+label+' '+stamp,
            description='Synthetic isolated acceptance', owner_id=state['accounts'][owner]['id']), 201)
    a, b = state['projects']['A'], state['projects']['B']
    assert call('manager','POST','/company/projects',dict(name='denied',owner_id=state['accounts']['manager']['id']))[0] == 403
    with Session(db.engine) as session, session.begin():
        for name in ['po','runner1','runner2','denied']:
            session.add(TenantAccountJoin(tenant_id=a['workspace_id'],account_id=state['accounts'][name]['id'],role='normal'))
        session.flush()
        state['memberships'] = {name: access.membership(session,a['workspace_id'],state['accounts'][name]['id']).id
            for name in ['manager','po','runner1','runner2','denied']}
    for name in ['root','manager','po','runner1','runner2','denied']:
        expect(name,'POST','/company/projects/'+a['id']+'/enter')
    expect('outsider','POST','/company/projects/'+b['id']+'/enter')
    assert call('manager','GET','/company/projects/'+b['id']+'/team/members')[0] == 404
    role_set('po',['po']); state['sources'] = []; state['agents'] = []; state['grants'] = []
    for index, runner in enumerate(['runner1','runner2']):
        with Session(db.engine) as session, session.begin():
            source = App(tenant_id=a['workspace_id'], name=f'قطعی پذیرش KP08 {index+1}', mode='workflow', status='normal',
                created_by=state['accounts']['manager']['id'], enable_api=False, enable_site=False, max_active_requests=0)
            session.add(source); session.flush()
            workflow = Workflow.new(tenant_id=a['workspace_id'],app_id=source.id,type='workflow',version='kp08-published',
                graph=json.dumps(graph()),features='{}',created_by=source.created_by,environment_variables=[],conversation_variables=[],rag_pipeline_variables=[])
            session.add(workflow);session.flush();source.workflow_id=workflow.id
            state['sources'].append(dict(app_id=source.id, workflow_id=workflow.id))
        agent = expect('manager','POST',base()+'/agents',dict(**state['sources'][-1],name=f'مرحلهٔ قطعی KP08 {index+1}',
            description='Synthetic echo; no LLM',expected_revision=1),201,str(uuid4()))
        state['agents'].append(agent)
        values = [dict(account_id=state['accounts'][name]['id'],membership_id=state['memberships'][name],actions=actions)
            for name,actions in [(runner,['view','run','feedback']),('po',['view','finalize'])]]
        state['grants'].append(values);grant(index,values)
    def binding(key,index,source):
        runner=['runner1','runner2'][index]
        return dict(key=key,title='تحلیل' if index==0 else 'بازبینی',agent_id=state['agents'][index]['id'],
            executor_id=state['accounts'][runner]['id'],executor_membership_id=state['memberships'][runner],
            finalizer_id=state['accounts']['po']['id'],finalizer_membership_id=state['memberships']['po'],
            decision_role='po',inputs={'request':source})
    state['bindings']=[binding('analysis',0,{'source':'request'}),binding('review',1,{'source':'stage','stage_key':'analysis','output':'answer'})]
    state['flows']=[]
    for title, bindings in [('فلو کامل پذیرش',state['bindings']),('فلو دوم پذیرش',[binding('single',1,{'source':'request'})])]:
        flow=expect('manager','POST',base()+'/flows',dict(name=title+' '+stamp,description='',stages=bindings,expected_revision=1),201,str(uuid4()))
        state['flows'].append(expect('manager','POST',base()+'/flows/'+flow['id']+'/publish',dict(expected_revision=flow['revision']),key=str(uuid4())))
    with Session(db.engine) as session:
        assert all(access.membership(session,a['workspace_id'],state['accounts'][role]['id']).role=='normal' for role in ['po','runner1','runner2','denied'])
    checks.append('Root HTTP creates two projects; scoped owner/roles/grants; two published flows; four normal members.')


def exercise():
    first_flow=state['flows'][0]; instance=request(first_flow,'پذیرش سراسری چرخه KP08'); first,second=instance['stages']
    state['primary']=instance; save()
    for actor in ['denied','outsider','manager','runner2']:
        assert call(actor,'GET',sp(instance,first))[0] in (403,404)
    assert call('manager','POST','/apps/'+state['sources'][0]['app_id']+'/workflows/draft/run',{'inputs':{},'response_mode':'blocking'},str(uuid4()))[0]==403
    assert call('runner1','POST',sp(instance,first)+'/run',dict(expected_revision=first['revision']),str(uuid4()),False)[0]==401
    row=run(instance,first,'runner1')
    # Publish a future flow and a future native program pointer; existing run stays pinned.
    updated=expect('manager','PUT',base()+'/flows/'+first_flow['id'],dict(name=first_flow['name'],description='Future revision',
        stages=state['bindings'],expected_revision=first_flow['revision']),key=str(uuid4()))
    newer=expect('manager','POST',base()+'/flows/'+first_flow['id']+'/publish',dict(expected_revision=updated['revision']),key=str(uuid4()))
    assert newer['current_version_id']!=instance['flow_version_id']
    with Session(db.engine) as session,session.begin():
        source=session.get(App,state['sources'][0]['app_id']); future=Workflow.new(tenant_id=source.tenant_id,app_id=source.id,
            type='workflow',version='kp08-future-native',graph=json.dumps(graph()),features='{}',created_by=source.created_by,
            environment_variables=[],conversation_variables=[],rag_pipeline_variables=[])
        session.add(future);session.flush();source.workflow_id=future.id;state['future_workflow_id']=future.id
    for index in range(2):
        row=act(instance,row,'feedback','runner1',artifact_id=row['artifacts'][0]['id'],message='Synthetic feedback '+str(index+1),
            inputs=dict(row['preview_inputs'], feedback_context='Synthetic revision '+str(index+1)),feedback_variable='feedback_context')
        assert row['state']=='ready' and len(row['attempts'])==index+1
        row=run(instance,row,'runner1')
    assert len(row['attempts'])==3 and len(row['feedback'])==2
    row=act(instance,row,'edit_output','runner1',artifact_id=row['artifacts'][0]['id'],content={'answer':'Selected human KP08 output'},reason='Synthetic human correction')
    selected=row['artifacts'][0]; assert selected['kind']=='human'
    row=select(instance,row,'runner1',selected['id'])
    assert call('runner1','POST',sp(instance,row)+'/finalize',dict(expected_revision=row['revision'],artifact_id=selected['id'],reason='denied'),str(uuid4()))[0]==403
    role_set('po',[])
    assert call('po','POST',sp(instance,row)+'/finalize',dict(expected_revision=row['revision'],artifact_id=selected['id'],reason='role removed'),str(uuid4()))[0]==403
    role_set('po',['po']);finalize(instance,row,race=True)
    second_row=get(instance,second,'runner2');assert second_row['state']=='ready' and second_row['attempts']==[]
    assert second_row['handoffs'][0]['artifact_id']==selected['id'] and second_row['preview_inputs']=={'request':'Selected human KP08 output'}
    assert second_row['feedback']==[] and second_row['artifacts']==[] and call('runner2','GET',sp(instance,first))[0]==403
    grant(0,[v for v in state['grants'][0] if v['account_id']!=state['accounts']['runner1']['id']])
    assert call('runner1','GET',sp(instance,first))[0]==403
    assert get(instance,second,'runner2')['handoffs'][0]['artifact_id']==selected['id'];grant(0,state['grants'][0])
    second_row=run(instance,second_row,'runner2')
    second_row=act(instance,second_row,'feedback','runner2',artifact_id=second_row['artifacts'][0]['id'],message='Second person review',
        inputs=dict(second_row['preview_inputs'], feedback_context='Second person revision'),feedback_variable='feedback_context')
    second_row=run(instance,second_row,'runner2');finalize(instance,select(instance,second_row,'runner2'))
    summary=expect('po','GET',ip(instance)+'/controls');assert summary['state']=='completed'
    first_row=get(instance,first,'po');old_artifact=first_row['selected_artifact_id'];ctl(instance,first_row,'reopen','po')
    assert get(instance,second,'runner2')['state']=='stale'
    ctl(instance,get(instance,second,'runner2'),'revalidate','runner2',code=409)
    ctl(instance,get(instance,first,'runner1'),'revalidate','runner1')
    row=get(instance,first,'runner1');assert row['preview_inputs']=={'request':'Synthetic KP08 requirement'}
    assert call('runner1','POST',sp(instance,first)+'/request_decision',dict(expected_revision=row['revision'],artifact_id=old_artifact),str(uuid4()))[0]==409
    row=run(instance,row,'runner1');finalize(instance,select(instance,row,'runner1'))
    ctl(instance,get(instance,second,'runner2'),'revalidate','runner2')
    row=run(instance,get(instance,second,'runner2'),'runner2');finalize(instance,select(instance,row,'runner2'))
    assert expect('po','GET',ip(instance)+'/controls')['state']=='completed'
    assert len(get(instance,first,'po')['decisions'])==2 and len(get(instance,second,'po')['decisions'])==2
    state['secondary']=request(state['flows'][1],'پذیرش صف و راه‌اندازی مجدد KP08')
    waiting=state['secondary']; stage=waiting['stages'][0]
    queued=run(waiting,stage,'runner2',execute=False)
    grant(1,[v for v in state['grants'][1] if v['account_id']!=state['accounts']['runner2']['id']])
    agent_execution.execute(queued['active_attempt_id'])
    grant(1,state['grants'][1]);row=get(waiting,stage,'runner2');assert row['state']=='stale' and row['artifacts']==[]
    ctl(waiting,row,'revalidate','runner2');queued=run(waiting,get(waiting,stage,'runner2'),'runner2',execute=False)
    state['pending_attempt_id']=queued['active_attempt_id']
    checks.append('Seven native echo runs; two-person handoff/feedback/finalization; role/grant revocation and scope; 200/409 finalization; cascade and fresh re-finalization; flow/program pinning; queued revocation fenced.')


def after_restart():
    instance=state['secondary'];stage=instance['stages'][0];deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        row=get(instance,stage,'runner2')
        if row['state']!='running':break
        time.sleep(1)
    assert row['state']=='awaiting_feedback',row
    assert row['attempts'][-1]['attempt_id']==state['pending_attempt_id']
    finalize(instance,select(instance,row,'runner2'))
    with Session(db.engine) as session:
        native=session.get(WorkflowRun,state['pending_attempt_id']);assert native and native.status=='succeeded'
    checks.append('API restart and real Celery worker deliver committed pending attempt once; old duplicate deliveries do not repeat completed runs.')


def controls():
    instance=request(state['flows'][1],'پذیرش لغو و بازیابی KP08');stage=instance['stages'][0]
    row=run(instance,stage,'runner2',execute=False);identity=row['active_attempt_id']
    with Session(db.engine) as session,session.begin():
        assert agent_execution.claim(session,identity)
        native=stages.table(session,'company_team_agent_attempts')
        session.execute(native.update().where(native.c.id==identity).values(started_at=agents.now()-timedelta(hours=2)))
    ctl(instance,row,'recover','manager',acknowledge_effects=True)
    with Session(db.engine) as session,session.begin():
        assert not agent_execution.finish(session,identity,'succeeded',{'outputs':{'answer':'late'}})
    row=get(instance,stage,'runner2');assert row['state']=='failed'
    row=act(instance,row,'retry','runner2');assert row['state']=='ready'
    summary=expect('po','GET',ip(instance)+'/controls')
    key=str(uuid4());body=dict(expected_revision=summary['revision'],reason='Synthetic explicit cancellation')
    first=expect('po','POST',ip(instance)+'/cancellations',body,key=key)
    assert expect('po','POST',ip(instance)+'/cancellations',body,key=key)==first
    assert call('runner2','POST',sp(instance,stage)+'/run',dict(expected_revision=row['revision']),str(uuid4()))[0]==409
    assert get(instance,stage,'runner2')['state']=='cancelled'
    state['cancelled']=instance
    with Session(db.engine) as session:
        source_ids=[v['app_id'] for v in state['sources']]
        count=session.scalar(sa.select(sa.func.count()).select_from(WorkflowRun).where(WorkflowRun.app_id.in_(source_ids)))
        assert count==8,count
    state['native_run_count']=8
    checks.append('Explicit orphan recovery and late-result fence, no automatic rerun; terminal cancellation/replay; exactly eight synthetic WorkflowRuns across both flows.')


if __name__=='__main__':
    with app.app_context():
        assert db.engine.url.database=='kara_kp08_acceptance'
        phase=sys.argv[1]
        if phase!='seed':
            state=json.loads((PROOF/'fixture.json').read_text());checks=json.loads((PROOF/'checks.json').read_text());authenticate()
        {'seed':seed,'exercise':exercise,'after-restart':after_restart,'controls':controls}[phase]()
        save()
        print('KP08 '+phase+': PASS; evidence private; no LLM invoked by lifecycle fixture.')
