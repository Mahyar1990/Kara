"""Synthetic API-shaped snapshots: no model, runtime mutation or private sources."""
import copy
import json
import unittest
from clasor_agents.pa04.contract import ROOT, ContractError, canonical
from clasor_agents.pa04.inputs import assemble, check_preview


class InputAssemblyTests(unittest.TestCase):
    def setUp(self):
        case = json.loads((ROOT/'fixtures/cases.json').read_text())[0]
        self.case = case
        b = case['expected_binding']
        scope = dict(project_id=b['project_id'], workspace_id='synthetic-workspace')
        self.request = dict(scope, id=b['request_id'], current_revision_id=b['request_revision_id'],
            intake_valid=True, current=dict(scope, id=b['request_revision_id'], request_id=b['request_id'],
            content=case['input']['request']['text'], digest='native-request-digest'))
        self.instance = dict(scope, id='synthetic-instance', request_id=b['request_id'],
            request_revision_id=b['request_revision_id'], request_digest='native-request-digest',
            intake_valid=True, state='active')
        self.stage = dict(scope, id=b['stage_id'], instance_id=self.instance['id'], revision=2,
            round=1, input_digest='native-input-digest', intake_valid=True, input_error=None,
            preview_inputs=dict(request=self.request['current']['content']), artifacts=[])
        self.sources = case['input']['sources']

    def build(self, **kw):
        return assemble(self.request, self.instance, self.stage, self.sources,
                        [s['id'] for s in self.sources], **kw)

    def test_preserves_request_and_separates_native_and_text_digests(self):
        p = self.build()
        self.assertEqual(p['inputs']['request'], self.request['current']['content'])
        self.assertNotEqual(p['provenance']['request_digest'], p['expected_binding']['request_sha256'])
        self.assertEqual(p['expected_binding']['base_revision'], 2)
        self.stage['preview_inputs'] = p['inputs']
        check_preview(p, self.stage)
        self.stage['preview_inputs'] = dict(p['inputs'], request='changed')
        with self.assertRaisesRegex(ContractError, 'preview_inputs_mismatch'):
            check_preview(p, self.stage)

    def test_rejects_foreign_stale_invalid_and_mutated_request_snapshots(self):
        for obj, key, value in [(self.stage, 'project_id', 'other'),
                (self.instance, 'request_revision_id', 'other'),
                (self.request, 'intake_valid', False), (self.stage, 'input_error', 'stale')]:
            old = obj[key]; obj[key] = value
            with self.subTest(key=key), self.assertRaises(ContractError): self.build()
            obj[key] = old
        self.stage['preview_inputs']['request'] += ' feedback'
        with self.assertRaisesRegex(ContractError, 'original_request_changed'): self.build()

    def test_previous_is_selected_from_current_artifact_and_revalidated(self):
        aid = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        artifact = dict(id=aid, **{k:self.stage[k] for k in ('project_id','workspace_id','round','input_digest')},
            stage_id=self.stage['id'], digest='native-artifact-digest',
            content=dict(analysis=canonical(self.case['reference_output'])))
        self.stage['artifacts'] = [artifact]
        p = self.build(mode='review_change', feedback_context='بازبینی', previous_artifact_id=aid)
        self.assertEqual(p['expected_binding']['previous_artifact_id'], aid)
        self.assertEqual(p['provenance']['previous_artifact_digest'], 'native-artifact-digest')
        artifact['round'] += 1
        with self.assertRaisesRegex(ContractError, 'previous_artifact_stale'):
            self.build(previous_artifact_id=aid)
        artifact['round'] -= 1
        artifact['content']['analysis'] = '{}'
        with self.assertRaises(ContractError): self.build(previous_artifact_id=aid)

    def test_feedback_round_keeps_explicit_parent_from_previous_round(self):
        aid = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        self.stage['artifacts'] = [dict(id=aid, stage_id=self.stage['id'],
            project_id=self.stage['project_id'], workspace_id=self.stage['workspace_id'],
            round=1, input_digest='previous-input', digest='artifact-digest',
            content=dict(analysis=canonical(self.case['reference_output'])))]
        self.stage['round'] = 2
        self.stage['feedback'] = [dict(round=2, parent_artifact_id=aid,
            input_digest=self.stage['input_digest'],
            inputs=dict(effective=copy.deepcopy(self.stage['preview_inputs'])))]
        self.build(mode='clarify', feedback_context='بازخورد', previous_artifact_id=aid)
        self.stage['feedback'][0]['parent_artifact_id'] = 'other'
        with self.assertRaisesRegex(ContractError, 'previous_artifact_stale'):
            self.build(previous_artifact_id=aid)

    def test_missing_previous_source_tampering_and_overflow_fail_closed(self):
        with self.assertRaisesRegex(ContractError, 'previous_artifact_missing'):
            self.build(previous_artifact_id='missing')
        with self.assertRaisesRegex(ContractError, 'schema_length'):
            self.build(feedback_context='x'*8001)
        case = json.loads((ROOT/'fixtures/cases.json').read_text())[-1]
        sources = copy.deepcopy(case['input']['sources'])
        sources[0]['content'] = 'tampered'
        with self.assertRaisesRegex(ContractError, 'source_digest_mismatch'):
            assemble(self.request, self.instance, self.stage, sources, [sources[0]['id']])
        with self.assertRaisesRegex(ContractError, 'source_selection'):
            assemble(self.request, self.instance, self.stage, sources, ['missing'])
