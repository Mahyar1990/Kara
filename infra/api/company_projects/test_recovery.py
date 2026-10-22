"""Recovery boundaries on persisted data; external-effect replay stays a human decision."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import access, agents, agent_execution, recovery, stages
from company_projects.test_stages import StageFixture


class RecoveryTests(StageFixture):
    def control(self, row, action, actor=None, key=None, **data):
        return recovery.mutate(self.session, self.a['id'], self.workspace_a.id, (actor or self.project_owner).id,
            self.inst['id'], row['id'], action, dict(expected_revision=row['revision'], reason='explicit test decision', **data), key or str(uuid4()))

    def cancel(self, actor=None, key=None, expected=None):
        current = stages.list_instances(self.session, self.a['id'], self.workspace_a.id, self.admin.id)['data'][0]
        return recovery.cancel(self.session, self.a['id'], self.workspace_a.id, (actor or self.admin).id, self.inst['id'],
            dict(expected_revision=expected or current['revision'], reason='explicit cancellation'), key or str(uuid4()))

    def done(self, row=None):
        row = self.complete(row); row = self.act(row, 'request_decision', artifact_id=row['artifacts'][0]['id'])
        return self.act(row, 'finalize', actor=self.project_owner, artifact_id=row['selected_artifact_id'], reason='explicit finalizer')

    def test_cancel_pending_is_terminal_idempotent_scoped_and_audited(self):
        row = self.act(self.get(), 'run'); attempt = row['active_attempt_id']
        with self.assertRaises(Forbidden): self.cancel(actor=self.editor)
        key = str(uuid4()); expected = sum(s['revision'] for s in stages.stage_rows(self.session, stages.instance(self.session,
            dict(project_id=self.a['id'],workspace_id=self.workspace_a.id),self.inst['id'])))
        result = self.cancel(key=key, expected=expected)
        self.assertEqual(self.cancel(key=key, expected=expected), result)
        self.assertIsNone(agent_execution.claim(self.session, attempt)); self.assertEqual(self.get()['state'], 'cancelled')
        self.assertEqual(self.get()['actions'], []); self.assertEqual(self.get(self.second)['state'], 'cancelled')
        with self.assertRaises(Conflict): self.act(self.get(), 'run')
        with self.assertRaises(Conflict): self.control(self.get(), 'revalidate', actor=self.editor)
        entity = stages.table(self.session,'company_team_cancellations')
        for query in (entity.delete(),entity.update().values(reason='overwrite')):
            with self.assertRaises(sa.exc.DBAPIError), self.session.begin_nested(): self.session.execute(query)
        with self.assertRaises(NotFound): recovery.overview(self.session,self.b['id'],self.workspace_b.id,self.other.id,self.inst['id'])

    def test_running_cancel_wins_over_late_success_and_failure(self):
        row=self.act(self.get(),'run'); attempt=row['active_attempt_id']; self.assertIsNotNone(agent_execution.claim(self.session,attempt))
        self.cancel(actor=self.project_owner)
        for status in ('succeeded','failed'):
            self.assertFalse(agent_execution.finish(self.session,attempt,status,{'outputs':{'answer':'late'}}))
        native=stages.table(self.session,'company_team_agent_attempts')
        attempt=self.session.execute(sa.select(native).where(native.c.id==attempt)).mappings().one()
        self.assertEqual(attempt['status'],'interrupted'); self.assertTrue(attempt['result']['stop_requested'])
        self.assertEqual(self.get()['artifacts'],[])
        token=agent_execution._execution.set((attempt['id'],'app','workflow','actor'))
        try:self.assertEqual(agent_execution.native_task_id('app',attempt['id']),attempt['id'])
        finally:agent_execution._execution.reset(token)
        self.assertNotEqual(agent_execution.native_task_id('unmanaged','run'),'run')

    def test_manual_orphan_recovery_requires_age_authority_ack_and_new_attempt(self):
        row=self.act(self.get(),'run'); identity=row['active_attempt_id']; agent_execution.claim(self.session,identity)
        with self.assertRaises(Conflict):self.control(row,'recover',acknowledge_effects=True)
        native=stages.table(self.session,'company_team_agent_attempts')
        self.session.execute(native.update().where(native.c.id==identity).values(started_at=agents.now()-timedelta(hours=2)))
        with self.assertRaises(Forbidden):self.control(row,'recover',actor=self.editor,acknowledge_effects=True)
        with self.assertRaises(BadRequest):self.control(row,'recover',acknowledge_effects=False)
        self.control(row,'recover',acknowledge_effects=True); row=self.get();self.assertEqual(row['state'],'failed')
        self.assertEqual(len(row['attempts']),1)
        row=self.act(row,'retry');self.assertEqual(row['state'],'ready');self.assertEqual(len(row['attempts']),1)
        row=self.act(row,'run');self.assertNotEqual(row['active_attempt_id'],identity)
        self.assertFalse(agent_execution.finish(self.session,identity,'succeeded',{'outputs':{'answer':'late'}}))
        self.assertEqual(self.get()['active_attempt_id'],row['active_attempt_id'])

    def test_retry_budget_is_per_round_and_manager_releases_it_explicitly(self):
        with patch.dict('os.environ',{'KARA_TEAM_STAGE_RETRY_LIMIT':'1'}):
            row=self.complete(status='failed');row=self.act(row,'retry');row=self.complete(self.act(row,'run'),status='failed')
            self.assertNotIn('retry',row['actions'])
            with self.assertRaises(Conflict):self.act(row,'retry')
            self.control(row,'recover',acknowledge_effects=True);self.assertIn('retry',self.get()['actions'])

    def test_reassignment_requires_current_grants_and_keeps_published_binding_and_old_results(self):
        row=self.complete(); original=row['binding']; member=access.membership(self.session,self.workspace_a.id,self.admin.id)
        data=dict(executor_id=self.admin.id,executor_membership_id=member.id,
            finalizer_id=self.project_owner.id,finalizer_membership_id=original['finalizer']['membership_id'])
        with self.assertRaises(Forbidden):self.control(row,'reassign',**data)
        agent=agents.load(self.session,dict(project_id=self.a['id'],workspace_id=self.workspace_a.id),self.agent_ids[0])
        grants=agents.grant_snapshot(self.session,agent)['grants'];grants.append(dict(account_id=self.admin.id,membership_id=member.id,actions=['view','run','feedback']))
        agents.set_grants(self.session,self.a['id'],self.workspace_a.id,self.project_owner.id,agent['id'],dict(expected_revision=agent['acl_revision'],grants=grants),str(uuid4()))
        with self.assertRaises(Conflict):self.control(row,'reassign',**dict(data,executor_membership_id=str(uuid4())))
        self.control(row,'reassign',**data); fresh=self.get(actor=self.admin)
        self.assertEqual(fresh['state'],'stale');self.assertEqual(len(fresh['artifacts']),1)
        self.assertNotEqual(fresh['round'],fresh['artifacts'][0]['round'])
        raw=self.session.execute(sa.select(stages.tables(self.session)[1]).where(stages.tables(self.session)[1].c.id==row['id'])).mappings().one()
        self.assertEqual(raw['binding'],original);self.assertEqual(fresh['binding']['executor']['account_id'],self.admin.id)
        with self.assertRaises(Forbidden):self.control(fresh,'revalidate',actor=self.editor)
        self.control(fresh,'revalidate',actor=self.admin);self.assertEqual(self.get(actor=self.admin)['state'],'ready')

    def test_reopen_invalidates_consumers_and_old_decisions_cannot_finalize_new_round(self):
        first=self.done();second=self.done(self.act(self.get(self.second),'run'))
        with self.assertRaises(Forbidden):self.control(first,'reopen',actor=self.editor)
        result=self.control(first,'reopen');self.assertEqual(result['change']['affected_stage_ids'],[first['id'],second['id']])
        first=self.get();second=self.get(self.second)
        self.assertEqual([first['state'],second['state']],['stale','stale']);self.assertEqual(len(second['decisions']),1)
        with self.assertRaises(Conflict):self.control(second,'revalidate',actor=self.editor)
        self.control(first,'revalidate',actor=self.editor);first=self.get()
        with self.assertRaises(Conflict):self.act(first,'request_decision',artifact_id=first['artifacts'][0]['id'])
        self.done(self.act(first,'run')); second=self.get(self.second)
        self.control(second,'revalidate',actor=self.editor);self.assertEqual(self.get(self.second)['state'],'ready')
        self.assertEqual(len(self.get(self.second)['attempts']),1)

    def test_request_revision_invalidates_and_fences_inflight_attempt(self):
        first=self.done();second=self.act(self.get(self.second),'run');identity=second['active_attempt_id']
        agent_execution.claim(self.session,identity);self.request(self.req,content='changed scope needs fresh PO')
        self.assertEqual([self.get()['state'],self.get(self.second)['state']],['stale','stale'])
        self.assertFalse(agent_execution.finish(self.session,identity,'succeeded',{'outputs':{'answer':'late'}}))
        with self.assertRaises(Conflict):self.control(self.get(),'revalidate',actor=self.editor)
        overview=recovery.overview(self.session,self.a['id'],self.workspace_a.id,self.admin.id,self.inst['id'])
        self.assertTrue(overview['history']);self.assertEqual(len(self.get()['decisions']),1)
