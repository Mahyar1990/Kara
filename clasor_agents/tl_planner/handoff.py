"""Read-only specialized preflight on Kara's recipient handoff projection."""
from copy import deepcopy
import re
from clasor_agents.pa04.contract import ContractError, canonical, digest, validate_output

REPOSITORIES = {'server', 'client', 'newman', 'playwright'}


def prepare(pa04_package, tl_stage, expected_receipt, repositories):
    """Receipt is independently saved after human PO finalization by trusted caller.

    No upstream stage history is needed by the recipient. This is a local check,
    not proof of human identity/ACL or installation of a server validation hook.
    """
    try:
        return _prepare(pa04_package, tl_stage, expected_receipt, repositories)
    except (KeyError, TypeError, AttributeError):
        raise ContractError('handoff_fields') from None


def _prepare(package, stage, receipt, repositories):
    b = package['expected_binding']
    if (stage['project_id'] != b['project_id']
            or stage['workspace_id'] != package['provenance']['workspace_id']
            or stage['instance_id'] != package['provenance']['instance_id']
            or stage['id'] == b['stage_id'] or stage['intake_valid'] is not True
            or stage['input_error'] is not None or stage['state'] != 'ready'):
        raise ContractError('handoff_not_ready')
    fields = {'stage_id', 'artifact_id', 'digest', 'decision_id', 'finalized_by', 'finalized_at'}
    if (set(receipt) != fields or receipt['stage_id'] != b['stage_id']
            or any(type(v) is not str or not v.strip() for v in receipt.values())):
        raise ContractError('finalization_receipt_required')
    matches = [h for h in stage['handoffs'] if h['input'] == 'analysis' and h['output'] == 'analysis']
    if len(matches) != 1:
        raise ContractError('selected_analysis_required')
    h = matches[0]
    if any(h[k] != receipt[k] for k in fields):
        raise ContractError('handoff_receipt_mismatch')
    if stage['preview_inputs'].get('analysis') != h['content']:
        raise ContractError('handoff_content_mismatch')
    analysis = validate_output(h['content'], package['envelope'], b)
    if analysis['status'] != 'ready_for_review':
        raise ContractError('analysis_not_ready')
    if set(repositories) != REPOSITORIES:
        raise ContractError('repository_baselines_required')
    for repo in repositories.values():
        if (repo['ref'] != 'refs/remotes/origin/sandbox'
                or type(repo['commit']) is not str
                or re.fullmatch('[0-9a-f]{40}', repo['commit']) is None):
            raise ContractError('repository_baseline_mismatch')
        # Source text is supplied explicitly; an index is not technical evidence.
        for kind in ('repository_rules', 'evidence'):
            for source in repo[kind]:
                if (source['commit'] != repo['commit'] or not source['path']
                        or not source['content'] or digest(source['content']) != source['sha256']):
                    raise ContractError('repository_source_mismatch')
    result = dict(contract_version='0.1.0', role_id='TL-PLANNER',
        binding=dict(project_id=b['project_id'], request_id=b['request_id'],
            request_revision_id=b['request_revision_id'], request_sha256=b['request_sha256'],
            stage_id=stage['id'], base_revision=stage['revision'],
            analysis_sha256=digest(h['content']), finalization=deepcopy(receipt)),
        request=package['envelope']['request']['text'], analysis=h['content'],
        repositories=deepcopy(repositories), status='draft_contract_only')
    if len(canonical(result).encode('utf-8')) > 32768:
        raise ContractError('transport_budget')
    return result
