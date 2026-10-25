"""Pinned team agents. All authority comes from native sessions and memberships."""
import hashlib
import json
import math
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import access, store, team
from models.account import Account, AccountStatus
from models.model import App
from models.workflow import Workflow, WorkflowRun

ACTIONS = ('view', 'run', 'feedback', 'finalize', 'edit_definition', 'publish_definition')


def tables(session):
    return tuple(reflected(session, 'company_team_agent_' + name)
        for name in ('grants', 'events', 'attempts'))


def definitions(session):
    return reflected(session, 'company_team_agents')


def reflected(session, name):
    table = sa.Table(name, sa.MetaData(), autoload_with=session.connection())
    for column in table.c:
        if isinstance(column.type, sa.Uuid):
            column.type = sa.Uuid(as_uuid=False)
    return table


def now():
    return datetime.now(timezone.utc)


def digest(value):
    try:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    except (ValueError, TypeError, UnicodeError):
        raise BadRequest('ورودی JSON معتبر نیست.') from None


def body(data, fields):
    if not isinstance(data, dict) or set(data) != set(fields):
        raise BadRequest('فیلدهای درخواست معتبر نیستند.')


def revision(value):
    if type(value) is not int or value < 1:
        raise BadRequest('نسخهٔ مبنا معتبر نیست.')
    return value


def action_key(value):
    key = store.uid(value)
    if key != value:
        raise BadRequest('شناسهٔ اقدام باید UUID استاندارد باشد.')
    return key


def fingerprint(workflow):
    # Hash encrypted environment storage, never expose it or graph/prompt content.
    return digest([workflow.graph, workflow._features, workflow._environment_variables,
        workflow._conversation_variables, workflow._rag_pipeline_variables, workflow.type])


def contracts(workflow):
    nodes = workflow.graph_dict.get('nodes', [])
    starts = [node for node in nodes if node.get('data', {}).get('type') == 'start']
    if len(starts) != 1 or any(node.get('data', {}).get('type', '').startswith('trigger-') or
            node.get('data', {}).get('type') in {'human-input', 'agent'} for node in nodes):
        raise UnprocessableEntity('فرایند باید شروع دستی داشته باشد؛ شروع خودکار، ایجنت داخلی و فرم تصمیم هنوز در ایجنت تیمی پشتیبانی نمی‌شوند.')
    values = starts[0]['data'].get('variables', [])
    result = []
    for item in values:
        kind, name = item.get('type'), item.get('variable')
        from company_projects.runtime_models import INPUT, policy
        if name == INPUT:
            policy(workflow.graph_dict)
            continue
        if kind not in {'text-input', 'paragraph', 'select', 'number', 'checkbox'} or not isinstance(name, str) or not name or name.startswith('sys.'):
            raise UnprocessableEntity('نوع ورودی این فرایند برای اجرای تیمی پشتیبانی نمی‌شود.')
        result.append(dict(variable=name, label=item.get('label') or name, type=kind,
            required=bool(item.get('required')), max_length=item.get('max_length'), options=item.get('options', [])))
    if len({item['variable'] for item in result}) != len(result):
        raise UnprocessableEntity('نام ورودی‌ها باید یکتا باشد.')
    outputs = sorted({item['variable'] for node in nodes if node.get('data', {}).get('type') == 'end'
        for item in node['data'].get('outputs', []) if isinstance(item.get('variable'), str)})
    if not outputs:
        raise UnprocessableEntity('خروجی فرایند را پیش از ثبت ایجنت مشخص کنید.')
    from company_projects.output_validation import definition
    definition(workflow)
    return result, outputs


def load(session, scope, agent_id, *, lock=False):
    table = definitions(session)
    query = sa.select(table).where(table.c.id == store.uid(agent_id),
        *(table.c[k] == v for k, v in scope.items()))
    row = session.execute(query.with_for_update() if lock else query).mappings().first()
    if row is None:
        raise NotFound('ایجنت در این پروژه پیدا نشد.')
    return dict(row)


def permissions(session, agent, actor_id):
    join = access.membership(session, agent['workspace_id'], actor_id)
    if join is None:
        return []
    grants, _, _ = tables(session)
    return sorted(session.scalars(sa.select(grants.c.action).where(grants.c.agent_id == agent['id'],
        grants.c.account_id == str(actor_id), grants.c.membership_id == join.id)))


def require(session, agent, actor_id, action):
    team.scope(session, agent['project_id'], agent['workspace_id'], actor_id)
    if action not in permissions(session, agent, actor_id) or agent['archived']:
        raise Forbidden('مجوز این اقدام برای ایجنت را ندارید یا ایجنت بایگانی شده است.')
    return team.member(session, agent['workspace_id'], actor_id)


