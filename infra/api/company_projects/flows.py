"""Ordered human team flows; immutable publication snapshots, no second engine."""
import re
import json
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import access, agents, team, stage_config
from models.account import Account, AccountStatus, Tenant, TenantAccountJoin
from models.model import App
from models.workflow import Workflow

KEY = re.compile(r'^[a-z][a-z0-9_-]{0,39}$')


def tables(session):
    return tuple(agents.reflected(session, name) for name in ('company_team_flows', 'company_team_flow_versions'))


def scope(session, project_id, workspace_id, actor_id, *, write=False):
    result = team.scope(session, project_id, workspace_id, actor_id)
    if write:
        session.scalar(sa.select(Tenant).where(Tenant.id == str(workspace_id)).with_for_update())
        result = team.scope(session, project_id, workspace_id, actor_id)
        require_author(session, workspace_id, actor_id)
    return result


def require_author(session, workspace_id, actor_id):
    join = team.member(session, workspace_id, actor_id)
    if join.role not in {'owner', 'admin', 'editor'}:
        raise Forbidden('تعریف و انتشار فلو به مجوز فنی ساخت برنامه نیاز دارد.')
    from configs import dify_config
    if dify_config.RBAC_ENABLED:
        from services.enterprise.rbac_service import RBACService
        from core.rbac import RBACPermission
        if not RBACService.CheckAccess.check(str(workspace_id), str(actor_id),
                scene=RBACPermission.APP_CREATE_AND_MANAGEMENT, resource_type='workspace', resource_id=str(workspace_id)):
            raise Forbidden('مجوز بومی ساخت برنامه لازم است.')


def can_author(session, workspace_id, actor_id):
    try:
        require_author(session, workspace_id, actor_id)
        return True
    except (Forbidden, NotFound):
        return False


def load(session, scoped, flow_id, *, lock=False):
    table, _ = tables(session)
    query = sa.select(table).where(table.c.id == str(flow_id), *(table.c[k] == v for k, v in scoped.items()))
    row = session.execute(query.with_for_update() if lock else query).mappings().first()
    if not row:
        raise NotFound('فلو در این پروژه پیدا نشد.')
    return dict(row)


def version(session, scoped, flow_id, version_id):
    load(session, scoped, flow_id)
    _, versions = tables(session)
    row = session.execute(sa.select(versions).where(versions.c.id == str(version_id),
        versions.c.flow_id == str(flow_id), *(versions.c[k] == v for k, v in scoped.items()))).mappings().first()
    if not row:
        raise NotFound('نسخهٔ فلو پیدا نشد.')
    return version_public(row)


def version_public(row):
    return {key: (row[key].isoformat() if key == 'published_at' else row[key]) for key in (
        'id', 'flow_id', 'version', 'source_revision', 'contract_version', 'digest', 'name', 'description',
        'stage_bindings', 'published_by', 'published_at')}


def public(session, row, author):
    result = {key: row[key] for key in ('id', 'name', 'description', 'revision', 'archived', 'current_version_id')}
    _, versions = tables(session)
    published = session.execute(sa.select(versions).where(versions.c.id == row['current_version_id'])).mappings().first()
    result['published'] = version_public(published) if published else None
    if author:
        result['draft_stages'] = row['draft_stages']
    elif published:
        result.update(name=published['name'], description=published['description'])
    return result


def list_flows(session, project_id, workspace_id, actor_id):
    scoped = scope(session, project_id, workspace_id, actor_id)
    author = can_author(session, workspace_id, actor_id)
    table, _ = tables(session)
    query = sa.select(table).where(table.c.deleted_at.is_(None), *(table.c[k] == v for k, v in scoped.items())).order_by(table.c.created_at, table.c.id)
    if not author:
        query = query.where(table.c.current_version_id.is_not(None))
    return dict(can_edit=author, data=[public(session, row, author) for row in session.execute(query).mappings()])


