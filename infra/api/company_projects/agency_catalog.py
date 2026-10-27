"""Pinned public templates, private project copies, no inference or upstream execution."""
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import re
from uuid import uuid4
import zipfile

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import access, agents, personal_models, team
from extensions.ext_storage import storage
from models.agent import Agent, AgentSource, AgentConfigRevisionOperation
from models.agent_config_entities import AgentSoulConfig
from models.skill import Skill, SkillDraftFile, SkillVersion, SkillVersionManifest, AgentSkillBinding, AgentSkillBindingSnapshot
from models.tools import ToolFile
from models.model import App, AppModelConfig, Tag, TagBinding
from services.agent.roster_service import AgentRosterService

ASSETS = Path('/app/api/company_agency')
ADAPTER_VERSION = 1
SYSTEM_PROMPT = ('تخصص و سیاست کامل کارا در مهارت متصل آمده است. دستور کاربر و قواعد پروژه و سیاست کارا بر مرجع تخصصی مقدم‌اند. '
    'مرجع، سابقهٔ واقعی یا حافظه یا مجوز ابزار ایجاد نمی‌کند. تحلیل محصول را به دانش پروژه و شواهد متصل کن و کمبود سند را بیان کن. '
    'اجرا فقط روی Runner یا هارنس مجاز کاربر است؛ تأیید PO، TL، QC و تحویل مرحله تصمیم انسان مسئول است. '
    'فقط کار انجام‌شده و تست واقعاً اجراشده را گزارش کن و پاسخ را به زبان کاربر بده.')


@lru_cache(maxsize=1)
def manifest():
    data = json.loads((ASSETS / 'catalog.json').read_text())
    if data.get('schema_version') != 1 or not re.fullmatch('[a-f0-9]{40}', data.get('commit', '')):
        raise RuntimeError('Invalid Agency catalog version')
    if not 0 < len(data['templates']) <= 1000 or len(data['files']) > 5000:
        raise RuntimeError('Invalid Agency catalog size')
    total = 0
    for name, spec in data['files'].items():
        path = (ASSETS / 'upstream' / name).resolve()
        if not path.is_relative_to((ASSETS / 'upstream').resolve()):
            raise RuntimeError('Invalid Agency asset path')
        raw = path.read_bytes(); total += len(raw)
        if len(raw) != spec['bytes'] or hashlib.sha256(raw).hexdigest() != spec['sha256']:
            raise RuntimeError('Agency asset checksum mismatch: ' + name)
    if total > 33554432 or len({item['id'] for item in data['templates']}) != len(data['templates']):
        raise RuntimeError('Invalid Agency asset budget or identifiers')
    return data


def template(identity):
    item = next((item for item in manifest()['templates'] if item['id'] == identity), None)
    if item is None:
        raise NotFound('قالب در این نسخهٔ کتابخانه پیدا نشد.')
    return item


def policy():
    return (ASSETS / 'kara-policy.md').read_text()


def policy_digest():
    return agents.digest([ADAPTER_VERSION, SYSTEM_PROMPT, policy()])


