"""Focused offline boundary tests; fixtures are not semantic model-test results."""
import copy
import json
from pathlib import Path
import unittest
from clasor_agents.pa04.contract import (
    ROOT,ContractError,build_inputs,canonical,digest,parse,source_bundle,
    validate_attempt,validate_input,validate_output,
)
from clasor_agents.pa04.package import build


class PA04ContractTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((ROOT/'fixtures/cases.json').read_text())
        self.case = copy.deepcopy(self.cases[0])
        self.envelope = self.case['input']
        self.binding = copy.deepcopy(self.case['expected_binding'])
        self.output = copy.deepcopy(self.case['reference_output'])

    def reject(self, code, fn, *args):
        with self.assertRaises(ContractError) as caught:
            fn(*args)
        self.assertEqual(str(caught.exception),code)

    def check_output(self):
        return validate_output(canonical(self.output),self.envelope,self.binding)

    def test_four_cases_and_manifest_are_reproducible(self):
        for case in self.cases:
            with self.subTest(case=case['id']):
                validate_output(canonical(case['reference_output']),case['input'],case['expected_binding'])
        self.assertEqual(build(),json.loads((ROOT/'manifest.json').read_text()))

    def test_feedback_suffix_is_separate_and_request_stays_exact(self):
        original=self.envelope['request']['text']
        self.envelope['feedback_context']='\n\nبازخورد انسانی و خروجی مبنا:\n{"previous_output":{},"feedback_history":["حالت خطا را اضافه کن"]}'
        values=build_inputs(self.envelope,self.binding)
        self.assertEqual(values['request'],original)
        self.assertEqual(values['feedback_context'],self.envelope['feedback_context'])
        self.assertNotIn('binding',values)

    def test_project_and_revision_must_match_trusted_context(self):
        for key,value in [('project_id','00000000-0000-4000-8000-000000000099'),('base_revision',2)]:
            altered=copy.deepcopy(self.binding);altered[key]=value
            self.reject('binding_mismatch',validate_input,self.envelope,altered)
        self.output['request_sha256']=digest('نسخهٔ دیگر')
        self.reject('output_request_mismatch',self.check_output)

    def test_request_and_sources_cannot_be_rehashed_under_old_binding(self):
        self.envelope['request']={'text':'متن جایگزین','sha256':digest('متن جایگزین')}
        self.reject('request_digest_mismatch',validate_input,self.envelope,self.binding)
        case=copy.deepcopy(self.cases[-1]);source=case['input']['sources'][0]
        source['content']='مدرک عوض شده';source['sha256']=digest(source['content'])
        self.reject('source_bundle_mismatch',validate_input,case['input'],case['expected_binding'])

    def test_unknown_source_and_invented_quote_are_rejected(self):
        self.output['requirements'][0]['source_refs']=['S-missing']
        self.reject('unknown_source',self.check_output)
        self.output['requirements'][0]['source_refs']=['request']
        self.output['conditions'][0]['quote']='عبارت اعلام‌نشده'
        self.reject('invented_quote',self.check_output)

    def test_missing_ac_and_unmapped_conditions_are_rejected(self):
        self.output['acceptance_criteria']=[]
        self.reject('requirement_without_ac',self.check_output)
        self.output=copy.deepcopy(self.case['reference_output'])
        self.output['conditions'].append(dict(id='C-unmapped',quote='اسناد',source_refs=['request']))
        self.reject('unmapped_condition',self.check_output)

    def test_model_cannot_add_approval_or_authority_fields(self):
        for key in ['approved','finalizer_id','grants']:
            self.output[key]=True
            self.reject('schema_fields',self.check_output)
            del self.output[key]
        self.output['assumptions']=[dict(id='A-1',statement='فرض آزمایشی',needs_confirmation=False)]
        self.reject('schema_const',self.check_output)

    def test_strict_json_and_byte_budget(self):
        self.reject('schema_fields',validate_output,'{}',self.envelope,self.binding)
        for text,code in [('{} trailing','invalid_json'),('{"a":1,"a":2}','duplicate_key'),('{"a":NaN}','non_finite_number'),('{"a":1e999}','non_finite_number'),('{"a":','invalid_json'),('ی'*17000,'payload_too_large')]:
            with self.subTest(code=code):self.reject(code,parse,text)
        self.envelope['binding']['base_revision']=True
        self.reject('schema_type',validate_input,self.envelope,self.binding)

    def test_failed_timed_out_or_truncated_attempt_cannot_be_accepted(self):
        attempt=dict(status='succeeded',finish_reason='stop',outputs={'analysis':canonical(self.output)})
        self.assertEqual(validate_attempt(attempt,self.envelope,self.binding),self.output)
        for status in ['timeout','failed','cancelled']:
            attempt['status']=status
            self.reject('attempt_incomplete',validate_attempt,attempt,self.envelope,self.binding)
        attempt['status']='succeeded'
        for reason in ['length',None,'content_filter']:
            attempt['finish_reason']=reason
            self.reject('incomplete_output',validate_attempt,attempt,self.envelope,self.binding)

    def test_change_review_needs_pinned_previous_artifact(self):
        self.envelope['mode']='review_change';self.envelope['feedback_context']='رفتار تازه را تحلیل کن'
        self.reject('previous_analysis_required',validate_input,self.envelope,self.binding)
        previous=canonical(self.output)
        self.envelope['previous_analysis']=previous
        self.binding['previous_analysis_sha256']=digest(previous)
        self.binding['previous_artifact_id']='00000000-0000-4000-8000-000000000009'
        self.envelope['binding']=copy.deepcopy(self.binding)
        validate_input(self.envelope,self.binding)
        self.envelope['previous_analysis']=previous+' '
        self.reject('previous_artifact_mismatch',validate_input,self.envelope,self.binding)

    def test_blocking_question_cannot_claim_ready(self):
        case=copy.deepcopy(self.cases[1]);case['reference_output']['status']='ready_for_review'
        self.reject('status_conflict',validate_output,canonical(case['reference_output']),case['input'],case['expected_binding'])


if __name__=='__main__':
    unittest.main()
