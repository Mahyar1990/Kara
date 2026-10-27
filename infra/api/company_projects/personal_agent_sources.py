"""Freeze an explicitly reviewed, task-oriented roster Agent into a local workflow.

This is a compiler for stateless text tasks, not a proxy to the native Agent SDK.
No inference, tool execution, credential export, or source mutation happens here.
"""
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import PurePosixPath
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import agents, store, team
from models.agent import Agent, AgentConfigSnapshot, AgentConfigRevision
from models.model import App
from models.workflow import Workflow

FEATURE = 'kara_personal_agent'
VERSION = 1
LIMIT = 1048576


def permission(s, workspace, actor, source_id, *, export=False):
    from configs import dify_config
    if not dify_config.RBAC_ENABLED:
        return
    from controllers.common.agent_access import resolve_agent_access_filter
    from core.rbac import RBACPermission
    from services.enterprise.rbac_service import RBACService
    allowed = resolve_agent_access_filter(str(workspace), str(actor), session=s).accessible_agent_ids
    scene = RBACPermission.AGENT_IMPORT_EXPORT_DSL if export else RBACPermission.AGENT_TEST_AND_RUN
    if (allowed is not None and str(source_id) not in allowed) or not RBACService.CheckAccess.check(
            str(workspace), str(actor), scene=scene, resource_type='agent', resource_id=str(source_id)):
        raise Forbidden('مجوز استفاده از این ایجنت کتابخانه را ندارید.')


def load(s, workspace, identity, snapshot_id=None):
    source = s.scalar(sa.select(Agent).where(Agent.id == store.uid(identity), Agent.tenant_id == str(workspace)).execution_options(populate_existing=True))
    if not source or str(source.scope) != 'roster' or str(source.status) != 'active':
        raise NotFound('ایجنت کتابخانه فعال در این پروژه پیدا نشد.')
    snapshot = s.scalar(sa.select(AgentConfigSnapshot).where(
        AgentConfigSnapshot.id == store.uid(snapshot_id or source.active_config_snapshot_id),
        AgentConfigSnapshot.agent_id == source.id, AgentConfigSnapshot.tenant_id == str(workspace)).execution_options(populate_existing=True)) if (
            snapshot_id or source.active_config_snapshot_id) else None
    if not snapshot:
        raise Conflict('ایجنت کتابخانه نسخهٔ منتشرشده ندارد؛ ابتدا آن را منتشر کنید.')
    from core.agent.publish_visibility import PUBLISH_VISIBLE_APP_BACKED_REVISION_OPERATIONS
    if (str(source.source) == 'agent_app' or (str(source.source) == 'imported' and source.app_id)) and not s.scalar(
            sa.select(AgentConfigRevision.id).where(AgentConfigRevision.tenant_id == str(workspace),
                AgentConfigRevision.agent_id == source.id, AgentConfigRevision.current_snapshot_id == snapshot.id,
                AgentConfigRevision.operation.in_(PUBLISH_VISIBLE_APP_BACKED_REVISION_OPERATIONS)).limit(1)):
        raise Conflict('نسخهٔ ایجنت کتابخانه برای استفاده در فرایند منتشر نشده است.')
    if source.app_id:
        app = s.get(App, source.app_id)
        if not app or app.tenant_id != str(workspace) or str(app.status) != 'normal':
            raise Conflict('برنامهٔ منبع ایجنت کتابخانه در دسترس نیست.')
    return source, snapshot


def snapshot_digest(snapshot):
    return agents.digest([snapshot.config_snapshot_dict, snapshot.home_snapshot_id, snapshot.version])


def metadata(workflow):
    return workflow.features_dict.get(FEATURE) if workflow else None


def catalog_filter(s):
    """Generated adapters are managed in Team Agents, not the editable app catalog."""
    events = agents.reflected(s, 'company_team_agent_events')
    return ~sa.exists(sa.select(events.c.id).where(events.c.workspace_id == App.tenant_id,
        events.c.event_type == 'agent.personal-source.registered',
        events.c.result['app_id'].astext == sa.cast(App.id, sa.Text)))


def skill_version_digest(version):
    return agents.digest([version.skill_id, version.version_number, version.hash_code,
        version.archive_tool_file_id, version.manifest.model_dump(mode='json'), version.archive_size])


