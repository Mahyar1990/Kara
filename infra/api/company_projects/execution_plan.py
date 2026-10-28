"""Public node requirements and explicit, credential-free execution choices."""
import json
from werkzeug.exceptions import BadRequest

PREFIX = 'kara-plan:'
WORK = {'llm', 'code', 'template-transform', 'http-request', 'knowledge-retrieval'}

def describe(graph):
    from company_projects.runtime_models import INPUT, policy
    policy(graph)  # Validate the declaration before exposing a plan.
    declared = next((v.get('kara_model_input', {}).get('capabilities', [])
        for n in graph.get('nodes', []) if n.get('data', {}).get('type') == 'start'
        for v in n['data'].get('variables', []) if v.get('variable') == INPUT), [])
    nodes = []
    for node in graph.get('nodes', []):
        data = node.get('data', {}); kind = data.get('type')
        caps = set(declared) if kind == 'llm' else set()
        if kind == 'llm' and data.get('vision', {}).get('enabled'): caps.add('vision')
        if kind == 'llm' and data.get('structured_output_enabled'): caps.add('json')
        requirements = ['node-routing-v1'] if kind in WORK else []
        if kind == 'code': requirements.append(data.get('code_language', ''))
        if kind == 'template-transform': requirements.append('python3')
        if kind == 'http-request': requirements.append('http')
        nodes.append(dict(id=node['id'], title=data.get('title') or node['id'], type=kind,
            capabilities=sorted(caps), runner_required=kind in WORK, requirements=requirements))
    return dict(version=2, capabilities=[], nodes=nodes)

def decode(value):
    if isinstance(value, str) and value.lstrip().startswith('{'):
        try: value = json.loads(value)
        except (ValueError, TypeError): raise BadRequest('تنظیمات اجرای گام‌ها معتبر نیست.') from None
    if isinstance(value, dict):
        if set(value) != {'version', 'models', 'runners'} or value['version'] != 2 or not isinstance(value['models'], dict) or not isinstance(value['runners'], dict):
            raise BadRequest('تنظیمات اجرای گام‌ها معتبر نیست.')
        return value
    return None

def require_choices(graph, value):
    plan = describe(graph); choice = decode(value)
    models = {n['id'] for n in plan['nodes'] if n['type'] == 'llm'}
    runners = {n['id'] for n in plan['nodes'] if n['runner_required']}
    if not models and not runners: return None
    if choice is None or set(choice['models']) != models or set(choice['runners']) != runners:
        raise BadRequest('برای هر گام LLM مدل و برای هر گام اجرایی Runner را صریحاً انتخاب کنید.')
    return choice
