"""Bounded TL draft validation. No human approval, execution or merge authority."""
import json
from pathlib import Path
from clasor_agents.pa04.contract import ContractError, bounded, canonical, digest, parse
from .handoff import REPOSITORIES

ROOT = Path(__file__).parent
VERSION = '0.1.0'
OUTPUT_SCHEMA = json.loads((ROOT/'schemas/output.schema.json').read_text())


def validate_plan(text, prepared_input, expected_input_sha256):
    """Expected hash is saved by the trusted caller after prepare(), never the model.

    Hash the complete prepared input, including human receipt and private source
    snapshots. For human edits call this directly; run metadata belongs to attempts.
    """
    input_hash = digest(canonical(prepared_input))
    if input_hash != expected_input_sha256:
        raise ContractError('planner_input_mismatch')
    # prepare() already validated the input. Do not accept an arbitrary model
    # object as prepared_input or derive the expected hash from received output.
    analysis = parse(prepared_input['analysis'])
    result = parse(text)
    bounded(result, OUTPUT_SCHEMA)
    if (result['input_sha256'] != input_hash
            or result['analysis_sha256'] != prepared_input['binding']['analysis_sha256']
            or result['analysis_sha256'] != digest(prepared_input['analysis'])):
        raise ContractError('plan_binding_mismatch')
    if result['scope'] != analysis['scope']:
        raise ContractError('plan_scope_changed')
    ac_ids = {ac['id'] for ac in analysis['acceptance_criteria']}
    sources = {'analysis': None}
    for repo, context in prepared_input['repositories'].items():
        for kind in ('repository_rules', 'evidence'):
            for source in context[kind]:
                key = f"{repo}/{kind}/{source['path']}"
                if key in sources:
                    raise ContractError('duplicate_context_source')
                sources[key] = (repo, kind)

    def references(refs):
        if not set(refs) <= sources.keys():
            raise ContractError('unknown_plan_source')

    def technical(refs, repo):
        return any(sources[r] is not None and sources[r][0] == repo for r in refs)

    impacts = {r['repository']: r for r in result['repository_impact']}
    if set(impacts) != REPOSITORIES:
        raise ContractError('repository_impact_incomplete')
    ready = result['status'] == 'ready_for_technical_discussion'
    for repo, impact in impacts.items():
        references(impact['source_refs'])
        if ready and (impact['effect'] == 'unknown'
                      or not technical(impact['source_refs'], repo)):
            raise ContractError('repository_impact_unsubstantiated')
    tasks = {t['id']: t for t in result['tasks']}
    if len(tasks) != len(result['tasks']):
        raise ContractError('duplicate_task')
    for task in tasks.values():
        references(task['source_refs'])
        if not set(task['ac_ids']) <= ac_ids:
            raise ContractError('unknown_plan_ac')
        if not set(task['depends_on']) <= tasks.keys():
            raise ContractError('unknown_task_dependency')
        for repo in task['repositories']:
            if impacts[repo]['effect'] == 'unrelated':
                raise ContractError('task_repository_conflict')
            if ready and not technical(task['source_refs'], repo):
                raise ContractError('task_source_required')
    # Kahn's algorithm avoids recursion and rejects self and multi-task cycles.
    pending = {key:set(t['depends_on']) for key,t in tasks.items()}
    while pending:
        free = {key for key,deps in pending.items() if not deps}
        if not free:
            raise ContractError('cyclic_task_dependency')
        pending = {key:deps-free for key,deps in pending.items() if key not in free}
    covered, linked_tasks = set(), set()
    for row in result['coverage']:
        if row['ac_id'] not in ac_ids:
            raise ContractError('unknown_plan_ac')
        if not set(row['task_ids']) <= tasks.keys():
            raise ContractError('unknown_coverage_task')
        if any(row['ac_id'] not in tasks[t]['ac_ids'] for t in row['task_ids']):
            raise ContractError('coverage_task_ac_mismatch')
        references(row['method_source_refs'])
        repo = row['test_repository']
        expected_repo = {'newman':'newman','playwright':'playwright'}.get(row['method'])
        if ((expected_repo and repo != expected_repo)
                or (row['method'] == 'repository_check' and repo is None)
                or (row['method'] == 'manual' and repo is not None)):
            raise ContractError('test_repository_mismatch')
        used = {r for t in row['task_ids'] for r in tasks[t]['repositories']}
        if repo is not None:
            if impacts[repo]['effect'] == 'unrelated':
                raise ContractError('test_repository_conflict')
            used.add(repo)
            if ready and not technical(row['method_source_refs'], repo):
                raise ContractError('test_method_source_required')
        versions = {v['repository']:v['commit'] for v in row['versions']}
        if len(versions) != len(row['versions']) or set(versions) != used:
            raise ContractError('test_versions_incomplete')
        if any(commit != prepared_input['repositories'][r]['commit'] for r,commit in versions.items()):
            raise ContractError('test_version_mismatch')
        covered.add(row['ac_id'])
        linked_tasks.update((t,row['ac_id']) for t in row['task_ids'])
    if covered != ac_ids:
        raise ContractError('uncovered_ac')
    if any((t['id'],ac) not in linked_tasks for t in tasks.values() for ac in t['ac_ids']):
        raise ContractError('task_without_coverage')
    questions = result['questions']
    if len({q['id'] for q in questions}) != len(questions):
        raise ContractError('duplicate_question')
    for question in questions:
        if not set(question['ac_ids']) <= ac_ids:
            raise ContractError('unknown_plan_ac')
    po_blocked = any(q['blocking'] and q['owner'] == 'PO' for q in questions)
    tl_blocked = any(q['blocking'] and q['owner'] == 'TL' for q in questions)
    expected_status = ('needs_product_decision' if po_blocked else
                       'needs_technical_review' if tl_blocked else 'ready_for_technical_discussion')
    if result['status'] != expected_status:
        raise ContractError('plan_status_conflict')
    for proposal in result['proposals']:
        references(proposal['source_refs'])
    return result


def validate_attempt(attempt, prepared_input, expected_input_sha256):
    """Metadata must come from trusted native records; never guess stop."""
    if type(attempt) is not dict or set(attempt) != {'status','finish_reason','outputs'}:
        raise ContractError('attempt_fields')
    if attempt['status'] != 'succeeded':
        raise ContractError('attempt_incomplete')
    if attempt['finish_reason'] != 'stop':
        raise ContractError('incomplete_output')
    if type(attempt['outputs']) is not dict or set(attempt['outputs']) != {'plan'}:
        raise ContractError('output_fields')
    return validate_plan(attempt['outputs']['plan'], prepared_input, expected_input_sha256)


def manifest():
    """Reproducible offline contract inventory, separate from future Workflow."""
    files = ('contract.py', 'handoff.py', 'schemas/output.schema.json', 'fixtures/cases.json')
    return dict(kind='kara-agent-contract', role_id='TL-PLANNER', contract_version=VERSION,
        status='offline-contract-only', live_model_test=False, workflow_revision=None,
        artifacts={name:digest((ROOT/name).read_text()) for name in files},
        limits=dict(max_payload_bytes=32768, max_tasks=30, automatic_model_retries=0))
