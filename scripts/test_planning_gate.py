import copy
import json
from pathlib import Path
import runpy
import unittest

import planning_fixture

ROOT = Path(__file__).resolve().parents[1]
review = runpy.run_path(str(ROOT / 'workflows/klassor-review/decision.py'))
gate = runpy.run_path(str(ROOT / 'workflows/klassor-planning/gate.py'), init_globals=review)
prepare = runpy.run_path(str(ROOT / 'workflows/klassor-analysis/prepare.py'))['main']


class PlanningGateTests(unittest.TestCase):
    def setUp(self):
        sample = planning_fixture.sample()
        self.request = prepare(title=sample['title'], request_text=sample['request_text'], sources_text=sample['sources_text'])['input_json']
        self.context = planning_fixture.context()
        self.reviewed = review['prepare_review'](self.request, sample['analysis_report'], 'بازبین آزمایشی', review['LOCAL'])

    def decide(self, action='approve', trial=False, **changes):
        saved = json.loads(self.reviewed['context_json'])
        if trial:
            saved['review_kind'] = review['TRIAL']
        args = dict(context_json=json.dumps(saved), action=action, reviewer='بازبین آزمایشی',
                    assessment=review['READY'], reviewed_body=self.reviewed['reviewed_body'], notes='فقط آزمون محلی قواعد')
        args.update(changes)
        result = review['record_decision'](**args)
        result.update(source_review=gate['SOURCE_READY'], reviewed_agent_context_id=self.context['agent_context_id'])
        return result

    def run_gate(self, result, **kwargs):
        return gate['prepare_planning'](self.request, json.dumps(result), json.dumps(self.context), **kwargs)

    def test_exact_approval_and_edited_version_handoff(self):
        self.assertEqual(self.run_gate(self.decide())['can_run'], 1)
        edited = self.decide(reviewed_body=self.reviewed['reviewed_body'] + '\nاصلاح معیار در نمونهٔ آزمون')
        output = self.run_gate(edited)
        self.assertEqual(output['can_run'], 1)
        self.assertIn(':v2:', json.loads(output['gate_context_json'])['analysis_ref'])
        changed = self.decide()
        changed['requirement'] += '\nتغییر پس از تأیید'
        self.assertEqual(self.run_gate(changed)['can_run'], 0)
        changed = self.decide()
        d = json.loads(changed['decision_record_json'])
        d['decision_source'] = 'model'
        changed['decision_record_json'] = json.dumps(d)
        self.assertEqual(self.run_gate(changed)['can_run'], 0)

    def test_reject_revision_expiry_and_source_review_stop_before_model(self):
        for action in ('reject', 'request_changes', 'timeout'):
            self.assertEqual(self.run_gate(self.decide(action))['can_run'], 0)
        declined = self.decide()
        declined['source_review'] = gate['SOURCE_NOT_READY']
        self.assertEqual(self.run_gate(declined)['can_run'], 0)
        declined = self.decide()
        declined['reviewed_agent_context_id'] = 'old-context'
        self.assertEqual(self.run_gate(declined)['can_run'], 0)
        self.context['repository_policies'][0]['content'] = 'changed'
        self.assertEqual(self.run_gate(self.decide())['can_run'], 0)

    def test_trial_is_only_explicit_preview_and_never_development_or_merge(self):
        decision = self.decide(trial=True)
        self.assertEqual(self.run_gate(decision)['can_run'], 0)
        output = self.run_gate(decision, allow_trial=True)
        self.assertEqual(output['can_run'], 1)
        record = json.loads(output['gate_context_json'])
        self.assertTrue(record['is_trial'])
        self.assertFalse(record['development_ready'])
        self.assertFalse(record['can_merge'])

    def test_model_cannot_grant_development_and_unknown_sources_are_flagged(self):
        output = self.run_gate(self.decide(trial=True), allow_trial=True)
        report = '\n\n'.join('### ' + str(i) + '. بخش\nمتن نمونه' for i in range(1, 9))
        plan = {'status': 'ready_for_technical_discussion', 'report': report,
                'source_ids': ['backend:doc/api/categories.md'], 'development_ready': True, 'can_merge': True}
        result = gate['finalize_planning'](json.dumps(plan), output['gate_context_json'])
        record = json.loads(result['planning_record_json'])
        self.assertFalse(record['development_ready'])
        self.assertFalse(record['can_merge'])
        self.assertFalse(record['technical_discussion_recorded'])
        self.assertEqual(record['quality_issues'], [])
        plan['source_ids'] = ['unknown:invented.md']
        result = gate['finalize_planning'](json.dumps(plan), output['gate_context_json'])
        self.assertEqual(result['planning_status'], 'نیازمند بررسی فنی')
        plan['status'] = 'ready_for_development'
        result = gate['finalize_planning'](json.dumps(plan), output['gate_context_json'])
        self.assertFalse(json.loads(result['planning_record_json'])['development_ready'])
        result = gate['finalize_planning']('not-json', output['gate_context_json'])
        self.assertEqual(result['planning_status'], 'نیازمند بررسی فنی')


if __name__ == '__main__':
    unittest.main()
