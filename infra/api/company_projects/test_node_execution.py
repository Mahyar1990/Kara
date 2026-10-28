"""Deterministic node admission/relay checks; no client, provider or code execution."""
import json
from copy import deepcopy
from unittest.mock import patch
from werkzeug.exceptions import BadRequest, Conflict, NotFound, Forbidden
from company_projects import runtime_models as runtime, local_execution as local, local_rpc, node_routing, source_code as source
from company_projects.test_runtime_models import RuntimeModelTests, model_schema


class NodeExecutionTests(RuntimeModelTests):
    def choices(self):
        graph = self.workflow.graph_dict
        other = deepcopy(graph['nodes'][1]); other['id'] = 'second'; other['data']['title'] = 'Second model'
        graph['nodes'].insert(2, other)
        graph['edges'] = [dict(source='start', target='llm'), dict(source='llm', target='second'), dict(source='second', target='end')]
        graph['nodes'][-1]['data']['outputs'][0]['value_selector'] = ['second', 'text']
        self.workflow.graph = json.dumps(graph); self.session.flush()
        first = self.save_model()
        second = self.save_model(name='Second', model_name='second-model', is_default=False)
        devices = []; self.device_secrets=[]
        for name in ('Coordinator', 'Remote'):
            code = source.pairing(self.session, self.editor.id, dict(name=name))['code']
            paired=source.pair(self.session, dict(code=code)); self.device_secrets.append(paired['secret'])
            device = source.authenticate(self.session, paired['secret'])
            local.register(self.session, device, dict(protocol=2, capabilities=['workflow-v2', 'node-routing-v1']))
            devices.append(device)
        choice = dict(version=2, models={'llm': first['id'], 'second': second['id']},
            runners={key: dict(device_id=device['id'], source_job_id=None) for key, device in zip(('llm', 'second'), devices)})
        return choice, first, second, devices

    def test_each_llm_checks_its_own_model_capabilities_and_parameters(self):
        choice, first, second, _ = self.choices()
        graph = self.workflow.graph_dict; graph['nodes'][2]['data']['structured_output_enabled'] = True
        self.workflow.graph = json.dumps(graph)
        original = self.workflow.graph
        with patch.object(runtime, 'schema_for', side_effect=lambda tenant, actor, row: model_schema(features=['structured-output'] if row['id'] == second['id'] else [])):
            selected = runtime.select(self.session, self.workflow, self.editor.id, json.dumps(choice))
            resolved = runtime.execution_workflow(self.workflow, selected, self.editor.id)
            self.assertEqual([n['data']['model']['name'] for n in resolved.graph_dict['nodes'] if n['data']['type'] == 'llm'], ['synthetic-model', 'second-model'])
            swapped = deepcopy(choice); swapped['models']['second'] = first['id']
            with self.assertRaises(BadRequest): runtime.select(self.session, self.workflow, self.editor.id, json.dumps(swapped))
        self.assertEqual(original, self.workflow.graph)
        self.assertNotIn('synthetic-key-', resolved.graph)
        for invalid in ('', first['id'], json.dumps(dict(choice, models={'llm': first['id']}))):
            with self.assertRaises(BadRequest): runtime.attempt_inputs(self.session, self.workflow, self.editor.id, {runtime.INPUT: invalid})
        foreign = self.save_model(actor=self.project_owner, model_name='foreign')
        choice['models']['second'] = foreign['id']
        with self.assertRaises(NotFound): runtime.attempt_inputs(self.session, self.workflow, self.editor.id, {runtime.INPUT: json.dumps(choice)})

    def test_model_revision_is_frozen_at_admission_and_cannot_be_forged(self):
        choice, first, _, _ = self.choices()
        legacy = local.build_snapshot(self.session, self.workflow, self.editor.id, {runtime.INPUT:first['id']}, trusted=True)
        self.assertFalse(legacy['routes'])
        self.assertEqual({v['id'] for v in legacy['models'].values()}, {first['id']})
        inputs = runtime.attempt_inputs(self.session, self.workflow, self.editor.id, {'request': 'Synthetic', runtime.INPUT: json.dumps(choice)})
        self.assertEqual(runtime.business_inputs(inputs), {'request': 'Synthetic'})
        with self.assertRaises(BadRequest): runtime.attempt_inputs(self.session, self.workflow, self.editor.id, inputs)
        self.save_model(old=first, name='Changed')
        with self.assertRaises(Conflict): local.build_snapshot(self.session, self.workflow, self.editor.id, inputs, trusted=True)

    def test_two_devices_receive_only_their_node_models_and_delegate_idempotently(self):
        choice, first, second, devices = self.choices()
        inputs = {'request': 'Synthetic', runtime.INPUT: json.dumps(choice)}
        job = local.enqueue(self.session, self.app_model, self.workflow, self.editor, inputs)
        claimed = local.claim(self.session, devices[0])['job']
        self.assertEqual(claimed['device_id'], devices[0]['id'])
        self.assertEqual(claimed['models']['llm']['id'], first['id'])
        self.assertEqual(claimed['models']['second']['id'], second['id'])
        self.assertEqual(set(local.credentials(self.session, devices[0], job['id'])['models']), {'llm'})
        payload = dict(node_id='second', pool={'llm': {'text': 'Synthetic first output'}})
        child = node_routing.request(self.session, devices[0], job['id'], payload)
        self.assertEqual(child['id'], node_routing.request(self.session, devices[0], job['id'], payload)['id'])
        with self.assertRaises(NotFound): local_rpc.credentials(self.session, devices[0], child['id'])
        remote = local_rpc.claim(self.session, devices[1])['job']
        self.assertEqual(remote['node_id'], 'second')
        self.assertEqual(set(local_rpc.credentials(self.session, devices[1], child['id'])['models']), {'second'})
        result = dict(state='succeeded', value=dict(output={'text': 'Synthetic second output'}, branch=None, total_tokens=0), error=None)
        local_rpc.complete(self.session, devices[1], child['id'], result)
        self.assertEqual(node_routing.request(self.session, devices[0], job['id'], payload)['result']['value'], result['value'])
        self.assertIsNone(local_rpc.claim(self.session, devices[1])['job'])
        with self.assertRaises(Conflict): node_routing.request(self.session, devices[0], job['id'], dict(payload, pool={}))
        local.cancel(self.session, self.a['id'], self.workspace_a.id, self.editor.id, job['id'])
        with self.assertRaises(Conflict): node_routing.request(self.session, devices[0], job['id'], payload)
        pending = local.enqueue(self.session, self.app_model, self.workflow, self.editor, inputs)
        local.claim(self.session, devices[0])
        child=node_routing.request(self.session, devices[0], pending['id'], payload)
        local.cancel(self.session, self.a['id'], self.workspace_a.id, self.editor.id, pending['id'])
        self.assertEqual(local_rpc.load(self.session,child['id'])['state'],'cancelled')
        self.assertIsNone(local_rpc.claim(self.session,devices[1])['job'])

    def test_foreign_or_incompatible_runners_and_reserved_pool_are_rejected(self):
        choice, _, _, devices = self.choices()
        code = source.pairing(self.session, self.project_owner.id, dict(name='Foreign'))['code']
        foreign = source.pair(self.session, dict(code=code))
        invalid = deepcopy(choice); invalid['runners']['llm']['device_id'] = foreign['device_id']
        with self.assertRaises(NotFound): runtime.attempt_inputs(self.session, self.workflow, self.editor.id, {runtime.INPUT:json.dumps(invalid)})
        local.register(self.session, devices[1], dict(protocol=2, capabilities=['workflow-v2']))
        with self.assertRaises(BadRequest): runtime.attempt_inputs(self.session, self.workflow, self.editor.id, {runtime.INPUT: json.dumps(choice)})
        local.register(self.session, devices[1], dict(protocol=2, capabilities=['workflow-v2', 'node-routing-v1']))
        job = local.enqueue(self.session, self.app_model, self.workflow, self.editor, {runtime.INPUT: json.dumps(choice)})
        local.claim(self.session, devices[0])
        with self.assertRaises(BadRequest): node_routing.request(self.session, devices[0], job['id'], dict(node_id='second', pool={'env': {}}))
        source.revoke(self.session, self.editor.id, devices[1]['id'])
        with self.assertRaises(Forbidden): local.heartbeat(self.session, devices[0], job['id'])

    def test_device_http_delegation_authentication_and_completion(self):
        from sqlalchemy.orm import Session
        from company_projects import source_controller
        choice, _, _, devices = self.choices()
        job = local.enqueue(self.session, self.app_model, self.workflow, self.editor, {runtime.INPUT:json.dumps(choice)})
        # Test the registered device endpoints, without a browser or real model.
        self.session.commit()
        factory=lambda *a,**k:Session(bind=self.connection,join_transaction_mode='create_savepoint')
        with patch.object(source_controller,'Session',side_effect=factory):
            client=self.app.test_client(); base='/console/api/company/source-runner/'
            coordinator={'Authorization':'Bearer '+self.device_secrets[0]}; remote={'Authorization':'Bearer '+self.device_secrets[1]}
            self.assertEqual(client.post(base+'execution/'+job['id']+'/node',json=dict(node_id='second',pool={})).status_code,401)
            self.assertEqual(client.post(base+'execution/claim',headers=coordinator).status_code,200)
            response=client.post(base+'execution/'+job['id']+'/node',json=dict(node_id='second',pool={}),headers=coordinator)
            self.assertEqual(response.status_code,200,response.get_data(as_text=True)); child=response.json['id']
            self.assertEqual(client.post(base+'rpc/claim',headers=remote).json['job']['node_id'],'second')
            self.assertEqual(set(client.post(base+'rpc/'+child+'/credentials',headers=remote).json['models']),{'second'})
            result=dict(state='succeeded',value=dict(output={'text':'synthetic'},branch=None,total_tokens=0),error=None)
            self.assertEqual(client.post(base+'rpc/'+child+'/complete',json=result,headers=remote).status_code,200)

    def test_overlapping_coordinators_wait_without_blocking_remote_node_delivery(self):
        choice, _, _, devices = self.choices()
        first=local.enqueue(self.session,self.app_model,self.workflow,self.editor,{runtime.INPUT:json.dumps(choice)})
        reverse=deepcopy(choice)
        reverse['runners']['llm']['device_id']=devices[1]['id']
        reverse['runners']['second']['device_id']=devices[0]['id']
        second=local.enqueue(self.session,self.app_model,self.workflow,self.editor,{runtime.INPUT:json.dumps(reverse)})
        self.assertEqual(local.claim(self.session,devices[0])['job']['id'],first['id'])
        self.assertIsNone(local.claim(self.session,devices[1])['job'])
        local.set_binding(self.session,self.a['id'],self.workspace_a.id,self.editor.id,dict(device_id=devices[1]['id'],source_job_id=None,expected_revision=1))
        for _ in range(21):local_rpc.enqueue(self.session,self.workspace_a.id,self.editor.id,'invoke_llm',{})
        self.assertIsNone(local_rpc.claim(self.session,devices[1])['job'])
        child=node_routing.request(self.session,devices[0],first['id'],dict(node_id='second',pool={}))
        self.assertEqual(local_rpc.claim(self.session,devices[1])['job']['id'],child['id'])
        local_rpc.complete(self.session,devices[1],child['id'],dict(state='succeeded',value=dict(output={'text':'synthetic'},branch=None,total_tokens=0),error=None))
        local.cancel(self.session,self.a['id'],self.workspace_a.id,self.editor.id,first['id'])
        self.assertEqual(local.claim(self.session,devices[1])['job']['id'],second['id'])
