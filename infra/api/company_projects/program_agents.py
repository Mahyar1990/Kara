"""Compose pinned library roles into ordinary local workflows; never invoke an SDK."""
from copy import deepcopy
import json
import re
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import access, agents, personal_agent_sources as library, runtime_models, store, team
from models.agent import Agent
from models.model import App
from models.workflow import Workflow

PIN = 'kara_library_role'
SELECTOR = re.compile(r'\{\{#([A-Za-z0-9_-]+)\.([A-Za-z0-9_.-]+)#\}\}')
SEMANTICS = ('type', 'model', 'prompt_template', 'template', 'variables', 'dataset_ids', 'query_variable_selector',
    'retrieval_mode', 'metadata_filtering_mode', 'multiple_retrieval_config', 'context', 'vision', 'memory', 'structured_output_enabled')


def authorize(s, project, workspace, actor, app_id=None):
    scope = team.scope(s, project, workspace, actor, write=True)
    if str(team.member(s, workspace, actor).role) not in ('owner', 'admin', 'editor'):
        raise Forbidden('مجوز فنی ویرایش برنامه لازم است.')
    from configs import dify_config
    from core.rbac import RBACPermission
    from services.enterprise.rbac_service import RBACService
    scene = RBACPermission.APP_EDIT if app_id else RBACPermission.APP_CREATE_AND_MANAGEMENT
    extra = dict(resource_type='app', resource_id=str(app_id)) if app_id else {}
    if dify_config.RBAC_ENABLED and not RBACService.CheckAccess.check(str(workspace), str(actor), scene=scene, **extra):
        raise Forbidden('مجوز ساخت یا ویرایش این برنامه لازم است.')
    if app_id:
        from company_projects.agent_execution import native_permission
        app = s.scalar(sa.select(App).where(App.id == store.uid(app_id), App.tenant_id == str(workspace)).with_for_update())
        if not app or app.mode != 'workflow' or app.status != 'normal':
            raise NotFound('برنامهٔ فرایندی در این پروژه پیدا نشد.')
        native_permission(s, app.id, actor)
        return scope, app
    return scope, None


def checked_source(s, workspace, actor, identity, snapshot_id):
    library.permission(s, workspace, actor, identity, export=True)
    source, snapshot = library.load(s, workspace, identity, snapshot_id)
    graph, meta = library.compile_graph(s, source, snapshot, actor, executor_model=True)
    return graph, meta


def catalog(s, project, workspace, actor):
    authorize(s, project, workspace, actor)
    sources = []
    for source in s.scalars(sa.select(Agent).where(Agent.tenant_id == str(workspace), Agent.scope == 'roster', Agent.status == 'active').order_by(Agent.name)):
        try:
            library.permission(s, workspace, actor, source.id, export=True)
        except Forbidden:
            continue
        reason = ''; snapshot = None
        try:
            _, snapshot = library.load(s, workspace, source.id)
            library.configuration(snapshot, executor_model=True)
        except (Conflict, NotFound, UnprocessableEntity) as exc:
            reason = exc.description
        sources.append(dict(id=source.id, name=source.name, snapshot_id=snapshot.id if snapshot else None, reason=reason))
    from company_projects.controller import visible_filters
    filters = visible_filters(s, str(workspace), str(actor))
    apps = list(s.scalars(sa.select(App).where(*filters, App.tenant_id == str(workspace), App.mode == 'workflow', App.status == 'normal').order_by(App.name))) if filters else []
    return dict(sources=sources, programs=[dict(id=a.id, name=a.name) for a in apps])


def preview(s, project, workspace, actor, identity, snapshot_id):
    authorize(s, project, workspace, actor)
    graph, meta = checked_source(s, workspace, actor, identity, snapshot_id)
    return dict(source_digest=agents.digest([graph, meta]), name=meta['name'], version=meta['snapshot_version'],
        inputs=[v for v in graph['nodes'][0]['data']['variables'] if v['variable'] != runtime_models.INPUT],
        prompt=next(n['data']['prompt_template'][0]['text'] for n in graph['nodes'] if n['id'] == 'task_agent'),
        skills=meta['skills'], knowledge=[n['data']['title'] for n in graph['nodes'] if n['data']['type'] == 'knowledge-retrieval'])


