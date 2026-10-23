"""Offline contract preparation, not human or model acceptance."""
import unittest
from scripts import test_clasor_pa04_inputs as fixtures
from clasor_agents.pa04.contract import ContractError, canonical, digest
from clasor_agents.tl_planner.handoff import prepare, REPOSITORIES


class TLHandoffTests(unittest.TestCase):
    def setUp(self):
        base = fixtures.InputAssemblyTests(); base.setUp()
        self.package = base.build()
        self.receipt = dict(stage_id=base.stage['id'], artifact_id='synthetic-artifact',
            digest='native-digest', decision_id='synthetic-decision',
            finalized_by='synthetic-po', finalized_at='2026-10-23T00:00:00Z')
        analysis = canonical(base.case['reference_output'])
        self.stage = dict(project_id=base.stage['project_id'], workspace_id=base.stage['workspace_id'],
            instance_id=base.instance['id'], id='synthetic-tl-stage', revision=1,
            state='ready', intake_valid=True, input_error=None,
            preview_inputs=dict(analysis=analysis),
            handoffs=[dict(self.receipt, input='analysis', output='analysis', content=analysis)])
        self.repos = {name:dict(ref='refs/remotes/origin/sandbox', commit='a'*40,
            repository_rules=[], evidence=[]) for name in REPOSITORIES}

    def build(self):
        return prepare(self.package, self.stage, self.receipt, self.repos)

    def test_only_selected_content_and_receipt_reach_draft_input(self):
        result = self.build()
        self.assertEqual(result['binding']['finalization'], self.receipt)
        self.assertEqual(result['binding']['analysis_sha256'], digest(result['analysis']))
        self.assertEqual(result['status'], 'draft_contract_only')
        self.assertNotIn('approved', result)

    def test_stale_foreign_unfinalized_and_changed_content_fail(self):
        for key, value in [('state','stale'), ('intake_valid',False), ('project_id','other')]:
            old=self.stage[key]; self.stage[key]=value
            with self.subTest(key=key), self.assertRaises(ContractError): self.build()
            self.stage[key]=old
        h = self.stage['handoffs'][0]
        h['decision_id'] = 'other'
        with self.assertRaisesRegex(ContractError,'handoff_receipt_mismatch'): self.build()
        h['decision_id'] = self.receipt['decision_id']
        self.stage['preview_inputs']['analysis'] = '{}'
        with self.assertRaisesRegex(ContractError,'handoff_content_mismatch'): self.build()

    def test_empty_receipt_and_malformed_human_edit_fail(self):
        self.receipt['finalized_by']=''
        with self.assertRaisesRegex(ContractError,'finalization_receipt_required'): self.build()
        self.receipt['finalized_by']='synthetic-po'
        self.stage['preview_inputs']['analysis']='{}'
        self.stage['handoffs'][0]['content']='{}'
        with self.assertRaisesRegex(ContractError,'schema_fields'): self.build()

    def test_repository_snapshot_hash_and_budget_are_enforced(self):
        repo = self.repos['server']
        repo['ref']='HEAD'
        with self.assertRaisesRegex(ContractError,'repository_baseline_mismatch'): self.build()
        repo['ref']='refs/remotes/origin/sandbox'
        source=dict(path='doc/synthetic.md', commit='b'*40, content='synthetic', sha256=digest('synthetic'))
        repo['evidence']=[source]
        with self.assertRaisesRegex(ContractError,'repository_source_mismatch'): self.build()
        source['commit']=repo['commit']; self.build()
        source['content']='x'*32768; source['sha256']=digest(source['content'])
        with self.assertRaisesRegex(ContractError,'transport_budget'): self.build()
