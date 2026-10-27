"""Focused server-only checks. Never start a harness, model, browser or client."""
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest,Conflict,Forbidden,NotFound,ServiceUnavailable
from company_projects import harness,agents,stages,access,source_code as source
from company_projects.test_stages import StageFixture
from models.workflow import WorkflowRun

EVIDENCE=dict(summary='Synthetic result',changes=[],tests=dict(status='not_run',summary='Not executed'),references=[],diff='')

class HarnessTests(StageFixture):
    def setUp(self):
        super().setUp()
        agent=agents.load(self.session,dict(project_id=self.a['id'],workspace_id=self.workspace_a.id),self.agent_ids[0])
        grants=agents.grant_snapshot(self.session,agent)['grants']
        for g in grants:
            if g['account_id']==self.project_owner.id:g['actions']=['view','finalize','publish_definition']
        agents.set_grants(self.session,self.a['id'],self.workspace_a.id,self.project_owner.id,agent['id'],dict(expected_revision=agent['acl_revision'],grants=grants),str(uuid4()))
        self.policy_args=(self.session,self.a['id'],self.workspace_a.id,self.project_owner.id,agent['id'])
        harness.save_policy(*self.policy_args,dict(expected_revision=1,enabled=True,instructions='Synthetic mission and acceptance',requires_source=False))
        pair=source.pair(self.session,dict(code=source.pairing(self.session,self.editor.id,dict(name='Synthetic harness device'))['code']))
        self.runner=source.authenticate(self.session,pair['secret'])
        self.selection=dict(method='harness',mode='manual',device_id=str(self.runner['id']),source_job_id=None,profile_key=None)

    def launch_harness(self,mode='manual'):
        selection=dict(self.selection,mode=mode,profile_key='synthetic' if mode=='managed' else None)
        with patch('company_projects.runtime_models.attempt_inputs',side_effect=AssertionError('must not select a Kara model')):
            return self.act(self.get(),'run',execution=selection)

    def payload(self,row,**changes):
        body=dict(expected_revision=row['revision'],attempt_id=row['harness']['attempt_id'],snapshot_digest=row['harness']['snapshot_digest'],outputs={'answer':'Harness result'},evidence=EVIDENCE,session_id=None,continue_flow=False,reason='')
        return body|changes

    def submit(self,row,body=None,key=None,actor=None):
        return harness.stage_submit(self.session,self.a['id'],self.workspace_a.id,(actor or self.editor).id,self.inst['id'],row['id'],body or self.payload(row),key or str(uuid4()))

    def test_manual_result_uses_own_provenance_and_existing_human_handoff(self):
        row=self.launch_harness(); identity=row['active_attempt_id']; key=str(uuid4());body=self.payload(row)
        self.assertEqual(row['harness']['state'],'awaiting_user');self.assertIsNone(self.session.get(WorkflowRun,identity))
        from company_projects.runner_overview import overview
        activity=next(j for j in overview(self.session,self.editor.id)['active'] if j['id']==identity)
        self.assertEqual(activity['kind'],'harness');self.assertEqual(activity['stage_id'],row['id'])
        result=self.submit(row,body,key)
        self.assertEqual(result['state'],'awaiting_feedback');self.assertEqual(result['artifacts'][0]['kind'],'harness')
        self.assertEqual(self.get(self.second)['state'],'blocked')
        self.assertEqual(self.submit(row,body,key),result)
        chosen=self.act(result,'request_decision',artifact_id=result['artifacts'][0]['id'])
        done=self.act(chosen,'finalize',actor=self.project_owner,artifact_id=chosen['selected_artifact_id'],reason='Reviewed synthetic output')
        self.assertEqual(done['state'],'completed');self.assertEqual(self.get(self.second)['state'],'ready')
        self.assertEqual(self.get(self.second)['preview_inputs']['request'],'Harness result')
        self.assertEqual(harness.load(self.session,identity)['result']['origin'],'user_submission')

    def test_output_permission_and_old_round_are_fenced(self):
        row=self.launch_harness()
        with self.assertRaises(BadRequest):self.submit(row,self.payload(row,outputs={'unexpected':'x'}))
        with self.assertRaises(Forbidden):self.submit(row,self.payload(row,continue_flow=True,reason='No authority'))
        with self.assertRaises(NotFound):harness.load(self.session,row['active_attempt_id'],actor=self.other.id)
        self.assertEqual(self.get()['state'],'running');self.assertEqual(self.get()['artifacts'],[])
        harness.cancel_console(self.session,self.a['id'],self.workspace_a.id,self.editor.id,self.agent_ids[0],row['active_attempt_id'])
        with self.assertRaises(Conflict):self.submit(row)
        self.assertEqual(self.get(self.second)['state'],'blocked')

    def test_managed_claim_result_replay_and_profile_binding(self):
        profile=dict(key='synthetic',name='Synthetic adapter',kind='custom',version='test',digest='a'*64)
        harness.register(self.session,self.runner,dict(profiles=[profile]))
        row=self.launch_harness('managed')
        claimed=harness.claim(self.session,self.runner)['job'];self.assertEqual(claimed['id'],row['active_attempt_id'])
        self.assertIsNone(harness.claim(self.session,self.runner)['job'])
        harness.prepared(self.session,self.runner,claimed['id'],dict(snapshot_digest=claimed['snapshot_digest']))
        body={k:v for k,v in self.payload(row).items() if k in ('snapshot_digest','outputs','evidence','session_id')}
        with self.assertRaises(Conflict):harness.submit(self.session,harness.load(self.session,claimed['id']),body)
        self.assertTrue(harness.complete(self.session,self.runner,claimed['id'],body)['recorded'])
        self.assertTrue(harness.complete(self.session,self.runner,claimed['id'],body)['recorded'])
        self.assertEqual(self.get()['harness']['result']['origin'],'managed_harness')
        self.assertEqual(self.get(self.second)['state'],'blocked')

    def test_policy_and_device_revocation_are_enforced(self):
        with self.assertRaises(Forbidden):harness.save_policy(self.session,self.a['id'],self.workspace_a.id,self.editor.id,self.agent_ids[0],dict(expected_revision=2,enabled=True,instructions='x',requires_source=False))
        row=self.launch_harness();source.revoke(self.session,self.editor.id,self.runner['id'])
        self.assertEqual(harness.load(self.session,row['active_attempt_id'])['state'],'cancelled')
        with self.assertRaises(Conflict):self.submit(row)
        self.assertEqual(self.get(self.second)['state'],'blocked')

    def test_combined_delivery_requires_the_assigned_finalizer(self):
        # A new published synthetic flow explicitly assigns the executor as finalizer.
        agent=agents.load(self.session,dict(project_id=self.a['id'],workspace_id=self.workspace_a.id),self.agent_ids[0]);grants=agents.grant_snapshot(self.session,agent)['grants']
        for g in grants:
            if g['account_id']==self.editor.id:g['actions']=['view','run','feedback','finalize']
        agents.set_grants(self.session,self.a['id'],self.workspace_a.id,self.project_owner.id,agent['id'],dict(expected_revision=agent['acl_revision'],grants=grants),str(uuid4()))
        first=self.stage();first.update(finalizer_id=self.editor.id,finalizer_membership_id=access.membership(self.session,self.workspace_a.id,self.editor.id).id)
        self.flow=self.publish(self.save(stages=[first,self.stage('review',1,{'source':'stage','stage_key':'analysis','output':'answer'})]))
        self.req=self.decision(self.request());self.inst=self.create_instance();self.first,self.second=self.inst['stages']
        row=self.launch_harness();body=self.payload(row,continue_flow=True,reason='Explicit synthetic acceptance');key=str(uuid4())
        result=self.submit(row,body,key);self.assertEqual(result['state'],'completed')
        self.assertEqual(self.get(self.second)['state'],'ready');self.assertEqual(len(self.get()['decisions']),1)
        self.submit(row,body,key);self.assertEqual(len(self.get()['decisions']),1)

    def test_source_requirement_and_program_validator_cannot_be_bypassed(self):
        with patch.object(harness,'compatible',return_value='Special validator needs a mapping'):
            with self.assertRaises(Forbidden):self.launch_harness()
        cfg=harness.settings(*self.policy_args)['policy']
        harness.save_policy(*self.policy_args,dict(expected_revision=cfg['revision'],enabled=True,instructions='Requires source',requires_source=True))
        with self.assertRaises(BadRequest):self.launch_harness()

    def test_stale_cleanup_cannot_replace_a_successful_result(self):
        row=self.launch_harness();old=harness.load(self.session,row['active_attempt_id'])
        result=self.submit(row)
        self.assertFalse(harness.finish(self.session,old,'interrupted',{'error':'stale sweep'})['recorded'])
        current=harness.load(self.session,old['attempt_id'])
        self.assertEqual(current['state'],'succeeded');self.assertEqual(current['result']['outputs'],{'answer':'Harness result'})
        self.assertEqual(len(self.get()['artifacts']),1);self.assertEqual(self.get()['state'],result['state'])

    def test_policy_change_stops_active_work_and_program_retry_has_no_stale_harness_card(self):
        row=self.launch_harness();cfg=harness.settings(*self.policy_args)['policy']
        same=dict(expected_revision=cfg['revision'],enabled=True,instructions=cfg['instructions'],requires_source=False)
        self.assertEqual(harness.save_policy(*self.policy_args,same)['policy']['revision'],cfg['revision'])
        self.assertEqual(harness.load(self.session,row['active_attempt_id'])['state'],'awaiting_user')
        harness.save_policy(*self.policy_args,dict(same,enabled=False))
        self.assertEqual(self.get()['state'],'failed');self.assertEqual(harness.load(self.session,row['active_attempt_id'])['state'],'blocked')
        ready=self.act(self.get(),'retry');program=self.act(ready,'run')
        self.assertIsNone(program['harness']);self.assertEqual(self.get(self.second)['state'],'blocked')

    def test_read_expiry_rechecks_a_renewed_lease(self):
        profile=dict(key='synthetic',name='Synthetic',kind='custom',version='test',digest='b'*64)
        harness.register(self.session,self.runner,dict(profiles=[profile]));row=self.launch_harness('managed')
        harness.claim(self.session,self.runner);t=harness.table(self.session)
        self.session.execute(t.update().where(t.c.attempt_id==row['active_attempt_id']).values(lease_until=agents.now()-timedelta(seconds=1)))
        old=harness.load(self.session,row['active_attempt_id'])
        self.session.execute(t.update().where(t.c.attempt_id==row['active_attempt_id']).values(lease_until=agents.now()+timedelta(seconds=90)))
        self.assertFalse(harness._expire_one(self.session,old)['recorded'])
        self.assertEqual(harness.load(self.session,row['active_attempt_id'])['state'],'running')
        self.session.execute(t.update().where(t.c.attempt_id==row['active_attempt_id']).values(lease_until=agents.now()-timedelta(seconds=1)))
        with patch.object(harness,'_lock_tenant',side_effect=ServiceUnavailable('busy')):
            with self.assertRaises(Conflict):harness.heartbeat(self.session,self.runner,row['active_attempt_id'])
        self.assertEqual(self.get()['state'],'failed')
        self.assertEqual(harness.load(self.session,row['active_attempt_id'])['state'],'interrupted')

    def test_removed_profile_blocks_pending_work_but_preserves_a_completed_delivery(self):
        profile=dict(key='synthetic',name='Synthetic',kind='custom',version='test',digest='c'*64)
        harness.register(self.session,self.runner,dict(profiles=[profile]));row=self.launch_harness('managed')
        harness.register(self.session,self.runner,dict(profiles=[]))
        self.assertEqual(harness.load(self.session,row['active_attempt_id'])['state'],'blocked');self.assertEqual(self.get()['state'],'failed')
        ready=self.act(self.get(),'retry');harness.register(self.session,self.runner,dict(profiles=[profile]))
        row=self.act(ready,'run',execution=dict(self.selection,mode='managed',profile_key='synthetic'))
        claimed=harness.claim(self.session,self.runner)['job']
        body={k:v for k,v in self.payload(row).items() if k in ('snapshot_digest','outputs','evidence','session_id')}
        harness.complete(self.session,self.runner,claimed['id'],body)
        harness.register(self.session,self.runner,dict(profiles=[]))
        self.assertEqual(harness.load(self.session,claimed['id'])['state'],'succeeded');self.assertEqual(len(self.get()['artifacts']),1)

    def test_busy_stage_keeps_result_retryable_without_reexecution(self):
        profile=dict(key='synthetic',name='Synthetic',kind='custom',version='test',digest='d'*64)
        harness.register(self.session,self.runner,dict(profiles=[profile]));row=self.launch_harness('managed')
        claimed=harness.claim(self.session,self.runner)['job']
        body={k:v for k,v in self.payload(row).items() if k in ('snapshot_digest','outputs','evidence','session_id')}
        with patch.object(harness,'_lock_tenant',side_effect=ServiceUnavailable('retry')):
            with self.assertRaises(ServiceUnavailable):harness.complete(self.session,self.runner,claimed['id'],body)
            self.assertTrue(harness.heartbeat(self.session,self.runner,claimed['id'])['active'])
        self.assertEqual(harness.load(self.session,claimed['id'])['state'],'running');self.assertEqual(self.get()['artifacts'],[])
        harness.complete(self.session,self.runner,claimed['id'],body)
        self.assertEqual(len(self.get()['artifacts']),1)

    def test_harness_does_not_export_knowledge_when_a_program_filter_is_unsupported(self):
        import json
        from models.workflow import Workflow
        agent=agents.load(self.session,dict(project_id=self.a['id'],workspace_id=self.workspace_a.id),self.agent_ids[0])
        workflow=self.session.get(Workflow,agent['workflow_id']);graph=workflow.graph_dict
        graph['nodes'].append(dict(id='filtered-knowledge',data=dict(type='knowledge-retrieval',dataset_ids=[],metadata_filtering_mode='manual')))
        workflow.graph=json.dumps(graph);self.session.flush()
        candidate=dict(agent,workflow_digest=agents.fingerprint(workflow))
        self.assertIsNotNone(harness.compatible(self.session,candidate))
        with self.assertRaises(BadRequest):harness.knowledge(self.session,workflow,self.editor.id)