def draft(s, app):
    value = s.scalar(sa.select(Workflow).where(Workflow.app_id == app.id, Workflow.tenant_id == app.tenant_id,
        Workflow.version == 'draft').with_for_update())
    if not value:
        raise Conflict('ابتدا برنامه را در طراح باز و پیش‌نویس را ذخیره کنید.')
    return value


def upstream(graph, target):
    result = set(); pending = [target]
    while pending:
        current = pending.pop()
        for e in graph['edges']:
            if e['target'] == current and e['source'] not in result:
                result.add(e['source']); pending.append(e['source'])
    result.discard(target)
    return result


def available(graph, target):
    ancestors = upstream(graph, target); result = []
    for n in graph['nodes']:
        if n['id'] not in ancestors:
            continue
        d = n['data']; kind = d['type']; fields = []
        if kind == 'start': fields = [v['variable'] for v in d.get('variables', []) if v['variable'] != runtime_models.INPUT and v.get('type') in ('paragraph', 'text-input', 'number', 'select', 'checkbox')]
        elif kind == 'llm': fields = ['text']
        elif kind in ('template-transform', 'variable-aggregator'): fields = ['output']
        elif kind == 'code': fields = list(d.get('outputs', {}))
        result.extend(dict(value='{{#' + n['id'] + '.' + v + '#}}', label=(d.get('title') or n['id']) + ' · ' + v) for v in fields)
    return result


def detail(s, project, workspace, actor, app_id):
    _, app = authorize(s, project, workspace, actor, app_id); w = draft(s, app); graph = w.graph_dict
    managed = {m for n in graph['nodes'] if PIN in n['data'] for m in n['data'][PIN]['members'] if m != n['id']}
    return dict(id=app.id, name=app.name, hash=w.unique_hash, nodes=[dict(id=n['id'], name=n['data'].get('title') or n['id'],
        role=({k: n['data'][PIN]['source'][k] for k in ('name', 'snapshot_version')} if PIN in n['data'] else None),
        variables=available(graph, n['id']), task='\n'.join(p.get('text', '') for p in n['data'].get('prompt_template', []) if p.get('role') == 'user'))
        for n in graph['nodes'] if n['id'] not in managed and n['data']['type'] == 'llm' and not n.get('parentId') and not n['data'].get('isInIteration') and not n['data'].get('isInLoop')])


def block_digest(graph, members):
    def semantic(data):
        result = {k: v for k, v in data.items() if k in SEMANTICS}
        if isinstance(result.get('prompt_template'), list):
            result['prompt_template'] = [{k: v for k, v in item.items() if k in ('role', 'text')} for item in result['prompt_template']]
        if isinstance(result.get('variables'), list):
            result['variables'] = [{k: v for k, v in item.items() if k in ('variable', 'value_selector')} for item in result['variables']]
        return result
    nodes = sorted([dict(id=n['id'], data=semantic(n['data']))
        for n in graph['nodes'] if n['id'] in members], key=lambda n: n['id'])
    edges = sorted([(e['source'], e['target'], e.get('sourceHandle') or 'source', e.get('targetHandle') or 'target')
        for e in graph['edges'] if e['source'] in members and e['target'] in members])
    return agents.digest([nodes, edges])


def valid_pin(pin):
    if not isinstance(pin, dict) or set(pin) != {'version', 'source', 'members', 'digest', 'original'} or pin.get('version') != 1 or not isinstance(pin.get('members'), list) or not pin['members'] or any(not isinstance(m, str) for m in pin['members']) or not isinstance(pin.get('source'), dict) or not {'name', 'snapshot_version', 'agent_id', 'snapshot_id', 'skills', 'snapshot_digest'} <= pin['source'].keys() or (pin['original'] is not None and not isinstance(pin['original'], dict)):
        raise Conflict('اتصال ایجنت داخل برنامه معتبر نیست.')