def public(session, row, actor_id):
    from company_projects.runtime_models import policy, llm_nodes
    source = session.get(Workflow, row['workflow_id'])
    return {k: row[k] for k in ('id', 'name', 'description', 'app_id', 'workflow_id', 'revision',
        'acl_revision', 'archived', 'input_contract', 'output_contract')} | {
        'actions': permissions(session, row, actor_id), 'runtime_model': policy(source.graph_dict) if source and llm_nodes(source.graph_dict) else None}


def list_agents(session, project_id, workspace_id, actor_id):
    scope = team.scope(session, project_id, workspace_id, actor_id)
    manager = access.can_manage_members(session, workspace_id, actor_id)
    table = definitions(session)
    rows = session.execute(sa.select(table).where(*(table.c[k] == v for k, v in scope.items()))
        .order_by(table.c.created_at, table.c.id)).mappings()
    return dict(can_manage=manager, data=[public(session, row, actor_id) for row in rows
        if manager or permissions(session, row, actor_id)])


def sources(session, project_id, workspace_id, actor_id):
    team.scope(session, project_id, workspace_id, actor_id, write=True)
    rows = session.execute(sa.select(App, Workflow).join(Workflow, sa.and_(Workflow.app_id == App.id,
        Workflow.tenant_id == App.tenant_id)).where(App.tenant_id == str(workspace_id), App.mode == 'workflow',
        App.status == 'normal', Workflow.version != 'draft').order_by(App.name, Workflow.created_at.desc()))
    result = []
    for app, workflow in rows:
        try:
            inputs, outputs = contracts(workflow)
        except UnprocessableEntity:
            continue
        result.append(dict(app_id=app.id, app_name=app.name, workflow_id=workflow.id,
            version=workflow.marked_name or workflow.version, input_contract=inputs, output_contract=outputs))
    return dict(data=result)


def replay(session, scope, actor_id, key, request_digest):
    _, events, _ = tables(session)
    row = session.execute(sa.select(events).where(*(events.c[k] == v for k, v in scope.items()),
        events.c.actor_id == str(actor_id), events.c.correlation_id == key)).mappings().first()
    if row:
        if row['request_digest'] != request_digest:
            raise Conflict('این شناسهٔ اقدام قبلاً برای درخواست دیگری استفاده شده است.')
        return row['result']


def event(session, scope, actor_id, key, request_digest, kind, result):
    _, events, _ = tables(session)
    session.execute(events.insert().values(id=str(uuid4()), **scope, actor_id=str(actor_id),
        correlation_id=key, request_digest=request_digest, event_type=kind, result=result, occurred_at=now()))


def register(session, project_id, workspace_id, actor_id, data, key):
    body(data, ('app_id', 'workflow_id', 'name', 'description', 'expected_revision'))
    if revision(data['expected_revision']) != 1:
        raise Conflict('نسخهٔ آغاز تعریف باید یک باشد.')
    for field, limit in (('name', 120), ('description', 2000)):
        if not isinstance(data[field], str) or len(data[field]) > limit or (field == 'name' and not data[field].strip()):
            raise BadRequest('نام و توضیح ایجنت معتبر نیست.')
    key = action_key(key)
    scope = team.scope(session, project_id, workspace_id, actor_id, write=True)
    request_digest = digest(dict(operation='register', **data))
    previous = replay(session, scope, actor_id, key, request_digest)
    if previous:
        return previous
    app = session.scalar(sa.select(App).where(App.id == store.uid(data['app_id']),
        App.tenant_id == str(workspace_id)).with_for_update())
    if app is None:
        raise NotFound('برنامه در این پروژه پیدا نشد.')
    workflow = session.scalar(sa.select(Workflow).where(Workflow.id == store.uid(data['workflow_id']),
        Workflow.app_id == app.id, Workflow.tenant_id == str(workspace_id)).with_for_update())
    if app.mode != 'workflow' or app.status != 'normal' or workflow is None or workflow.version == 'draft':
        raise UnprocessableEntity('یک نسخهٔ منتشرشده از فرایند همین پروژه لازم است.')
    table = definitions(session)
    if session.scalar(sa.select(WorkflowRun.id).where(WorkflowRun.app_id == app.id,
            WorkflowRun.status.in_(['running', 'paused'])).limit(1)):
        raise Conflict('ابتدا اجراهای در جریان این برنامه را به پایان برسانید.')
    inputs, outputs = contracts(workflow)
    row = dict(id=str(uuid4()), **scope, app_id=app.id, workflow_id=workflow.id,
        name=data['name'].strip(), description=data['description'].strip(), input_contract=inputs,
        output_contract=outputs, workflow_digest=fingerprint(workflow), revision=1, acl_revision=1,
        archived=False, created_by=str(actor_id), created_at=now())
    session.execute(table.insert().values(**row))
    result = public(session, row, actor_id)
    event(session, scope, actor_id, key, request_digest, 'agent.registered', result)
    return result


