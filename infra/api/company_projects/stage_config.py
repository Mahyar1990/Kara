"""Stage-owned execution sources and authority, frozen with each FlowVersion.

Internal source rows reuse the existing execution outbox, never standalone grants.
The binding is loaded from a published version/stage, never from an HTTP capability.
"""
from uuid import uuid4
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, UnprocessableEntity
from company_projects import agents, team
from company_projects.store import uid
from models.account import Account, AccountStatus
from models.model import App
from models.workflow import Workflow


def owned(binding):
    return binding.get('execution_scope') == 'stage'


def validate(stage):
    for field in ('app_id', 'workflow_id'):
        if stage[field] is not None:
            uid(stage[field])
    if stage['agent_id'] is not None:
        raise BadRequest('مرحلهٔ جدید مستقیماً به نسخهٔ برنامه متصل می‌شود.')
    cfg = stage['execution']
    agents.body(cfg, ('program_enabled', 'enabled', 'instructions', 'requires_source'))
    if any(type(cfg[k]) is not bool for k in ('program_enabled', 'enabled', 'requires_source')) or (
            not isinstance(cfg['instructions'], str) or len(cfg['instructions']) > 32000):
        raise BadRequest('تنظیم روش اجرا یا دستورالعمل مرحله معتبر نیست.')
    people = stage['participants']
    if not isinstance(people, list) or len(people) > 200:
        raise BadRequest('فهرست دسترسی مرحله معتبر نیست.')
    seen = set()
    for person in people:
        agents.body(person, ('account_id', 'membership_id', 'actions'))
        uid(person['account_id']); uid(person['membership_id'])
        if person['account_id'] in seen or not isinstance(person['actions'], list) or (
                not person['actions'] or any(a not in ('view', 'feedback') for a in person['actions']) or
                len(set(person['actions'])) != len(person['actions'])):
            raise BadRequest('دسترسی همکار فقط مشاهده یا بازخورد همین مرحله است.')
        seen.add(person['account_id'])


def source(session, scope, actor, stage):
    """Create an ungrantable private source only inside the publication transaction."""
    if not stage['app_id'] or not stage['workflow_id']:
        raise UnprocessableEntity('برنامه و نسخهٔ منتشرشدهٔ هر مرحله را انتخاب کنید.')
    app = session.scalar(sa.select(App).where(App.id == stage['app_id'], App.tenant_id == scope['workspace_id']).with_for_update())
    workflow = session.scalar(sa.select(Workflow).where(Workflow.id == stage['workflow_id']).with_for_update())
    if not app or app.status != 'normal' or app.mode != 'workflow' or not workflow or (
            workflow.app_id != app.id or workflow.tenant_id != scope['workspace_id'] or workflow.version == 'draft'):
        raise UnprocessableEntity('نسخهٔ منتشرشدهٔ برنامه در این پروژه معتبر نیست.')
    from company_projects.controller import visible_filters
    filters = visible_filters(session, scope['workspace_id'], str(actor))
    if not filters or not session.scalar(sa.select(App.id).where(App.id == app.id, *filters)):
        raise Forbidden('مجوز استفاده از برنامهٔ مرحله لازم است.')
    # Reusing a published version does not edit or publish its source program.
    # Flow authoring, source visibility and native release checks live in flows.
    inputs, outputs = agents.contracts(workflow)
    row = dict(id=str(uuid4()), **scope, app_id=app.id, workflow_id=workflow.id, name=app.name[:120],
        description='', input_contract=inputs, output_contract=outputs, workflow_digest=agents.fingerprint(workflow),
        revision=1, acl_revision=1, archived=False, created_by=str(actor), created_at=agents.now(), execution_scope='stage')
    session.execute(agents.definitions(session).insert().values(**row))
    return row