def skill_permission(workspace, actor, skill):
    from configs import dify_config
    if dify_config.RBAC_ENABLED:
        from core.rbac import RBACPermission
        from services.enterprise.rbac_service import RBACService
        if not RBACService.CheckAccess.check(str(workspace), str(actor), scene=RBACPermission.SKILL_VIEW,
                resource_type='skill', resource_id=str(skill.id)):
            raise Forbidden('مجوز خواندن مهارت ایجنت کتابخانه را ندارید.')


def validate(s, workflow, actor=None):
    """Fresh lifecycle/ACL fencing; newer published versions never replace the pin."""
    meta = metadata(workflow)
    if meta is None:
        return
    if not isinstance(meta, dict) or meta.get('version') != VERSION:
        raise Conflict('اتصال ایجنت کتابخانه معتبر نیست.')
    source, snapshot = load(s, workflow.tenant_id, meta['agent_id'], meta['snapshot_id'])
    if snapshot_digest(snapshot) != meta['snapshot_digest']:
        raise Conflict('نسخهٔ ثابت ایجنت کتابخانه تغییر کرده است؛ اتصال تازه بسازید.')
    if actor:
        permission(s, workflow.tenant_id, actor, source.id)
    from models.skill import Skill, SkillVersion
    for pin in meta['skills']:
        if 'skill_id' not in pin:
            continue  # Uploaded packages are embedded in this immutable workflow.
        skill = s.get(Skill, pin['skill_id'])
        version = s.get(SkillVersion, pin['version_id'])
        if not skill or skill.tenant_id != workflow.tenant_id or not version or (
                version.skill_id != skill.id or skill_version_digest(version) != pin['digest']):
            raise Conflict('نسخهٔ مهارت متصل به ایجنت کتابخانه در دسترس نیست.')
        if actor:
            skill_permission(workflow.tenant_id, actor, skill)


def public(workflow):
    meta = metadata(workflow)
    if meta is None:
        return None
    return {key: meta[key] for key in ('agent_id', 'name', 'snapshot_id', 'snapshot_version', 'model', 'skills')}


