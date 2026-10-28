"""Human-owned stage lifecycle over the existing pinned native execution outbox."""
import json
import os
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, HTTPException, NotFound, UnprocessableEntity

from company_projects import agents, flows, requests, team, stage_config
from company_projects.store import uid
from models.account import Tenant
from models.model import App
from models.workflow import Workflow

NAMES = ('instances', 'stages', 'stage_attempts', 'feedback', 'artifacts', 'stage_decisions')


def table(session, name):
    cache = session.info.setdefault('kara_stage_tables', {})
    if name not in cache:
        value = sa.Table(name, sa.MetaData(), autoload_with=session.connection(), resolve_fks=False)
        for column in value.c:
            if isinstance(column.type, sa.Uuid):
                column.type = sa.Uuid(as_uuid=False)
        cache[name] = value
    return cache[name]


def tables(session):
    return tuple(table(session, 'company_team_' + name) for name in NAMES)


def scoped(session, project, workspace, actor, *, write=False):
    return requests.scope(session, project, workspace, actor, write=write)


def load(session, entity, scope, identity, *, lock=False):
    row = requests.load(session, entity, scope, identity, lock=lock)
    return effective(row) if entity.name == 'company_team_stages' else row


def instance(session, scope, identity):
    return load(session, tables(session)[0], scope, identity)


def intake(session, value):
    """Never trust a cached HTTP result or an intake_valid supplied by a client."""
    scope = {k: value[k] for k in ('project_id', 'workspace_id')}
    header = load(session, table(session, 'company_team_requests'), scope, value['request_id'])
    revisions, decisions = table(session, 'company_team_request_revisions'), table(session, 'company_team_intake_decisions')
    revision = session.execute(sa.select(revisions).where(revisions.c.id == value['request_revision_id'],
        revisions.c.request_id == value['request_id'], *(revisions.c[k] == v for k, v in scope.items()))).mappings().first()
    decision = session.execute(sa.select(decisions).where(decisions.c.id == value['intake_decision_id'],
        decisions.c.request_id == value['request_id'], *(decisions.c[k] == v for k, v in scope.items()))).mappings().first()
    if not revision or not decision or header['current_revision_id'] != value['request_revision_id'] or (
            header['current_decision_id'] != decision['id'] or decision['outcome'] != 'approved' or decision['mode'] != 'real'
            or decision['request_revision_id'] != revision['id'] or decision['request_digest'] != revision['digest']
            or value['request_digest'] != revision['digest'] or decision['flow_id'] != value['flow_id']
            or decision['flow_version_id'] != value['flow_version_id'] or decision['flow_digest'] != value['flow_digest']
            or (decision['expires_at'] is not None and decision['expires_at'] <= agents.now())):
        raise Conflict('تصمیم ورود یا نسخهٔ درخواست دیگر معتبر نیست؛ تصمیم تازهٔ PO لازم است.')
    version = flows.version(session, scope, value['flow_id'], value['flow_version_id'])
    if version['digest'] != value['flow_digest']:
        raise Conflict('مرجع نسخهٔ فلو تغییر کرده است.')
    return dict(revision)


def valid_intake(session, value):
    try:
        intake(session, value)
        return True
    except HTTPException:
        return False


def effective(row):
    value = dict(row)
    if value.get('assignment'):
        value['binding'] = dict(value['binding'], **value['assignment'])
    return value


def stage_rows(session, value):
    stages = tables(session)[1]
    return [effective(row) for row in session.execute(sa.select(stages).where(stages.c.instance_id == value['id'])
        .order_by(stages.c.ordinal)).mappings()]


