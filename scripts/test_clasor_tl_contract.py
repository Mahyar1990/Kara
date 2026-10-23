"""Offline TL contract regressions. Fixtures are neither model nor PO acceptance."""
import copy
import json
import unittest
from clasor_agents.pa04.contract import ContractError, canonical, digest
from clasor_agents.tl_planner.contract import ROOT, validate_plan, validate_attempt, manifest


class TLContractTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((ROOT/'fixtures/cases.json').read_text())
        self.case = self.cases[0]
        self.context = self.case['prepared_input']
        self.plan = copy.deepcopy(self.case['reference_output'])
        self.expected = self.case['expected_input_sha256']

    def validate(self):
        return validate_plan(canonical(self.plan), self.context, self.expected)

    def rejects(self, code, mutate):
        self.plan = copy.deepcopy(self.case['reference_output'])
        mutate(self.plan)
        with self.assertRaisesRegex(ContractError, '^'+code+'$'): self.validate()

    def test_reference_drafts_and_missing_context_status(self):
        for case in self.cases:
            with self.subTest(case=case['id']):
                self.assertTrue(case['synthetic'])
                self.assertEqual(validate_plan(canonical(case['reference_output']),case['prepared_input'],case['expected_input_sha256']),case['reference_output'])

    def test_binds_complete_input_and_analysis_and_preserves_scope(self):
        for key in ('input_sha256','analysis_sha256'):
            self.rejects('plan_binding_mismatch',lambda p:p.update({key:'0'*64}))
        self.rejects('plan_scope_changed',lambda p:p['scope']['included'].append('new behavior'))
        # Same analysis, different snapshot/receipt: independent saved hash rejects.
        self.context['binding']['finalization']['decision_id']='other'
        with self.assertRaisesRegex(ContractError,'planner_input_mismatch'): self.validate()

    def test_rejects_unknown_uncovered_or_mismatched_ac(self):
        self.rejects('unknown_plan_ac',lambda p:p['tasks'][0].update(ac_ids=['AC-missing']))
        self.rejects('uncovered_ac',lambda p:p.update(coverage=[]))
        self.rejects('unknown_coverage_task',lambda p:p['coverage'][0].update(task_ids=['T-missing']))
        self.plan = copy.deepcopy(self.case['reference_output'])
        analysis = json.loads(self.context['analysis'])
        second = copy.deepcopy(analysis['acceptance_criteria'][0]); second['id']='AC-second'
        analysis['acceptance_criteria'].append(second)
        self.context['analysis']=canonical(analysis)
        self.context['binding']['analysis_sha256']=digest(self.context['analysis'])
        self.expected=digest(canonical(self.context))
        self.plan.update(analysis_sha256=self.context['binding']['analysis_sha256'],input_sha256=self.expected)
        self.plan['tasks'][0]['ac_ids']=['AC-second']
        with self.assertRaisesRegex(ContractError,'coverage_task_ac_mismatch'): self.validate()

    def test_dependencies_missing_duplicate_self_and_multitask_cycles(self):
        self.rejects('unknown_task_dependency',lambda p:p['tasks'][0].update(depends_on=['T-missing']))
        self.rejects('duplicate_task',lambda p:p['tasks'].append(copy.deepcopy(p['tasks'][0])))
        self.rejects('cyclic_task_dependency',lambda p:p['tasks'][0].update(depends_on=['T-01']))
        def cycle(p):
            t=copy.deepcopy(p['tasks'][0]);t['id']='T-02';t['depends_on']=['T-01']
            p['tasks'].append(t);p['tasks'][0]['depends_on']=['T-02']
        self.rejects('cyclic_task_dependency',cycle)

    def test_rejects_unread_sources_and_repository_impact_conflicts(self):
        self.rejects('unknown_plan_source',lambda p:p['tasks'][0].update(source_refs=['server/evidence/unread.md']))
        self.rejects('task_source_required',lambda p:p['tasks'][0].update(source_refs=['analysis']))
        self.rejects('repository_impact_incomplete',lambda p:p['repository_impact'].__setitem__(0,copy.deepcopy(p['repository_impact'][1])))
        def unrelated(p):
            next(r for r in p['repository_impact'] if r['repository']=='server')['effect']='unrelated'
        self.rejects('task_repository_conflict',unrelated)
        self.rejects('repository_impact_unsubstantiated',lambda p:p['repository_impact'][0].update(effect='unknown'))

    def test_test_repo_method_source_and_exact_version_combination(self):
        self.rejects('test_repository_mismatch',lambda p:p['coverage'][0].update(test_repository='playwright'))
        self.rejects('test_method_source_required',lambda p:p['coverage'][0].update(method_source_refs=['analysis']))
        self.rejects('test_versions_incomplete',lambda p:p['coverage'][0].update(versions=p['coverage'][0]['versions'][:1]))
        self.rejects('test_version_mismatch',lambda p:p['coverage'][0]['versions'][0].update(commit='b'*40))
        # Valid repository-local and human checks are supported too.
        self.plan = copy.deepcopy(self.case['reference_output'])
        row=self.plan['coverage'][0];row['method']='repository_check';row['test_repository']='server'
        row['method_source_refs']=['server/evidence/doc/synthetic.md'];row['versions']=row['versions'][:1]
        self.validate()
        row['method']='manual';row['test_repository']=None;row['method_source_refs']=['analysis'];self.validate()

    def test_valid_cross_repository_dependency_and_coverage(self):
        task=copy.deepcopy(self.plan['tasks'][0])
        task.update(id='T-02',kind='verification',repositories=['newman'],depends_on=['T-01'],
                    source_refs=['newman/evidence/doc/synthetic.md'])
        self.plan['tasks'].append(task)
        self.plan['coverage'][0]['task_ids'].append('T-02')
        self.validate()

    def test_blocking_product_question_requires_product_status(self):
        q=dict(id='Q-01',question='تغییر رفتار لازم است؟',impact='تغییر AC',owner='PO',blocking=True,blocked_stage='analysis',ac_ids=[])
        self.plan['questions']=[q]
        with self.assertRaisesRegex(ContractError,'plan_status_conflict'):self.validate()
        self.plan['status']='needs_product_decision';self.validate()
        self.plan['questions'].append(copy.deepcopy(q))
        with self.assertRaisesRegex(ContractError,'duplicate_question'):self.validate()

    def test_attempt_requires_real_stop_and_single_plan_output(self):
        attempt=dict(status='succeeded',finish_reason='stop',outputs=dict(plan=canonical(self.plan)))
        validate_attempt(attempt,self.context,self.expected)
        for reason in (None,'','length','content_filter'):
            with self.subTest(reason=reason),self.assertRaisesRegex(ContractError,'incomplete_output'):
                validate_attempt(dict(attempt,finish_reason=reason),self.context,self.expected)
        with self.assertRaisesRegex(ContractError,'attempt_incomplete'):
            validate_attempt(dict(attempt,status='failed'),self.context,self.expected)
        with self.assertRaisesRegex(ContractError,'output_fields'):
            validate_attempt(dict(attempt,outputs=dict(plan='{}',approved=True)),self.context,self.expected)

    def test_closed_schema_and_strict_json_limits(self):
        self.rejects('schema_fields',lambda p:p.update(approved=True))
        self.rejects('schema_enum',lambda p:p.update(status='ready_for_development'))
        self.rejects('schema_pattern',lambda p:p.update(summary='   '))
        for text, code in [('{','invalid_json'),('{"x":1,"x":2}','duplicate_key'),
                           ('{"x":NaN}','non_finite_number'),('x'*32769,'payload_too_large')]:
            with self.subTest(code=code),self.assertRaisesRegex(ContractError,code):
                validate_plan(text,self.context,self.expected)

    def test_versioned_manifest_matches_contract_assets(self):
        self.assertEqual(manifest(), json.loads((ROOT/'manifest.json').read_text()))
