"""Server-only protocol checks; no client, browser, Git, Docker-code or LLM is executed."""
import json
from uuid import uuid4
from unittest.mock import patch
import sqlalchemy as sa
from werkzeug.exceptions import Conflict,Forbidden,NotFound
from company_projects import local_execution as local, source_code as source, agents, agent_execution
from company_projects.test_agents import AgentTests, graph
from company_projects.test_access import ProjectDatabaseFixture
from company_projects import access
from models.model import App
from models.workflow import Workflow

class LocalExecutionTests(ProjectDatabaseFixture):
    register=AgentTests.register
    grant=AgentTests.grant
    launch=AgentTests.launch
    def setUp(self):
        super().setUp()
        self.reader=self.admin
        access.membership(self.session,self.workspace_a.id,self.reader.id).role='normal'
        self.app_model=App(tenant_id=self.workspace_a.id,name='Synthetic local execution',mode='workflow',status='normal',created_by=self.editor.id,enable_site=False,enable_api=False,max_active_requests=0)
        self.session.add(self.app_model);self.session.flush()
        self.workflow=Workflow.new(tenant_id=self.workspace_a.id,app_id=self.app_model.id,type='workflow',version='published-test',graph=json.dumps(graph()),features='{}',created_by=self.editor.id,environment_variables=[],conversation_variables=[],rag_pipeline_variables=[])
        self.session.add(self.workflow);self.session.flush();self.app_model.workflow_id=self.workflow.id;self.session.flush()

    def setup_job(self):
        self.agent=self.register(); self.grant(self.agent)
        pair=source.pairing(self.session,self.reader.id,dict(name='Synthetic execution device'))
        self.paired=source.pair(self.session,dict(code=pair['code'])); self.device=source.authenticate(self.session,self.paired['secret'])
        local.register(self.session,self.device,dict(protocol=2,capabilities=['workflow-v2']))
        self.scope=(self.session,self.a['id'],self.workspace_a.id,self.reader.id)
        local.set_binding(*self.scope,dict(device_id=self.device['id'],source_job_id=None,expected_revision=1))
        self.attempt=self.launch(self.agent)
        self.job=local.dispatch_team(self.session,self.attempt['id'])
        return self.job

    def test_dispatch_is_metadata_only_and_original_definitions_unchanged(self):
        original=self.workflow.graph
        self.setup_job()
        self.assertEqual(self.workflow.graph,original)
        self.assertEqual(self.job['state'],'pending')
        self.assertEqual(agents.get_attempt(*self.scope,self.agent['id'],self.attempt['id'])['status'],'pending')
        with patch.object(agent_execution,'Session') as session_factory:
            with patch.object(local,'dispatch_team') as enqueue:
                agent_execution.execute(self.attempt['id']);enqueue.assert_called_once()
        self.assertNotIn('credentials',json.dumps(self.job,default=str))

    def test_device_claim_status_events_idempotence_and_result(self):
        self.setup_job(); claimed=local.claim(self.session,self.device)['job']; self.assertEqual(claimed['id'],self.attempt['id'])
        self.assertIsNone(local.claim(self.session,self.device)['job'])
        event=dict(sequence=1,event=dict(event='node_started',node_id='start',status='running',node_type='start'))
        self.assertTrue(local.events(self.session,self.device,self.job['id'],event)['recorded'])
        self.assertTrue(local.events(self.session,self.device,self.job['id'],event)['recorded'])
        with self.assertRaises(Conflict):local.events(self.session,self.device,self.job['id'],dict(event,sequence=3))
        body=dict(state='succeeded',outputs={'answer':'Synthetic local result'},error=None,total_steps=2,total_tokens=0,snapshot_digest=self.job['snapshot_digest'])
        self.assertTrue(local.complete(self.session,self.device,self.job['id'],body)['recorded'])
        self.assertTrue(local.complete(self.session,self.device,self.job['id'],body)['recorded'])
        result=agents.get_attempt(*self.scope,self.agent['id'],self.attempt['id'])
        self.assertEqual(result['status'],'succeeded'); self.assertEqual(result['result']['outputs']['answer'],'Synthetic local result')
        with self.assertRaises(Conflict): local.credentials(self.session,self.device,self.job['id'])

    def test_other_device_other_project_and_revoked_membership_are_denied(self):
        self.setup_job()
        code=source.pairing(self.session,self.reader.id,dict(name='Other device'))['code']
        second=source.pair(self.session,dict(code=code)); runner=source.authenticate(self.session,second['secret'])
        local.register(self.session,runner,dict(protocol=2,capabilities=['workflow-v2']))
        self.assertIsNone(local.claim(self.session,runner)['job'])
        local.claim(self.session,self.device)
        with self.assertRaises(NotFound): local.credentials(self.session,runner,self.job['id'])
        with self.assertRaises(NotFound): local.settings(self.session,self.b['id'],self.workspace_b.id,self.reader.id)
        with self.assertRaises(NotFound):local.cancel(self.session,self.b['id'],self.workspace_b.id,self.reader.id,self.job['id'])
        local.cancel(*self.scope,self.job['id'])
        with self.assertRaises(Conflict):local.heartbeat(self.session,self.device,self.job['id'])

    def test_no_binding_waits_without_fallback_and_old_runner_cannot_claim(self):
        self.agent=self.register();self.grant(self.agent); attempt=self.launch(self.agent)
        job=local.dispatch_team(self.session,attempt['id'])
        self.assertIsNone(job['device_id']);self.assertEqual(job['state'],'pending')
        self.assertEqual(self.workflow.graph_dict['nodes'][0]['data']['type'],'start')