def summary(session, value, actor):
    from company_projects.team_inbox import responsibility
    from company_projects.recovery import cancellation
    rows = stage_rows(session, value)
    revision = table(session, 'company_team_request_revisions')
    title = session.scalar(sa.select(revision.c.title).where(revision.c.id == value['request_revision_id']))
    cancelled = cancellation(session, value)
    valid = valid_intake(session, value)
    current = next((row for row in rows if row['state'] != 'completed'), None)
    scope = {k: value[k] for k in ('project_id', 'workspace_id')}
    return requests.serial(value) | dict(title=title, intake_valid=valid,
        state='cancelled' if cancelled else 'completed' if rows and not current else 'active',
        revision=sum(row['revision'] for row in rows), cancellation=requests.serial(cancelled) if cancelled else None,
        completed_stages=sum(row['state'] == 'completed' for row in rows), total_stages=len(rows),
        current_stage_id=current['id'] if current else None,
        responsibility=dict(kind='cancelled', person=None, reason=cancelled['reason']) if cancelled else responsibility(session, scope, current, valid),
        stages=[dict(id=row['id'], key=row['step_key'], title=row['binding']['title'], state=row['state'],
            revision=row['revision'], executor=row['binding']['executor'], finalizer=row['binding']['finalizer']) for row in rows])


def list_instances(session, project, workspace, actor):
    scope = scoped(session, project, workspace, actor)
    entity = tables(session)[0]
    values = [summary(session, row, actor) for row in session.execute(sa.select(entity)
        .where(*(entity.c[k] == v for k, v in scope.items())).order_by(entity.c.created_at.desc())).mappings()]
    used = {value['intake_decision_id'] for value in values}
    available = []
    for request in requests.list_requests(session, project, workspace, actor)['data']:
        if not request['intake_valid'] or request['current_decision_id'] in used:
            continue
        decision = request['decision']
        if flows.load(session, scope, decision['flow_id'])['archived']:
            continue
        allowed = requests.is_po(session, scope, actor)
        if not allowed:
            version = flows.version(session, scope, decision['flow_id'], decision['flow_version_id'])
            first = version['stage_bindings'][0]
            try:
                _, join = stage_config.require(session, scope, first, actor, 'run')
                allowed = first['executor']['account_id'] == str(actor) and first['executor']['membership_id'] == join.id
            except HTTPException:
                pass
        if allowed:
            available.append(dict(id=request['id'], title=request['title'], revision=request['revision'],
                intake_decision_id=request['current_decision_id']))
    return dict(data=values, available_requests=available)


def create(session, project, workspace, actor, data, key):
    agents.body(data, ('request_id', 'intake_decision_id', 'expected_revision'))
    key, expected = agents.action_key(key), agents.revision(data['expected_revision'])
    request_id, decision_id = uid(data['request_id']), uid(data['intake_decision_id'])
    scope = scoped(session, project, workspace, actor, write=True)
    request = load(session, table(session, 'company_team_requests'), scope, request_id, lock=True)
    decisions = table(session, 'company_team_intake_decisions')
    decision = session.execute(sa.select(decisions).where(decisions.c.id == decision_id,
        decisions.c.request_id == request_id, *(decisions.c[k] == v for k, v in scope.items()))).mappings().first()
    if not decision:
        raise NotFound('تصمیم ورود در این درخواست پیدا نشد.')
    if not decision['flow_version_id']:
        raise Conflict('تأیید ورود معتبر لازم است.')
    value = dict(id=str(uuid4()), **scope, request_id=request_id, request_revision_id=decision['request_revision_id'],
        intake_decision_id=decision_id, flow_id=decision['flow_id'], flow_version_id=decision['flow_version_id'],
        request_digest=decision['request_digest'], flow_digest=decision['flow_digest'], created_by=str(actor), created_at=agents.now())
    intake(session, value)
    version = flows.version(session, scope, value['flow_id'], value['flow_version_id'])
    if flows.load(session, scope, value['flow_id'])['archived']:
        raise Conflict('برای فلو بایگانی‌شده اجرای تازه ایجاد نمی‌شود.')
    first = version['stage_bindings'][0]
    if not requests.is_po(session, scope, actor):
        _, join = stage_config.require(session, scope, first, actor, 'run')
        if first['executor']['account_id'] != str(actor) or first['executor']['membership_id'] != join.id:
            raise Forbidden('ایجاد اجرا با PO یا اجراکنندهٔ مرحلهٔ اول است.')
    fingerprint = agents.digest(dict(operation='instance.create', body=data))
    replay = agents.replay(session, scope, actor, key, fingerprint)
    if replay:
        return replay
    if request['revision'] != expected:
        raise Conflict('نسخهٔ درخواست تغییر کرده است.')
    instances, stages, *_ = tables(session)
    if session.scalar(sa.select(instances.c.id).where(instances.c.intake_decision_id == decision_id)):
        raise Conflict('این تصمیم ورود قبلاً اجرای تیمی دارد؛ همان اجرا را باز کنید.')
    session.execute(instances.insert().values(**value))
    session.execute(stages.insert(), [dict(id=str(uuid4()), instance_id=value['id'], **scope, ordinal=index,
        step_key=binding['key'], binding=binding, revision=1, round=1, state='ready' if index == 0 else 'blocked',
        inputs=None, dependencies=None, input_digest=None, active_attempt_id=None, selected_artifact_id=None,
        updated_at=agents.now()) for index, binding in enumerate(version['stage_bindings'])])
    result = summary(session, value, actor)
    agents.event(session, scope, actor, key, fingerprint, 'instance.created', result)
    return result