def compile_config(session, scope, stage, agent):
    cfg = dict(stage['execution'], instructions=stage['execution']['instructions'].strip())
    if not cfg['program_enabled'] and not cfg['enabled']:
        raise UnprocessableEntity('حداقل یک روش اجرا را برای مرحله فعال کنید.')
    if cfg['enabled']:
        from company_projects.harness import compatible
        reason = compatible(session, agent)
        if reason or not cfg['instructions']:
            raise UnprocessableEntity(reason or 'مأموریت و معیار پذیرش مرحله را بنویسید.')
    people = []
    for person in stage['participants']:
        if person['account_id'] in (stage['executor_id'], stage['finalizer_id']):
            continue  # Assigned people already have the precise role's actions.
        join = team.member(session, scope['workspace_id'], person['account_id'], lock=True)
        if join.id != person['membership_id'] or session.get(Account, join.account_id).status != AccountStatus.ACTIVE:
            raise Conflict('عضویت همکار مرحله تغییر کرده است.')
        people.append(dict(person, name=session.get(Account, join.account_id).name))
    return dict(execution_scope='stage', execution=dict(cfg, revision=1), participants=people)


def permissions(session, scope, binding, actor):
    team.scope(session, scope['project_id'], scope['workspace_id'], actor)
    join = team.member(session, scope['workspace_id'], actor)
    actions = set()
    for key, allowed in (('executor', ('view', 'run', 'feedback')), ('finalizer', ('view', 'feedback', 'finalize'))):
        person = binding[key]
        if person['account_id'] == str(actor) and person['membership_id'] == join.id:
            actions.update(allowed)
    for person in binding['participants']:
        if person['account_id'] == str(actor) and person['membership_id'] == join.id:
            actions.update(['view', *person['actions']])
    return sorted(actions)


def require(session, scope, binding, actor, action):
    agent = agents.load(session, scope, binding['agent_id'], _stage=True)
    if not owned(binding):
        return agent, agents.require(session, agent, actor, action)
    if agent['execution_scope'] != 'stage' or agent['archived'] or action not in permissions(session, scope, binding, actor):
        raise Forbidden('مجوز این اقدام فقط با مسئول یا همکار مجاز همین مرحله است.')
    from company_projects.personal_agent_sources import validate as validate_source
    validate_source(session, session.get(Workflow, binding['workflow_id']), actor if action == 'run' else None)
    return agent, team.member(session, scope['workspace_id'], actor)


def attempt_join(session, agent, attempt):
    """Workers must find an actual persisted stage link for a stage-only source."""
    if agent.get('execution_scope', 'program') != 'stage':
        return agents.require(session, agent, attempt['actor_id'], 'run')
    from company_projects import stages
    bridge = stages.tables(session)[2]
    link = session.execute(sa.select(bridge).where(bridge.c.attempt_id == attempt['id'])).mappings().first()
    if not link:
        raise Forbidden('این منبع فقط داخل مرحلهٔ منتشرشده قابل اجرا است.')
    scope = {k: attempt[k] for k in ('project_id', 'workspace_id')}
    stage = stages.load(session, stages.tables(session)[1], scope, link['stage_id'])
    if stage['binding']['agent_id'] != agent['id'] or not owned(stage['binding']):
        raise Forbidden('منبع تلاش با مرحله یکسان نیست.')
    return stages.require(session, scope, stage, attempt['actor_id'], 'run')[1]


def attempt_policy(session, agent, attempt_id):
    if agent.get('execution_scope', 'program') == 'stage':
        from company_projects import stages
        bridge = stages.tables(session)[2]
        link = session.execute(sa.select(bridge).where(bridge.c.attempt_id == str(attempt_id))).mappings().first()
        if not link:
            raise Forbidden('تلاش به مرحله متصل نیست.')
        row = session.execute(sa.select(stages.tables(session)[1]).where(stages.tables(session)[1].c.id == link['stage_id'])).mappings().one()
        if row['binding']['agent_id'] != agent['id'] or not owned(row['binding']):
            raise Forbidden('تنظیم اجرا با مرحله یکسان نیست.')
        return row['binding']['execution']
    from company_projects.harness import policy
    return policy(session, agent)