def get_flow(session, project_id, workspace_id, actor_id, flow_id):
    scoped = scope(session, project_id, workspace_id, actor_id)
    row = load(session, scoped, flow_id)
    if row.get('deleted_at') is not None:
        raise NotFound('فلو حذف شده است.')
    author = can_author(session, workspace_id, actor_id)
    if not author and not row['current_version_id']:
        raise NotFound('فلو منتشر نشده است.')
    return dict(can_edit=author, **public(session, row, author))


def list_versions(session, project_id, workspace_id, actor_id, flow_id):
    scoped = scope(session, project_id, workspace_id, actor_id)
    load(session, scoped, flow_id)
    _, versions = tables(session)
    return dict(data=[version_public(row) for row in session.execute(sa.select(versions).where(
        versions.c.flow_id == str(flow_id), *(versions.c[k] == v for k, v in scoped.items()))
        .order_by(versions.c.version.desc())).mappings()])


def get_version(session, project_id, workspace_id, actor_id, flow_id, version_id):
    return version(session, scope(session, project_id, workspace_id, actor_id), flow_id, version_id)


def legacy_options(session, scoped, actor_id, members):
    """Read conversion hints once; never grant standalone access to a new stage."""
    definitions = agents.definitions(session)
    grants = agents.tables(session)[0]
    memberships = {member['account_id']: member['membership_id'] for member in members}
    actions = {}
    for grant in session.execute(sa.select(grants).where(*(grants.c[k] == v for k, v in scoped.items()))).mappings():
        if memberships.get(grant['account_id']) == grant['membership_id']:
            actions.setdefault(grant['agent_id'], {}).setdefault(grant['account_id'], set()).add(grant['action'])
    manager = access.can_manage_members(session, scoped['workspace_id'], actor_id)
    rows = session.execute(sa.select(definitions).where(definitions.c.deleted_at.is_(None),
        definitions.c.archived.is_(False), definitions.c.execution_scope == 'program',
        *(definitions.c[k] == v for k, v in scoped.items())).order_by(definitions.c.created_at, definitions.c.id)).mappings()
    from company_projects import harness
    result = []
    for agent in rows:
        allowed = actions.get(agent['id'], {})
        if not manager and not allowed.get(str(actor_id)):
            continue
        app, workflow = session.get(App, agent['app_id']), session.get(Workflow, agent['workflow_id'])
        cfg = harness.policy(session, agent)
        participants = []
        for member in members:
            permissions = allowed.get(member['account_id'], set())
            # Legacy execution/finalization also conferred view. Preserve that
            # visibility in the new stage without delegating either action.
            if permissions & {'view', 'run', 'feedback', 'finalize'}:
                participants.append(dict(account_id=member['account_id'], membership_id=member['membership_id'],
                    actions=['view', 'feedback'] if 'feedback' in permissions else ['view']))
        result.append({k: agent[k] for k in ('id', 'name', 'app_id', 'workflow_id', 'input_contract', 'output_contract')} | dict(
            app_name=app.name if app else agent['name'], workflow_version=(workflow.marked_name or workflow.version) if workflow else None,
            runners=[m['account_id'] for m in members if 'run' in allowed.get(m['account_id'], set())],
            finalizers=[m['account_id'] for m in members if 'finalize' in allowed.get(m['account_id'], set())],
            execution={k: cfg[k] for k in ('enabled', 'instructions', 'requires_source')} | dict(program_enabled=True),
            participants=participants))
    return result


