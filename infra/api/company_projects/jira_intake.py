"""Explicit, project-scoped import of stored Jira JSON or one's own Workflow result.

No network request, credential, model inference, or automatic human decision.
"""
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid5

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, NotFound

from company_projects import access, agents, requests
from models.model import App
from models.workflow import WorkflowRun


def table(session):
    return agents.reflected(session, 'company_team_jira_sources')


def allowed(session, scoped, actor_id):
    return access.can_manage_members(session, scoped['workspace_id'], actor_id) or requests.is_po(session, scoped, actor_id)


def authorize(session, project_id, workspace_id, actor_id, *, write=False):
    from werkzeug.exceptions import Forbidden
    scoped = requests.scope(session, project_id, workspace_id, actor_id, write=write)
    if not allowed(session, scoped, actor_id):
        raise Forbidden('ورود و همگام‌سازی درخواست جیرا با مدیر پروژه یا PO است.')
    return scoped


def base_url(value):
    try:
        parsed = urlsplit(value if isinstance(value, str) else '')
        port = parsed.port
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or len(value) > 512
                or any(c.isspace() or ord(c) < 32 or c == '\\' for c in value)):
            raise ValueError()
        host = parsed.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        if port and port != 443:
            host += ':' + str(port)
        return urlunsplit(('https', host, parsed.path.rstrip('/'), '', ''))
    except (ValueError, TypeError):
        raise BadRequest('نشانی پایهٔ HTTPS جیرا را بدون توکن، نام کاربری یا پارامتر وارد کنید.') from None


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise BadRequest('زمان updated هر درخواست باید معتبر و دارای منطقهٔ زمانی باشد.') from None


def parse(response):
    if not isinstance(response, dict) or not isinstance(response.get('issues'), list):
        raise BadRequest('پاسخ باید یک شیء JSON دارای فهرست issues باشد؛ متن نمایشی تب نتیجه کافی نیست.')
    try:
        size = len(json.dumps(response, ensure_ascii=False, allow_nan=False).encode())
    except (ValueError, TypeError, UnicodeError):
        raise BadRequest('پاسخ JSON معتبر نیست.') from None
    issues = response['issues']
    total, start = response.get('total'), response.get('startAt', response.get('start_at'))
    if size > 2 * 1024 * 1024 or len(issues) > 100:
        raise BadRequest('هر ورود حداکثر ۱۰۰ درخواست و دو مگابایت است.')
    if any(type(n) is not int or n < 0 for n in (total, start)) or start + len(issues) > total:
        raise BadRequest('مقادیر total و startAt یا start_at با تعداد درخواست‌ها سازگار نیستند.')
    if 'received_count' in response and (type(response['received_count']) is not int or response['received_count'] != len(issues)):
        raise BadRequest('تعداد received_count با فهرست issues سازگار نیست.')
    seen, values = set(), []
    for issue in issues:
        if not isinstance(issue, dict) or not isinstance(issue.get('fields'), dict):
            raise BadRequest('ساختار issue یا fields معتبر نیست.')
        issue_id, key, fields = issue.get('id'), issue.get('key'), issue['fields']
        if (not isinstance(issue_id, str) or not issue_id.isascii() or not issue_id.isdigit()
                or len(issue_id) > 64 or issue_id in seen or not isinstance(key, str) or not key.strip() or len(key) > 128):
            raise BadRequest('شناسه یا کلید درخواست معتبر نیست یا شناسه در همین پاسخ تکرار شده است.')
        seen.add(issue_id)
        if 'description' not in fields:
            raise BadRequest('فیلد description در پاسخ موجود نیست؛ پاسخ را با فیلد توضیحات دریافت کنید. null مجاز است.')
        title, content = fields.get('summary'), fields.get('description')
        if content is None:
            content = ''  # Retain the original null in the source snapshot.
        requests.validate(dict(title=title, content=content, attachment_ids=[], expected_revision=1), (), origin='jira')
        values.append(dict(issue_id=issue_id, snapshot=issue, title=title, content=content,
            updated=timestamp(fields.get('updated')), digest=agents.digest([title, content])))
    return values, total, start


def runs_query(session, workspace_id, actor_id):
    managed = agents.definitions(session)
    return sa.select(WorkflowRun, App.name).join(App, App.id == WorkflowRun.app_id).where(
        WorkflowRun.tenant_id == str(workspace_id), App.tenant_id == str(workspace_id),
        WorkflowRun.created_by_role == 'account', WorkflowRun.created_by == str(actor_id),
        WorkflowRun.status == 'succeeded', App.mode == 'workflow',
        ~sa.exists(sa.select(managed.c.id).where(managed.c.app_id == App.id)))