def require(session, scope, stage, actor, action):
    binding = stage['binding']
    agent, join = stage_config.require(session, scope, binding, actor, action)
    if action in ('run', 'finalize'):
        person = binding['executor' if action == 'run' else 'finalizer']
        if person['account_id'] != str(actor) or person['membership_id'] != join.id:
            raise Forbidden('این اقدام با مسئول تعیین‌شده و عضویت فعلی همان مرحله است.')
    if action == 'finalize' and binding['decision_role'] and binding['decision_role'] not in team.get_roles(
            session, scope['project_id'], scope['workspace_id'], actor, actor)['roles']:
        raise Forbidden('نقش کاری لازم برای نهایی‌سازی را ندارید.')
    workflow, app = session.get(Workflow, binding['workflow_id']), session.get(App, agent['app_id'])
    if agent['workflow_id'] != binding['workflow_id'] or agent['revision'] != binding['agent_revision'] or (
            agent['workflow_digest'] != binding['workflow_digest'] or not workflow or not app or app.status != 'normal'
            or app.mode != 'workflow' or workflow.app_id != app.id or app.tenant_id != scope['workspace_id']
            or workflow.tenant_id != scope['workspace_id'] or agents.fingerprint(workflow) != binding['workflow_digest']):
        raise Conflict('نسخهٔ ایجنت با نسخهٔ ثابت مرحله یکسان نیست.')
    return agent, join


def resolve(session, value, stage):
    request = intake(session, value)
    rows = stage_rows(session, value)
    previous = [row for row in rows if row['ordinal'] < stage['ordinal']]
    artifacts = tables(session)[4]
    outputs, dependencies = {}, []
    for row in previous:
        if row['state'] != 'completed' or not row['selected_artifact_id']:
            raise Conflict('پیش‌نیاز مرحله هنوز نهایی نشده است.')
        artifact = session.execute(sa.select(artifacts).where(artifacts.c.id == row['selected_artifact_id'],
            artifacts.c.stage_id == row['id'])).mappings().one()
        if artifact['input_digest'] != row['input_digest'] or artifact['round'] != row['round']:
            raise Conflict('خروجی پیش‌نیاز قدیمی است.')
        outputs[row['step_key']] = artifact['content']
        dependencies.append(dict(stage_id=row['id'], artifact_id=artifact['id'], digest=artifact['digest']))
    if stage['inputs'] is not None:
        if stage['dependencies'] != dependencies:
            raise Conflict('خروجی‌های مصرف‌شده تغییر کرده‌اند.')
        return stage['inputs'], dependencies
    inputs = agents.input_defaults(stage['binding']['input_contract'], {})
    for name, source in stage['binding']['inputs'].items():
        if source['source'] == 'request':
            inputs[name] = request['content']
        elif source['source'] == 'constant':
            inputs[name] = source['value']
        else:
            try:
                inputs[name] = outputs[source['stage_key']][source['output']]
            except KeyError:
                raise UnprocessableEntity('خروجی لازم در مرحلهٔ قبلی وجود ندارد.') from None
    return inputs, dependencies


