"""PA-04 input assembly from authenticated Kara read snapshots; no HTTP or writes."""
from copy import deepcopy
from .contract import (ContractError, VERSION, build_inputs, canonical, digest,
                       source_bundle, validate_analysis)


def assemble(request, instance, stage, source_catalog, selected_source_ids, *,
             mode='analyze', feedback_context='', previous_artifact_id=None):
    """Caller supplies authorized, fresh API reads and a trusted source catalog.

    IDs select records, never model-provided content. This local preflight does
    not replace server ACL, optimistic locking, or finalization validation.
    """
    try:
        return _assemble(request, instance, stage, source_catalog, selected_source_ids,
                         mode, feedback_context, previous_artifact_id)
    except (KeyError, TypeError, AttributeError):
        raise ContractError('snapshot_fields') from None


def _assemble(request, instance, stage, catalog, selected, mode, feedback, previous_id):
    current = request['current']
    for key in ('project_id', 'workspace_id'):
        if len({request[key], current[key], instance[key], stage[key]}) != 1:
            raise ContractError('snapshot_scope_mismatch')
    if (current['request_id'] != request['id'] or instance['request_id'] != request['id']
            or instance['request_revision_id'] != current['id']
            or request['current_revision_id'] != current['id']
            or instance['request_digest'] != current['digest']
            or stage['instance_id'] != instance['id']):
        raise ContractError('snapshot_revision_mismatch')
    if (request['intake_valid'] is not True or instance['intake_valid'] is not True
            or stage['intake_valid'] is not True or instance['state'] == 'cancelled'
            or stage['input_error'] is not None):
        raise ContractError('snapshot_not_ready')
    # Feedback can currently overwrite the generic request input: fail locally.
    if stage['preview_inputs'].get('request') != current['content']:
        raise ContractError('original_request_changed')
    if (type(selected) is not list or any(type(i) is not str for i in selected)
            or len(selected) != len(set(selected))):
        raise ContractError('source_selection')
    by_id = {s['id']: s for s in catalog}
    if len(by_id) != len(catalog) or not set(selected) <= by_id.keys():
        raise ContractError('source_selection')
    sources = deepcopy([by_id[i] for i in sorted(selected)])
    previous = None
    artifact_digest = None
    if previous_id is not None:
        matches = [a for a in stage['artifacts'] if a['id'] == previous_id]
        if len(matches) != 1:
            raise ContractError('previous_artifact_missing')
        artifact = matches[0]
        feedback_parent = any(
            f['round'] == stage['round'] and f['parent_artifact_id'] == previous_id
            and f['input_digest'] == stage['input_digest']
            and f['inputs']['effective'] == stage['preview_inputs']
            for f in stage.get('feedback', []))
        current_artifact = (artifact['round'] == stage['round']
                            and artifact['input_digest'] == stage['input_digest'])
        if (artifact['stage_id'] != stage['id'] or artifact['project_id'] != stage['project_id']
                or artifact['workspace_id'] != stage['workspace_id']
                or not (current_artifact or (feedback_parent
                        and artifact['round'] == stage['round'] - 1))):
            raise ContractError('previous_artifact_stale')
        if set(artifact['content']) != {'analysis'}:
            raise ContractError('output_fields')
        previous = artifact['content']['analysis']
        validate_analysis(previous, current['content'], sources)
        artifact_digest = artifact['digest']
    binding = dict(project_id=request['project_id'], request_id=request['id'],
        request_revision_id=current['id'], stage_id=stage['id'], base_revision=stage['revision'],
        request_sha256=digest(current['content']), source_bundle_sha256=source_bundle(sources),
        previous_artifact_id=previous_id,
        previous_analysis_sha256=digest(previous) if previous is not None else None)
    envelope = dict(contract_version=VERSION, role_id='PA-04', binding=deepcopy(binding), mode=mode,
        request=dict(text=current['content'], sha256=binding['request_sha256']),
        sources=sources, previous_analysis=previous, feedback_context=feedback)
    inputs = build_inputs(envelope, binding)
    return dict(envelope=envelope, expected_binding=binding, inputs=inputs,
        provenance=dict(workspace_id=request['workspace_id'], instance_id=instance['id'],
            request_digest=current['digest'], previous_artifact_digest=artifact_digest,
            stage_input_digest=stage['input_digest'], inputs_sha256=digest(canonical(inputs))))


def check_preview(package, stage):
    """Run after configuration/feedback, before execution; do not repair drift."""
    binding = package['expected_binding']
    if stage['id'] != binding['stage_id'] or stage['revision'] != binding['base_revision']:
        raise ContractError('snapshot_revision_mismatch')
    if stage['preview_inputs'] != package['inputs']:
        raise ContractError('preview_inputs_mismatch')