def validate(s, workflow, actor=None, *, publishing=False):
    if not workflow:
        return
    graph = workflow.graph_dict
    for n in graph.get('nodes', []):
        pin = n.get('data', {}).get(PIN)
        if pin is None:
            continue
        valid_pin(pin)
        members = pin['members']
        if n['id'] not in members or len(set(members)) != len(members) or not set(members) <= {v['id'] for v in graph['nodes']} or block_digest(graph, members) != pin.get('digest'):
            raise Conflict('بخش متصل به ایجنت تغییر کرده است؛ اتصال را در «ایجنت‌های برنامه» بازبینی یا جدا کنید.')
        if any(e['target'] in members and e['source'] not in members and e['target'] != members[0] for e in graph['edges']):
            raise Conflict('ترتیب اجرای بخش متصل به ایجنت تغییر کرده است؛ اتصال را بازبینی کنید.')
        library.validate_reference(s, workflow.tenant_id, pin['source'], actor)
        if publishing and actor:
            from configs import dify_config
            from core.rbac import RBACPermission
            from services.enterprise.rbac_service import RBACService
            if dify_config.RBAC_ENABLED and not RBACService.CheckAccess.check(str(workflow.tenant_id), str(actor),
                    scene=RBACPermission.AGENT_RELEASE_AND_VERSION, resource_type='agent', resource_id=pin['source']['agent_id']):
                raise Forbidden('مجوز انتشار ایجنت منبع داخل برنامه لازم است.')
        if runtime_models.policy(graph) is None:
            raise Conflict('برنامهٔ دارای ایجنت باید مدل را از اجراکننده دریافت کند.')


def positioned(graph):
    for i, n in enumerate(graph['nodes']):
        n.update(type='custom', position=dict(x=i * 330, y=180))
        n['data'].setdefault('desc', '')
    for e in graph['edges']:
        e.update(type='custom', data=dict(sourceType=next(n['data']['type'] for n in graph['nodes'] if n['id'] == e['source']),
            targetType=next(n['data']['type'] for n in graph['nodes'] if n['id'] == e['target'])))
    return graph


def record(s, scope, actor, key, digest, kind, result):
    agents.event(s, scope, actor, key, digest, kind, result)
    return result


def create(s, project, workspace, actor, data, key):
    agents.body(data, ('name', 'source_id', 'snapshot_id', 'source_digest'))
    scope, _ = authorize(s, project, workspace, actor); key = agents.action_key(key)
    digest = agents.digest(dict(operation='program-library-create', **data)); previous = agents.replay(s, scope, actor, key, digest)
    if previous:
        return previous
    if not isinstance(data['name'], str) or not data['name'].strip() or len(data['name']) > 120:
        raise BadRequest('نام برنامه الزامی و حداکثر ۱۲۰ نویسه است.')
    from services.feature_service import FeatureService
    quota = FeatureService.get_features(str(workspace), exclude_vector_space=True).apps
    if 0 < quota.limit <= quota.size:
        raise Conflict('ظرفیت برنامه‌های پروژه تکمیل است.')
    graph, meta = checked_source(s, workspace, actor, data['source_id'], data['snapshot_id'])
    if agents.digest([graph, meta]) != data['source_digest']:
        raise Conflict('نسخهٔ منبع تغییر کرده است؛ پیش‌نمایش را تازه کنید.')
    target = next(n for n in graph['nodes'] if n['id'] == 'task_agent')
    members = [n['id'] for n in graph['nodes'] if n['data']['type'] not in ('start', 'end')]
    # A new program may keep its imported instructions when detached; existing nodes restore their original definition.
    target['data'][PIN] = dict(version=1, source=meta, members=members, digest=block_digest(graph, members), original=None)
    positioned(graph)
    app = App(tenant_id=str(workspace), name=data['name'].strip(), description='برنامه با ایجنت کتابخانه؛ انتخاب مدل با اجراکننده',
        mode='workflow', status='normal', created_by=str(actor), updated_by=str(actor), maintainer=str(actor),
        enable_api=False, enable_site=False, max_active_requests=0, icon_type='emoji', icon='🧩', icon_background='#E0F2FE')
    s.add(app); s.flush()
    w = Workflow.new(tenant_id=str(workspace), app_id=app.id, type='workflow', version='draft', graph=json.dumps(graph, ensure_ascii=False),
        features='{}', created_by=str(actor), environment_variables=[], conversation_variables=[], rag_pipeline_variables=[])
    s.add(w); s.flush()
    store.assign(s.connection(), access.authority(s)['tenant_id'], str(project), app.id)
    return record(s, scope, actor, key, digest, 'program.library.created', dict(app_id=app.id, workflow_id=w.id, name=app.name))