def get_grants(session, project_id, workspace_id, actor_id, agent_id):
    scope = team.scope(session, project_id, workspace_id, actor_id, write=True)
    row = load(session, scope, agent_id)
    from models.account import TenantAccountJoin
    members = session.execute(sa.select(Account, TenantAccountJoin).join(TenantAccountJoin,
        TenantAccountJoin.account_id == Account.id).where(TenantAccountJoin.tenant_id == str(workspace_id)).order_by(Account.name))
    return grant_snapshot(session, row) | {'members': [dict(account_id=account.id, name=account.name,
        membership_id=join.id, status=account.status) for account, join in members]}


def grant_snapshot(session, row):
    grants, _, _ = tables(session)
    values = session.execute(sa.select(grants).where(grants.c.agent_id == row['id'])
        .order_by(grants.c.account_id, grants.c.action)).mappings()
    grouped = {}
    for value in values:
        target = grouped.setdefault(value['account_id'], dict(account_id=value['account_id'],
            membership_id=value['membership_id'], actions=[]))
        target['actions'].append(value['action'])
    return dict(agent_id=row['id'], revision=row['acl_revision'], grants=list(grouped.values()))


def set_grants(session, project_id, workspace_id, actor_id, agent_id, data, key):
    body(data, ('expected_revision', 'grants'))
    expected = revision(data['expected_revision'])
    if not isinstance(data['grants'], list):
        raise BadRequest('فهرست مجوزها معتبر نیست.')
    key = action_key(key)
    scope = team.scope(session, project_id, workspace_id, actor_id, write=True)
    row = load(session, scope, agent_id, lock=True)
    normalized = []
    for item in data['grants']:
        body(item, ('account_id', 'membership_id', 'actions'))
        actions = item['actions']
        if not isinstance(actions, list) or any(type(a) is not str or a not in ACTIONS for a in actions) or len(actions) != len(set(actions)):
            raise BadRequest('مجوزهای انتخاب‌شده معتبر و یکتا نیستند.')
        join = team.member(session, workspace_id, store.uid(item['account_id']), lock=True)
        if join.id != store.uid(item['membership_id']):
            raise Conflict('عضویت تغییر کرده است؛ فهرست تازه را دریافت کنید.')
        if session.get(Account, join.account_id).status != AccountStatus.ACTIVE:
            raise BadRequest('مجوز فقط به عضو فعال داده می‌شود.')
        normalized.append(dict(account_id=join.account_id, membership_id=join.id, actions=sorted(actions)))
    if len({item['account_id'] for item in normalized}) != len(normalized):
        raise BadRequest('کاربر تکراری در فهرست مجوزها وجود دارد.')
    request_digest = digest(dict(operation='grants', agent_id=row['id'], expected_revision=expected,
        grants=sorted(normalized, key=lambda item: item['account_id'])))
    previous = replay(session, scope, actor_id, key, request_digest)
    if previous:
        return previous
    if row['acl_revision'] != expected or row['archived']:
        raise Conflict('مجوزها یا وضعیت ایجنت تغییر کرده‌اند؛ فهرست تازه را دریافت کنید.')
    grants, _, _ = tables(session)
    session.execute(grants.delete().where(grants.c.agent_id == row['id']))
    for target in normalized:
        for action in target['actions']:
            session.execute(grants.insert().values(**scope, agent_id=row['id'], account_id=target['account_id'],
                membership_id=target['membership_id'], action=action, granted_by=str(actor_id), granted_at=now()))
    table = definitions(session)
    session.execute(table.update().where(table.c.id == row['id']).values(acl_revision=expected + 1))
    result = grant_snapshot(session, dict(row, acl_revision=expected + 1))
    event(session, scope, actor_id, key, request_digest, 'agent.grants.replaced', result)
    return result


def archive(session, project_id, workspace_id, actor_id, agent_id, data, key):
    body(data, ('expected_revision',))
    expected, key = revision(data['expected_revision']), action_key(key)
    scope = team.scope(session, project_id, workspace_id, actor_id, write=True)
    row = load(session, scope, agent_id, lock=True)
    request_digest = digest(dict(operation='archive', agent_id=row['id'], **data))
    previous = replay(session, scope, actor_id, key, request_digest)
    if previous:
        return previous
    if row['revision'] != expected or row['archived']:
        raise Conflict('وضعیت ایجنت تغییر کرده است.')
    table = definitions(session)
    session.execute(table.update().where(table.c.id == row['id']).values(archived=True, revision=expected + 1))
    result = public(session, dict(row, archived=True, revision=expected + 1), actor_id)
    event(session, scope, actor_id, key, request_digest, 'agent.archived', result)
    return result


