"""Review/CAS/immutable snapshot checks; no live publication or model calls."""
import copy
import unittest
from unittest.mock import Mock
from uuid import UUID
from scripts import test_clasor_product_flow as fixtures
from clasor_agents.pa04.contract import ContractError, canonical, digest
from clasor_agents.product_flow.flow import bind
from clasor_agents.product_flow.definitions import PACKAGES,verify_graph
from clasor_agents.product_flow.publication import FlowPublisher,verify_version


def uid(i):return str(UUID(int=i))


class PublicationTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.ProductFlowTests();f.setUp()
        self.options=f.options;self.selections=f.selections;self.receipts={};self.workflows={}
        for i,key in enumerate(('analysis','planning')):
            agent=self.options['agents'][i]
            agent.update(app_id=uid(500+i),revision=1,name='synthetic '+key,archived=False)
            self.options['members'][i]['name']='synthetic '+key
            workflow=dict(PACKAGES[key].build()['workflow'],id=agent['workflow_id'],version='published')
            self.workflows[key]=workflow
            self.receipts[key]=dict(role=key,revision=PACKAGES[key].REVISION,app_id=agent['app_id'],
                workflow_id=agent['workflow_id'],graph_sha256=verify_graph(key,workflow))
        body=bind(self.options,self.selections)
        self.draft=dict(id=uid(600),name=body['name'],description=body['description'],revision=2,
            current_version_id=None,draft_stages=body['stages'],archived=False,can_edit=True,published=None)
        self.c=FlowPublisher('http://localhost:8080',uid(1),uid(2),uid(3));self.c._scope=Mock()
        self.posts=[];self.version=None
        self.c._request=Mock(side_effect=self.request)

    def request(self,method,path,body=None,key=None):
        base=self.c.team+'/flows/'+self.draft['id']
        if method=='GET' and path==base:return copy.deepcopy(self.draft)
        if method=='GET' and path==self.c.team+'/flows/options':return copy.deepcopy(self.options)
        if method=='GET' and path==self.c.team+'/agents':return dict(data=copy.deepcopy(self.options['agents']))
        for role,receipt in self.receipts.items():
            if method=='GET' and path=='/apps/'+receipt['app_id']+'/workflows/publish':return copy.deepcopy(self.workflows[role])
        if method=='POST' and path==base+'/publish':
            self.posts.append((path,body,key));self.draft['revision']+=1
            self.draft['current_version_id']=self.version['id'];return {}
        if method=='GET' and path==base+'/versions/'+self.version['id']:return copy.deepcopy(self.version)
        raise AssertionError('unexpected endpoint')

    def review(self):return self.c.review(copy.deepcopy(self.draft),self.selections,self.receipts)

    def native_version(self,packet):
        stages=[dict(copy.deepcopy(s),workflow_digest='a'*64) for s in packet['stages']]
        content=dict(contract_version=1,name=packet['draft']['name'],description=packet['draft']['description'],stage_bindings=stages)
        return dict(content,id=uid(601),flow_id=packet['draft']['id'],source_revision=packet['draft']['revision'],
            version=1,digest=digest(canonical(content)))

    def test_review_is_read_only_and_pins_both_responsibles_and_selected_output(self):
        packet=self.review()
        self.assertFalse(self.posts)
        self.assertFalse(any('/apps/' in call.args[1] for call in self.c._request.call_args_list))
        stages=packet['stages']
        self.assertEqual([s['decision_role'] for s in stages],['po','tl'])
        self.assertEqual(stages[1]['depends_on'],['analysis'])
        self.assertEqual(stages[1]['inputs']['analysis'],dict(source='stage',stage_key='analysis',output='analysis'))
        self.assertEqual(stages[0]['executor'],stages[0]['finalizer'])

    def test_publication_uses_reviewed_revision_then_independent_get_and_recovers_without_republish(self):
        packet=self.review();self.version=self.native_version(packet)
        self.assertEqual(self.c.publish_reviewed(packet,uid(602)),self.version)
        self.assertEqual(self.posts,[(self.c.team+'/flows/'+self.draft['id']+'/publish',dict(expected_revision=2),uid(602))])
        self.assertEqual(self.c.publish_reviewed(packet,uid(602)),self.version)
        self.assertEqual(len(self.posts),1)

    def test_draft_revision_and_grant_changes_fail_before_post(self):
        packet=self.review();self.draft['revision']+=1
        with self.assertRaisesRegex(ContractError,'flow_review_stale'):self.c.publish_reviewed(packet,uid(602))
        self.draft['revision']-=1;self.options['agents'][1]['runners']=[]
        with self.assertRaisesRegex(ContractError,'flow_authority_missing'):self.c.publish_reviewed(packet,uid(602))
        self.assertFalse(self.posts)

    def test_installed_graph_and_receipt_must_match_export_before_publication(self):
        self.receipts['planning']['graph_sha256']='0'*64
        with self.assertRaisesRegex(ContractError,'flow_receipt_mismatch'):self.review()
        self.assertFalse(self.posts)

    def test_snapshot_rejects_rebound_people_workflow_or_mapping_even_with_new_digest(self):
        packet=self.review();version=self.native_version(packet)
        mutations=[lambda s:s['executor'].update(membership_id=uid(999)),
            lambda s:s.update(workflow_id=uid(999)),lambda s:s.update(depends_on=['planning']),
            lambda s:s.update(inputs={}),lambda s:s.update(workflow_digest='invalid')]
        for mutate in mutations:
            v=copy.deepcopy(version);mutate(v['stage_bindings'][0])
            v['digest']=digest(canonical({k:v[k] for k in ('contract_version','name','description','stage_bindings')}))
            with self.subTest(mutation=mutate),self.assertRaisesRegex(ContractError,'flow_snapshot_mismatch'):verify_version(packet,v)

    def test_native_digest_is_checked_without_substituting_graph_hash(self):
        packet=self.review();version=self.native_version(packet)
        self.assertNotEqual(version['stage_bindings'][0]['workflow_digest'],self.receipts['analysis']['graph_sha256'])
        verify_version(packet,version)
        version['digest']='0'*64
        with self.assertRaisesRegex(ContractError,'flow_snapshot_digest_mismatch'):verify_version(packet,version)
        version=self.native_version(packet);version['source_revision']+=1
        with self.assertRaisesRegex(ContractError,'flow_publication_mismatch'):verify_version(packet,version)

    def test_transport_does_not_allow_model_run_or_decisions_or_unreviewed_flow_publish(self):
        c=self.c
        self.assertFalse(c._allowed('POST',c.team+'/flows/'+uid(600)+'/publish'))
        c.reviewed_flows.add(uid(600))
        self.assertTrue(c._allowed('POST',c.team+'/flows/'+uid(600)+'/publish'))
        for path in [c.team+'/flows/'+uid(999)+'/publish',
            c.team+'/instances',c.team+'/requests/'+uid(4)+'/intake-decisions',
            c.team+'/instances/'+uid(5)+'/stages/'+uid(6)+'/run',
            c.team+'/instances/'+uid(5)+'/stages/'+uid(6)+'/finalize']:
            self.assertFalse(c._allowed('POST',path))