def package_text(s, workspace, file_id, expected_hash=None):
    """Bounded in-memory extraction; never writes or executes archive contents."""
    from models.tools import ToolFile
    from extensions.ext_storage import storage
    file = s.get(ToolFile, store.uid(file_id))
    if not file or file.tenant_id != str(workspace):
        raise UnprocessableEntity('فایل مهارت در همین پروژه پیدا نشد.')
    chunks = []; size = 0
    try:
        for chunk in storage.load(file.file_key, stream=True):
            size += len(chunk)
            if size > LIMIT:
                raise UnprocessableEntity('مهارت متنی باید کمتر از یک مگابایت باشد.')
            chunks.append(chunk)
        raw = b''.join(chunks)
        digest = hashlib.sha256(raw).hexdigest()
        if expected_hash and expected_hash != digest:
            raise UnprocessableEntity('اثر انگشت فایل مهارت معتبر نیست.')
        parts = []; paths = set(); total = 0
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if len(archive.infolist()) > 100:
                raise UnprocessableEntity('تعداد فایل‌های مهارت بیش از حد مجاز است.')
            for entry in sorted(archive.infolist(), key=lambda e: e.filename):
                path = PurePosixPath(entry.filename)
                if entry.is_dir():
                    continue
                if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or (
                        entry.filename in paths or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise UnprocessableEntity('مسیر فایل مهارت معتبر نیست.')
                paths.add(entry.filename); total += entry.file_size
                if total > LIMIT or path.suffix.lower() not in ('.md', '.txt'):
                    raise UnprocessableEntity('اتصال تیمی فعلاً مهارت‌های متنی md و txt را می‌پذیرد؛ فایل اجرایی یا باینری را به هارنس محلی بسپارید.')
                value = archive.read(entry).decode('utf-8')
                if '\x00' in value:
                    raise UnprocessableEntity('متن مهارت معتبر نیست.')
                parts.append(f'\n### {entry.filename}\n{value}')
        if 'SKILL.md' not in paths:
            raise UnprocessableEntity('مهارت باید فایل SKILL.md داشته باشد.')
        return '\n'.join(parts), digest
    except (UnprocessableEntity, Forbidden):
        raise
    except Exception:
        raise UnprocessableEntity('خواندن نسخهٔ متنی مهارت انجام نشد.') from None


def skills(s, source, snapshot, actor):
    from models.skill import AgentSkillBindingSnapshot, Skill, SkillVersion
    texts = []; pins = []
    # Snapshot bindings only: unpublished draft bindings must never leak into a team version.
    bindings = list(s.scalars(sa.select(AgentSkillBindingSnapshot).where(
        AgentSkillBindingSnapshot.tenant_id == source.tenant_id,
        AgentSkillBindingSnapshot.agent_id == source.id,
        AgentSkillBindingSnapshot.config_snapshot_id == snapshot.id).order_by(AgentSkillBindingSnapshot.priority).limit(21)))
    attached = snapshot.config_snapshot_dict.get('config_skills', [])
    if len(bindings) + len(attached) > 20:
        raise UnprocessableEntity('حداکثر بیست مهارت برای هر اتصال انتخاب کنید.')
    total = 0
    def append(text, pin):
        nonlocal total
        total += len(text.encode())
        if total > LIMIT:
            raise UnprocessableEntity('حجم مهارت‌های این اتصال بیش از بودجهٔ مجاز است.')
        texts.append(text); pins.append(pin)
    for binding in bindings:
        skill = s.get(Skill, binding.skill_id)
        if not skill or skill.tenant_id != source.tenant_id:
            raise UnprocessableEntity('مهارت متصل به نسخهٔ ایجنت در دسترس نیست.')
        skill_permission(source.tenant_id, actor, skill)
        version = s.get(SkillVersion, skill.latest_published_version_id) if skill.latest_published_version_id else None
        if not version or version.skill_id != skill.id:
            raise UnprocessableEntity('مهارت متصل باید نسخهٔ منتشرشده داشته باشد.')
        text, archive_hash = package_text(s, source.tenant_id, version.archive_tool_file_id)
        append(f'\n## Skill: {skill.name}\n{text}', dict(skill_id=skill.id, name=skill.display_name, version_id=version.id,
            version=version.version_number, digest=skill_version_digest(version), archive_digest=archive_hash))
    for item in attached:
        if item.get('is_missing') or not item.get('file_id'):
            raise UnprocessableEntity('فایل مهارت پیوست‌شده در دسترس نیست.')
        text, archive_hash = package_text(s, source.tenant_id, item['file_id'], item.get('hash'))
        append(f"\n## Skill: {item['name']}\n{text}", dict(name=item['name'], file_id=item['file_id'], archive_digest=archive_hash))
    return '\n'.join(texts), pins


def configuration(snapshot):
    c = snapshot.config_snapshot_dict
    unsupported = []
    if snapshot.home_snapshot_id: unsupported.append('فایل‌ها و محیط Home')
    if any(c['tools'].values()): unsupported.append('ابزارها و فرمان‌های ایجنت')
    if any(c['human'].values()): unsupported.append('ابزارهای تماس انسانی')
    if any(c['env'].values()): unsupported.append('متغیرها و کلیدهای محیط')
    if c['config_files']: unsupported.append('فایل‌های پیوست')
    if any(c['memory'].values()): unsupported.append('حافظهٔ پایدار')
    if c['sandbox']['provider'] or any(c['sandbox']['config'].values()): unsupported.append('محیط اختصاصی')
    for section in ('app_features', 'misc_legacy'):
        # Chat presentation/upload toggles do not grant file inputs to a text task.
        # Moderation is an execution policy and must never be silently removed.
        value = c[section].get('sensitive_word_avoidance')
        if value and (value.get('enabled') or any(isinstance(v, dict) and v.get('enabled') for v in value.values())):
            unsupported.append('بررسی محتوای گفت‌وگو')
    if unsupported:
        raise UnprocessableEntity('این نسخه به پشتیبانی محلی بیشتری نیاز دارد: ' + '، '.join(dict.fromkeys(unsupported)) + '. از برنامهٔ تیمی سازگار یا هارنس شخصی استفاده کنید.')
    if not c.get('model'):
        raise UnprocessableEntity('مدل ایجنت کتابخانه را پیش از اتصال تنظیم و منتشر کنید.')
    if 'openai' not in c['model']['model_provider']:
        raise UnprocessableEntity('این اتصال به مدل سازگار با OpenAI روی Runner نیاز دارد؛ برای مدل‌های دیگر از هارنس شخصی یا برنامهٔ سازگار استفاده کنید.')
    return c


def template(value, names):
    """Translate declared form variables only; unknown native selectors fail closed."""
    def replace(match):
        key = match.group(1).strip()
        if key in ('query', 'sys.query'): key = 'task'
        if key.startswith('start.'): key = key[6:]
        if key not in names:
            raise UnprocessableEntity('متغیر متن ایجنت برای اجرای تیمی شناخته‌شده نیست: ' + key[:100])
        return '{{#start.' + key + '#}}'
    return re.sub(r'\{\{#?([^{}#]+)#?\}\}', replace, value)


def query_template(value, names):
    if '{%' in value or re.search(r'(?<!\{)\{#', value):
        raise UnprocessableEntity('متن جستجو فقط متن و متغیرهای اعلام‌شده را می‌پذیرد؛ دستور قالب پشتیبانی نمی‌شود.')
    variables = []
    chunks = []
    for part in re.split(r'(\{\{#start\.[A-Za-z][A-Za-z0-9_]*#\}\})', template(value, names)):
        if part.startswith('{{#start.') and part.endswith('#}}'):
            name = f'kara_query_{len(variables)}'
            variables.append(dict(variable=name, value_selector=['start', part[9:-3]]))
            chunks.append('{{ ' + name + ' }}')
        elif part:
            chunks.append('{{ ' + repr(part) + ' }}')
    return ''.join(chunks), variables


def compile_graph(s, source, snapshot, actor):
    c = configuration(snapshot)
    text_skills, skill_pins = skills(s, source, snapshot, actor)
    variables = [dict(variable='task', label='شرح تسک و نیازمندی', type='paragraph', required=True, max_length=120000),
        dict(variable='feedback_context', label='بازخورد مرحلهٔ قبل', type='paragraph', required=False, default='', max_length=120000)]
    names = {'task', 'feedback_context'}
    kinds = {'string': 'paragraph', 'text': 'paragraph', 'paragraph': 'paragraph', 'text-input': 'text-input', 'number': 'number', 'boolean': 'checkbox', 'checkbox': 'checkbox'}
    for item in c['app_variables']:
        name = item['name']; kind = kinds.get(item['type'])
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name) or name in names or name == 'query' or not kind:
            raise UnprocessableEntity('نام یا نوع متغیر ایجنت برای اتصال تیمی پشتیبانی نمی‌شود.')
        default = item.get('default')
        if default is not None and ((kind == 'number' and type(default) not in (int, float)) or (
                kind == 'checkbox' and type(default) is not bool) or (kind in ('paragraph', 'text-input') and not isinstance(default, str))):
            raise UnprocessableEntity('مقدار پیش‌فرض متغیر ایجنت معتبر نیست.')
        variables.append(dict(variable=name, label=name, type=kind, required=item['required'], default=default, max_length=120000))
        names.add(name)
    params = {k: v for k, v in c['model']['model_settings'].items() if v is not None}
    # Local model transport must not silently discard provider-specific parameters.
    if set(params) - {'temperature', 'top_p', 'presence_penalty', 'frequency_penalty', 'max_tokens', 'stop', 'response_format'}:
        raise UnprocessableEntity('پارامتر اختصاصی مدل این ایجنت به پشتیبانی Runner نیاز دارد.')
    model = dict(provider=c['model']['model_provider'], name=c['model']['model'], mode='chat', completion_params=params)
    nodes = [dict(id='start', data=dict(type='start', title='ورودی تسک', variables=variables))]
    def add(identity, **data): nodes.append(dict(id=identity, data=data))
    knowledge_prompts = []
    from models.dataset import Dataset
    from company_projects.local_execution import check_dataset
    if len(c['knowledge']['sets']) > 10:
        raise UnprocessableEntity('حداکثر ده مجموعهٔ دانش برای هر اتصال انتخاب کنید.')
    for i, group in enumerate(c['knowledge']['sets']):
        retrieval = group['retrieval']; query = group['query']; identity = f'knowledge_{i}'
        if '{{#' in group['name']:
            raise UnprocessableEntity('نام مجموعهٔ دانش نباید انتخابگر فرایند داشته باشد.')
        if retrieval['mode'] != 'multiple' or retrieval.get('weights') or retrieval.get('model') or (
                retrieval.get('reranking_mode') != 'reranking_model' or group['metadata_filtering']['mode'] != 'disabled'):
            raise UnprocessableEntity('این تنظیم جستجوی دانش به پشتیبانی محلی بیشتری نیاز دارد؛ بازیابی چندمنبعی بدون فیلتر فراداده پشتیبانی می‌شود.')
        top = retrieval.get('top_k') or 4
        if top > 20:
            raise UnprocessableEntity('تعداد نتیجهٔ دانش برای Runner حداکثر بیست است.')
        for selected in group['datasets']:
            dataset = s.get(Dataset, store.uid(selected['id']))
            if not dataset or dataset.tenant_id != source.tenant_id or dataset.provider == 'external':
                raise UnprocessableEntity('دانش داخلی همین پروژه برای اجرای محلی لازم است.')
            check_dataset(s, dataset, actor, source.tenant_id)
        if query['mode'] == 'generated_query':
            add(f'query_{i}', type='llm', title='تولید عبارت جستجو', model=model,
                prompt_template=[dict(role='system', text='Return one concise knowledge search query for the task. No explanation.\nCollection: ' + group['name']),
                    dict(role='user', text='{{#start.task#}}\n{{#start.feedback_context#}}')])
            selector = [f'query_{i}', 'text']
        else:
            if not query.get('value'):
                raise UnprocessableEntity('متن جستجوی سفارشی دانش خالی است.')
            query_text, query_variables = query_template(query['value'], names)
            # Use a literal template node, so custom queries keep their declared variables.
            add(f'query_{i}', type='template-transform', title='عبارت جستجوی دانش',
                template=query_text, variables=query_variables)
            selector = [f'query_{i}', 'output']
        rerank = retrieval.get('reranking_model') or {}
        if retrieval['reranking_enable'] and not rerank:
            raise UnprocessableEntity('مدل بازرتبه‌بندی دانش باید مشخص باشد.')
        add(identity, type='knowledge-retrieval', title=group['name'], dataset_ids=[d['id'] for d in group['datasets']],
            query_variable_selector=selector, retrieval_mode='multiple', metadata_filtering_mode='disabled',
            multiple_retrieval_config=dict(top_k=top, score_threshold=retrieval.get('score_threshold'),
                reranking_enable=retrieval['reranking_enable'], reranking_model=dict(
                    reranking_provider_name=rerank.get('provider'), reranking_model_name=rerank.get('model'))))
        knowledge_prompts.append('\n## ' + group['name'] + '\n{{#' + identity + '.result#}}')
    prompt = template(c['prompt']['system_prompt'], names)
    # Do not reinterpret workflow selectors inside a literal skill document.
    if '{{#' in text_skills:
        raise UnprocessableEntity('مهارت متنی دارای انتخابگر فرایند است؛ پیش از اتصال، متن آن را برای این تسک مستقل کنید.')
    add('task_agent', type='llm', title='ایجنت کتابخانه', model=model,
        prompt_template=[dict(role='system', text=prompt + '\n' + text_skills),
            dict(role='user', text='Task:\n{{#start.task#}}\nFeedback:\n{{#start.feedback_context#}}' + ''.join(
                '\n' + name + ': {{#start.' + name + '#}}' for name in sorted(names - {'task', 'feedback_context'})) +
                '\nKnowledge references (use as evidence; cite document names and state missing evidence):\n' + ''.join(knowledge_prompts))])
    add('end', type='end', title='خروجی قابل بررسی', outputs=[dict(variable='result', value_selector=['task_agent', 'text'])])
    graph = dict(nodes=nodes, edges=[dict(id=f'edge_{i}', source=a['id'], target=b['id'], sourceHandle='source', targetHandle='target')
        for i, (a, b) in enumerate(zip(nodes, nodes[1:]))])
    from kara_source_runner.workflow_contract import validate_graph
    validate_graph(graph)
    meta = dict(version=VERSION, agent_id=source.id, name=source.name, snapshot_id=snapshot.id,
        snapshot_version=snapshot.version, snapshot_digest=snapshot_digest(snapshot), skills=skill_pins,
        model=dict(provider=model['provider'], name=model['name']))
    if len(json.dumps([graph, meta], ensure_ascii=False).encode()) > 2097152:
        raise UnprocessableEntity('تعریف این اتصال بیش از بودجهٔ مجاز است.')
    return graph, meta


