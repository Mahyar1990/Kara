"""Definition setup checks without provider calls, publication or real accounts."""
import copy
from unittest.mock import Mock
import unittest
from uuid import UUID
from clasor_agents.pa04.contract import ContractError
from clasor_agents.product_flow.definitions import DefinitionCaller,PACKAGES,verify_graph
from clasor_agents.product_flow.flow import contracts


def uid(i):return str(UUID(int=i))


class DefinitionTests(unittest.TestCase):
    def setUp(self):
        self.c=DefinitionCaller('http://localhost:8080',uid(1),uid(2),uid(3))
        self.c._scope=Mock()
        self.receipt=dict(role='analysis',app_id=uid(4),revision=PACKAGES['analysis'].REVISION)
        self.draft=dict(PACKAGES['analysis'].build()['workflow'],version='draft')
        self.published=dict(self.draft,id=uid(5),version='published-version',marked_name='PA04-'+self.receipt['revision'])

    def test_graph_and_variables_are_verified_with_only_viewport_ignored(self):
        draft=copy.deepcopy(self.draft);draft['graph'].pop('viewport',None)
        expected=verify_graph('analysis',draft)
        self.assertEqual(verify_graph('analysis',self.draft),expected)
        draft['graph']['nodes'][2]['data']['prompt_template'][0]['text']='different prompt'
        with self.assertRaisesRegex(ContractError,'definition_graph_mismatch'):verify_graph('analysis',draft)
        draft=copy.deepcopy(self.draft);draft['environment_variables']=[dict(name='extra')]
        with self.assertRaisesRegex(ContractError,'definition_variables_mismatch'):verify_graph('analysis',draft)

    def test_import_is_new_app_only_with_exact_export_no_update_target(self):
        self.c._request=Mock(return_value=dict(status='completed',app_id=uid(4)))
        receipt=self.c.import_definition('analysis')
        self.assertEqual(receipt,self.receipt)
        method,path,body=self.c._request.call_args.args
        self.assertEqual((method,path),('POST','/apps/imports'))
        self.assertNotIn('app_id',body)
        self.assertIn(PACKAGES['analysis'].REVISION,body['name'])

    def test_publication_marker_fits_native_limit_and_exact_readback_is_required(self):
        c=self.c;c._request=Mock(side_effect=[self.draft,None,dict(result='success'),self.published])
        receipt=c.publish_definition(self.receipt)
        self.assertEqual(receipt['workflow_id'],uid(5))
        calls=[a.args for a in c._request.call_args_list if a.args[0]=='POST']
        self.assertEqual(len(calls),1)
        self.assertLessEqual(len(calls[0][2]['marked_name']),20)
        self.assertLessEqual(len(calls[0][2]['marked_comment']),100)
        c._request=Mock(side_effect=[self.draft,self.published])
        self.assertEqual(c.publish_definition(self.receipt),receipt)
        self.assertFalse(any(a.args[0]=='POST' for a in c._request.call_args_list))
        changed=copy.deepcopy(self.published);changed['marked_name']='another-release'
        c._request=Mock(side_effect=[self.draft,changed])
        with self.assertRaisesRegex(ContractError,'definition_publication_mismatch'):c.publish_definition(self.receipt)

    def test_registration_requires_verified_published_graph_and_contract(self):
        c=self.c;ic,oc=contracts(PACKAGES['analysis'].build())
        receipt=dict(self.receipt,workflow_id=uid(5),graph_sha256=verify_graph('analysis',self.published))
        agent=dict(id=uid(6),app_id=uid(4),workflow_id=uid(5),archived=False,input_contract=ic,output_contract=oc)
        c._request=Mock(side_effect=[self.published,dict(data=[]),agent])
        self.assertEqual(c.register_definition(receipt,uid(7)),agent)
        self.assertIn(uid(6),c.agents)
        c._request=Mock(side_effect=[self.published,dict(data=[dict(agent,workflow_id=uid(99))])])
        with self.assertRaisesRegex(ContractError,'definition_registration_mismatch'):c.register_definition(receipt,uid(7))

    def test_grants_do_not_overwrite_other_people_or_create_edit_publish_rights(self):
        c=self.c;c.agents.add(uid(6));person=dict(account_id=uid(2),membership_id=uid(8))
        grants=[dict(person,actions=['feedback','finalize','run','view'])]
        c._request=Mock(side_effect=[dict(revision=1,grants=[]),{},dict(revision=2,grants=grants)])
        c.assign_responsible(uid(6),person,uid(7))
        self.assertEqual(c._request.call_args_list[1].args[2]['grants'],grants)
        c._request=Mock(return_value=dict(revision=2,grants=[dict(person,account_id=uid(99),actions=['run'])]))
        with self.assertRaisesRegex(ContractError,'definition_grants_conflict'):c.assign_responsible(uid(6),person,uid(7))
        self.assertEqual(c._request.call_count,1)

    def test_setup_transport_never_allows_execution_flow_publication_or_model_configuration(self):
        c=self.c;c.apps.add(uid(4));c.agents.add(uid(6))
        self.assertTrue(c._allowed('POST','/apps/'+uid(4)+'/workflows/publish'))
        self.assertFalse(c._allowed('POST','/apps/'+uid(99)+'/workflows/publish'))
        for path in ['/apps/'+uid(4)+'/workflows/draft/run',c.team+'/flows/'+uid(7)+'/publish',
            c.team+'/instances/'+uid(7)+'/stages/'+uid(8)+'/run',
            '/workspaces/current/model-providers/example/models/credentials/validate',
            '/workspaces/current/model-providers/example/models/credentials']:
            with self.subTest(path=path):self.assertFalse(c._allowed('POST',path))