def options(session, project_id, workspace_id, actor_id):
    scoped = scope(session, project_id, workspace_id, actor_id, write=True)
    members = []
    for account, join in session.execute(sa.select(Account, TenantAccountJoin).join(TenantAccountJoin,
            TenantAccountJoin.account_id == Account.id).where(TenantAccountJoin.tenant_id == str(workspace_id),
                Account.status == AccountStatus.ACTIVE).order_by(Account.name)):
        roles = team.get_roles(session, project_id, workspace_id, actor_id, account.id)['roles']
        members.append(dict(account_id=account.id, membership_id=join.id, name=account.name, roles=roles))
    result = legacy_options(session, scoped, actor_id, members)
    from company_projects import harness
    from company_projects.execution_plan import describe
    from company_projects.controller import visible_filters
    filters = visible_filters(session, str(workspace_id), str(actor_id))
    programs = []
    rows = session.execute(sa.select(App, Workflow).join(Workflow, sa.and_(Workflow.app_id == App.id,
        Workflow.tenant_id == App.tenant_id)).where(App.tenant_id == str(workspace_id), App.mode == 'workflow',
        App.status == 'normal', Workflow.version != 'draft', *filters).order_by(App.name, Workflow.created_at.desc())) if filters else []
    for app, workflow in rows:
        from company_projects.personal_agent_sources import metadata
        if metadata(workflow) is not None:
            continue
        try:
            inputs, outputs = agents.contracts(workflow)
        except (BadRequest, UnprocessableEntity):
            # One invalid imported/legacy definition must not hide valid choices.
            continue
        reason = harness.compatible(session, dict(workflow_id=workflow.id, workflow_digest=agents.fingerprint(workflow)))
        programs.append(dict(app_id=app.id, app_name=app.name, workflow_id=workflow.id,
            version=workflow.marked_name or workflow.version, input_contract=inputs, output_contract=outputs,
            execution_plan=describe(workflow.graph_dict), harness_compatible=reason is None, harness_reason=reason))
    return dict(agents=result, programs=programs, members=members)


def validate_draft(data):
    agents.body(data, ('name', 'description', 'stages', 'expected_revision'))
    agents.revision(data['expected_revision'])
    if not isinstance(data['name'], str) or not data['name'].strip() or len(data['name']) > 120 or (
            not isinstance(data['description'], str) or len(data['description']) > 2000):
        raise BadRequest('نام یا توضیح فلو معتبر نیست.')
    stages = data['stages']
    if not isinstance(stages, list) or len(stages) > 30:
        raise BadRequest('حداکثر ۳۰ مرحله در هر فلو مجاز است.')
    keys = set()
    for stage in stages:
        extra = ('app_id', 'workflow_id', 'execution', 'participants') if isinstance(stage, dict) and 'execution' in stage else ()
        agents.body(stage, ('key', 'title', 'agent_id', 'executor_id', 'executor_membership_id',
            'finalizer_id', 'finalizer_membership_id', 'decision_role', 'inputs', *extra))
        if extra:
            stage_config.validate(stage)
        if not isinstance(stage['key'], str) or not KEY.fullmatch(stage['key']) or stage['key'] in keys:
            raise BadRequest('شناسهٔ مراحل باید معتبر و یکتا باشد.')
        keys.add(stage['key'])
        if not isinstance(stage['title'], str) or not stage['title'].strip() or len(stage['title']) > 120:
            raise BadRequest('عنوان مرحله لازم و حداکثر ۱۲۰ نویسه است.')
        if stage['decision_role'] not in (None, 'po', 'tl') or not isinstance(stage['inputs'], dict):
            raise BadRequest('نقش تصمیم یا ورودی مرحله معتبر نیست.')
        for key in ('agent_id', 'executor_id', 'executor_membership_id', 'finalizer_id', 'finalizer_membership_id'):
            if stage[key] is not None:
                from company_projects.store import uid
                uid(stage[key])
    if len(json.dumps(data, ensure_ascii=False).encode()) > 262144:
        raise BadRequest('حجم تعریف فلو بیش از حد مجاز است.')
    return dict(name=data['name'].strip(), name_key=data['name'].strip().casefold(),
        description=data['description'].strip(), draft_stages=stages)


