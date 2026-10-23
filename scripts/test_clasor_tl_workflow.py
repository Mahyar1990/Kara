"""Exercise exact exported TL Code nodes offline; never invoke an LLM."""
import ast
import copy
import json
import unittest
from clasor_agents.pa04.contract import ContractError, canonical, digest
from clasor_agents.tl_planner.contract import ROOT
from clasor_agents.tl_planner.transport import build_inputs
from clasor_agents.tl_planner.workflow import build, manifest


class TLWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.cases=json.loads((ROOT/'fixtures/cases.json').read_text())
        self.case=self.cases[0]
        self.nodes={n['id']:n['data'] for n in build()['workflow']['graph']['nodes']}
        self.prepare={};exec(compile(self.nodes['prepare']['code'],'<TL-prepare>','exec'),self.prepare)
        self.validate={};exec(compile(self.nodes['validate']['code'],'<TL-validate>','exec'),self.validate)

    def wire(self):
        return build_inputs(self.case['prepared_input'],self.case['expected_input_sha256'])

    def test_exported_nodes_roundtrip_reference_cases(self):
        for case in self.cases:
            with self.subTest(case=case['id']):
                wire=build_inputs(case['prepared_input'],case['expected_input_sha256'])
                prepared=self.prepare['main'](**wire)
                self.assertEqual(json.loads(prepared['prepared_input']),case['prepared_input'])
                prompt=json.loads(prepared['prompt_data'])
                self.assertEqual(prompt['request'],wire['request'])
                self.assertNotIn('finalization',prompt)
                result=self.validate['main'](canonical(case['reference_output']),'stop',
                    prepared['prepared_input'],prepared['input_sha256'])
                self.assertEqual(json.loads(result['plan']),case['reference_output'])

    def test_null_length_and_invalid_json_never_reach_end(self):
        prepared=self.prepare['main'](**self.wire())
        for text,reason in [(canonical(self.case['reference_output']),None),
                (canonical(self.case['reference_output']),'length'),('{','stop'),('{}','stop')]:
            with self.subTest(reason=reason),self.assertRaises(self.validate['ContractError']):
                self.validate['main'](text,reason,prepared['prepared_input'],prepared['input_sha256'])

    def test_guard_rejects_request_analysis_context_drift_before_llm(self):
        for key in ('request','analysis','expected_input_sha256'):
            wire=self.wire();wire[key]+='changed'
            with self.subTest(key=key),self.assertRaises(self.prepare['ContractError']):
                self.prepare['main'](**wire)
        wire=self.wire();context=json.loads(wire['planning_context'])
        context['repositories']['server']['evidence'][0]['content']='tampered'
        wire['planning_context']=canonical(context)
        with self.assertRaisesRegex(self.prepare['ContractError'],'planner_input_mismatch'):
            self.prepare['main'](**wire)

    def test_guard_rechecks_sources_snapshot_and_structure_even_with_matching_hash(self):
        for mutation,code in [
            (lambda p:p['repositories']['server']['evidence'][0].update(content='tampered'),'repository_source_mismatch'),
            (lambda p:p['repositories']['server'].update(ref='HEAD'),'schema_const'),
            (lambda p:p['binding'].update(request_sha256='0'*64),'request_digest_mismatch'),
            (lambda p:p.update(approved=True),'planning_context_fields')]:
            p=copy.deepcopy(self.case['prepared_input']);mutation(p)
            context={k:v for k,v in p.items() if k not in ('request','analysis')}
            wire=dict(request=p['request'],analysis=p['analysis'],planning_context=canonical(context),
                      expected_input_sha256=digest(canonical(p)),feedback_context='')
            with self.subTest(code=code),self.assertRaisesRegex(self.prepare['ContractError'],code):
                self.prepare['main'](**wire)

    def test_feedback_is_separate_and_native_prefix_remains_data(self):
        wire=self.wire();wire['feedback_context']=None
        self.assertEqual(json.loads(self.prepare['main'](**wire)['prompt_data'])['feedback_context'],'')
        feedback='بازخورد انسانی و خروجی مبنا:\n'+canonical(dict(
            previous_output=dict(plan=canonical(self.case['reference_output'])),feedback_history=['سناریو را روشن‌تر کن']))
        wire['feedback_context']=feedback
        prompt=json.loads(self.prepare['main'](**wire)['prompt_data'])
        self.assertEqual(prompt['feedback_context'],feedback)
        self.assertEqual(prompt['request'],wire['request'])
        self.assertEqual(prompt['analysis'],json.loads(wire['analysis']))
        self.assertEqual(prompt['input_sha256'],self.case['expected_input_sha256'])

    def test_budgets_and_duplicate_json_are_rejected_without_truncation(self):
        wire=self.wire();wire['feedback_context']='x'*8001
        with self.assertRaisesRegex(self.prepare['ContractError'],'schema_length'):
            self.prepare['main'](**wire)
        wire=self.wire();wire['planning_context']='{"binding":{},"binding":{}}'
        with self.assertRaisesRegex(self.prepare['ContractError'],'duplicate_key'):
            self.prepare['main'](**wire)
        p=copy.deepcopy(self.case['prepared_input'])
        for context in p['repositories'].values():
            source=context['evidence'][0];source['content']='x'*3000;source['sha256']=digest(source['content'])
            extra=copy.deepcopy(source);extra['path']='doc/second.md';context['evidence'].append(extra)
        self.assertLess(len(canonical(p).encode()),32768)
        with self.assertRaisesRegex(ContractError,'transport_budget'):
            build_inputs(p,digest(canonical(p)),feedback_context='x'*8000)

    def test_graph_uses_validated_input_native_metadata_and_plan_only(self):
        graph=build()['workflow']['graph']
        self.assertEqual([(e['source'],e['target']) for e in graph['edges']],
            [('start','prepare'),('prepare','llm'),('llm','validate'),('validate','end')])
        self.assertEqual({v['variable'] for v in self.nodes['start']['variables']},set(self.wire()))
        self.assertIn(dict(variable='finish_reason',value_selector=['llm','finish_reason']),self.nodes['validate']['variables'])
        self.assertIn(dict(variable='prepared_input',value_selector=['prepare','prepared_input']),self.nodes['validate']['variables'])
        self.assertEqual(self.nodes['end']['outputs'],[dict(variable='plan',value_selector=['validate','plan'],value_type='string')])
        self.assertFalse(self.nodes['llm']['retry_config']['retry_enabled'])
        self.assertEqual(self.nodes['llm']['model']['completion_params']['max_tokens'],4096)
        for key in ('prepare','validate'):
            imports=[n for n in ast.walk(ast.parse(self.nodes[key]['code'])) if isinstance(n,(ast.Import,ast.ImportFrom))]
            self.assertEqual([a.name for n in imports for a in n.names],['hashlib','json','math','re'])

    def test_versioned_export_and_matching_prompt_manifest(self):
        self.assertEqual(build(),json.loads((ROOT/'workflow.json').read_text()))
        self.assertEqual(manifest(),json.loads((ROOT/'workflow-manifest.json').read_text()))
