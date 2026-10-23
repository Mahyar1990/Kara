"""Small offline checks for the exact sandbox code shipped in PA-04 DSL."""
import json
import unittest
from clasor_agents.pa04.contract import ROOT,ContractError,build_inputs,canonical
from clasor_agents.pa04.native import validate_native_result
from clasor_agents.pa04.workflow import build,manifest,prepare_code,validator_code


class PA04WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.cases=json.loads((ROOT/'fixtures/cases.json').read_text())
        self.prepare={};exec(compile(prepare_code(),'<prepare>','exec'),self.prepare)
        self.validate={};exec(compile(validator_code(),'<validator>','exec'),self.validate)

    def test_exact_shipped_code_accepts_all_reference_cases(self):
        for case in self.cases:
            with self.subTest(case=case['id']):
                inputs=build_inputs(case['input'],case['expected_binding'])
                data=json.loads(self.prepare['main'](**inputs)['prompt_data'])
                self.assertEqual(data['request_sha256'],case['input']['request']['sha256'])
                result=self.validate['main'](text=canonical(case['reference_output']),finish_reason='stop',request=inputs['request'],source_context=inputs['source_context'])
                self.assertEqual(json.loads(result['analysis']),case['reference_output'])

    def test_invalid_or_truncated_model_response_has_no_analysis(self):
        case=self.cases[0];wire=build_inputs(case['input'],case['expected_binding'])
        for text,reason in [('{','stop'),(canonical(case['reference_output']),'length'),('{}','stop')]:
            with self.subTest(reason=reason),self.assertRaises(self.validate['ContractError']):
                self.validate['main'](text=text,finish_reason=reason,request=wire['request'],source_context=wire['source_context'])

    def test_tampered_sources_are_rejected_before_llm(self):
        case=self.cases[-1];wire=build_inputs(case['input'],case['expected_binding'])
        context=json.loads(wire['source_context']);context['sources'][0]['content']='changed'
        wire['source_context']=canonical(context)
        with self.assertRaisesRegex(self.prepare['ContractError'],'source_digest_mismatch'):
            self.prepare['main'](**wire)

    def test_previous_analysis_respects_contract_text_budget_before_llm(self):
        case=self.cases[0];wire=build_inputs(case['input'],case['expected_binding'])
        wire['source_context']=canonical(dict(sources=[],previous_analysis='x'*16001))
        with self.assertRaisesRegex(self.prepare['ContractError'],'schema_length'):
            self.prepare['main'](**wire)

    def test_graph_gates_input_and_output_and_uses_native_finish_reason(self):
        graph=build()['workflow']['graph'];nodes={n['id']:n['data'] for n in graph['nodes']}
        self.assertEqual([(e['source'],e['target']) for e in graph['edges']],[('start','prepare'),('prepare','llm'),('llm','validate'),('validate','end')])
        self.assertIn({'variable':'finish_reason','value_selector':['llm','finish_reason']},nodes['validate']['variables'])
        self.assertEqual(nodes['end']['outputs'][0]['value_selector'],['validate','analysis'])
        self.assertFalse(nodes['llm']['retry_config']['retry_enabled'])
        self.assertEqual(nodes['llm']['model']['completion_params']['max_tokens'],4096)

    def test_native_result_uses_independent_run_actor_and_workflow_identity(self):
        case=self.cases[0]
        identity=dict(id='native-attempt',created_by='synthetic-actor',workflow_id='pinned-workflow')
        result=dict(identity,status='succeeded',finish_reason='stop',outputs=dict(analysis=canonical(case['reference_output'])))
        self.assertEqual(validate_native_result(result,identity,case['input'],case['expected_binding']),case['reference_output'])
        for key in identity:
            with self.subTest(key=key),self.assertRaisesRegex(ContractError,'native_identity_mismatch'):
                validate_native_result(dict(result,**{key:'other'}),identity,case['input'],case['expected_binding'])
        with self.assertRaisesRegex(ContractError,'incomplete_output'):
            validate_native_result(dict(result,finish_reason=None),identity,case['input'],case['expected_binding'])

    def test_optional_initial_feedback_and_feedback_mode_requirements(self):
        case=self.cases[0];wire=build_inputs(case['input'],case['expected_binding'])
        wire['feedback_context']=None
        self.assertEqual(json.loads(self.prepare['main'](**wire)['prompt_data'])['feedback_context'],'')
        for mode in ('clarify','review_change'):
            with self.subTest(mode=mode),self.assertRaisesRegex(self.prepare['ContractError'],'feedback_required'):
                self.prepare['main'](**dict(wire,mode=mode))

    def test_workflow_and_prompt_manifest_have_no_drift(self):
        self.assertEqual(build(),json.loads((ROOT/'workflow.json').read_text()))
        self.assertEqual(manifest(),json.loads((ROOT/'workflow-manifest.json').read_text()))


if __name__=='__main__':unittest.main()