def mutate(session, project_id, workspace_id, actor_id, data, key, flow_id=None, action='save'):
    key = agents.action_key(key)
    expected = agents.revision(data.get('expected_revision')) if isinstance(data, dict) else None
    scoped = scope(session, project_id, workspace_id, actor_id, write=True)
    request_digest = agents.digest(dict(operation='flow.' + action, flow_id=str(flow_id) if flow_id else None, body=data))
    previous = agents.replay(session, scoped, actor_id, key, request_digest)
    if previous:
        return previous
    table, versions = tables(session)
    row = load(session, scoped, flow_id, lock=True) if flow_id else None
    if row and (row['archived'] or row['revision'] != expected):
        raise Conflict('فلو تغییر کرده یا بایگانی شده است؛ نسخهٔ تازه را دریافت کنید.')
    if row is None and (action != 'save' or expected != 1):
        raise BadRequest('تعریف تازه با نسخهٔ یک ساخته می‌شود.')
    if action == 'save':
        values = validate_draft(data)
        if session.scalar(sa.select(table.c.id).where(*(table.c[k] == v for k, v in scoped.items()),
                table.c.deleted_at.is_(None), table.c.name_key == values['name_key'], table.c.id != (row['id'] if row else str(uuid4())))):
            raise Conflict('نام این فلو در پروژه استفاده شده است.')
        if row:
            row.update(**values, revision=expected + 1, updated_at=agents.now())
            session.execute(table.update().where(table.c.id == row['id']).values(**values,
                revision=row['revision'], updated_at=row['updated_at']))
        else:
            row = dict(id=str(uuid4()), **scoped, **values, revision=1, current_version_id=None,
                archived=False, created_by=str(actor_id), created_at=agents.now(), updated_at=agents.now())
            session.execute(table.insert().values(**row))
        result = public(session, row, True)
    else:
        agents.body(data, ('expected_revision',))
        if action == 'archive':
            session.execute(table.update().where(table.c.id == row['id']).values(archived=True,
                revision=expected + 1, updated_at=agents.now()))
            result = public(session, dict(row, archived=True, revision=expected + 1), True)
        elif action == 'publish':
            bindings = compile_stages(session, scoped, actor_id, row['draft_stages'])
            number = (session.scalar(sa.select(sa.func.max(versions.c.version)).where(versions.c.flow_id == row['id'])) or 0) + 1
            content = dict(contract_version=1, name=row['name'], description=row['description'], stage_bindings=bindings)
            published = dict(id=str(uuid4()), flow_id=row['id'], **scoped, version=number,
                source_revision=expected, **content, digest=agents.digest(content), published_by=str(actor_id), published_at=agents.now())
            session.execute(versions.insert().values(**published))
            session.execute(table.update().where(table.c.id == row['id']).values(current_version_id=published['id'],
                revision=expected + 1, updated_at=agents.now()))
            result = public(session, dict(row, current_version_id=published['id'], revision=expected + 1), True)
        else:
            raise BadRequest('اقدام فلو معتبر نیست.')
    agents.event(session, scoped, actor_id, key, request_digest, 'flow.' + action, result)
    return result


