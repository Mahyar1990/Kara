"""Read-only human work projections. No engine dispatch, decision or new authority."""
import unicodedata
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, HTTPException

from company_projects import agents, stages


def responsibility(session, scope, stage, valid):
    if not stage:
        return dict(kind='completed', person=None, reason=None)
    if not valid:
        return dict(kind='po', person=None, reason='تصمیم ورود نیاز به بررسی مجدد مالک محصول دارد.')
    key = 'finalizer' if stage['state'] == 'awaiting_decision' else 'executor'
    person = stage['binding'][key]
    reason = None
    if stage['state'] == 'stale':
        reason = 'ورودی یا دسترسی مرحله نامعتبر است؛ بررسی مسئول پروژه لازم است.'
    else:
        try:
            stages.require(session, scope, stage, person['account_id'], 'finalize' if key == 'finalizer' else 'run')
        except HTTPException:
            reason = 'مسئول ثبت‌شده اکنون مجوز، عضویت یا نسخهٔ معتبر لازم را ندارد؛ بررسی مدیر پروژه لازم است.'
    return dict(kind=key, person=person, reason=reason)


def handoffs(session, value, stage):
    """Only the finalized fields mapped to this recipient; never upstream drafts/logs."""
    _, dependencies = stages.resolve(session, value, stage)
    by_id = {row['stage_id']: row for row in dependencies}
    previous = {row['step_key']: row for row in stages.stage_rows(session, value)}
    artifacts, decisions = stages.tables(session)[4:]
    result = []
    for target, source in stage['binding']['inputs'].items():
        if source['source'] != 'stage':
            continue
        origin = previous[source['stage_key']]
        dependency = by_id[origin['id']]
        artifact = session.execute(sa.select(artifacts).where(artifacts.c.id == dependency['artifact_id'],
            artifacts.c.stage_id == origin['id'], artifacts.c.digest == dependency['digest'])).mappings().one()
        decision = session.execute(sa.select(decisions).where(decisions.c.stage_id == origin['id'],
            decisions.c.artifact_id == artifact['id'], decisions.c.input_digest == artifact['input_digest'])
            .order_by(decisions.c.created_at.desc())).mappings().first()
        if decision is None:
            # Fail closed: a selected pointer alone is not a human decision.
            from werkzeug.exceptions import Conflict
            raise Conflict('خروجی تحویلی تصمیم نهایی معتبر ندارد.')
        result.append(dict(input=target, output=source['output'], stage_id=origin['id'], stage_title=origin['binding']['title'],
            artifact_id=artifact['id'], version=artifact['version'], digest=artifact['digest'],
            content=artifact['content'][source['output']], decision_id=decision['id'],
            finalized_by=decision['actor_id'], finalized_at=decision['created_at'].isoformat(),
            consumed=stage['inputs'] is not None))
    return result


def list_actions(session, project, workspace, actor, page='1', name='', kind='all'):
    kinds = ('finalize', 'revalidate', 'run', 'retry', 'request_decision', 'feedback')
    if not isinstance(name, str) or len(name) > 200 or kind not in ('all', *kinds):
        raise BadRequest('فیلتر کارتابل معتبر نیست.')
    def normalize(value):
        text = unicodedata.normalize('NFKC', value or '').casefold().translate(str.maketrans('يك۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', 'یک01234567890123456789')).replace('\u200c', ' ').replace('\u200d', ' ')
        return ' '.join(''.join(c for c in text if unicodedata.category(c) != 'Mn').split())
    words = normalize(name).split()
    try:
        page = int(page)
        if page < 1:
            raise ValueError()
    except (ValueError, TypeError):
        raise BadRequest('شمارهٔ صفحه معتبر نیست.') from None
    scope = stages.scoped(session, project, workspace, actor)
    instances, entity, *_ = stages.tables(session)
    values = session.execute(sa.select(instances).where(*(instances.c[k] == v for k, v in scope.items()))
        .order_by(instances.c.created_at.desc(), instances.c.id.desc())).mappings()
    result = []
    for value in values:
        if not stages.valid_intake(session, value):
            continue
        for stage in stages.stage_rows(session, value):
            if stage['state'] in ('blocked', 'running', 'completed', 'cancelled'):
                continue
            error = None
            try:
                inputs, _ = stages.resolve(session, value, stage)
                agents.validate_inputs(stage['binding']['input_contract'], inputs)
            except HTTPException as exc:
                error = exc.description
            actions = stages.available_actions(session, scope, value, stage, actor, input_error=error)
            if not actions:
                continue
            task_kind = next((action for action in kinds if action in actions), None)
            revision = stages.table(session, 'company_team_request_revisions')
            title = session.scalar(sa.select(revision.c.title).where(revision.c.id == value['request_revision_id']))
            result.append(dict(instance_id=value['id'], stage_id=stage['id'], request_id=value['request_id'],
                title=title, stage_title=stage['binding']['title'], state=stage['state'], kind=task_kind,
                actions=actions, expected_outputs=stage['binding']['output_contract'],
                executor=stage['binding']['executor'], finalizer=stage['binding']['finalizer'],
                selected_artifact_id=stage['selected_artifact_id']))
    counts = {item: sum(row['kind'] == item for row in result) for item in kinds}
    total = len(result)
    result = [row for row in result if (kind == 'all' or row['kind'] == kind) and all(word in normalize(row['title'] + ' ' + row['stage_title']) for word in words)]
    offset = (page - 1) * 25
    return dict(data=result[offset:offset + 25], total=len(result), unfiltered_total=total, counts=counts, page_size=25, page=page, has_more=offset + 25 < len(result))
