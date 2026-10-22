"""Bounded offline PA-04 contract; never authenticates a user or finalizes a stage."""
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).parent
VERSION = '1.0.0'
MAX_BYTES = 32768
SCHEMAS = {name: json.loads((ROOT / 'schemas' / (name + '.schema.json')).read_text()) for name in ('input', 'output')}


class ContractError(ValueError):
    """Stable safe code; raw inputs, outputs and credentials are never included."""


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ContractError('invalid_json') from None


def parse(text):
    """Reject truncation, duplicate keys, non-finite numbers and oversized payloads."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError('duplicate_key')
            result[key] = value
        return result
    def constant(_):
        raise ContractError('non_finite_number')
    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ContractError('non_finite_number')
        return parsed
    try:
        if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
            raise ContractError('payload_too_large')
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant, parse_float=number)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError('invalid_json') from None


def shape(value, schema):
    """Execute only the JSON Schema vocabulary used by these owned schema files."""
    supported = {'$schema', '$id', 'type', 'const', 'enum', 'properties', 'required', 'additionalProperties',
        'items', 'minItems', 'maxItems', 'uniqueItems', 'minLength', 'maxLength', 'pattern', 'minimum'}
    if set(schema) - supported:
        raise ContractError('unsupported_schema_keyword')
    predicates = {'object': lambda v: type(v) is dict, 'array': lambda v: type(v) is list,
        'string': lambda v: type(v) is str, 'integer': lambda v: type(v) is int,
        'boolean': lambda v: type(v) is bool, 'null': lambda v: v is None}
    if 'type' in schema:
        kinds = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any(predicates[k](value) for k in kinds):
            raise ContractError('schema_type')
    if 'const' in schema and (type(value) is not type(schema['const']) or value != schema['const']):
        raise ContractError('schema_const')
    if 'enum' in schema and value not in schema['enum']:
        raise ContractError('schema_enum')
    if type(value) is dict:
        props = schema['properties']
        if set(value) != set(schema['required']) or set(value) - set(props):
            raise ContractError('schema_fields')
        for key in value:
            shape(value[key], props[key])
    if type(value) is list:
        if not schema.get('minItems', 0) <= len(value) <= schema['maxItems']:
            raise ContractError('schema_items')
        if schema.get('uniqueItems') and len({canonical(v) for v in value}) != len(value):
            raise ContractError('schema_unique')
        for item in value:
            shape(item, schema['items'])
    if type(value) is str:
        if not schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', MAX_BYTES):
            raise ContractError('schema_length')
        if 'pattern' in schema and re.fullmatch(schema['pattern'], value) is None:
            raise ContractError('schema_pattern')
    if type(value) is int and value < schema.get('minimum', value):
        raise ContractError('schema_minimum')


def bounded(value, schema):
    text = canonical(value)
    try:
        if len(text.encode('utf-8')) > MAX_BYTES:
            raise ContractError('payload_too_large')
    except UnicodeError:
        raise ContractError('invalid_json') from None
    shape(value, schema)


def source_bundle(sources):
    metadata = [{k: source[k] for k in ('id', 'kind', 'reference', 'revision', 'sha256')} for source in sources]
    return digest(canonical(sorted(metadata, key=lambda s: s['id'])))


def validate_input(envelope, expected_binding):
    """expected_binding must come from the trusted caller, never the model."""
    bounded(envelope, SCHEMAS['input'])
    shape(expected_binding, SCHEMAS['input']['properties']['binding'])
    if not isinstance(expected_binding, dict) or envelope['binding'] != expected_binding:
        raise ContractError('binding_mismatch')
    if digest(envelope['request']['text']) != envelope['request']['sha256'] or envelope['request']['sha256'] != envelope['binding']['request_sha256']:
        raise ContractError('request_digest_mismatch')
    ids = [s['id'] for s in envelope['sources']]
    if len(set(ids)) != len(ids):
        raise ContractError('duplicate_source')
    if any(digest(s['content']) != s['sha256'] for s in envelope['sources']):
        raise ContractError('source_digest_mismatch')
    if sum(len(s['content']) for s in envelope['sources']) > 6000:
        raise ContractError('source_budget')
    if source_bundle(envelope['sources']) != envelope['binding']['source_bundle_sha256']:
        raise ContractError('source_bundle_mismatch')
    previous = envelope['previous_analysis']
    if (digest(previous) if previous is not None else None) != envelope['binding']['previous_analysis_sha256']:
        raise ContractError('previous_artifact_mismatch')
    if (previous is None) != (envelope['binding']['previous_artifact_id'] is None):
        raise ContractError('previous_artifact_mismatch')
    if previous is not None:
        bounded(parse(previous), SCHEMAS['output'])
    if envelope['mode'] in ('clarify', 'review_change') and not envelope['feedback_context'].strip():
        raise ContractError('feedback_required')
    if envelope['mode'] == 'review_change' and previous is None:
        raise ContractError('previous_analysis_required')
    return envelope


def build_inputs(envelope, expected_binding):
    validate_input(envelope, expected_binding)
    result = dict(request=envelope['request']['text'], mode=envelope['mode'],
        source_context=canonical(dict(sources=envelope['sources'], previous_analysis=envelope['previous_analysis'])),
        feedback_context=envelope['feedback_context'])
    if len(canonical(result).encode('utf-8')) > MAX_BYTES:
        raise ContractError('transport_budget')
    return result


def validate_output(text, envelope, expected_binding):
    """Traceability/shape checks; cannot prove semantic completeness or PO approval."""
    validate_input(envelope, expected_binding)
    result = parse(text)
    bounded(result, SCHEMAS['output'])
    if result['request_sha256'] != envelope['request']['sha256']:
        raise ContractError('output_request_mismatch')
    sources = {'request': envelope['request']['text']} | {s['id']: s['content'] for s in envelope['sources']}
    groups = {name: {r['id']: r for r in result[name]} for name in ('conditions', 'requirements', 'acceptance_criteria', 'questions', 'assumptions')}
    if any(len(groups[name]) != len(result[name]) for name in groups):
        raise ContractError('duplicate_id')
    for name in ('conditions', 'requirements', 'acceptance_criteria', 'questions'):
        for row in result[name]:
            if not set(row['source_refs']) <= set(sources):
                raise ContractError('unknown_source')
    for condition in result['conditions']:
        if not all(condition['quote'] in sources[s] for s in condition['source_refs']):
            raise ContractError('invented_quote')
    covered, accepted, questioned = set(), set(), set()
    for req in result['requirements']:
        if not set(req['condition_ids']) <= groups['conditions'].keys():
            raise ContractError('unknown_condition')
        covered.update(req['condition_ids'])
    for ac in result['acceptance_criteria']:
        if not set(ac['requirement_ids']) <= groups['requirements'].keys():
            raise ContractError('unknown_requirement')
        accepted.update(ac['requirement_ids'])
    for question in result['questions']:
        if not set(question['condition_ids']) <= groups['conditions'].keys():
            raise ContractError('unknown_condition')
        if question['blocking']:
            questioned.update(question['condition_ids'])
    if set(groups['requirements']) - accepted:
        raise ContractError('requirement_without_ac')
    ready = result['status'] == 'ready_for_review'
    blocking = any(q['blocking'] for q in result['questions'])
    if ready == blocking:
        raise ContractError('status_conflict')
    if ready and not result['requirements']:
        raise ContractError('empty_ready_analysis')
    if set(groups['conditions']) - (covered if ready else covered | questioned):
        raise ContractError('unmapped_condition')
    return result


def validate_attempt(attempt, envelope, expected_binding):
    """Execution metadata is supplied by the adapter, never parsed from model text."""
    if type(attempt) is not dict or set(attempt) != {'status', 'finish_reason', 'outputs'}:
        raise ContractError('attempt_fields')
    if attempt['status'] != 'succeeded':
        raise ContractError('attempt_incomplete')
    if attempt['finish_reason'] != 'stop':
        raise ContractError('incomplete_output')
    if type(attempt['outputs']) is not dict or set(attempt['outputs']) != {'analysis'}:
        raise ContractError('output_fields')
    return validate_output(attempt['outputs']['analysis'], envelope, expected_binding)
