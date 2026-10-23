"""Offline mapping/readback checks with synthetic IDs and no human decisions."""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from uuid import UUID
from scripts import test_clasor_pa04_inputs as pa_fixtures
from scripts import test_clasor_tl_handoff as tl_fixtures
from clasor_agents.pa04.contract import ContractError, canonical
from clasor_agents.product_flow.flow import (ROOT,template,bind,contracts,manifest,
    analysis_workflow,planning_workflow,analysis_run,planning_setup,planning_run)


def uid(i): return str(UUID(int=i))


class ProductFlowTests(unittest.TestCase):
    def setUp(self):
        base=pa_fixtures.InputAssemblyTests();base.setUp()
        tl=tl_fixtures.TLHandoffTests();tl.setUp()
        self.package=base.build();self.request=base.request;self.instance=base.instance
        self.instance['flow_version_id']=uid(30)
        self.actor=dict(account_id=uid(10),membership_id=uid(11))
        self.stage=tl.stage
        self.stage['preview_inputs']['request']=self.request['current']['content']
        self.stage.update(step_key='planning',round=1,inputs=None,attempts=[],feedback=[],artifacts=[],
                          actions=['run','feedback'],input_digest=None)
        self.receipt=tl.receipt;self.repos=tl.repos
        self.binding=dict(inputs=template()['stages'][1]['inputs'],decision_role='tl',
            executor=dict(self.actor,name='TL ساختگی'),finalizer=dict(self.actor,name='TL ساختگی'),
            agent_id=uid(21),workflow_id=uid(22))
        self.stage['binding']=copy.deepcopy(self.binding)
        self.selections={};self.options=dict(agents=[],members=[])
        for i,(key,role,wf) in enumerate([('analysis','po',analysis_workflow()),('planning','tl',planning_workflow())]):
            spec=dict(agent_id=uid(100+i),workflow_id=uid(200+i),account_id=uid(300+i),membership_id=uid(400+i))
            self.selections[key]=spec
            ic,oc=contracts(wf)
            self.options['agents'].append(dict(id=spec['agent_id'],workflow_id=spec['workflow_id'],
                input_contract=ic,output_contract=oc,runners=[spec['account_id']],finalizers=[spec['account_id']]))
            self.options['members'].append(dict(account_id=spec['account_id'],membership_id=spec['membership_id'],roles=[role]))

    def setup_packet(self):
        return planning_setup(self.package,self.request,self.instance,self.stage,self.actor,self.binding,self.receipt,self.repos)

    def readback(self,packet):
        stage=copy.deepcopy(self.stage);e=packet['expectation'];inputs=copy.deepcopy(packet['body']['inputs'])
        stage.update(revision=e['revision'],round=e['round'],inputs=inputs,preview_inputs=copy.deepcopy(inputs),input_digest='native-setup-digest')
        stage['feedback']=[dict(round=e['round'],input_digest=stage['input_digest'],parent_artifact_id=None,
            inputs=dict(submitted=copy.deepcopy(inputs),effective=copy.deepcopy(inputs),feedback_variable=None))]
        return stage

    def run_body(self,packet,stage):
        return planning_run(packet,self.package,self.request,self.instance,stage,self.actor)

    def test_bound_mapping_has_single_responsible_and_selected_analysis_only(self):
        draft=bind(self.options,self.selections)
        self.assertEqual(draft['stages'][1]['inputs']['analysis'],dict(source='stage',stage_key='analysis',output='analysis'))
        for stage in draft['stages']:
            self.assertEqual(stage['executor_id'],stage['finalizer_id'])
            self.assertEqual(stage['executor_membership_id'],stage['finalizer_membership_id'])
        # Exercise actual native binding/constant validators without database/imports.
        api=Path(__file__).resolve().parents[1]/'infra/api/company_projects'
        def functions(path,names):
            source=path.read_text();return '\n\n'.join(ast.get_source_segment(source,n) for n in ast.parse(source).body
                if isinstance(n,ast.FunctionDef) and n.name in names)
        env=dict(hashlib=hashlib,json=json,math=math,BadRequest=ContractError,UnprocessableEntity=ContractError)
        exec(functions(api/'agents.py',{'digest','body','validate_inputs'}),env)
        env['agents']=SimpleNamespace(**{k:env[k] for k in ('body','validate_inputs')})
        exec(functions(api/'flows.py',{'validate_bindings'}),env)
        previous=[]
        for stage,agent in zip(draft['stages'],self.options['agents']):
            env['validate_bindings'](agent['input_contract'],stage['inputs'],previous)
            previous.append(dict(key=stage['key'],output_contract=agent['output_contract']))

    def test_missing_grant_role_stale_membership_workflow_and_contract_rejected(self):
        for field,value,code in [('runners',[],'flow_authority_missing'),('finalizers',[],'flow_authority_missing'),
                ('workflow_id',uid(999),'flow_selection_stale'),('output_contract',['other'],'flow_contract_mismatch')]:
            options=copy.deepcopy(self.options);options['agents'][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ContractError,code):bind(options,self.selections)
        for field,value,code in [('roles',[],'flow_authority_missing'),('membership_id',uid(999),'flow_selection_stale')]:
            options=copy.deepcopy(self.options);options['members'][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ContractError,code):bind(options,self.selections)

    def test_initial_tl_sentinel_rejected_before_llm(self):
        wf=planning_workflow();node=next(n['data'] for n in wf['workflow']['graph']['nodes'] if n['id']=='prepare')
        env={};exec(node['code'],env)
        values={k:v['value'] for k,v in template()['stages'][1]['inputs'].items() if v['source']=='constant'}
        values.update(request=self.request['current']['content'],analysis=self.stage['preview_inputs']['analysis'])
        with self.assertRaisesRegex(env['ContractError'],'planning_context_fields'):env['main'](**values)

    def test_setup_predicts_one_cas_step_and_requires_fresh_readback(self):
        packet=self.setup_packet()
        self.assertEqual(packet['body']['expected_revision'],self.stage['revision'])
        self.assertIsNone(packet['body']['feedback_variable'])
        self.assertIsNone(packet['body']['artifact_id'])
        self.assertEqual(packet['prepared_input']['binding']['base_revision'],self.stage['revision']+1)
        with self.assertRaisesRegex(ContractError,'planning_setup_stale'):self.run_body(packet,self.stage)
        stage=self.readback(packet)
        self.assertEqual(self.run_body(packet,stage),dict(expected_revision=stage['revision']))
        self.assertEqual(self.run_body(packet,stage),dict(expected_revision=stage['revision']))
        self.assertNotEqual(packet['idempotency_key'],packet['run_idempotency_key'])

    def test_po_cannot_run_tl_by_shared_grant_and_membership_change_rejected(self):
        for actor in [dict(self.actor,account_id=uid(900)),dict(self.actor,membership_id=uid(901))]:
            with self.assertRaisesRegex(ContractError,'flow_responsible_mismatch'):
                planning_setup(self.package,self.request,self.instance,self.stage,actor,self.binding,self.receipt,self.repos)
        self.stage['actions']=[]
        with self.assertRaisesRegex(ContractError,'flow_action_unavailable'):self.setup_packet()

    def test_unselected_receipt_changed_request_and_started_setup_fail(self):
        self.stage['handoffs'][0]['decision_id']='other'
        with self.assertRaisesRegex(ContractError,'handoff_receipt_mismatch'):self.setup_packet()
        self.stage['handoffs'][0]['decision_id']=self.receipt['decision_id']
        self.request['current']['content']+='changed'
        with self.assertRaisesRegex(ContractError,'flow_request_stale'):self.setup_packet()
        self.request['current']['content']=self.package['envelope']['request']['text']
        self.stage['inputs']={}
        with self.assertRaisesRegex(ContractError,'planning_setup_already_started'):self.setup_packet()

    def test_preflight_rejects_preview_drift_new_version_stale_or_reassigned_stage(self):
        packet=self.setup_packet()
        for key,value in [('state','stale'),('revision',99),('input_digest','other')]:
            stage=self.readback(packet);stage[key]=value
            with self.subTest(key=key),self.assertRaises(ContractError):self.run_body(packet,stage)
        stage=self.readback(packet);stage['preview_inputs']['expected_input_sha256']='0'*64
        with self.assertRaisesRegex(ContractError,'preview_inputs_mismatch'):self.run_body(packet,stage)
        stage=self.readback(packet);stage['handoffs'][0]['artifact_id']='other'
        with self.assertRaisesRegex(ContractError,'handoff_receipt_mismatch'):self.run_body(packet,stage)
        stage=self.readback(packet);stage['binding']['executor']['account_id']=uid(900)
        with self.assertRaisesRegex(ContractError,'flow_binding_mismatch'):self.run_body(packet,stage)
        stage=self.readback(packet);self.instance['flow_version_id']=uid(901)
        with self.assertRaisesRegex(ContractError,'planning_setup_stale'):self.run_body(packet,stage)

    def test_analysis_preflight_preserves_original_inputs(self):
        base=pa_fixtures.InputAssemblyTests();base.setUp();package=base.build();stage=base.stage
        actor=dict(account_id=uid(10),membership_id=uid(11))
        binding=dict(decision_role='po',executor=actor,finalizer=actor,inputs=template()['stages'][0]['inputs'])
        stage.update(binding=binding,step_key='analysis',actions=['run'],state='ready',preview_inputs=package['inputs'])
        self.assertEqual(analysis_run(package,base.request,base.instance,stage,actor,binding),dict(expected_revision=2))
        stage['preview_inputs']['request']+=' feedback'
        with self.assertRaisesRegex(ContractError,'original_request_changed'):
            analysis_run(package,base.request,base.instance,stage,actor,binding)

    def test_template_and_manifest_have_no_drift(self):
        self.assertEqual(template(),json.loads((ROOT/'flow-template.json').read_text()))
        self.assertEqual(manifest(),json.loads((ROOT/'manifest.json').read_text()))
