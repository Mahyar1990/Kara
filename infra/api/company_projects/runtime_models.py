"""Resolve a declared program model input into an ephemeral, account-bound graph."""
from copy import deepcopy
import json
import math
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, HTTPException

from company_projects import personal_models
from company_projects.personal_model_runtime import require_actor, require_account_execution
from extensions.ext_database import db
from graphon.model_runtime.entities.model_entities import ModelType
from models.workflow import Workflow

INPUT = '__kara_model_connection'
FROZEN = '__kara_execution_selection'
EXTRA = 'kara_runtime_model'
PROVIDER = 'kara/runtime'
CAPABILITIES = {'json', 'tools', 'vision'}


def enable_graph(graph):
    graph = deepcopy(graph)
    starts = [node for node in graph.get('nodes', []) if node.get('data', {}).get('type') == 'start']
    if len(starts) != 1:
        raise BadRequest('ورودی مدل اجراکننده به یک مرحلهٔ شروع دستی نیاز دارد.')
    variables = starts[0]['data'].setdefault('variables', [])
    if not any(item.get('variable') == INPUT for item in variables):
        variables.insert(0, dict(variable=INPUT, label='مدل اجرای برنامه', type='text-input', required=False,
            max_length=36, options=[], kara_model_input=dict(version=1, capabilities=[])))
    for node in llm_nodes(graph):
        node['data']['model'].update(provider=PROVIDER, name='executor-model')
        node['data'].pop('model_selector', None)
    return graph


def policy(graph):
    entries = [item for node in graph.get('nodes', []) if node.get('data', {}).get('type') == 'start'
        for item in node['data'].get('variables', []) if item.get('variable') == INPUT]
    if not entries:
        return None
    if len(entries) != 1 or entries[0].get('type') != 'text-input':
        raise BadRequest('ورودی مدل اجرای برنامه باید یکتا و از نوع اتصال مدل باشد.')
    value = entries[0].get('kara_model_input')
    if not isinstance(value, dict) or set(value) != {'version', 'capabilities'} or value['version'] != 1:
        raise BadRequest('تعریف ورودی مدل اجرای برنامه معتبر نیست.')
    capabilities = value['capabilities']
    if not isinstance(capabilities, list) or any(not isinstance(item, str) or item not in CAPABILITIES for item in capabilities):
        raise BadRequest('نیازمندی‌های مدل اجرای برنامه معتبر نیست.')
    required = set(capabilities)
    for node in llm_nodes(graph):
        data = node['data']
        if data.get('vision', {}).get('enabled'):
            required.add('vision')
        if data.get('structured_output_enabled'):
            required.add('json')
    return dict(version=1, capabilities=sorted(required))


def llm_nodes(graph):
    return [node for node in graph.get('nodes', []) if node.get('data', {}).get('type') == 'llm']


def form_variables(graph, variables):
    from company_projects.execution_plan import describe, PREFIX
    result = deepcopy(variables)
    if any(n.get('data', {}).get('kara_runtime_model_used') for n in graph.get('nodes', [])):
        return [item for item in result if item.get('variable') != INPUT]
    plan = describe(graph)
    if not any(n['runner_required'] for n in plan['nodes']):
        return [item for item in result if item.get('variable') != INPUT]
    if not any(item.get('variable') == INPUT for item in result):
        result.insert(0, dict(variable=INPUT, label='مدل‌ها و دستگاه‌های اجرا', type='text-input'))
    for item in result:
        if item.get('variable') == INPUT:
            item.update(options=[PREFIX + json.dumps(plan, ensure_ascii=False)], required=True, max_length=262144)
    return result


def business_inputs(inputs):
    if not isinstance(inputs, dict):
        raise BadRequest('ورودی برنامه معتبر نیست.')
    return {key: value for key, value in inputs.items() if key not in (INPUT, FROZEN)}


def schema_for(tenant_id, actor_id, row):
    from core.plugin.impl.model_runtime_factory import create_plugin_model_runtime
    runtime = create_plugin_model_runtime(tenant_id=str(tenant_id), user_id=str(actor_id))
    try:
        return runtime.get_model_schema(provider=row['provider'], model_type=ModelType.LLM,
            model=row['model_name'], credentials=personal_models.decrypt(row))
    except HTTPException:
        raise
    except Exception:
        raise BadRequest('دریافت قابلیت‌های مدل شخصی انجام نشد؛ اتصال، نصب افزونه و دسترسی شبکه را بررسی کنید.') from None


