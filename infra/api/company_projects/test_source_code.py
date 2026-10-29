"""Source-only integration: user/project isolation, pinned definitions and device leases."""
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, Unauthorized
from company_projects import source_code as source, gitlab_connections as gitlab
from company_projects.test_access import ProjectDatabaseFixture

class SourceCodeTests(ProjectDatabaseFixture):
    def test_runner_overview_names_tasks_and_isolates_accounts_and_project_access(self):
        import json
        from company_projects import runner_overview, local_execution as local, local_rpc
        from models.account import TenantAccountJoin, TenantAccountRole
        self.setup_source()
        local.register(self.session, self.runner, dict(protocol=2, capabilities=['workflow-v2', 'source-v1']))
        local.set_binding(*self.args(), dict(device_id=self.runner['id'], source_job_id=None, expected_revision=1))
        job = self.enqueue()
        source.claim(self.session, self.runner)
        source.complete(self.session, self.runner, job['id'], dict(state='succeeded', components=[dict(key='backend', commit='a'*40)], error=None))
        local.set_binding(*self.args(), dict(device_id=self.runner['id'], source_job_id=job['id'], expected_revision=1))
        pending = self.enqueue()
        local_rpc.enqueue(self.session, self.workspace_a.id, self.project_owner.id, 'invoke_llm', {'private': 'synthetic-hidden-payload'})
        second = source.pair(self.session, dict(code=source.pairing(self.session, self.project_owner.id, dict(name='Home VDI'))['code']))
        second_runner = source.authenticate(self.session, second['secret'])
        member = TenantAccountJoin(tenant_id=self.workspace_b.id, account_id=self.project_owner.id, role=TenantAccountRole.NORMAL)
        self.session.add(member); self.session.flush()
        local.set_binding(self.session, self.b['id'], self.workspace_b.id, self.project_owner.id,
                          dict(device_id=second_runner['id'], source_job_id=None, expected_revision=1))
        report = runner_overview.overview(self.session, self.project_owner.id)
        self.assertEqual({p['id'] for p in report['projects']}, {self.a['id'], self.b['id']})
        self.assertEqual(next(p for p in report['projects'] if p['id'] == self.b['id'])['binding']['device_id'], second['device_id'])
        self.assertEqual(next(j for j in report['active'] if j['id'] == pending['id'])['title'], self.tree['name'])
        self.assertEqual(next(p for p in report['projects'] if p['id'] == self.a['id'])['binding']['source_name'], self.tree['name'])
        self.assertIn('درخواست مدل', [j['title'] for j in report['active']])
        for private in ('secret_hash', 'snapshot', 'payload', 'synthetic-hidden-payload', self.device['secret']):
            self.assertNotIn(private, json.dumps(report, default=str))
        self.session.delete(member); self.session.flush()
        self.assertEqual([p['id'] for p in runner_overview.overview(self.session, self.project_owner.id)['projects']], [self.a['id']])
        other = runner_overview.overview(self.session, self.editor.id)
        self.assertEqual(other['devices'], []); self.assertEqual(other['active'], [])
        self.assertTrue(all(p['binding'] is None for p in other['projects']))
        # Reading the dashboard does not claim or alter a pending preparation.
        self.assertEqual(source.row(self.session, 'jobs', pending['id'], {})['state'], 'pending')

    def test_update_reuses_directory_is_scoped_versioned_and_rebinds_on_success(self):
        from company_projects import local_execution as local
        self.setup_source(); original=self.enqueue(); source.claim(self.session,self.runner)
        source.complete(self.session,self.runner,original['id'],dict(state='succeeded',components=[dict(key='backend',commit='a'*40)],error=None))
        local.set_binding(*self.args(),dict(device_id=self.runner['id'],source_job_id=original['id'],expected_revision=1))
        data=dict(device_id=self.runner['id'],expected_revision=1,action_key=str(uuid4()),update_of=original['id'])
        for invalid in (None,'','not-a-uuid'):
            with self.assertRaises(source.agents.store.ProjectError): source.enqueue_update(*self.args(),self.tree['id'],data|dict(update_of=invalid))
        with self.assertRaises(Conflict): source.enqueue_update(*self.args(),self.tree['id'],data)
        local.register(self.session,self.runner,dict(protocol=2,capabilities=['workflow-v2','source-v1','source-update-v1']))
        update=source.enqueue_update(*self.args(),self.tree['id'],data)
        self.assertEqual(source.enqueue_update(*self.args(),self.tree['id'],data)['id'],update['id'])
        with self.assertRaises(Conflict): source.usable(self.session,source.row(self.session,'jobs',original['id'],{}))
        claimed=source.claim(self.session,self.runner)['job']
        self.assertEqual(claimed['local_directory'],original['id']); self.assertEqual(claimed['update_of'],original['id'])
        self.assertEqual(source.row(self.session,'jobs',original['id'],{})['result']['superseded_by'],update['id'])
        source.complete(self.session,self.runner,update['id'],dict(state='succeeded',components=[dict(key='backend',commit='b'*40)],error=None))
        result=source.row(self.session,'jobs',update['id'],{})
        self.assertEqual(result['result']['local_directory'],original['id']); source.usable(self.session,result)
        self.assertEqual(local.binding(*self.args())['source_job_id'],update['id'])
        with self.assertRaises(Conflict): source.enqueue_update(*self.args(),self.tree['id'],data|dict(action_key=str(uuid4())))
        with self.assertRaises(NotFound): source.enqueue_update(*self.args(self.editor),self.tree['id'],data|dict(action_key=str(uuid4())))
        next_job=source.enqueue_update(*self.args(),self.tree['id'],data|dict(action_key=str(uuid4()),update_of=update['id']))
        self.assertEqual(source.claim(self.session,self.runner)['job']['local_directory'],original['id'])
        source.complete(self.session,self.runner,next_job['id'],dict(state='failed',components=[],error='merge_conflict'))
        with self.assertRaises(Conflict): source.usable(self.session,source.row(self.session,'jobs',update['id'],{}))
        retry=source.enqueue_update(*self.args(),self.tree['id'],data|dict(action_key=str(uuid4()),update_of=next_job['id']))
        self.assertEqual(source.row(self.session,'jobs',retry['id'],{})['snapshot']['local_directory'],original['id'])

    def args(self,actor=None): return (self.session,self.a['id'],self.workspace_a.id,(actor or self.project_owner).id)
    def setup_source(self):
        self.connection_value=gitlab.save(self.session,self.project_owner.id,dict(name='Synthetic',base_url='https://git.example.test',token='synthetic-source-token',expected_revision=1))
        self.repo=source.save_repository(*self.args(),dict(name='Backend',url='https://git.example.test/group/backend',branch='sandbox',expected_revision=1))
        self.data=dict(name='Private workspace',expected_revision=1,components=[dict(key='backend',path='services/backend',repository_id=self.repo['id'],connection_id=self.connection_value['id'])],documents=[dict(path='docs/map.md',content='# Synthetic architecture')])
        self.tree=source.save_workspace(*self.args(),self.data)
        self.code=source.pairing(self.session,self.project_owner.id,dict(name='Synthetic local'))['code']
        self.device=source.pair(self.session,dict(code=self.code))
        self.runner=source.authenticate(self.session,self.device['secret'])
    def enqueue(self,key=None): return source.enqueue(*self.args(),self.tree['id'],dict(device_id=self.runner['id'],expected_revision=1,action_key=key or str(uuid4())))

    def test_members_can_register_but_only_owner_or_manager_can_edit_and_workspace_is_personal(self):
        self.setup_source()
        self.assertEqual(len(source.listing(*self.args(self.editor))['repositories']),1)
        self.assertEqual(source.listing(*self.args(self.editor))['workspaces'],[])
        with self.assertRaises(NotFound): source.save_workspace(*self.args(self.editor),self.data,self.tree['id'])
        with self.assertRaises(Forbidden): source.save_repository(*self.args(self.editor),dict(name='x',url=self.repo['url'],branch='main',expected_revision=1),self.repo['id'])
        with self.assertRaises(NotFound): source.listing(self.session,self.b['id'],self.workspace_b.id,self.editor.id)
        with self.assertRaises(NotFound): source.enqueue(*self.args(self.editor),self.tree['id'],dict(device_id=self.runner['id'],expected_revision=1,action_key=str(uuid4())))
        public=str(source.listing(*self.args()))+str(source.devices(self.session,self.project_owner.id))
        self.assertNotIn('synthetic-source-token',public); self.assertNotIn('secret_hash',public)

    def test_pair_code_once_device_auth_revoke_and_account_status(self):
        self.setup_source()
        with self.assertRaises(Unauthorized): source.pair(self.session,dict(code=self.code))
        with self.assertRaises(Unauthorized): source.authenticate(self.session,'malformed.'+'x'*48)
        with self.assertRaises(Unauthorized): source.authenticate(self.session,self.device['device_id']+'.'+'x'*48)
        with self.assertRaises(NotFound): source.revoke(self.session,self.editor.id,self.runner['id'])
        self.enqueue(); source.revoke(self.session,self.project_owner.id,self.runner['id'])
        with self.assertRaises(Unauthorized): source.authenticate(self.session,self.device['secret'])
        self.assertEqual(source.listing(*self.args())['jobs'][0]['state'],'cancelled')
        first=source.pairing(self.session,self.project_owner.id,dict(name='one'))['code']
        source.pairing(self.session,self.project_owner.id,dict(name='two'))
        with self.assertRaises(Unauthorized): source.pair(self.session,dict(code=first))

    def test_job_is_bound_idempotent_leased_and_completion_records_sha_only(self):
        self.setup_source(); key=str(uuid4()); job=self.enqueue(key)
        self.assertEqual(self.enqueue(key)['id'],job['id'])
        with self.assertRaises(Conflict): self.enqueue()
        other=source.pair(self.session,dict(code=source.pairing(self.session,self.editor.id,dict(name='other'))['code']))
        other_runner=source.authenticate(self.session,other['secret'])
        self.assertIsNone(source.claim(self.session,other_runner)['job'])
        claimed=source.claim(self.session,self.runner)['job']; self.assertEqual(claimed['components'][0]['branch'],'sandbox')
        with self.assertRaises(NotFound): source.credentials(self.session,other_runner,job['id'])
        self.assertEqual(source.credentials(self.session,self.runner,job['id'])['connections'][0]['token'],'synthetic-source-token')
        source.heartbeat(self.session,self.runner,job['id'])
        with self.assertRaises(Conflict): source.save_workspace(*self.args(),self.data,self.tree['id'])
        source.complete(self.session,self.runner,job['id'],dict(state='succeeded',components=[dict(key='backend',commit='a'*40)],error=None))
        self.assertTrue(source.complete(self.session,self.runner,job['id'],dict(state='succeeded',components=[dict(key='backend',commit='a'*40)],error=None))['recorded'])
        result=source.listing(*self.args())['jobs'][0]
        self.assertEqual(result['state'],'succeeded'); self.assertEqual(result['result']['components'][0]['commit'],'a'*40)
        with self.assertRaises(Conflict): source.credentials(self.session,self.runner,job['id'])
        next_job=self.enqueue(); source.claim(self.session,self.runner)
        t=source.table(self.session,'jobs'); self.session.execute(t.update().where(t.c.id==next_job['id']).values(lease_until=source.agents.now()-timedelta(seconds=1)))
        self.assertEqual(source.listing(*self.args())['jobs'][0]['state'],'interrupted')

    def test_revision_changes_and_cancellation_fail_closed_without_touching_definitions(self):
        self.setup_source(); job=self.enqueue(); source.claim(self.session,self.runner)
        source.cancel(*self.args(),job['id'])
        with self.assertRaises(Conflict): source.credentials(self.session,self.runner,job['id'])
        source.save_repository(*self.args(),dict(name='Backend',url=self.repo['url'],branch='main',expected_revision=1),self.repo['id'])
        with self.assertRaises(Conflict): self.enqueue()
        changed=source.save_workspace(*self.args(),self.data,self.tree['id'])
        self.assertEqual(changed['components'][0]['branch'],'main')
        self.assertEqual(changed['revision'],2)
        source.retire(*self.args(),'repositories',self.repo['id'],dict(expected_revision=2))
        self.assertEqual(source.listing(*self.args())['repositories'],[])
        self.assertEqual(len(source.listing(*self.args())['jobs']),1)

    def test_destination_and_path_validation(self):
        self.setup_source()
        bad=[dict(self.data,components=[dict(self.data['components'][0],path='../escape')]),dict(self.data,documents=[dict(path='services/backend/a.md',content='x')])]
        for data in bad:
            with self.assertRaises(BadRequest): source.save_workspace(*self.args(),data)
        foreign=source.save_repository(*self.args(),dict(name='Foreign',url='https://other.test/group/repo',branch='main',expected_revision=1))
        with self.assertRaises(BadRequest): source.save_workspace(*self.args(),self.data|dict(components=[self.data['components'][0]|dict(repository_id=foreign['id'])]))

    def test_http_device_protocol_works_without_console_session_and_requires_scoped_secret(self):
        from sqlalchemy.orm import Session
        from company_projects import source_controller
        self.setup_source(); job=self.enqueue(); self.session.commit()
        # All HTTP transactions share an outer rollback-only synthetic connection.
        factory=lambda *args,**kwargs: Session(bind=self.connection,join_transaction_mode='create_savepoint')
        with patch.object(source_controller,'Session',side_effect=factory):
            client=self.app.test_client(); base='/console/api/company/source-runner/'
            self.assertEqual(client.post(base+'claim').status_code,401)
            auth={'Authorization':'Bearer '+self.device['secret']}
            response=client.post(base+'claim',headers=auth)
            self.assertEqual(response.status_code,200,response.get_data(as_text=True))
            self.assertEqual(response.json['job']['id'],job['id'])
            self.assertEqual(response.headers['Cache-Control'],'private, no-store')
            prefix=base+'jobs/'+job['id']+'/'
            creds=client.post(prefix+'credentials',headers=auth)
            self.assertEqual(creds.status_code,200,creds.get_data(as_text=True))
            self.assertEqual(creds.json['connections'][0]['token'],'synthetic-source-token')
            done=client.post(prefix+'complete',headers=auth,json=dict(state='succeeded',components=[dict(key='backend',commit='b'*40)],error=None))
            self.assertEqual(done.status_code,200,done.get_data(as_text=True))
            self.assertEqual(client.post(prefix+'credentials',headers=auth).status_code,409)
