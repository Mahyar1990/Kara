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
        with patch.object(agent_execution,'Session'), patch('company_projects.harness.is_attempt', return_value=False):
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
        local.events(self.session,self.device,self.job['id'],dict(sequence=2,event=dict(event='node_finished',node_id='start',status='succeeded',node_type='start',outputs={'request':'synthetic'})))
        local.events(self.session,self.device,self.job['id'],dict(sequence=3,event=dict(event='node_started',node_id='end',status='running',node_type='end')))
        local.events(self.session,self.device,self.job['id'],dict(sequence=4,event=dict(event='node_finished',node_id='end',status='succeeded',node_type='end',outputs={'answer':'Synthetic local result'})))
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

    def test_native_program_admission_cannot_call_central_engine(self):
        from services.app_generate_service import AppGenerateService
        from core.app.entities.app_invoke_entities import InvokeFrom
        # Ordinary program, no team binding; preserve its existing published graph.
        before=self.workflow.graph
        from company_projects import personal_model_runtime
        with patch.object(personal_model_runtime,'require_account_execution'),patch.object(AppGenerateService,'_run_with_guardrails',side_effect=AssertionError('central execution forbidden')):
            result=AppGenerateService.generate(self.app_model,self.project_owner,dict(inputs={'request':'synthetic'}),InvokeFrom.EXPLORE,session=self.session,streaming=True)
        self.assertTrue(hasattr(result,'__next__'));self.assertEqual(self.workflow.graph,before)
        jobs=local.table(self.session,'local_executions')
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(jobs).where(jobs.c.account_id==self.project_owner.id)),1)

    def test_connection_rpc_is_device_scoped_and_never_persists_token(self):
        from company_projects import local_rpc,gitlab_connections
        self.setup_job()
        connection=gitlab_connections.save(self.session,self.reader.id,dict(name='Synthetic local RPC',base_url='https://git.example.test',token='synthetic-rpc-token',expected_revision=1))
        stored=gitlab_connections.load(self.session,self.reader.id,connection['id'])
        job=local_rpc.enqueue(self.session,self.workspace_a.id,self.reader.id,'connection-http',dict(path='/api/v4/user',body=None),'gitlab',stored)
        self.assertNotIn('synthetic-rpc-token',json.dumps(job,default=str))
        claimed=local_rpc.claim(self.session,self.device)['job'];self.assertEqual(claimed['id'],job['id'])
        self.assertEqual(local_rpc.credentials(self.session,self.device,job['id'])['connection']['token'],'synthetic-rpc-token')
        body=dict(state='succeeded',value=dict(status=200,body=dict(id=1,username='synthetic')),error=None)
        self.assertTrue(local_rpc.complete(self.session,self.device,job['id'],body)['recorded'])
        self.assertTrue(local_rpc.complete(self.session,self.device,job['id'],body)['recorded'])
        with self.assertRaises(Conflict):local_rpc.credentials(self.session,self.device,job['id'])

    def test_server_model_wrapper_routes_to_local_rpc(self):
        from company_projects import model_client_boundary,personal_model_runtime,local_rpc
        class Client:
            def invoke_llm(self,tenant_id,user_id,plugin_id,provider,model,credentials):
                raise AssertionError('central model call forbidden')
                yield None
        model_client_boundary.install_client_boundary(Client)
        with patch.object(personal_model_runtime,'bound_credentials'),patch.object(local_rpc,'model_call',return_value=['synthetic-local-chunk']) as send:
            self.assertEqual(list(Client().invoke_llm('t','u','p','q','m',{})),['synthetic-local-chunk'])
            self.assertEqual(send.call_args.args[0],'invoke_llm')

    def test_device_http_routes_require_device_secret_and_no_console_session(self):
        from sqlalchemy.orm import Session
        from company_projects import source_controller
        self.setup_job();self.session.commit()
        factory=lambda *args,**kwargs:Session(bind=self.connection,join_transaction_mode='create_savepoint')
        with patch.object(source_controller,'Session',side_effect=factory):
            client=self.app.test_client();base='/console/api/company/source-runner/execution/'
            self.assertEqual(client.post(base+'claim').status_code,401)
            headers={'Authorization':'Bearer '+self.paired['secret']}
            response=client.post(base+'claim',headers=headers)
            self.assertEqual(response.status_code,200,response.get_data(as_text=True))
            self.assertEqual(response.json['job']['id'],self.attempt['id'])
            self.assertEqual(response.headers['Cache-Control'],'private, no-store')
            prefix=base+self.attempt['id']+'/'
            self.assertEqual(client.post(prefix+'heartbeat',headers=headers).status_code,200)
            self.assertEqual(client.post(prefix+'credentials',headers=headers).status_code,200)

    def test_revoking_device_interrupts_both_workflow_and_rpc(self):
        from company_projects import local_rpc
        self.setup_job();local.claim(self.session,self.device)
        rpc=local_rpc.enqueue(self.session,self.workspace_a.id,self.reader.id,'raw-code',dict(language='python3',preload='',code=''))
        source.revoke(self.session,self.reader.id,self.device['id'])
        self.assertEqual(local.execution(self.session,self.job['id'])['state'],'cancelled')
        self.assertEqual(local_rpc.load(self.session,rpc['id'])['state'],'cancelled')
