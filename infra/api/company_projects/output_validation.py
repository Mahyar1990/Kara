"""Replay an explicitly declared, pinned Code validator; never invoke a model."""
import copy

import sqlalchemy as sa
from werkzeug.exceptions import Conflict, UnprocessableEntity

from company_projects import agents
from models.workflow import Workflow, WorkflowNodeExecutionModel, WorkflowRun

def definition(workflow):
    nodes = workflow.graph_dict.get('nodes', [])
    declared = [node for node in nodes if 'kara_output_validator' in node.get('data', {})]
    if not declared:
        return None
    if len(declared) != 1:
        raise UnprocessableEntity('فقط یک اعتبارسنج خروجی صریح در هر Workflow پشتیبانی می‌شود.')
    node = declared[0]
    data, config = node['data'], node['data']['kara_output_validator']
    if not isinstance(config, dict) or set(config) != {'version', 'candidate_arguments'} or type(config['version']) is not int or config['version'] != 1:
        raise UnprocessableEntity('قرارداد اعتبارسنج خروجی معتبر نیست.')
    if data.get('type') != 'code' or data.get('code_language') != 'python3' or not isinstance(data.get('code'), str) or not data['code'].strip() or len(data['code'].encode()) > 262144:
        raise UnprocessableEntity('اعتبارسنج خروجی باید Code پایتون نسخه‌دار باشد.')
    arguments = config['candidate_arguments']
    variables = data.get('variables', [])
    if not isinstance(variables, list) or any(not isinstance(item, dict) or not isinstance(item.get('variable'), str) for item in variables):
        raise UnprocessableEntity('ورودی‌های اعتبارسنج معتبر نیستند.')
    names = [item.get('variable') for item in variables]
    ends = [node for node in nodes if node.get('data', {}).get('type') == 'end']
    outputs = ends[0]['data'].get('outputs', []) if len(ends) == 1 else []
    if not isinstance(arguments, dict) or not arguments or any(not isinstance(k, str) or not isinstance(v, str) for k, v in arguments.items()) or (
            len(names) != len(set(names)) or not set(arguments) <= set(names) or not outputs or
            len({item['variable'] for item in outputs}) != len(outputs) or
            set(arguments.values()) != {item['variable'] for item in outputs} or
            len(set(arguments.values())) != len(arguments) or
            any(item.get('value_selector') != [node['id'], item['variable']] for item in outputs)):
        raise UnprocessableEntity('ورودی پیشنهادی و تمام خروجی‌های End باید به همان اعتبارسنج متصل باشند.')
    return node


def context(session, stage, selected, workflow, node):
    """Use native execution inputs, never context or metadata submitted by a client."""
    from company_projects import stages
    native = agents.tables(session)[2]
    attempt = session.execute(sa.select(native).where(native.c.id == selected['attempt_id'],
        native.c.agent_id == stage['binding']['agent_id'], native.c.workflow_id == workflow.id,
        native.c.project_id == stage['project_id'], native.c.workspace_id == stage['workspace_id'])).mappings().first()
    bridge = stages.tables(session)[2]
    link = session.execute(sa.select(bridge).where(bridge.c.attempt_id == selected['attempt_id'],
        bridge.c.stage_id == stage['id'])).mappings().first()
    run = session.get(WorkflowRun, selected['attempt_id'])
    if not attempt or attempt['status'] != 'succeeded' or not link or (
            link['round'] != stage['round'] or link['input_digest'] != stage['input_digest'] or
            attempt['inputs'] != stage['inputs'] or not run or run.status != 'succeeded' or
            run.workflow_id != workflow.id or run.tenant_id != stage['workspace_id'] or
            run.app_id != workflow.app_id or run.created_by != attempt['actor_id']):
        raise Conflict('منشأ اجرایی معتبر برای اعتبارسنج خروجی در دسترس نیست.')
    query = sa.select(WorkflowNodeExecutionModel).where(
        WorkflowNodeExecutionModel.workflow_run_id == run.id,
        WorkflowNodeExecutionModel.tenant_id == stage['workspace_id'],
        WorkflowNodeExecutionModel.app_id == workflow.app_id,
        WorkflowNodeExecutionModel.workflow_id == workflow.id,
        WorkflowNodeExecutionModel.node_id == node['id'])
    executions = list(session.scalars(WorkflowNodeExecutionModel.preload_offload_data_and_files(query)))
    if len(executions) != 1 or executions[0].status != 'succeeded' or executions[0].node_type != 'code' or executions[0].created_by != attempt['actor_id']:
        raise Conflict('اجرای یکتای موفق اعتبارسنج و ورودی آن لازم است.')
    from extensions.ext_storage import storage
    try:
        inputs = executions[0].load_full_inputs(session, storage)
    except Exception:
        raise Conflict('زمینهٔ کامل ثبت‌شدهٔ اعتبارسنج در دسترس نیست.') from None
    names = {item['variable'] for item in node['data']['variables']}
    if not isinstance(inputs, dict) or set(inputs) != names:
        raise Conflict('زمینهٔ ثبت‌شدهٔ اعتبارسنج ناقص است.')
    return copy.deepcopy(inputs)


def execute(code, inputs):
    from core.helper.code_executor.code_executor import CodeExecutor, CodeLanguage
    try:
        return CodeExecutor.execute_workflow_code_template(CodeLanguage.PYTHON3, code, inputs)
    except Exception:
        # Sandbox errors may contain source/context. Do not expose them to HTTP.
        raise UnprocessableEntity('اعتبارسنج تخصصی خروجی را نپذیرفت یا در دسترس نیست؛ خروجی اصلاح و دوباره بررسی شود.') from None


def validate(session, stage, selected, content):
    from company_projects.stages import validate_output
    validate_output(stage['binding'], content)
    workflow = session.get(Workflow, stage['binding']['workflow_id'])
    if not workflow or agents.fingerprint(workflow) != stage['binding']['workflow_digest']:
        raise Conflict('نسخهٔ اعتبارسنج با نسخهٔ ثابت مرحله یکسان نیست.')
    node = definition(workflow)
    if node is None:
        return content, None  # Existing generic workflows retain their contract.
    inputs = context(session, stage, selected, workflow, node)
    for argument, output in node['data']['kara_output_validator']['candidate_arguments'].items():
        if output not in content:
            raise UnprocessableEntity('خروجی پیشنهادی ناقص است.')
        inputs[argument] = content[output]
    normalized = execute(node['data']['code'], inputs)
    validate_output(stage['binding'], normalized)
    proof = dict(validator_node_id=node['id'], workflow_id=workflow.id,
        workflow_digest=stage['binding']['workflow_digest'], code_digest=agents.digest(node['data']['code']),
        attempt_id=selected['attempt_id'], artifact_id=selected['id'], input_digest=stage['input_digest'],
        candidate_digest=agents.digest(content), content_digest=agents.digest(normalized), outcome='passed')
    return normalized, proof