def compile_stages(session, scoped, actor_id, stages):
    if not stages:
        raise UnprocessableEntity('فلو برای انتشار حداقل یک مرحله لازم دارد.')
    compiled = []
    for stage in stages:
        stage_owned = 'execution' in stage
        required = ('executor_id', 'executor_membership_id', 'finalizer_id', 'finalizer_membership_id') + (() if stage_owned else ('agent_id',))
        if any(stage[field] is None for field in required):
            raise UnprocessableEntity('ایجنت، اجراکننده و نهایی‌کنندهٔ هر مرحله را مشخص کنید.')
        agent = stage_config.source(session, scoped, actor_id, stage) if stage_owned else agents.load(session, scoped, stage['agent_id'], lock=True)
        if agent['archived'] or (not stage_owned and not access.can_manage_members(session, scoped['workspace_id'], actor_id)
                and not agents.permissions(session, agent, actor_id)):
            raise Forbidden('ایجنت مرحله در دسترس شما نیست.')
        workflow = session.scalar(sa.select(Workflow).where(Workflow.id == agent['workflow_id']).with_for_update())
        app = session.get(App, agent['app_id'])
        if not workflow or not app or app.tenant_id != scoped['workspace_id'] or app.status != 'normal' or app.mode != 'workflow' or (
                workflow.tenant_id != scoped['workspace_id'] or workflow.app_id != app.id or workflow.version == 'draft' or
                agents.fingerprint(workflow) != agent['workflow_digest']):
            raise UnprocessableEntity('نسخهٔ منتشرشدهٔ ایجنت معتبر نیست.')
        from company_projects.personal_agent_sources import validate
        validate(session, workflow, stage['executor_id'])
        from company_projects.program_agents import validate as validate_program_roles
        validate_program_roles(session, workflow, actor_id, publishing=True)
        from configs import dify_config
        if dify_config.RBAC_ENABLED:
            from core.rbac import RBACPermission
            from services.enterprise.rbac_service import RBACService
            from company_projects.personal_agent_sources import metadata
            origin = metadata(workflow)
            scene = RBACPermission.AGENT_RELEASE_AND_VERSION if origin else RBACPermission.APP_RELEASE_AND_VERSION
            if not RBACService.CheckAccess.check(scoped['workspace_id'], str(actor_id), scene=scene,
                    resource_type='agent' if origin else 'app', resource_id=origin['agent_id'] if origin else app.id):
                raise Forbidden('مجوز بومی انتشار منبع ایجنتِ مرحله لازم است.')
        people = {}
        for prefix, action in (('executor', 'run'), ('finalizer', 'finalize')):
            join = team.member(session, scoped['workspace_id'], stage[prefix + '_id'], lock=True)
            if join.id != stage[prefix + '_membership_id']:
                raise Conflict('عضویت مسئول مرحله تغییر کرده است.')
            if not stage_owned:
                agents.require(session, agent, join.account_id, action)
            account = session.get(Account, join.account_id)
            if account.status != AccountStatus.ACTIVE:
                raise Forbidden('مسئول مرحله باید حساب فعال داشته باشد.')
            people[prefix] = dict(account_id=join.account_id, membership_id=join.id, name=account.name)
        if stage['decision_role'] and stage['decision_role'] not in team.get_roles(session, scoped['project_id'],
                scoped['workspace_id'], actor_id, stage['finalizer_id'])['roles']:
            raise UnprocessableEntity('نهایی‌کننده نقش کاری لازم برای تصمیم این مرحله را ندارد.')
        validate_bindings(agent['input_contract'], stage['inputs'], compiled)
        config = stage_config.compile_config(session, scoped, stage, agent) if stage_owned else {}
        compiled.append(dict(**config, key=stage['key'], title=stage['title'], agent_id=agent['id'], agent_name=agent['name'],
            agent_revision=agent['revision'], workflow_id=workflow.id, workflow_digest=agent['workflow_digest'],
            app_id=app.id, app_name=app.name, workflow_version=workflow.marked_name or workflow.version,
            input_contract=agent['input_contract'], output_contract=agent['output_contract'], contract_version=1,
            executor=people['executor'], finalizer=people['finalizer'], decision_role=stage['decision_role'],
            inputs=stage['inputs'], depends_on=[compiled[-1]['key']] if compiled else []))
    return compiled


def validate_bindings(contract, bindings, preceding):
    known = {item['variable']: item for item in contract}
    if set(bindings) - set(known):
        raise UnprocessableEntity('ورودی ناشناخته در مرحله وجود دارد.')
    previous = {stage['key']: stage for stage in preceding}
    for name, item in known.items():
        source = bindings.get(name)
        if source is None:
            if item['required']:
                raise UnprocessableEntity('منبع ورودی الزامی را مشخص کنید: ' + item['label'])
            continue
        if not isinstance(source, dict):
            raise BadRequest('منبع ورودی معتبر نیست.')
        kind = source.get('source')
        if kind == 'request':
            agents.body(source, ('source',))
            if item['type'] not in {'text-input', 'paragraph'}:
                raise UnprocessableEntity('متن درخواست فقط به ورودی متنی متصل می‌شود.')
        elif kind == 'constant':
            agents.body(source, ('source', 'value'))
            agents.validate_inputs([dict(item, required=True)], {name: source['value']})
        elif kind == 'stage':
            agents.body(source, ('source', 'stage_key', 'output'))
            if type(source['stage_key']) is not str or type(source['output']) is not str or (
                    source['stage_key'] not in previous or source['output'] not in previous[source['stage_key']]['output_contract']):
                raise UnprocessableEntity('ورودی باید به خروجی معتبر مرحلهٔ قبل وصل باشد؛ ارجاع آینده، چرخه یا منبع گم‌شده مجاز نیست.')
        else:
            raise BadRequest('نوع منبع ورودی پشتیبانی نمی‌شود.')