def validate_inputs(contract, inputs):
    if not isinstance(inputs, dict) or set(inputs) - {item['variable'] for item in contract}:
        raise BadRequest('ورودی‌های ناشناخته ارسال شده‌اند.')
    digest(inputs)
    if len(json.dumps(inputs, ensure_ascii=False).encode()) > 262144:
        raise BadRequest('حجم ورودی بیش از حد مجاز است.')
    for item in contract:
        value = inputs.get(item['variable'])
        if value is None or value == '':
            if item['required']:
                raise BadRequest('ورودی الزامی را تکمیل کنید: ' + item['label'])
            continue
        kind = item['type']
        valid = (type(value) in (int, float) and math.isfinite(value) if kind == 'number' else
            type(value) is bool if kind == 'checkbox' else isinstance(value, str))
        if not valid or (kind == 'select' and value not in item['options']) or (
                isinstance(value, str) and item['max_length'] and len(value) > item['max_length']):
            raise BadRequest('نوع یا مقدار ورودی معتبر نیست: ' + item['label'])


def start(session, project_id, workspace_id, actor_id, agent_id, data, key):
    body(data, ('inputs', 'expected_revision'))
    expected, key = revision(data['expected_revision']), action_key(key)
    scope = team.scope(session, project_id, workspace_id, actor_id)
    # Serialize with ACL updates and membership/owner changes, without requiring manager authority.
    from models.account import Tenant
    session.scalar(sa.select(Tenant).where(Tenant.id == str(workspace_id)).with_for_update())
    row = load(session, scope, agent_id, lock=True)
    join = require(session, row, actor_id, 'run')
    request_digest = digest(dict(operation='run', agent_id=row['id'], **data))
    replay(session, scope, actor_id, key, request_digest)  # Detect keys used by other operations.
    _, _, attempts = tables(session)
    previous = session.execute(sa.select(attempts).where(*(attempts.c[k] == v for k, v in scope.items()),
        attempts.c.actor_id == str(actor_id), attempts.c.correlation_id == key)).mappings().first()
    if previous:
        if previous['request_digest'] != request_digest or previous['membership_id'] != join.id:
            raise Conflict('شناسهٔ اقدام یا عضویت تغییر کرده است.')
        return attempt_public(previous)
    if row['revision'] != expected:
        raise Conflict('تعریف ایجنت تغییر کرده است.')
    from company_projects.runtime_models import attempt_inputs, business_inputs
    inputs = attempt_inputs(session, session.get(Workflow, row['workflow_id']), actor_id, data['inputs'])
    validate_inputs(row['input_contract'], business_inputs(inputs))
    attempt = dict(id=str(uuid4()), agent_id=row['id'], **scope, actor_id=str(actor_id), membership_id=join.id,
        workflow_id=row['workflow_id'], inputs=inputs, request_digest=request_digest,
        correlation_id=key, status='pending', result=None, created_at=now())
    session.execute(attempts.insert().values(**attempt))
    event(session, scope, actor_id, key, request_digest, 'agent.run.requested', attempt_public(attempt))
    return attempt_public(attempt)


def attempt_public(row):
    # No prompt, graph, intermediate logs, or other actors' raw results.
    return dict(id=row['id'], agent_id=row['agent_id'], workflow_id=row['workflow_id'],
        status=row['status'], result=row['result'])


def get_attempt(session, project_id, workspace_id, actor_id, agent_id, attempt_id):
    scope = team.scope(session, project_id, workspace_id, actor_id)
    row = load(session, scope, agent_id)
    join = require(session, row, actor_id, 'run')
    _, _, attempts = tables(session)
    attempt = session.execute(sa.select(attempts).where(attempts.c.id == store.uid(attempt_id),
        attempts.c.agent_id == row['id'], attempts.c.actor_id == str(actor_id),
        attempts.c.membership_id == join.id)).mappings().first()
    if not attempt:
        raise NotFound('اجرا پیدا نشد.')
    return attempt_public(attempt)


def before_member_removal(session, key, actor_id, membership_id):
    grants, _, _ = tables(session)
    rows = list(session.execute(sa.select(grants).where(grants.c.workspace_id == key['workspace_id'],
        grants.c.account_id == key['account_id'], grants.c.membership_id == membership_id)).mappings())
    if rows:
        scope = {k: key[k] for k in ('project_id', 'workspace_id')}
        event(session, scope, actor_id, str(uuid4()), digest(membership_id), 'agent.grants.member_removed',
            dict(account_id=key['account_id'], membership_id=membership_id,
                revoked=[dict(agent_id=row['agent_id'], action=row['action']) for row in rows]))
