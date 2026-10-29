"""Delegate individual workflow nodes to explicitly selected, actor-owned devices.

The central service authorizes and relays; it never evaluates graph nodes.
Deterministic child IDs prevent retrying a request from running a node twice.
"""
from uuid import UUID, uuid5
import json
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden
from company_projects import agents, local_execution as local, source_code as source
from company_projects.execution_plan import describe

def validate_choices(s, workflow, actor, choice):
    key = local.project_key(s, workflow.tenant_id, actor)
    requirements = {n['id']: n for n in describe(workflow.graph_dict)['nodes'] if n['runner_required']}
    if set(choice['runners']) != set(requirements): raise BadRequest('Runner هر گام اجرایی همین نسخه را انتخاب کنید.')
    routes = {}; devices = {}; prepared = {}
    for node in requirements:
        selected=choice['runners'][node]
        if not isinstance(selected, dict) or set(selected) != {'device_id', 'source_job_id'}: raise BadRequest('انتخاب Runner گام معتبر نیست.')
        if not isinstance(selected['device_id'],str) or (selected['source_job_id'] is not None and not isinstance(selected['source_job_id'],str)):
            raise BadRequest('شناسهٔ Runner یا سورس معتبر نیست.')
        if selected['device_id'] not in devices:
            device = source.device(s, actor, selected['device_id'])
            caps = local.table(s, 'runner_capabilities')
            registered = s.execute(sa.select(caps).where(caps.c.device_id == str(device['id']))).mappings().first()
            devices[selected['device_id']] = device, registered
        device, registered = devices[selected['device_id']]
        needed = set(requirements[node]['requirements']) | {'workflow-v2'}
        if not registered or registered['protocol'] != 2 or needed - set(registered['capabilities']):
            raise BadRequest('Runner انتخاب‌شده برای گام «' + requirements[node]['title'] + '» به‌روز یا سازگار نیست.')
        job = None
        if selected['source_job_id']:
            source_key=(selected['source_job_id'], str(device['id']))
            if source_key not in prepared:
                prepared[source_key] = source.row(s, 'jobs', selected['source_job_id'], key | dict(account_id=str(actor), device_id=str(device['id'])))
            job=prepared[source_key]
            source.usable(s,job)
            if job['state'] != 'succeeded': raise BadRequest('سورس این گام باید روی Runner انتخاب‌شده آماده باشد.')
        routes[node] = dict(device_id=str(device['id']), device_name=device['name'], source_job_id=str(job['id']) if job else None, requirements=sorted(needed))
    sources={}
    for route in routes.values():
        device=route['device_id']
        if device in sources and sources[device]!=route['source_job_id']: raise BadRequest('برای گام‌های یک Runner یک سورس آمادهٔ مشترک انتخاب کنید.')
        sources[device]=route['source_job_id']
    return routes

def check_routes(s, job):
    devices={}
    for route in job['snapshot'].get('routes', {}).values():
        if route['device_id'] not in devices: devices[route['device_id']]=dict(route,requirements=set())
        devices[route['device_id']]['requirements'].update(route['requirements'])
    for route in devices.values():
        source.device(s, job['account_id'], route['device_id'])
        caps=local.table(s,'runner_capabilities')
        current=s.execute(sa.select(caps).where(caps.c.device_id==route['device_id'])).mappings().first()
        if not current or current['protocol']!=2 or set(route['requirements'])-set(current['capabilities']):
            raise Conflict('قابلیت‌های Runner این اجرا تغییر کرده است.')
        if route['source_job_id']:
            row = source.row(s, 'jobs', route['source_job_id'], {k: job[k] for k in ('project_id', 'workspace_id', 'account_id')} | dict(device_id=route['device_id']))
            source.usable(s,row)
            if row['state'] != 'succeeded': raise Conflict('سورس گام تغییر کرده است.')

def parent(s, row):
    job = local.execution(s, row['payload']['parent_id'], actor=row['account_id'])
    if job['state'] != 'running' or job['lease_until'] < agents.now(): raise Conflict('اجرای اصلی فعال نیست.')
    local.validate_access(s, job)
    route = job['snapshot'].get('routes', {}).get(row['payload']['node_id'])
    if not route or route['device_id'] != str(row['device_id']): raise Forbidden('Runner مقصد این گام نیست.')
    return job

def request(s, runner, identity, data):
    from company_projects import local_rpc
    agents.body(data, ('node_id', 'pool'))
    job = local.running(s, runner, identity)
    route = job['snapshot'].get('routes', {}).get(data['node_id'])
    if not route or route['device_id'] == str(runner['id']): raise BadRequest('این گام مقصد راه‌دور ندارد.')
    if not isinstance(data['pool'], dict) or 'env' in data['pool'] or len(json.dumps(data).encode()) > 2097152: raise BadRequest('ورودی گام معتبر نیست.')
    child_id = str(uuid5(UUID(str(job['id'])), data['node_id']))
    table = local_rpc.table(s)
    payload = dict(parent_id=str(job['id']), node_id=data['node_id'], pool=data['pool'])
    old = s.execute(sa.select(table).where(table.c.id == child_id)).mappings().first()
    if old:
        if old['payload'] != payload: raise Conflict('ورودی گام پس از ثبت تغییر کرده است.')
        row = dict(old)
    else:
        row = dict(id=child_id, **{k: job[k] for k in ('project_id', 'workspace_id', 'account_id', 'membership_id')},
            device_id=route['device_id'], method='workflow-node', payload=payload, state='pending', created_at=agents.now())
        s.execute(table.insert().values(**row))
    return dict(id=child_id, state=row['state'], result=row.get('result'))

def claim_payload(s, row):
    job = parent(s, row); node_id = row['payload']['node_id']
    route = job['snapshot']['routes'][node_id]
    return dict(node_job=dict(id=str(job['id']), actor_id=job['account_id'], app_id=job['app_id'], workflow_id=job['workflow_id'],
        graph=job['snapshot']['graph'], inputs=job['inputs']), node_id=node_id, pool=row['payload']['pool'], source_job_id=route['source_job_id'], source_directory=source.directory(source.row(s,'jobs',route['source_job_id'],dict(account_id=str(job['account_id'])))) if route['source_job_id'] else None)

def secrets(s, row):
    from company_projects import personal_models
    from models.workflow import Workflow
    job = parent(s, row); node = row['payload']['node_id']
    # A worker receives only this node's model credentials (plus its knowledge models).
    keys = model_keys(job['snapshot'], [node])
    workflow = s.get(Workflow, job['workflow_id'])
    return dict(models={k: dict(**v, credentials=personal_models.decrypt(personal_models.load(s, job['account_id'], v['id'])))
        for k, v in job['snapshot']['models'].items() if k in keys}, environment={v.name: v.value for v in workflow.environment_variables})

def model_keys(snapshot, nodes):
    keys = set(nodes) | {node + ':rerank' for node in nodes}
    for node in nodes:
        for dataset in snapshot.get('knowledge', {}).get(node, {}).get('datasets', []):
            if dataset.get('embedding_key'): keys.add(dataset['embedding_key'])
    return keys

def knowledge(s, runner, identity, data):
    from company_projects import local_rpc
    row = local_rpc.running(s, runner, identity)
    if row['method'] != 'workflow-node' or data.get('node_id') != row['payload']['node_id']: raise Forbidden('دانش این گام در دسترس نیست.')
    return local.knowledge_for_job(s, parent(s, row), data)
