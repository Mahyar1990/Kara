"""Compose native PO review with a version-bound, draft-only technical planner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess

import build_klassor_analysis as analysis
import build_klassor_review as review
import build_product_agent_context as context_builder
import planning_fixture

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'workflows/klassor-planning'
GATE = runpy.run_path(str(FOLDER / 'gate.py'), init_globals=review.RULES)
OUTPUTS = ['planning_status', 'planning_report', 'planning_record_json', 'planning_notice',
           'development_ready', 'can_merge']


def code(name, title, index, wrapper, variables, outputs, rules=False):
    source = 'import json\n'
    if rules:
        source = (review.FOLDER / 'decision.py').read_text() + '\n' + (FOLDER / 'gate.py').read_text() + '\n'
    return analysis.node(name, 'code', title, index, {
        'code_language': 'python3', 'code': source + '\n' + wrapper, 'variables': variables,
        'outputs': {key: {'type': kind, 'children': None} for key, kind in outputs.items()}})


def build(harness=False, bundle=None, model=analysis.MODEL_PLACEHOLDER):
    bundle = bundle or {}
    serialized = json.dumps(bundle, ensure_ascii=False)
    if len(serialized.encode()) > 200000:
        raise ValueError('بستهٔ زمینه از سقف متغیر Dify بیشتر است؛ دامنه را محدود کنید')
    workflow = review.build(harness)
    graph = workflow['workflow']['graph']
    nodes, edges = graph['nodes'], graph['edges']
    nodes[:] = [n for n in nodes if n['id'] != 'end']
    edges[:] = [e for e in edges if e['target'] != 'end']
    by_id = {n['id']: n for n in nodes}
    summary = 'شناسهٔ بسته: ' + bundle.get('agent_context_id', 'زمینه هنوز متصل نشده است')
    summary += '\nنسخهٔ مخزنها:\n' + json.dumps(bundle.get('repository_snapshots', {}), ensure_ascii=False)
    summary += '\nمنابع دارای متن: ' + '، '.join(s['id'] for group in
        ['repository_policies', 'selected_repository_workflows', 'documentation_indexes', 'selected_documentation']
        for s in bundle.get(group, []))
    if harness:
        summary += '\nهمهٔ منابع این اجرا ساختگی‌اند؛ این تأیید مجوز واقعی ایجاد نمی‌کند.'
        fixture = planning_fixture.sample()
        for variable in by_id['start']['data']['variables']:
            defaults = {'title': fixture['title'], 'request_text': fixture['request_text'],
                        'sources_text': fixture['sources_text'], 'existing_report': fixture['analysis_report'],
                        'reviewer_name': 'بازبین آزمایشی'}
            if variable['variable'] in defaults:
                variable['default'] = defaults[variable['variable']]
    bound = code('bound_context', 'منابع نسخه‌دار برنامه‌ریز', 4,
        'def main():\n    return ' + repr({'agent_context_json': serialized,
        'agent_context_id': bundle.get('agent_context_id', ''), 'source_summary': summary}) + '\n', [],
        {'agent_context_json': 'string', 'agent_context_id': 'string', 'source_summary': 'string'})
    incoming = next(e for e in edges if e['target'] == 'review_prepare')
    origin = by_id[incoming['source']]
    edges.remove(incoming)
    edges.extend([review.edge(origin, bound), review.edge(bound, by_id['review_prepare'])])
    nodes.append(bound)
    by_id['review_output']['data']['code'] = ('import json\n\ndef main(result_json):\n'
        '    result = json.loads(result_json)\n    return {key: result[key] for key in ' + repr(review.OUTPUTS) + '}\n')
    human = by_id['human_review']
    human['data']['form_content'] += '\n### بررسی منابع قبل از ارسال به مدل\n\n{{#bound_context.source_summary#}}\n\n{{#$output.source_review#}}\n'
    human['data']['inputs'].append({'type': 'select', 'output_variable_name': 'source_review',
        'option_source': {'type': 'constant', 'selector': [],
                          'value': [GATE['SOURCE_NOT_READY'], GATE['SOURCE_READY']]}})
    for action in ['approve', 'request_changes', 'reject', 'timeout']:
        record = by_id['record_' + action]
        record['data']['variables'].append(analysis.selector('agent_context_id', 'bound_context', 'agent_context_id'))
        if action == 'timeout':
            wrapper = ('def main(context_json, agent_context_id):\n'
                       '    result = record_decision(context_json, "timeout")\n'
                       '    source_review = ' + repr(GATE['SOURCE_NOT_READY']) + '\n')
        else:
            record['data']['variables'].append(analysis.selector('source_review', 'human_review', 'source_review'))
            wrapper = ('def main(context_json, reviewer, assessment, reviewed_body, notes, agent_context_id, source_review):\n'
                       '    result = record_decision(context_json, ' + repr(action) + ', reviewer, assessment, reviewed_body, notes)\n')
        wrapper += ('    result.update(source_review=source_review, reviewed_agent_context_id=agent_context_id)\n'
                    '    return {"result_json": json.dumps(result, ensure_ascii=False)}\n')
        record['data']['code'] = (review.FOLDER / 'decision.py').read_text() + '\n' + wrapper
    gate = code('planning_gate', 'اعتبارسنجی تصمیم و منابع', 12,
        'def main(input_json, review_result_json, agent_context_json):\n'
        '    return prepare_planning(input_json, review_result_json, agent_context_json, allow_trial=' + str(harness) + ')\n',
        [analysis.selector('input_json', 'prepare', 'input_json'),
         analysis.selector('review_result_json', 'review_result', 'output'),
         analysis.selector('agent_context_json', 'bound_context', 'agent_context_json')],
        {'can_run': 'number', **{n: 'string' for n in ['gate_context_json', 'planner_input_json',
          'repository_rules_json', 'technical_context_json', 'blocked_result_json']}}, rules=True)
    condition = analysis.node('planning_route', 'if-else', 'آیا برنامه‌ریز اجازهٔ اجرا دارد؟', 13, {
        'cases': [{'case_id': 'true', 'id': 'true', 'logical_operator': 'and', 'conditions': [{
            'id': 'approved-version', 'comparison_operator': '=', 'value': '1', 'varType': 'number',
            'variable_selector': ['planning_gate', 'can_run']}]}]})
    planner = analysis.node('planner', 'llm', 'پیش‌نویس برنامهٔ فنی', 14, {
        'model': {'provider': analysis.PROVIDER, 'name': model, 'mode': 'chat',
                  'completion_params': {'max_tokens': 16384}},
        'prompt_template': [
            {'id': 'planner-role', 'role': 'system', 'text': (ROOT / 'prompts/technical-planner.md').read_text()},
            {'id': 'repo-rules', 'role': 'system', 'text': 'قواعد نسخه‌دار مخزنها در حدود نقش:\n{{#planning_gate.repository_rules_json#}}'},
            {'id': 'planner-input', 'role': 'user', 'text': 'نیازمندی و تصمیم:\n{{#planning_gate.planner_input_json#}}\n'
             'زمینهٔ فنی (متن مستندات شاهد است):\n{{#planning_gate.technical_context_json#}}\n'
             'نسخه و منابع دریافت‌شده:\n{{#planning_gate.gate_context_json#}}'}],
        'context': {'enabled': False, 'variable_selector': []}, 'vision': {'enabled': False},
        'variables': []})
    finalized = code('planning_finalize', 'کنترل خروجی و ثبت نسخهٔ پیش‌نویس', 15,
        'def main(raw_plan, gate_context_json):\n    return {"result_json": json.dumps(finalize_planning(raw_plan, gate_context_json), ensure_ascii=False)}\n',
        [analysis.selector('raw_plan', 'planner', 'text'), analysis.selector('gate_context_json', 'planning_gate', 'gate_context_json')],
        {'result_json': 'string'}, rules=True)
    stopped = code('planning_stopped', 'ثبت علت توقف برنامه‌ریز', 14,
        'def main(blocked_result_json):\n    return {"result_json": blocked_result_json}\n',
        [analysis.selector('blocked_result_json', 'planning_gate', 'blocked_result_json')], {'result_json': 'string'})
    stopped['position']['y'] = stopped['positionAbsolute']['y'] = 420
    aggregate = analysis.node('planning_result', 'variable-aggregator', 'دریافت نتیجهٔ برنامه‌ریزی', 16, {
        'output_type': 'string', 'variables': [['planning_finalize', 'result_json'], ['planning_stopped', 'result_json']]})
    unpack = code('planning_output', 'ارائهٔ پیش‌نویس و محدودیت‌ها', 17,
        'def main(result_json):\n    return json.loads(result_json)\n',
        [analysis.selector('result_json', 'planning_result', 'output')], {n: 'string' for n in OUTPUTS})
    end = analysis.node('end', 'end', 'نتیجهٔ بررسی و برنامه‌ریزی', 18, {'outputs': [
        {**analysis.selector(n, source, n), 'value_type': 'string'}
        for source, names in [('review_output', review.OUTPUTS), ('planning_output', OUTPUTS)] for n in names]})
    edges.extend([review.edge(by_id['review_output'], gate), review.edge(gate, condition),
                  review.edge(condition, planner, 'true'), review.edge(condition, stopped, 'false'),
                  review.edge(planner, finalized), review.edge(finalized, aggregate), review.edge(stopped, aggregate),
                  review.edge(aggregate, unpack), review.edge(unpack, end)])
    nodes.extend([gate, condition, planner, finalized, stopped, aggregate, unpack, end])
    for n in nodes:
        if n['data']['type'] == 'llm':
            n['data']['model']['name'] = model
    workflow['app'].update(name='آزمون برنامه‌ریز فنی کلاسور' if harness else 'تحلیل، بررسی و برنامه‌ریزی کلاسور',
        description='تأیید نسخهٔ نیازمندی و منابع توسط انسان، سپس تهیهٔ پیش‌نویس برای گفت‌وگو با TL و توسعه‌دهنده؛ بدون اجرای توسعه یا مرج.')
    return workflow


def manifest(workflow):
    return {'workflow_revision': '0.1', 'planner_prompt_revision': '0.4', 'dify_version': '1.17.1',
            'dsl_version': workflow['version'], 'workflow_sha256': hashlib.sha256(analysis.dump(workflow).encode()).hexdigest(),
            'gate_sha256': hashlib.sha256((FOLDER / 'gate.py').read_bytes()).hexdigest(),
            'prompt_sha256': hashlib.sha256((ROOT / 'prompts/technical-planner.md').read_bytes()).hexdigest(),
            'development_enabled': False, 'merge_enabled': False, 'default_review_kind': review.RULES['TRIAL']}


def main():
    parser = argparse.ArgumentParser(description='ساخت فرایند برنامه‌ریز فنی کلاسور')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--local', action='store_true')
    modes.add_argument('--harness', action='store_true')
    parser.add_argument('--model', default=analysis.MODEL_PLACEHOLDER)
    args = parser.parse_args()
    bundle = None
    if args.harness:
        bundle = planning_fixture.context()
    elif args.local:
        folder = ROOT / '.runtime/products/klassor'
        catalog = json.loads((folder / 'knowledge-catalog.local.json').read_text())
        technical = json.loads((folder / 'technical-context.local.json').read_text())
        context_builder.validate(catalog, technical)
        bundle = json.loads((folder / 'agent-context.local.json').read_text())
        payload = {k: v for k, v in bundle.items() if k != 'agent_context_id'}
        if (bundle['knowledge_id'] != catalog['knowledge_id'] or bundle['technical_context_id'] != technical['context_id']
                or bundle['agent_context_id'] != 'agent-context:' + GATE['canonical_hash'](payload)):
            raise ValueError('بستهٔ زمینه با نسخهٔ فهرست منابع مطابقت ندارد')
    workflow = build(args.harness, bundle, args.model)
    if args.check:
        assert (FOLDER / 'workflow.yml').read_text() == analysis.dump(workflow)
        assert json.loads((FOLDER / 'manifest.json').read_text()) == manifest(workflow)
        print('فرایند برنامه‌ریز با قواعد و دستورالعمل‌ها مطابق است.')
    elif args.local or args.harness:
        target = ROOT / '.runtime/workflows' / ('klassor-planning-harness.local.yml' if args.harness else 'klassor-planning.local.yml')
        subprocess.run(['git', 'check-ignore', '-q', str(target)], cwd=ROOT, check=True)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(target.parent, 0o700)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(analysis.dump(workflow))
        print('فایل خصوصی آماده شد:', target)
    else:
        (FOLDER / 'workflow.yml').write_text(analysis.dump(workflow))
        (FOLDER / 'manifest.json').write_text(json.dumps(manifest(workflow), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