def binding_node(identity, value, choices):
    if not isinstance(value, str) or len(value) > 120000:
        raise BadRequest('متن ورودی ایجنت معتبر نیست.')
    variables = []; chunks = []; cursor = 0
    allowed = {v['value'] for v in choices}
    for match in SELECTOR.finditer(value):
        if match[0] not in allowed:
            raise BadRequest('ورودی ایجنت فقط می‌تواند از خروجی‌های پیش از همین مرحله استفاده کند.')
        chunks.append('{{ ' + repr(value[cursor:match.start()]) + ' }}')
        name = 'v' + str(len(variables)); chunks.append('{{ ' + name + ' }}')
        variables.append(dict(variable=name, value_selector=[match[1], *match[2].split('.')]))
        cursor = match.end()
    chunks.append('{{ ' + repr(value[cursor:]) + ' }}')
    if '{{#' in SELECTOR.sub('', value):
        raise BadRequest('انتخابگر ورودی معتبر نیست.')
    return dict(id=identity, type='custom', position=dict(x=0, y=0), data=dict(type='template-transform', title='ورودی ایجنت',
        template=''.join(chunks), variables=variables))


def modify(s, project, workspace, actor, app_id, target_id, data, key, *, detach=False):
    fields = ('draft_hash',) if detach else ('draft_hash', 'source_id', 'snapshot_id', 'source_digest', 'bindings')
    agents.body(data, fields)
    scope, app = authorize(s, project, workspace, actor, app_id); key = agents.action_key(key)
    digest = agents.digest(dict(operation='detach' if detach else 'attach', app_id=str(app_id), target=target_id, **data))
    previous = agents.replay(s, scope, actor, key, digest)
    if previous:
        return previous
    w = draft(s, app)
    if data['draft_hash'] != w.unique_hash:
        raise Conflict('پیش‌نویس هم‌زمان تغییر کرده است؛ اطلاعات برنامه را تازه کنید.')
    graph = deepcopy(w.graph_dict)
    target = next((n for n in graph['nodes'] if n['id'] == target_id and n['data']['type'] == 'llm'), None)
    if not target or target.get('parentId') or target['data'].get('isInIteration') or target['data'].get('isInLoop'):
        raise BadRequest('یک مرحلهٔ LLM مستقل انتخاب کنید.')
    if detach:
        pin = target['data'].get(PIN)
        if not pin:
            raise Conflict('این مرحله اتصال کتابخانه ندارد.')
        valid_pin(pin)
        if pin.get('original') is None:
            target['data'].pop(PIN)
        else:
            removed = set(pin['members']) - {target_id}
            outside = [n for n in graph['nodes'] if n['id'] not in set(pin['members'])]
            if any(m in json.dumps(n['data']) for n in outside for m in removed) or any(e['source'] in removed and e['target'] not in pin['members'] for e in graph['edges']):
                raise Conflict('مرحلهٔ دیگری به بخش دانش این ایجنت متصل است؛ ابتدا وابستگی را در طراح جدا کنید.')
            graph['nodes'] = [n for n in graph['nodes'] if n['id'] not in removed]
            graph['edges'] = [dict(e, target=target_id) if e['target'] in removed and e['source'] not in pin['members'] else e
                for e in graph['edges'] if e['source'] not in removed and not (e['target'] == target_id and e['source'] in removed)]
            target['data'] = deepcopy(pin['original'])
    else:
        if PIN in target['data']:
            raise Conflict('ابتدا اتصال فعلی این مرحله را جدا کنید.')
        if any(target_id in n['data'].get(PIN, {}).get('members', []) for n in graph['nodes']):
            raise Conflict('این مرحله بخشی از یک ایجنت متصل است؛ اتصال مرحلهٔ اصلی را مدیریت کنید.')
        compiled, meta = checked_source(s, workspace, actor, data['source_id'], data['snapshot_id'])
        if agents.digest([compiled, meta]) != data['source_digest']:
            raise Conflict('نسخهٔ منبع تغییر کرده است؛ بررسی را تازه کنید.')
        inputs = [v for v in compiled['nodes'][0]['data']['variables'] if v['variable'] != runtime_models.INPUT]
        if not isinstance(data['bindings'], dict) or set(data['bindings']) != {v['variable'] for v in inputs}:
            raise BadRequest('نگاشت همهٔ ورودی‌های ایجنت لازم است.')
        if any(v['required'] and not str(data['bindings'][v['variable']]).strip() for v in inputs):
            raise BadRequest('ورودی‌های الزامی ایجنت را مشخص کنید.')
        prefix = 'role_' + uuid4().hex[:16] + '_'
        adapters = [binding_node(prefix + v['variable'], data['bindings'][v['variable']], available(graph, target_id)) for v in inputs]
        mapping = {n['id']: target_id if n['id'] == 'task_agent' else prefix + n['id'] for n in compiled['nodes']}
        def rewrite(value):
            if isinstance(value, list):
                if len(value) >= 2 and value[0] == 'start' and value[1] in data['bindings']:
                    return [prefix + value[1], 'output', *value[2:]]
                if value and isinstance(value[0], str) and value[0] in mapping:
                    return [mapping[value[0]], *value[1:]]
                return [rewrite(v) for v in value]
            if isinstance(value, dict): return {k: rewrite(v) for k, v in value.items()}
            if isinstance(value, str):
                return SELECTOR.sub(lambda m: '{{#' + (prefix + m[2] + '.output' if m[1] == 'start' and m[2] in data['bindings'] else mapping.get(m[1], m[1]) + '.' + m[2]) + '#}}', value)
            return value
        body = [dict(n, id=mapping[n['id']], data=rewrite(n['data'])) for n in compiled['nodes'] if n['data']['type'] not in ('start', 'end')]
        group = adapters + body; original = deepcopy(target['data']); target['data'] = body[-1]['data']
        target['data']['title'] = original.get('title') or meta['name']
        # Keep the target id and outgoing links: downstream output selectors stay valid.
        graph['nodes'] = [n for n in graph['nodes'] if n['id'] != target_id] + group[:-1] + [target]
        graph['edges'] = [dict(e, target=group[0]['id']) if e['target'] == target_id else e for e in graph['edges']]
        graph['edges'] += [dict(id=prefix + str(i), source=a['id'], target=b['id'], sourceHandle='source', targetHandle='target', type='custom') for i, (a, b) in enumerate(zip(group, group[1:]))]
        for i, n in enumerate(group[:-1]):
            n.update(type='custom', position=dict(x=target.get('position', {}).get('x', 0) - 330 * (len(group) - 1 - i), y=target.get('position', {}).get('y', 0)))
        graph = runtime_models.enable_graph(graph)
        target = next(n for n in graph['nodes'] if n['id'] == target_id)
        members = [n['id'] for n in group]
        target['data'][PIN] = dict(version=1, source=meta, members=members, digest=block_digest(graph, members), original=original)
    from kara_source_runner.workflow_contract import validate_graph
    kinds = {n['id']: n['data']['type'] for n in graph['nodes']}
    for edge in graph['edges']:
        edge.setdefault('type', 'custom')
        edge.setdefault('data', {}).update(sourceType=kinds[edge['source']], targetType=kinds[edge['target']])
    try:
        validate_graph(graph)
    except ValueError as exc:
        raise BadRequest('این برنامه با Runner فعلی سازگار نیست: ' + str(exc)) from None
    if len(json.dumps(graph).encode()) > 2097152:
        raise BadRequest('تعریف برنامه بیش از دو مگابایت است.')
    w.graph = json.dumps(graph, ensure_ascii=False); w.updated_by = str(actor); w.updated_at = agents.now().replace(tzinfo=None)
    validate(s, w, actor); s.flush()
    return record(s, scope, actor, key, digest, 'program.library.detached' if detach else 'program.library.attached', dict(app_id=app.id, hash=w.unique_hash))
