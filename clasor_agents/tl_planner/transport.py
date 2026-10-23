"""Bounded text Start inputs; trust/ACL and the expected digest stay with caller."""
import json
from .contract import ROOT
from clasor_agents.pa04.contract import (SCHEMAS, ContractError, bounded, canonical,
                                        digest, parse, shape)

INPUT_SCHEMA = json.loads((ROOT/'schemas/input.schema.json').read_text())
FEEDBACK_SCHEMA = dict(type='string', maxLength=8000)
HASH_SCHEMA = dict(type='string', minLength=64, maxLength=64, pattern='[0-9a-f]{64}')


def validate_prepared(prepared_input, expected_input_sha256):
    """Check a serialized prepare() result against the caller's independent hash.

    A matching hash is integrity, not authentication or proof of a human PO.
    """
    bounded(prepared_input, INPUT_SCHEMA)
    shape(expected_input_sha256, HASH_SCHEMA)
    if digest(canonical(prepared_input)) != expected_input_sha256:
        raise ContractError('planner_input_mismatch')
    binding = prepared_input['binding']
    if digest(prepared_input['request']) != binding['request_sha256']:
        raise ContractError('request_digest_mismatch')
    if digest(prepared_input['analysis']) != binding['analysis_sha256']:
        raise ContractError('analysis_digest_mismatch')
    analysis = parse(prepared_input['analysis'])
    bounded(analysis, SCHEMAS['output'])
    if analysis['request_sha256'] != binding['request_sha256'] or analysis['status'] != 'ready_for_review':
        raise ContractError('analysis_not_ready')
    for context in prepared_input['repositories'].values():
        for kind in ('repository_rules', 'evidence'):
            paths = [s['path'] for s in context[kind]]
            if len(set(paths)) != len(paths):
                raise ContractError('duplicate_context_source')
            if any(s['commit'] != context['commit'] or digest(s['content']) != s['sha256'] for s in context[kind]):
                raise ContractError('repository_source_mismatch')
    return prepared_input


def decode_inputs(request, analysis, planning_context, expected_input_sha256, feedback_context):
    """Reconstruct exactly the trusted prepared snapshot; no normalization."""
    context = parse(planning_context)
    if type(context) is not dict or set(context) != {'contract_version','role_id','status','binding','repositories'}:
        raise ContractError('planning_context_fields')
    prepared = dict(context, request=request, analysis=analysis)
    validate_prepared(prepared, expected_input_sha256)
    feedback = '' if feedback_context is None else feedback_context
    shape(feedback, FEEDBACK_SCHEMA)
    wire = dict(request=request, analysis=analysis, planning_context=planning_context,
                expected_input_sha256=expected_input_sha256, feedback_context=feedback)
    if len(canonical(wire).encode('utf-8')) > 32768:
        raise ContractError('transport_budget')
    # Only content and immutable hashes enter the prompt, not actor/decision IDs.
    prompt = dict(request=request, analysis=parse(analysis), repositories=context['repositories'],
        input_sha256=expected_input_sha256, analysis_sha256=context['binding']['analysis_sha256'],
        feedback_context=feedback)
    prompt_data = canonical(prompt)
    if len(prompt_data.encode('utf-8')) > 32768:
        raise ContractError('transport_budget')
    return dict(prepared_input=canonical(prepared), input_sha256=expected_input_sha256, prompt_data=prompt_data)


def build_inputs(prepared_input, expected_input_sha256, feedback_context=''):
    validate_prepared(prepared_input, expected_input_sha256)
    context = {k:v for k,v in prepared_input.items() if k not in ('request','analysis')}
    result = dict(request=prepared_input['request'], analysis=prepared_input['analysis'],
        planning_context=canonical(context), expected_input_sha256=expected_input_sha256,
        feedback_context=feedback_context)
    decode_inputs(**result)
    return result