def input_digest(value, stage, inputs, dependencies, feedback=None):
    return agents.digest(dict(request_revision_id=value['request_revision_id'], request_digest=value['request_digest'],
        flow_version_id=value['flow_version_id'], flow_digest=value['flow_digest'], binding=stage['binding'],
        round=stage['round'], inputs=inputs, dependencies=dependencies, feedback=feedback))


def request_inputs(stage):
    return {name for name, source in stage['binding']['inputs'].items() if source['source'] == 'request'}


def validate_request_inputs(session, value, stage, inputs):
    original = intake(session, value)['content']
    if any(inputs.get(name) != original for name in request_inputs(stage)):
        raise Conflict('متن اصلی درخواست در بازخورد تغییر نمی‌کند؛ برای تغییر نیازمندی نسخهٔ تازهٔ درخواست و تصمیم ورود تازه لازم است.')


def artifact(session, stage, identity):
    artifacts = tables(session)[4]
    row = session.execute(sa.select(artifacts).where(artifacts.c.id == uid(identity), artifacts.c.stage_id == stage['id'])).mappings().first()
    if not row:
        raise NotFound('خروجی در این مرحله پیدا نشد.')
    if row['round'] != stage['round'] or row['input_digest'] != stage['input_digest']:
        raise Conflict('خروجی متعلق به ورودی یا دور فعلی نیست.')
    return dict(row)


def validate_output(binding, content):
    if not isinstance(content, dict) or set(content) != set(binding['output_contract']):
        raise BadRequest('خروجی باید همهٔ نام‌های قرارداد همین مرحله را داشته باشد.')
    agents.digest(content)
    try:
        limit = max(1024, min(int(os.environ.get('KARA_TEAM_ARTIFACT_MAX_BYTES', '262144')), 16777216))
    except ValueError:
        limit = 262144
    if len(json.dumps(content, ensure_ascii=False).encode()) > limit:
        raise BadRequest('حجم خروجی بیش از سقف مجاز است.')


def new_artifact(session, stage, content, actor, membership, attempt_id, *, parent=None, reason=''):
    artifacts = tables(session)[4]
    validate_output(stage['binding'], content)
    from company_projects.harness import is_attempt
    kind = 'human' if parent else 'harness' if is_attempt(session,attempt_id) else 'workflow'
    version = (session.scalar(sa.select(sa.func.max(artifacts.c.version)).where(artifacts.c.stage_id == stage['id'])) or 0) + 1
    row = dict(id=str(uuid4()), stage_id=stage['id'], project_id=stage['project_id'], workspace_id=stage['workspace_id'],
        version=version, round=stage['round'], input_digest=stage['input_digest'], content=content, kind=kind,
        digest=agents.digest(dict(content=content, input_digest=stage['input_digest'], kind=kind, parent_id=parent)),
        attempt_id=attempt_id, parent_id=parent, author_id=str(actor), membership_id=membership, reason=reason, created_at=agents.now())
    session.execute(artifacts.insert().values(**row))
    return row


def available_actions(session, scope, value, stage, actor, *, input_error=None):
    """One fresh authority/state check for the detail page and personal inbox."""
    result = []
    allowed = dict(run=('ready', 'run'), retry=('failed', 'run'), feedback=(('ready', 'failed', 'awaiting_feedback', 'awaiting_decision'), 'feedback'),
        edit_output=(('awaiting_feedback', 'awaiting_decision'), 'feedback'), request_decision=('awaiting_feedback', 'feedback'), finalize=('awaiting_decision', 'finalize'))
    from company_projects.recovery import cancellation, retry_limit
    if not cancellation(session, value) and valid_intake(session, value):
        for action, (states, permission) in allowed.items():
            if stage['state'] not in ((states,) if isinstance(states, str) else states):
                continue
            try:
                require(session, scope, stage, actor, permission)
                if action == 'retry' and stage.get('retry_count', 0) >= retry_limit():
                    continue
                if not input_error or action == 'feedback':
                    result.append(action)
            except HTTPException:
                pass
    if stage['state'] == 'stale' and not cancellation(session, value) and valid_intake(session, value) and not input_error:
        try:
            require(session, scope, stage, actor, 'run')
            result.append('revalidate')
        except HTTPException:
            pass
    return result


