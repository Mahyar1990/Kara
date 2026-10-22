"""Real PostgreSQL checks for pinned definitions, grants and run admission."""
import json
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import access, agents
from company_projects.test_access import ProjectDatabaseFixture
from models.account import TenantAccountJoin
from models.model import App
from models.workflow import Workflow


def graph():
    return dict(nodes=[dict(id='start', data=dict(type='start', title='شروع', variables=[
        dict(variable='request', label='درخواست', type='paragraph', required=True, max_length=2000)])),
        dict(id='end', data=dict(type='end', title='پایان', outputs=[dict(variable='answer', value_selector=['start', 'request'])]))],
        edges=[dict(id='edge', source='start', target='end', sourceHandle='source', targetHandle='target')])


class AgentTests(ProjectDatabaseFixture):
    def setUp(self):
        super().setUp()
        self.reader = self.admin
        access.membership(self.session, self.workspace_a.id, self.reader.id).role = 'normal'
        self.app_model = App(tenant_id=self.workspace_a.id, name='Synthetic team workflow', mode='workflow',
            status='normal', created_by=self.editor.id, enable_site=False, enable_api=False, max_active_requests=0)
        self.session.add(self.app_model); self.session.flush()
        self.workflow = Workflow.new(tenant_id=self.workspace_a.id, app_id=self.app_model.id, type='workflow',
            version='published-test-1', graph=json.dumps(graph()), features='{}', created_by=self.editor.id,
            environment_variables=[], conversation_variables=[], rag_pipeline_variables=[])
        self.session.add(self.workflow); self.session.flush()
        self.app_model.workflow_id = self.workflow.id
        self.session.flush()

    def register(self, actor=None, key=None, **updates):
        return agents.register(self.session, self.a['id'], self.workspace_a.id,
            (actor or self.project_owner).id, dict(app_id=self.app_model.id, workflow_id=self.workflow.id,
                name='ایجنت نمونه', description='آزمون ساختگی', expected_revision=1, **updates), key or str(uuid4()))

    def grant(self, agent, actor=None, target=None, actions=None, expected=1, key=None):
        target = target or self.reader
        join = access.membership(self.session, self.workspace_a.id, target.id)
        return agents.set_grants(self.session, self.a['id'], self.workspace_a.id,
            (actor or self.project_owner).id, agent['id'], dict(expected_revision=expected,
                grants=[dict(account_id=target.id, membership_id=join.id, actions=actions or ['run'])]), key or str(uuid4()))

    def launch(self, agent, key=None, actor=None, **updates):
        data = dict(inputs={'request': 'ساختگی'}, expected_revision=1)
        data.update(updates)
        return agents.start(self.session, self.a['id'], self.workspace_a.id, (actor or self.reader).id,
            agent['id'], data, key or str(uuid4()))

    def test_registration_authority_and_explicit_minimal_visibility(self):
        for actor in (self.editor, self.reader, self.other):
            with self.assertRaises((Forbidden, NotFound)):
                self.register(actor=actor)
        agent = self.register(actor=self.product_owner)
        self.assertEqual(agents.list_agents(self.session, self.a['id'], self.workspace_a.id, self.reader.id)['data'], [])
        self.grant(agent)
        value = agents.list_agents(self.session, self.a['id'], self.workspace_a.id, self.reader.id)['data'][0]
        self.assertEqual(value['actions'], ['run'])
        self.assertNotIn('graph', value)
        self.assertNotIn('workflow_digest', value)
        self.assertEqual(value['output_contract'], ['answer'])

    def test_foreign_scope_draft_and_unsupported_start_rejected(self):
        self.app_model.tenant_id = self.workspace_b.id; self.session.flush()
        with self.assertRaises(NotFound):
            self.register()
        self.app_model.tenant_id = self.workspace_a.id
        self.workflow.version = 'draft'; self.session.flush()
        with self.assertRaises(UnprocessableEntity):
            self.register()
        self.workflow.version = 'published-test-1'
        data = graph(); data['nodes'][0]['data']['type'] = 'trigger-schedule'
        self.workflow.graph = json.dumps(data); self.session.flush()
        with self.assertRaises(UnprocessableEntity):
            self.register()

    def test_registration_idempotency_and_unique_app(self):
        key = str(uuid4())
        first = self.register(key=key)
        self.assertEqual(self.register(key=key), first)
        with self.assertRaises(Conflict):
            self.register()

    def test_grant_authority_stale_version_and_key_conflicts(self):
        agent = self.register()
        for actor in (self.editor, self.reader):
            with self.assertRaises(Forbidden):
                self.grant(agent, actor=actor)
        key = str(uuid4())
        first = self.grant(agent, key=key)
        self.assertEqual(self.grant(agent, key=key), first)
        with self.assertRaises(Conflict):
            self.grant(agent)
        with self.assertRaises(Conflict):
            self.grant(agent, key=key, actions=['finalize'])

    def test_no_delegated_management_foreign_members_or_body_actor(self):
        agent = self.register()
        with self.assertRaises(BadRequest):
            self.grant(agent, actions=['manage_access'])
        foreign_join = access.membership(self.session, self.workspace_b.id, self.other.id)
        with self.assertRaises(NotFound):
            agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
                agent['id'], dict(expected_revision=1, grants=[dict(account_id=self.other.id,
                    membership_id=foreign_join.id, actions=['run'])]), str(uuid4()))
        self.grant(agent)
        with self.assertRaises(BadRequest):
            self.launch(agent, actor_id=self.project_owner.id)

    def test_normal_member_can_run_only_after_explicit_grant_and_replay_is_stable(self):
        agent = self.register()
        for actor in (self.project_owner, self.product_owner, self.editor, self.reader):
            with self.assertRaises(Forbidden):
                self.launch(agent, actor=actor)
        self.grant(agent)
        key = str(uuid4())
        attempt = self.launch(agent, key=key)
        self.assertEqual(self.launch(agent, key=key), attempt)
        self.assertEqual(attempt['workflow_id'], self.workflow.id)
        self.assertEqual(access.membership(self.session, self.workspace_a.id, self.reader.id).role, 'normal')
        with self.assertRaises(Conflict):
            self.launch(agent, key=key, inputs={'request': 'تغییر'})

    def test_feedback_and_finalize_grants_do_not_grant_run(self):
        agent = self.register()
        self.grant(agent, actions=['feedback', 'finalize'])
        with self.assertRaises(Forbidden):
            self.launch(agent)

    def test_revoke_and_remove_rejoin_prevent_replay_and_read(self):
        agent = self.register(); self.grant(agent)
        key = str(uuid4()); attempt = self.launch(agent, key=key)
        join = access.membership(self.session, self.workspace_a.id, self.reader.id)
        self.session.delete(join); self.session.flush()
        self.session.add(TenantAccountJoin(tenant_id=self.workspace_a.id, account_id=self.reader.id, role='normal'))
        self.session.flush()
        with self.assertRaises(Forbidden):
            self.launch(agent, key=key)
        with self.assertRaises(Forbidden):
            agents.get_attempt(self.session, self.a['id'], self.workspace_a.id, self.reader.id, agent['id'], attempt['id'])

    def test_input_validation_and_version_guard(self):
        agent = self.register(); self.grant(agent)
        for inputs in ({}, {'request': 3}, {'request': 'x', 'workflow_id': str(uuid4())}, {'request': 'x' * 2001}):
            with self.assertRaises(BadRequest):
                self.launch(agent, inputs=inputs)
        with self.assertRaises(Conflict):
            self.launch(agent, expected_revision=2)
        with self.assertRaises(BadRequest):
            self.launch(agent, expected_revision=True)

    def test_new_publish_does_not_move_agent_and_archive_preserves_history(self):
        agent = self.register(); self.grant(agent)
        self.app_model.workflow_id = str(uuid4()); self.session.flush()
        self.assertEqual(self.launch(agent)['workflow_id'], self.workflow.id)
        result = agents.archive(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            agent['id'], dict(expected_revision=1), str(uuid4()))
        self.assertTrue(result['archived'])
        with self.assertRaises(Forbidden):
            self.launch(agent)

    def test_database_prevents_source_deletion(self):
        self.register()
        with self.assertRaises(sa.exc.IntegrityError):
            with self.session.begin_nested():
                self.session.execute(sa.delete(Workflow).where(Workflow.id == self.workflow.id))