def check_schema(schema, requirements, nodes=()):
    if schema is None or str(schema.model_properties.get('mode', '')) != 'chat':
        raise BadRequest('مدل اجرای این برنامه باید از نوع گفت‌وگو (chat) باشد.')
    features = {str(item) for item in schema.features or []}
    supported = dict(vision='vision' in features, tools=bool(features & {'tool-call', 'multi-tool-call'}),
        json='structured-output' in features or any(rule.name == 'response_format' and
            bool(set(rule.options or []) & {'json_object', 'json_schema'}) for rule in schema.parameter_rules))
    missing = set(requirements) - {key for key, available in supported.items() if available}
    if missing:
        labels = {'json': 'خروجی JSON', 'tools': 'فراخوانی ابزار', 'vision': 'پردازش تصویر'}
        raise BadRequest('مدل انتخاب‌شده نیاز برنامه را پشتیبانی نمی‌کند: ' + '، '.join(labels[item] for item in sorted(missing)))
    rules = {rule.name: rule for rule in schema.parameter_rules}
    for node in nodes:
        for name, value in node['data'].get('model', {}).get('completion_params', {}).items():
            if name == 'stop' and isinstance(value, list) and all(isinstance(item, str) for item in value):
                continue
            rule = rules.get(name)
            if rule is None:
                raise BadRequest('پارامتر مرحله با مدل انتخاب‌شده سازگار نیست: ' + name)
            kind = str(rule.type)
            if ((kind in {'int', 'float'} and (type(value) not in (int, float) or not math.isfinite(value)))
                    or (kind == 'int' and type(value) is not int)
                    or (kind == 'boolean' and type(value) is not bool)
                    or (kind in {'string', 'text'} and not isinstance(value, str))):
                raise BadRequest('نوع پارامتر مرحله با مدل انتخاب‌شده سازگار نیست: ' + name)
            if rule.options and value not in rule.options:
                raise BadRequest('مقدار پارامتر مرحله با مدل انتخاب‌شده سازگار نیست: ' + name)
            if type(value) in (int, float) and ((rule.min is not None and value < rule.min) or (rule.max is not None and value > rule.max)):
                raise BadRequest('پارامتر مرحله خارج از محدودهٔ مدل انتخاب‌شده است: ' + name)


def select(session, workflow, actor_id, requested=None):
    graph = workflow.graph_dict
    from company_projects.execution_plan import decode, describe
    choice = decode(requested)
    if choice is not None:
        identity = require_actor(workflow.tenant_id, actor_id)
        nodes = {n['id']: n for n in llm_nodes(graph)}
        if set(choice['models']) != set(nodes):
            raise BadRequest('مدل همهٔ گام‌های LLM همین نسخه را انتخاب کنید.')
        requirements = {n['id']: n['capabilities'] for n in describe(graph)['nodes']}
        models = {}; schemas = {}
        for key, node in nodes.items():
            selected = choice['models'][key]
            if not isinstance(selected, str): raise BadRequest('شناسهٔ مدل گام معتبر نیست.')
            try: UUID(selected)
            except ValueError: raise BadRequest('مدل هر گام را صریحاً انتخاب کنید.') from None
            row = personal_models.load(session, identity, selected)
            if row['model_type'] != 'llm': raise BadRequest('مدل گام باید از نوع LLM باشد.')
            if selected not in schemas: schemas[selected] = schema_for(workflow.tenant_id, identity, row)
            check_schema(schemas[selected], requirements[key], [node])
            models[key] = dict(connection_id=str(row['id']), connection_revision=row['revision'],
                provider=row['provider'], model_name=row['model_name'])
        return dict(version=2, actor_id=identity, tenant_id=str(workflow.tenant_id), workflow_id=str(workflow.id), models=models)
    requirements = policy(graph)
    if requirements is None or not llm_nodes(graph):
        if requested:
            raise BadRequest('این برنامه ورودی مدل اجراکننده ندارد یا مرحلهٔ LLM ندارد.')
        return None
    identity = require_actor(workflow.tenant_id, actor_id)
    if requested:
        if not isinstance(requested, str):
            raise BadRequest('اتصال مدل را از فهرست شخصی خودتان انتخاب کنید.')
        try:
            UUID(requested)
        except ValueError:
            raise BadRequest('شناسهٔ اتصال مدل معتبر نیست.') from None
        row = personal_models.load(session, identity, requested)
    else:
        row = next((item for item in personal_models.rows(session, identity)
            if item['model_type'] == 'llm' and item['is_default']), None)
        if row is None:
            raise BadRequest('مدل شخصی پیش‌فرض ندارید؛ اتصال مدل خودتان را ثبت یا انتخاب کنید.')
    if row['model_type'] != 'llm':
        raise BadRequest('اتصال انتخاب‌شده باید مدل متنی LLM باشد.')
    check_schema(schema_for(workflow.tenant_id, identity, row), requirements['capabilities'], llm_nodes(graph))
    return dict(version=1, actor_id=identity, tenant_id=str(workflow.tenant_id), workflow_id=str(workflow.id),
        connection_id=row['id'], connection_revision=row['revision'], provider=row['provider'], model_name=row['model_name'],
        mode='chat', capabilities=requirements['capabilities'])