def recent_runs(session, project_id, workspace_id, actor_id):
    authorize(session, project_id, workspace_id, actor_id)
    result = []
    for run, name in session.execute(runs_query(session, workspace_id, actor_id)
            .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc()).limit(50)):
        try:
            values, total, start = parse(run.outputs_dict)
        except (BadRequest, ValueError, TypeError):
            continue
        created_at = run.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        result.append(dict(id=run.id, app_name=name, created_at=created_at.isoformat(),
            received_count=len(values), total=total, start_at=start))
    return {'data': result}


def source_info(session, request_id, *, detail=False):
    sources = table(session)
    source = session.execute(sa.select(sources).where(sources.c.request_id == str(request_id))).mappings().first()
    if not source:
        return None
    fields = source['snapshot']['fields']
    label = lambda name: (fields.get(name) or {}).get('name') if isinstance(fields.get(name), dict) else None
    result = dict(base_url=source['base_url'], issue_id=source['issue_id'], key=source['snapshot']['key'],
        status=label('status'), priority=label('priority'), assignee=label('assignee'),
        updated_at=source['source_updated_at'].isoformat(), last_seen_at=source['last_seen_at'].isoformat(),
        needs_review=source['needs_review'])
    if detail:
        result.update(source_title=fields['summary'], source_content=fields.get('description'), last_run_id=source['last_run_id'])
    return result


def import_response(session, project_id, workspace_id, actor_id, data, key):
    if not isinstance(data, dict) or set(data) not in ({'base_url', 'response'}, {'base_url', 'run_id'}):
        raise BadRequest('نشانی پایه و یکی از response یا run_id لازم است.')
    key = agents.action_key(key)
    scoped = authorize(session, project_id, workspace_id, actor_id, write=True)
    address, run_id = base_url(data['base_url']), None
    if 'run_id' in data:
        from company_projects.store import uid
        run_id = str(uid(data['run_id']))
        run = session.execute(runs_query(session, workspace_id, actor_id).where(WorkflowRun.id == run_id)).first()
        if not run:
            raise NotFound('اجرای موفق خودتان در همین پروژه پیدا نشد یا برنامهٔ آن مدیریت‌شده است.')
        response = run[0].outputs_dict
    else:
        response = data['response']
    values, total, start = parse(response)
    fingerprint = agents.digest(dict(operation='jira.import', base_url=address, run_id=run_id, response=response))
    replay = agents.replay(session, scoped, actor_id, key, fingerprint)
    if replay:
        return replay
    sources, results = table(session), []
    for value in values:
        match = dict(**scoped, base_url=address, issue_id=value['issue_id'])
        link = session.execute(sa.select(sources).where(*(sources.c[k] == v for k, v in match.items()))
            .with_for_update()).mappings().first()
        if link and value['updated'] < link['source_updated_at']:
            results.append(dict(request_id=str(link['request_id']), key=value['snapshot']['key'], outcome='older_ignored'))
            continue
        current = requests.get_request(session, project_id, workspace_id, actor_id, link['request_id']) if link else None
        current_digest = agents.digest([current['title'], current['current']['content']]) if current else None
        local_diverged = bool(link and current_digest != link['applied_digest'])
        conflict = bool(local_diverged and value['digest'] != link['applied_digest'] and current_digest != value['digest'])
        # Re-reading an unchanged source must neither overwrite a PO refinement
        # nor misreport that local refinement as a new change at Jira.
        changed = not current or (current_digest != value['digest'] and not local_diverged)
        metadata_changed = bool(link and agents.digest(link['snapshot']) != agents.digest(value['snapshot']))
        if conflict:
            outcome = 'needs_review'
        elif changed:
            record = requests.save(session, project_id, workspace_id, actor_id,
                dict(title=value['title'], content=value['content'],
                    attachment_ids=current['current']['attachment_ids'] if current else [],
                    expected_revision=current['revision'] if current else 1),
                str(uuid5(UUID(key), value['issue_id'])), current['id'] if current else None, origin='jira')
            outcome = 'updated' if current else 'created'
        else:
            outcome = 'metadata_updated' if metadata_changed else 'unchanged'
        updates = dict(snapshot=value['snapshot'], source_updated_at=value['updated'],
            needs_review=conflict, last_seen_at=agents.now(), last_run_id=run_id,
            applied_digest=link['applied_digest'] if conflict else value['digest'])
        request_id = str(link['request_id']) if link else record['id']
        if link:
            session.execute(sources.update().where(*(sources.c[k] == v for k, v in match.items())).values(**updates))
        else:
            session.execute(sources.insert().values(**match, request_id=request_id, **updates))
        results.append(dict(request_id=request_id, key=value['snapshot']['key'], outcome=outcome))
    result = dict(data=results, received_count=len(values), total=total, start_at=start,
        has_more=start + len(values) < total)
    agents.event(session, scoped, actor_id, key, fingerprint, 'jira.imported', result)
    return result
