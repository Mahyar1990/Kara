"""Reproducible contract-only package; no Workflow, prompt or runtime publication."""
import json
from pathlib import Path
from .contract import ROOT,VERSION,canonical,digest,build_inputs,validate_output


def build():
    cases = json.loads((ROOT / 'fixtures/cases.json').read_text())
    for case in cases:
        assert case['synthetic'] is True
        build_inputs(case['input'], case['expected_binding'])
        validate_output(canonical(case['reference_output']), case['input'], case['expected_binding'])
    files = ['schemas/input.schema.json', 'schemas/output.schema.json', 'fixtures/cases.json', 'contract.py', 'package.py']
    artifacts = {name: digest((ROOT / name).read_text()) for name in files}
    return dict(kind='kara-agent-contract',role_id='PA-04',contract_version=VERSION,
        status='offline-contract-only',artifacts=artifacts,synthetic_cases=len(cases),
        workflow_revision=None,prompt_revision=None,live_model_test=False,
        limits=dict(max_payload_bytes=32768,max_sources=4,source_chars_total=6000,
            automatic_model_retries=0,planned_context_tokens=16384,planned_output_tokens=2048))


if __name__ == '__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