def execution_workflow(workflow, selection, actor_id):
    if selection is None:
        if policy(workflow.graph_dict) is not None and llm_nodes(workflow.graph_dict):
            raise Forbidden('انتخاب مدل شخصی این اجرا ثبت نشده است.')
        return workflow
    identity = require_actor(workflow.tenant_id, actor_id)
    if (selection.get('actor_id'), selection.get('tenant_id'), selection.get('workflow_id')) != (
            identity, str(workflow.tenant_id), str(workflow.id)):
        raise Forbidden('انتخاب مدل متعلق به این کاربر، پروژه و نسخهٔ برنامه نیست.')
    chosen = selection['models'] if selection.get('version') == 2 else {n['id']: selection for n in llm_nodes(workflow.graph_dict)}
    if set(chosen) != {n['id'] for n in llm_nodes(workflow.graph_dict)}: raise Forbidden('انتخاب مدل گام‌ها کامل نیست.')
    rows = {}
    with Session(db.engine) as session:
        for key, selected in chosen.items():
            row = personal_models.load(session, identity, selected['connection_id'])
            if (row['provider'], row['model_name'], row['revision'], row['model_type']) != (
                    selected['provider'], selected['model_name'], selected['connection_revision'], 'llm'):
                raise Conflict('اتصال مدل پس از انتخاب تغییر کرده است؛ اجرا را با تنظیمات تازه شروع کنید.')
            rows[key] = row
    graph = deepcopy(workflow.graph_dict)
    for node in graph.get('nodes', []):
        data = node.get('data', {})
        if data.get('type') == 'start':
            data['variables'] = [item for item in data.get('variables', []) if item.get('variable') != INPUT]
            data['kara_runtime_model_used'] = deepcopy(selection)
        if data.get('type') == 'llm':
            row = rows[node['id']]
            data['model'] = dict(data.get('model', {}), provider=row['provider'], name=row['model_name'], mode='chat')
            if isinstance(data.get('prompt_template'), dict):
                data['prompt_template'] = [dict(data['prompt_template'], role='user')]
            data.pop('model_selector', None)
    # A separate, transient ORM object cannot dirty the published source session.
    clone = Workflow(**{prop.key: getattr(workflow, prop.key) for prop in sa.inspect(Workflow).column_attrs})
    import json
    clone.graph = json.dumps(graph, ensure_ascii=False)
    return clone


def prepare(workflow, user, inputs):
    require_account_execution(workflow.tenant_id, user)
    clean = business_inputs(inputs)
    with Session(db.engine) as session:
        selection = select(session, workflow, user.id, inputs.get(INPUT))
    return execution_workflow(workflow, selection, user.id), clean, selection


def attempt_inputs(session, workflow, actor_id, inputs):
    from company_projects.execution_plan import require_choices, decode
    if FROZEN in inputs: raise BadRequest('انتخاب ثبت‌شدهٔ اجرا قابل ارسال توسط کاربر نیست.')
    clean = business_inputs(inputs)
    choice = require_choices(workflow.graph_dict, inputs.get(INPUT))
    if choice:
        from company_projects.node_routing import validate_choices
        validate_choices(session, workflow, actor_id, choice)
    selection = select(session, workflow, actor_id, inputs.get(INPUT))
    if selection and selection.get('version') == 2:
        # Freeze revisions at admission, not when a background worker eventually dispatches.
        choice = decode(inputs[INPUT])
        clean[INPUT] = json.dumps(choice, ensure_ascii=False)
        clean[FROZEN] = selection
        return clean
    return dict(clean, **{INPUT: selection['connection_id']}) if selection else clean


def execution_extras(args):
    value = args.get('_kara_runtime_selection') if isinstance(args, dict) else getattr(args, '_kara_runtime_selection', None)
    return {EXTRA: value} if value else {}


def bind_runner(runner):
    entity = runner.application_generate_entity
    runner._workflow = execution_workflow(runner._workflow, entity.extras.get(EXTRA), entity.user_id)


def options(session, tenant_id, actor_id, capabilities):
    if set(capabilities) - CAPABILITIES:
        raise BadRequest('نیازمندی مدل معتبر نیست.')
    require_actor(tenant_id, actor_id)
    result = []
    for row in personal_models.rows(session, actor_id):
        if row['model_type'] != 'llm':
            continue
        try:
            check_schema(schema_for(tenant_id, actor_id, row), capabilities)
        except Exception:
            continue  # Missing plugin, incompatible model or unavailable metadata is not a usable option.
        result.append(personal_models.public(row))
    return dict(data=result)