def get_stage(session, project, workspace, actor, instance_id, stage_id):
    scope = scoped(session, project, workspace, actor)
    from company_projects.harness import expire as expire_harness
    expire_harness(session,project=project)
    value = instance(session, scope, instance_id)
    stage = load(session, tables(session)[1], scope, stage_id)
    if stage['instance_id'] != value['id']:
        raise NotFound('مرحله در این اجرا پیدا نشد.')
    agent = agents.load(session, scope, stage['binding']['agent_id'], _stage=True)
    from company_projects.runtime_models import policy, llm_nodes
    source_graph = session.get(Workflow, agent['workflow_id']).graph_dict
    runtime_model = policy(source_graph) if llm_nodes(source_graph) else None
    permissions = stage_config.permissions(session, scope, stage['binding'], actor) if stage_config.owned(stage['binding']) else agents.permissions(session, agent, actor)
    if not set(permissions) & {'view', 'run', 'feedback', 'finalize'}:
        raise Forbidden('مجوز مشاهدهٔ محتوای این مرحله را ندارید.')
    bridge, feedback, artifacts, decisions = tables(session)[2:]
    native = table(session, 'company_team_agent_attempts')
    attempts = session.execute(sa.select(bridge.c.attempt_id, bridge.c.round, bridge.c.input_digest,
        native.c.status, native.c.actor_id, native.c.created_at).join(native, native.c.id == bridge.c.attempt_id)
        .where(bridge.c.stage_id == stage['id']).order_by(bridge.c.created_at)).mappings()
    result = requests.serial(stage) | dict(runtime_model=runtime_model, intake_valid=valid_intake(session, value), actions=[], preview_inputs={}, input_error=None,
        editable_inputs={}, attempts=[requests.serial(row) for row in attempts],
        feedback=[requests.serial(row) for row in session.execute(sa.select(feedback).where(feedback.c.stage_id == stage['id']).order_by(feedback.c.round)).mappings()],
        artifacts=[requests.serial(row) for row in session.execute(sa.select(artifacts).where(artifacts.c.stage_id == stage['id']).order_by(artifacts.c.version.desc())).mappings()],
        decisions=[requests.serial(row) for row in session.execute(sa.select(decisions).where(decisions.c.stage_id == stage['id']).order_by(decisions.c.created_at)).mappings()])
    try:
        result['preview_inputs'], _ = resolve(session, value, stage)
        current_feedback = [row for row in result['feedback'] if row['round'] == stage['round']]
        result['editable_inputs'] = current_feedback[-1]['inputs']['submitted'] if current_feedback else result['preview_inputs']
        validate_request_inputs(session, value, stage, result['preview_inputs'])
        agents.validate_inputs(stage['binding']['input_contract'], result['preview_inputs'])
    except HTTPException as exc:
        result['input_error'] = exc.description
    result['actions'] = available_actions(session, scope, value, stage, actor, input_error=result['input_error'])
    from company_projects.recovery import stage_controls
    result['controls'] = stage_controls(session, scope, value, stage, actor)
    from company_projects.team_inbox import handoffs
    result['handoffs'] = handoffs(session, value, stage) if not result['input_error'] else []
    from company_projects import harness
    result['harness'] = harness.stage_info(session,stage,actor)
    cfg = stage['binding'].get('execution') or dict(harness.policy(session, agent), program_enabled=True)
    reason = harness.compatible(session, agent)
    result['execution_policy'] = dict(policy={k: cfg[k] for k in ('revision', 'program_enabled', 'enabled', 'instructions', 'requires_source')},
        compatible=reason is None, reason=reason, can_manage=False, output_contract=agent['output_contract'], workflow_digest=agent['workflow_digest'])
    return result