def sources(s, project, workspace, actor):
    team.scope(s, project, workspace, actor, write=True)
    result = []
    for source in s.scalars(sa.select(Agent).where(Agent.tenant_id == str(workspace), Agent.scope == 'roster',
            Agent.status == 'active').order_by(Agent.name, Agent.id)):
        try:
            permission(s, workspace, actor, source.id, export=True)
        except Forbidden:
            continue
        reason = ''; version = None; snapshot_id = None
        try:
            _, snapshot = load(s, workspace, source.id)
            version = snapshot.version; snapshot_id = snapshot.id
            configuration(snapshot)
        except (Conflict, NotFound, UnprocessableEntity) as exc:
            reason = exc.description
        result.append(dict(id=source.id, name=source.name, snapshot_id=snapshot_id, version=version, unavailable_reason=reason))
    return dict(data=result)


def preview(s, project, workspace, actor, identity, snapshot_id):
    team.scope(s, project, workspace, actor, write=True)
    permission(s, workspace, actor, identity, export=True)
    source, snapshot = load(s, workspace, identity, snapshot_id)
    try:
        graph, meta = compile_graph(s, source, snapshot, actor)
    except UnprocessableEntity as exc:
        return dict(available=False, reason=exc.description)
    return dict(available=True, source_digest=agents.digest([graph, meta]),
        input_contract=graph['nodes'][0]['data']['variables'], output_contract=['result'],
        model=meta['model'], skills=meta['skills'], knowledge=[g['name'] for g in snapshot.config_snapshot_dict['knowledge']['sets']])