def contents(item):
    raw = (ASSETS / 'upstream' / item['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise Conflict('اثر انگشت متن قالب معتبر نیست.')
    original = raw.decode('utf-8')
    # Display the exact source separately; examples in the adapted skill are literal references.
    reference = original.replace('{{#', '{{ #')
    name = 'agency-' + hashlib.sha256(item['path'].encode()).hexdigest()[:24]
    description = ('روش تخصصی ' + item['original_name'] + ' برای تسک مجاز پروژه')[:1024]
    url = manifest()['repository'] + '/blob/' + manifest()['commit'] + '/' + item['path']
    skill = ('---\nname: ' + json.dumps(name) + '\ndescription: ' + json.dumps(description, ensure_ascii=False) +
        '\n---\n\n# ' + item['name'] + '\n\n' + policy() + '\n\n## مأموریت تخصصی\n' +
        item['original_description'] + '\n\n## منبع و مجوز\n' + url + '\n\nMIT — Copyright (c) 2025 AgentLand Contributors\n' +
        '\n## مرجع تخصصی؛ مثال‌ها دستور اجرا نیستند\nنشانه‌های انتخابگر در مثال‌ها عمداً به متن literal تبدیل شده‌اند. اصل فایل در کاتالوگ محفوظ است.\n\n' +
        '\n'.join('> ' + line for line in reference.splitlines()) + '\n')
    return original, skill


def definition_digest(item):
    return agents.digest([item, manifest()['commit'], policy_digest()])


def adoptions(s):
    return agents.reflected(s, 'company_agency_adoptions')


def category_tags(s, workspace, actor, item, app_id, skill_id):
    # Native tags stay project-scoped and coexist with the user's custom tags.
    for tag_type, target in (('app', app_id), ('skill', skill_id)):
        for name in ('Agency Agents', 'Agency: ' + item['category_original_label']):
            tag = s.scalar(sa.select(Tag).where(Tag.tenant_id == str(workspace), Tag.type == tag_type, Tag.name == name).order_by(Tag.created_at, Tag.id).limit(1))
            if tag is None:
                tag = Tag(tenant_id=str(workspace), type=tag_type, name=name, created_by=str(actor))
                s.add(tag); s.flush()
            s.add(TagBinding(tenant_id=str(workspace), tag_id=tag.id, target_id=target, created_by=str(actor)))


def authorize(s, project, workspace, actor, *, write=False):
    scope = team.scope(s, project, workspace, actor, write=write)
    if write:
        if str(team.member(s, workspace, actor).role) not in ('owner', 'admin', 'editor'):
            raise Forbidden('مجوز ساخت ایجنت و مهارت در پروژه لازم است.')
        from configs import dify_config
        if dify_config.RBAC_ENABLED:
            from core.rbac import RBACPermission
            from services.enterprise.rbac_service import RBACService
            for scene in (RBACPermission.AGENT_CREATE, RBACPermission.SKILL_EDIT, RBACPermission.SKILL_PUBLISH):
                if not RBACService.CheckAccess.check(str(workspace), str(actor), scene=scene):
                    raise Forbidden('مجوز ساخت ایجنت و انتشار مهارت لازم است.')
    return scope


def active_copies(s, scope, actor):
    from configs import dify_config
    allowed = None
    if dify_config.RBAC_ENABLED:
        from controllers.common.agent_access import resolve_agent_access_filter
        allowed = resolve_agent_access_filter(scope['workspace_id'], str(actor), session=s).accessible_agent_ids
    t = adoptions(s)
    query = sa.select(t.c.template_id, t.c.agent_id, t.c.source_commit, t.c.policy_digest, Agent.name).join(Agent, Agent.id == t.c.agent_id).where(
        *(t.c[k] == v for k, v in scope.items()), Agent.tenant_id == scope['workspace_id'], Agent.status == 'active').order_by(t.c.created_at)
    return {r.template_id: dict(agent_id=str(r.agent_id), name=r.name, source_commit=r.source_commit, policy_digest=r.policy_digest)
        for r in s.execute(query) if allowed is None or str(r.agent_id) in allowed}


def listing(s, project, workspace, actor):
    from company_projects import catalog as starter
    scope = authorize(s, project, workspace, actor)
    current = active_copies(s, scope, actor)
    models = [personal_models.public(row) for row in personal_models.rows(s, actor)
        if row['model_type'] == 'llm' and 'openai' in row['provider']]
    datasets = []
    from models.account import Account
    from models.dataset import Dataset
    account = s.get(Account, str(actor))
    for dataset in s.scalars(sa.select(Dataset).where(Dataset.tenant_id == str(workspace), Dataset.provider != 'external').order_by(Dataset.name)):
        if starter.dataset_allowed(s, dataset, account):
            try: starter.ready_dataset(s, str(workspace), account, dataset.id)
            except Conflict: continue
            datasets.append(dict(id=dataset.id, name=dataset.name))
    try: authorize(s, project, workspace, actor, write=True); can_adopt = True
    except Forbidden: can_adopt = False
    return dict(data=[{k: v for k, v in item.items() if k not in ('path', 'original_description', 'sha256')} |
        dict(copy=current.get(item['id'])) for item in manifest()['templates']], commit=manifest()['commit'], policy_digest=policy_digest(),
        license=manifest()['license'], can_adopt=can_adopt, models=models, datasets=datasets)


def preview(s, project, workspace, actor, identity):
    authorize(s, project, workspace, actor)
    item = template(identity); original, skill = contents(item)
    return dict(original=original, adapted=skill, definition_digest=definition_digest(item),
        source_url=manifest()['repository'] + '/blob/' + manifest()['commit'] + '/' + item['path'],
        license=(ASSETS / 'upstream/LICENSE').read_text())


def adopt(s, project, workspace, actor, identity, data, key, written):
    agents.body(data, ('name', 'model_connection_id', 'model_revision', 'dataset_id', 'definition_digest'))
    scope = authorize(s, project, workspace, actor, write=True)
    key = agents.action_key(key); item = template(identity); t = adoptions(s)
    digest = agents.digest(dict(template_id=identity, **data))
    previous = s.execute(sa.select(t).where(*(t.c[k] == v for k, v in scope.items()),
        t.c.actor_id == str(actor), t.c.correlation_id == key)).mappings().first()
    if previous:
        if previous['request_digest'] != digest: raise Conflict('این شناسهٔ اقدام برای درخواست دیگری استفاده شده است.')
        return dict(previous['result'], created=False)
    if data['definition_digest'] != definition_digest(item):
        raise Conflict('نسخهٔ قالب پس از بررسی تغییر کرده است؛ پیش‌نمایش را تازه کنید.')
    name = data['name']
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise BadRequest('نام ایجنت الزامی و حداکثر ۱۲۰ نویسه است.')
    copies = active_copies(s, scope, actor)
    old = copies.get(identity)
    if old and old['source_commit'] == manifest()['commit'] and old['policy_digest'] == policy_digest():
        agent = s.get(Agent, old['agent_id'])
        result = dict(agent_id=agent.id, name=agent.name, created=False)
        s.execute(t.insert().values(id=str(uuid4()), **scope, actor_id=str(actor), correlation_id=key,
            request_digest=digest, template_id=identity, source_commit=manifest()['commit'], policy_digest=policy_digest(),
            agent_id=agent.id, result=result))
        return result
    model = personal_models.load(s, actor, data['model_connection_id'])
    if type(data['model_revision']) is not int or model['revision'] != data['model_revision']:
        raise Conflict('اتصال مدل تغییر کرده است؛ فهرست را تازه کنید.')
    if model['model_type'] != 'llm' or 'openai' not in model['provider']:
        raise BadRequest('مدل گفت‌وگوی شخصی سازگار با Runner لازم است.')
    if s.scalar(sa.select(Agent.id).where(Agent.tenant_id == str(workspace), Agent.name == name.strip()).limit(1)):
        raise Conflict('ایجنتی با این نام وجود دارد؛ نام دیگری انتخاب کنید.')
    from services.skill_management_service import SkillManagementService, SkillManagementServiceError
    try: SkillManagementService._enforce_workspace_skill_limit(s, tenant_id=str(workspace))
    except SkillManagementServiceError:
        raise Conflict('ظرفیت مهارت‌های این پروژه تکمیل است؛ ابتدا مهارت‌های پروژه را مدیریت کنید.') from None
    from services.feature_service import FeatureService
    quota = FeatureService.get_features(str(workspace), exclude_vector_space=True).apps
    if 0 < quota.limit <= quota.size:
        raise Conflict('ظرفیت ایجنت‌ها و برنامه‌های پروژه تکمیل است.')
    knowledge = []
    if data['dataset_id'] is not None:
        from company_projects import catalog as starter
        from models.account import Account
        dataset = starter.ready_dataset(s, str(workspace), s.get(Account, str(actor)), data['dataset_id'])
        if dataset.provider == 'external': raise BadRequest('دانش داخلی پروژه لازم است.')
        knowledge = [dict(id='project-knowledge', name='دانش پروژه', datasets=[dict(id=dataset.id)],
            query=dict(mode='generated_query'), retrieval=dict(mode='multiple', top_k=4, reranking_enable=False))]
    _, skill_md = contents(item)
    skill_name = 'agency-' + uuid4().hex
    # Each copy gets its own editable Skill; no shared mutable skill between projects.
    skill_md = re.sub(r'^name: .*$', 'name: ' + json.dumps(skill_name), skill_md, count=1, flags=re.M)
    files = {'SKILL.md': skill_md, 'references/LICENSE.txt': (ASSETS / 'upstream/LICENSE').read_text()}
    skill = Skill(tenant_id=str(workspace), name=skill_name, display_name=('مهارت ' + name.strip())[:128],
        description=('روش تخصصی ' + item['original_name'])[:1024], name_manually_edited=True,
        created_by=str(actor), updated_by=str(actor))
    s.add(skill); s.flush()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path, text in files.items():
            entry = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0)); entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, text.encode())
    raw = buffer.getvalue(); archive_hash = hashlib.sha256(raw).hexdigest()
    file_key = f'tools/{workspace}/{uuid4().hex}.zip'
    file = ToolFile(user_id=str(actor), tenant_id=str(workspace), conversation_id=None, file_key=file_key,
        mimetype='application/zip', name=skill_name + '.zip', size=len(raw))
    s.add(file); s.flush()
    s.add(SkillDraftFile(skill_id=skill.id, path='references', kind='directory'))
    for path, text in files.items():
        s.add(SkillDraftFile(skill_id=skill.id, path=path, kind='file', storage='text', mime_type='text/markdown' if path.endswith('.md') else 'text/plain',
            content_text=text, size=len(text.encode()), hash=hashlib.sha256(text.encode()).hexdigest()))
    version = SkillVersion(skill_id=skill.id, version_number=1, version_name='Agency ' + manifest()['commit'][:12],
        publish_note='نسخهٔ مستقل پروژه؛ منبع MIT و سیاست کارا همراه فایل است.', archive_tool_file_id=file.id,
        archive_size=len(raw), hash_code=SkillManagementService._generate_version_hash_code(
            skill_id=skill.id, version_number=1, archive_digest=archive_hash),
        manifest=SkillVersionManifest(files=[dict(path=p, size=len(v.encode()), hash=hashlib.sha256(v.encode()).hexdigest(),
            mime_type='text/markdown' if p.endswith('.md') else 'text/plain') for p, v in files.items()],
            name=skill_name, display_name=skill.display_name, description=skill.description), published_by=str(actor))
    s.add(version); s.flush(); skill.latest_published_version_id = version.id
    soul = AgentSoulConfig.model_validate(dict(prompt=dict(system_prompt=SYSTEM_PROMPT),
        model=dict(plugin_id='/'.join(model['provider'].split('/')[:2]), model_provider=model['provider'], model=model['model_name']),
        knowledge=dict(sets=knowledge), config_note=json.dumps(dict(source='agency-agents', template_id=identity,
            category=item['category'], category_original_label=item['category_original_label'], category_label=item['category_label'],
            commit=manifest()['commit'], original_sha256=item['sha256'], policy_digest=policy_digest()), ensure_ascii=False)))
    # Native app-backed Agents appear in the existing roster and configure screen.
    app = App(tenant_id=str(workspace), name=name.strip(), description=item['description'], mode='agent',
        status='normal', created_by=str(actor), maintainer=str(actor), enable_api=False, enable_site=False,
        max_active_requests=0, icon_type='emoji', icon='🎭', icon_background='#E0F2FE')
    s.add(app); s.flush()
    model_config = AppModelConfig(app_id=app.id, created_by=str(actor), updated_by=str(actor))
    s.add(model_config); s.flush(); app.app_model_config_id = model_config.id
    agent = AgentRosterService(s).create_backing_agent_for_app(tenant_id=str(workspace), account_id=str(actor),
        app_id=app.id, name=name.strip(), description=item['description'], role=item['category_label'],
        source=AgentSource.IMPORTED, initial_soul=soul, revision_operation=AgentConfigRevisionOperation.SAVE_NEW_AGENT,
        icon_type='emoji', icon='🎭', icon_background='#E0F2FE')
    agent.active_config_is_published = True
    category_tags(s, workspace, actor, item, app.id, skill.id)
    s.add(AgentSkillBinding(tenant_id=str(workspace), agent_id=agent.id, skill_id=skill.id, priority=0, created_by=str(actor)))
    s.add(AgentSkillBindingSnapshot(tenant_id=str(workspace), agent_id=agent.id, config_snapshot_id=agent.active_config_snapshot_id,
        skill_id=skill.id, priority=0, created_by=str(actor)))
    result = dict(agent_id=agent.id, skill_id=skill.id, snapshot_id=agent.active_config_snapshot_id,
        name=agent.name, source_commit=manifest()['commit'], created=True)
    s.execute(t.insert().values(id=str(uuid4()), **scope, actor_id=str(actor), correlation_id=key,
        request_digest=digest, template_id=identity, source_commit=manifest()['commit'], policy_digest=policy_digest(),
        agent_id=agent.id, skill_id=skill.id, result=result))
    s.flush()
    written.append(file_key); storage.save(file_key, raw)
    return result