def mutate(session, project, workspace, actor, instance_id, stage_id, action, data, key):
    fields = dict(run=(), retry=(), feedback=('artifact_id', 'message', 'inputs', 'feedback_variable'),
        edit_output=('artifact_id', 'content', 'reason'), request_decision=('artifact_id',), finalize=('artifact_id', 'reason'))
    if action not in fields:
        raise BadRequest('اقدام مرحله معتبر نیست.')
    optional_execution = ('execution',) if action=='run' and isinstance(data,dict) and 'execution' in data else ()
    optional_model = ('model_connection_id',) if action == 'run' and isinstance(data, dict) and 'model_connection_id' in data else ()
    agents.body(data, ('expected_revision', *fields[action], *optional_model, *optional_execution))
    expected, key = agents.revision(data['expected_revision']), agents.action_key(key)
    scope = scoped(session, project, workspace, actor, write=True)
    value = instance(session, scope, instance_id)
    stage = load(session, tables(session)[1], scope, stage_id, lock=True)
    if stage['instance_id'] != value['id']:
        raise NotFound('مرحله در این اجرا پیدا نشد.')
    permission = 'run' if action in ('run', 'retry') else 'finalize' if action == 'finalize' else 'feedback'
    agent, join = require(session, scope, stage, actor, permission)
    from company_projects.recovery import ensure_active, retry_limit
    ensure_active(session, value)
    intake(session, value)
    fingerprint = agents.digest(dict(operation='stage.' + action, instance_id=str(instance_id), stage_id=str(stage_id), body=data))
    replay = agents.replay(session, scope, actor, key, fingerprint)
    if replay:
        return replay
    if stage['revision'] != expected:
        raise Conflict('مرحله تغییر کرده است؛ نسخهٔ تازه را دریافت کنید.')
    instances, stages, bridge, feedback, artifacts, decisions = tables(session)
    states = dict(run=('ready',), retry=('failed',), feedback=('ready', 'failed', 'awaiting_feedback', 'awaiting_decision'),
        edit_output=('awaiting_feedback', 'awaiting_decision'), request_decision=('awaiting_feedback',), finalize=('awaiting_decision',))
    if stage['state'] not in states[action]:
        raise Conflict('این اقدام در وضعیت فعلی مرحله مجاز نیست.')
    inputs, dependencies = resolve(session, value, stage)
    if action != 'feedback':
        validate_request_inputs(session, value, stage, inputs)
    changes = dict(revision=expected + 1, updated_at=agents.now())
    if action == 'run':
        agents.validate_inputs(stage['binding']['input_contract'], inputs)
        digest = stage['input_digest'] or input_digest(value, stage, inputs, dependencies)
        # The outer journal owns replay. A fresh server-only key prevents a
        # client from pre-creating/reusing a standalone attempt for this stage.
        inner_key = str(uuid4())
        from company_projects.runtime_models import INPUT
        run_inputs = dict(inputs, **{INPUT: data['model_connection_id']}) if optional_model else inputs
        attempt = agents.start(session, project, workspace, actor, agent['id'],
            dict(inputs=run_inputs, expected_revision=stage['binding']['agent_revision'], **({'execution':data['execution']} if optional_execution else {})), inner_key, _stage=stage)
        session.execute(bridge.insert().values(attempt_id=attempt['id'], stage_id=stage['id'], **scope,
            round=stage['round'], input_digest=digest, created_at=agents.now()))
        from company_projects.harness import bind_stage
        bind_stage(session,attempt['id'],stage,value,digest,dependencies)
        changes.update(state='running', active_attempt_id=attempt['id'], inputs=inputs, dependencies=dependencies,
            input_digest=digest, selected_artifact_id=None)
    elif action == 'retry':
        if stage['retry_count'] >= retry_limit():
            raise Conflict('سقف تلاش مجدد این دور رسیده است؛ بررسی و بازیابی صریح مدیر لازم است.')
        changes['retry_count'] = stage['retry_count'] + 1
        changes.update(state='ready', active_attempt_id=None, selected_artifact_id=None)
    elif action == 'feedback':
        message = data['message']
        if not isinstance(message, str) or not message.strip() or len(message) > 8000:
            raise BadRequest('بازخورد لازم و حداکثر ۸۰۰۰ نویسه است.')
        parent = artifact(session, stage, data['artifact_id']) if data['artifact_id'] is not None else None
        if stage['state'] in ('awaiting_feedback', 'awaiting_decision') and not parent:
            raise BadRequest('خروجی مبنای بازخورد را انتخاب کنید.')
        agents.validate_inputs(stage['binding']['input_contract'], data['inputs'])
        validate_request_inputs(session, value, stage, data['inputs'])
        variable = data['feedback_variable']
        textual = {item['variable'] for item in stage['binding']['input_contract'] if item['type'] in ('text-input', 'paragraph')}
        if isinstance(variable, str) and variable in request_inputs(stage):
            raise BadRequest('بازخورد باید ورودی متنی جدا از متن اصلی درخواست داشته باشد.')
        if variable is not None and (not isinstance(variable, str) or variable not in textual):
            raise BadRequest('برای بازخورد، یک ورودی متنی معتبر انتخاب کنید.')
        if parent and textual and variable is None:
            raise BadRequest('ورودی متنی دریافت‌کنندهٔ بازخورد را انتخاب کنید.')
        effective = dict(data['inputs'])
        if variable:
            history = list(session.scalars(sa.select(feedback.c.message).where(feedback.c.stage_id == stage['id'],
                feedback.c.round >= stage['feedback_floor']).order_by(feedback.c.round)))
            context = dict(previous_output=parent['content'] if parent else None, feedback_history=[*history, message])
            effective[variable] = str(effective.get(variable) or '') + '\n\nبازخورد انسانی و خروجی مبنا:\n' + json.dumps(context, ensure_ascii=False)
        agents.validate_inputs(stage['binding']['input_contract'], effective)
        validate_request_inputs(session, value, stage, effective)
        feedback_id = str(uuid4())
        digest = input_digest(value, dict(stage, round=stage['round'] + 1), effective, dependencies,
            dict(id=feedback_id, previous_digest=stage['input_digest'], message=message, parent_id=parent['id'] if parent else None))
        session.execute(feedback.insert().values(id=feedback_id, stage_id=stage['id'], **scope, base_revision=expected,
            round=stage['round'] + 1, parent_artifact_id=parent['id'] if parent else None, message=message,
            inputs=dict(submitted=data['inputs'], effective=effective, feedback_variable=variable),
            input_digest=digest, author_id=str(actor), membership_id=join.id, created_at=agents.now()))
        changes.update(state='ready', round=stage['round'] + 1, retry_count=0, inputs=effective, dependencies=dependencies,
            input_digest=digest, active_attempt_id=None, selected_artifact_id=None)
    else:
        selected = artifact(session, stage, data['artifact_id'])
        if action in ('edit_output', 'finalize') and (not isinstance(data['reason'], str)
                or not data['reason'].strip() or len(data['reason']) > 2000):
            raise BadRequest('علت لازم و حداکثر ۲۰۰۰ نویسه است.')
        from company_projects import output_validation
        normalized, validation_proof = output_validation.validate(session, stage, selected,
            data['content'] if action == 'edit_output' else selected['content'])
        if action != 'edit_output' and normalized != selected['content']:
            raise Conflict('خروجی منتخب با نتیجهٔ اعتبارسنج یکسان نیست؛ ویرایش تازه ثبت کنید.')
        if action == 'edit_output':
            edited = new_artifact(session, stage, normalized, actor, join.id, selected['attempt_id'], parent=selected['id'], reason=data['reason'])
            if validation_proof:
                validation_proof.update(parent_artifact_id=selected['id'], artifact_id=edited['id'])
            changes.update(state='awaiting_feedback', selected_artifact_id=None)
        elif action == 'request_decision':
            changes.update(state='awaiting_decision', selected_artifact_id=selected['id'])
        else:
            if stage['selected_artifact_id'] != selected['id']:
                raise Conflict('فقط خروجی منتخبِ درخواست تصمیم قابل نهایی‌سازی است.')
            session.execute(decisions.insert().values(id=str(uuid4()), stage_id=stage['id'], **scope, base_revision=expected,
                artifact_id=selected['id'], input_digest=stage['input_digest'], actor_id=str(actor), membership_id=join.id,
                reason=data['reason'], created_at=agents.now()))
            changes.update(state='completed', selected_artifact_id=selected['id'])
            session.execute(stages.update().where(stages.c.instance_id == value['id'], stages.c.ordinal == stage['ordinal'] + 1,
                stages.c.state == 'blocked').values(state='ready', revision=stages.c.revision + 1, updated_at=agents.now()))
    session.execute(stages.update().where(stages.c.id == stage['id']).values(**changes))
    result = get_stage(session, project, workspace, actor, instance_id, stage_id)
    if action in ('edit_output', 'request_decision', 'finalize') and validation_proof:
        result['output_validation'] = validation_proof
    agents.event(session, scope, actor, key, fingerprint, 'stage.' + action, result)
    return result