def register(s, project, workspace, actor, data, key):
    agents.body(data, ('personal_agent_id', 'snapshot_id', 'source_digest', 'name', 'description', 'expected_revision'))
    agents.revision(data['expected_revision'])
    if data['expected_revision'] != 1:
        raise Conflict('نسخهٔ آغاز تعریف باید یک باشد.')
    for field, limit in (('name', 120), ('description', 2000)):
        if not isinstance(data[field], str) or len(data[field]) > limit or (field == 'name' and not data[field].strip()):
            raise UnprocessableEntity('نام و توضیح ایجنت معتبر نیست.')
    key = agents.action_key(key)
    scope = team.scope(s, project, workspace, actor, write=True)
    fingerprint = agents.digest(dict(operation='register-personal', **data))
    previous = agents.replay(s, scope, actor, key, fingerprint)
    if previous:
        return previous
    permission(s, workspace, actor, data['personal_agent_id'], export=True)
    source, snapshot = load(s, workspace, data['personal_agent_id'], data['snapshot_id'])
    if snapshot.id != source.active_config_snapshot_id:
        raise Conflict('نسخهٔ فعال منبع تغییر کرده است؛ فهرست را تازه کنید.')
    from configs import dify_config
    from services.feature_service import FeatureService
    quota = FeatureService.get_features(str(workspace), exclude_vector_space=True).apps
    if 0 < quota.limit <= quota.size:
        raise Forbidden('ظرفیت برنامه‌های پروژه تکمیل است؛ اتصال ایجنت یک برنامهٔ نسخه‌دار ایجاد می‌کند.')
    if dify_config.RBAC_ENABLED:
        from core.rbac import RBACPermission
        from services.enterprise.rbac_service import RBACService
        for scene in (RBACPermission.APP_CREATE_AND_MANAGEMENT, RBACPermission.APP_RELEASE_AND_VERSION):
            if not RBACService.CheckAccess.check(str(workspace), str(actor), scene=scene):
                raise Forbidden('مجوز ساخت و انتشار برنامه برای ایجاد اتصال تیمی لازم است.')
    graph, meta = compile_graph(s, source, snapshot, actor)
    if agents.digest([graph, meta]) != data['source_digest']:
        raise Conflict('تنظیمات منبع یا نسخهٔ مهارت‌ها پس از بررسی تغییر کرده‌اند؛ پیش‌نمایش را تازه کنید.')
    # One transaction with the team definition: no AppService commits/signals/orphan programs.
    app = App(tenant_id=str(workspace), name=('برنامهٔ اتصال ' + data['name'].strip())[:255], mode='workflow',
        description='اتصال ثابت ایجنت کتابخانه به اجرای تیمی؛ مدیریت از صفحهٔ ایجنت‌های تیم.', status='normal',
        created_by=str(actor), maintainer=str(actor), enable_site=False, enable_api=False, max_active_requests=0)
    s.add(app); s.flush()
    workflow = Workflow.new(tenant_id=str(workspace), app_id=app.id, type='workflow', version='personal-agent-' + snapshot.id,
        graph=json.dumps(graph, ensure_ascii=False), features=json.dumps({FEATURE: meta}, ensure_ascii=False), created_by=str(actor),
        environment_variables=[], conversation_variables=[], rag_pipeline_variables=[], marked_name=f'ایجنت کتابخانه · نسخهٔ {snapshot.version}')
    s.add(workflow); s.flush(); app.workflow_id = workflow.id
    # The normal registration function keeps the same contracts, grants, execution and provenance.
    result = agents.register(s, project, workspace, actor, dict(app_id=app.id, workflow_id=workflow.id,
        name=data['name'], description=data['description'], expected_revision=1), str(uuid4()), _personal=True)
    agents.event(s, scope, actor, key, fingerprint, 'agent.personal-source.registered', result)
    return result