def validate_attempt(session, attempt):
    """Additional guard for stage-bound native attempts; standalone KP-02 stays intact."""
    bridge = tables(session)[2]
    link = session.execute(sa.select(bridge).where(bridge.c.attempt_id == attempt['id'])).mappings().first()
    if not link:
        return None
    scope = {k: attempt[k] for k in ('project_id', 'workspace_id')}
    stage = load(session, tables(session)[1], scope, link['stage_id'])
    value = instance(session, scope, stage['instance_id'])
    from company_projects.recovery import ensure_active
    ensure_active(session, value)
    intake(session, value)
    require(session, scope, stage, attempt['actor_id'], 'run')
    inputs, _ = resolve(session, value, stage)
    validate_request_inputs(session, value, stage, inputs)
    if stage['active_attempt_id'] != attempt['id'] or stage['state'] != 'running' or (
            stage['round'] != link['round'] or stage['input_digest'] != link['input_digest']
            or inputs != __import__('company_projects.runtime_models', fromlist=['business_inputs']).business_inputs(attempt['inputs']) or stage['binding']['workflow_id'] != attempt['workflow_id']):
        raise Conflict('نتیجه یا تلاش متعلق به ورودی فعال مرحله نیست.')
    return stage


def complete_attempt(session, attempt_id):
    native = table(session, 'company_team_agent_attempts')
    attempt = session.execute(sa.select(native).where(native.c.id == str(attempt_id))).mappings().first()
    if not attempt or attempt['status'] not in ('succeeded', 'failed', 'blocked', 'interrupted'):
        return
    bridge = tables(session)[2]
    link = session.execute(sa.select(bridge).where(bridge.c.attempt_id == str(attempt_id))).mappings().first()
    if not link:
        return
    session.scalar(sa.select(Tenant).where(Tenant.id == attempt['workspace_id']).with_for_update())
    scope = {k: attempt[k] for k in ('project_id', 'workspace_id')}
    stages = tables(session)[1]
    stage = load(session, stages, scope, link['stage_id'], lock=True)
    if stage['active_attempt_id'] != attempt['id'] or stage['state'] != 'running':
        return  # Re-delivery or late completion never replaces a newer round/output.
    state = 'failed'
    try:
        validate_attempt(session, attempt)
        if attempt['status'] == 'succeeded':
            new_artifact(session, stage, (attempt['result'] or {}).get('outputs'), attempt['actor_id'], attempt['membership_id'], attempt['id'])
            state = 'awaiting_feedback'
    except BadRequest:
        state = 'failed'
    except HTTPException:
        state = 'stale'
    session.execute(stages.update().where(stages.c.id == stage['id']).values(state=state,
        active_attempt_id=None, selected_artifact_id=None, revision=stage['revision'] + 1, updated_at=agents.now()))
