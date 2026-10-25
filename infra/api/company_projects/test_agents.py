"""Real PostgreSQL checks for pinned definitions, grants and run admission."""
import json
from contextlib import nullcontext
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import access, agents, agent_execution
from company_projects.test_access import ProjectDatabaseFixture
from models.account import TenantAccountJoin
from models.model import App
from models.workflow import Workflow, WorkflowRun


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
        data = dict(app_id=self.app_model.id, workflow_id=self.workflow.id,
            name='ایجنت نمونه', description='آزمون ساختگی', expected_revision=1)
        data.update(updates)
        return agents.register(self.session, self.a['id'], self.workspace_a.id,
            (actor or self.project_owner).id, data, key or str(uuid4()))

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

    def test_registration_idempotency_and_shared_app_remains_selectable(self):
        key = str(uuid4())
        first = self.register(key=key)
        self.assertEqual(self.register(key=key), first)
        second = self.register(name='ایجنت دوم')
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['app_id'], second['app_id'])
        self.assertEqual(first['workflow_id'], second['workflow_id'])
        self.assertIn(self.workflow.id, [source['workflow_id'] for source in agents.sources(
            self.session, self.a['id'], self.workspace_a.id, self.project_owner.id)['data']])
        self.grant(first)
        with self.assertRaises(Forbidden):
            self.launch(second)
        self.assertEqual([row['id'] for row in agents.list_agents(self.session,
            self.a['id'], self.workspace_a.id, self.reader.id)['data']], [first['id']])

    def test_shared_app_engine_uses_attempt_agent_and_independent_grants(self):
        first, second = self.register(), self.register()
        self.grant(second)
        second_attempt = self.launch(second)
        self.assertEqual(agent_execution.claim(self.session, second_attempt['id'])[1]['id'], second['id'])
        self.grant(first)
        first_attempt = self.launch(first)
        agent_execution.claim(self.session, first_attempt['id'])
        with patch.object(agent_execution, 'Session', side_effect=lambda *_args, **_kwargs: nullcontext(self.session)):
            args = (self.workspace_a.id, self.app_model.id, self.workflow.id, self.reader.id)
            token = agent_execution._execution.set((second_attempt['id'], self.app_model.id, self.workflow.id, self.reader.id))
            try:
                agent_execution.assert_execution(*args, run_id=second_attempt['id'])
                with self.assertRaises(Forbidden):
                    agent_execution.assert_execution(*args, run_id=first_attempt['id'])
                agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
                    second['id'], dict(expected_revision=2, grants=[]), str(uuid4()))
                with self.assertRaises(Forbidden):
                    agent_execution.assert_execution(*args, run_id=second_attempt['id'])
            finally:
                agent_execution._execution.reset(token)
            token = agent_execution._execution.set((first_attempt['id'], self.app_model.id, self.workflow.id, self.reader.id))
            try:
                agent_execution.assert_execution(*args, run_id=first_attempt['id'])
            finally:
                agent_execution._execution.reset(token)

    def test_shared_app_pins_each_version_and_archive_is_independent(self):
        first = self.register()
        newer = Workflow.new(tenant_id=self.workspace_a.id, app_id=self.app_model.id, type='workflow',
            version='published-test-2', graph=json.dumps(graph()), features='{}', created_by=self.editor.id,
            environment_variables=[], conversation_variables=[], rag_pipeline_variables=[])
        self.session.add(newer); self.session.flush()
        second = self.register(workflow_id=newer.id)
        self.app_model.workflow_id = newer.id; self.session.flush()
        for agent in (first, second):
            self.grant(agent)
            self.assertEqual(self.launch(agent)['workflow_id'], agent['workflow_id'])
        agents.archive(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            first['id'], dict(expected_revision=1), str(uuid4()))
        with self.assertRaises(Forbidden):
            self.launch(first)
        attempt = self.launch(second)
        agent_execution.claim(self.session, attempt['id'])
        token = agent_execution._execution.set((attempt['id'], self.app_model.id, newer.id, self.reader.id))
        try:
            with patch.object(agent_execution, 'Session', side_effect=lambda *_args, **_kwargs: nullcontext(self.session)):
                agent_execution.assert_execution(self.workspace_a.id, self.app_model.id, newer.id,
                    self.reader.id, run_id=attempt['id'])
        finally:
            agent_execution._execution.reset(token)

    def test_shared_source_edit_and_publish_require_all_active_agent_grants(self):
        first, second = self.register(), self.register()
        self.grant(first, target=self.editor, actions=['edit_definition', 'publish_definition'])
        for action in ('edit_definition', 'publish_definition'):
            with self.assertRaises(Forbidden):
                agent_execution.native_permission(self.session, self.app_model.id, self.editor.id, action)
        self.grant(second, target=self.editor, actions=['edit_definition'])
        agent_execution.native_permission(self.session, self.app_model.id, self.editor.id)
        with self.assertRaises(Forbidden):
            agent_execution.native_permission(self.session, self.app_model.id, self.editor.id, 'publish_definition')
        self.grant(second, target=self.editor, actions=['edit_definition', 'publish_definition'], expected=2)
        agent_execution.native_permission(self.session, self.app_model.id, self.editor.id, 'publish_definition')
        agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            first['id'], dict(expected_revision=2, grants=[]), str(uuid4()))
        agents.archive(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            first['id'], dict(expected_revision=1), str(uuid4()))
        agent_execution.native_permission(self.session, self.app_model.id, self.editor.id, 'publish_definition')
        agents.archive(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            second['id'], dict(expected_revision=1), str(uuid4()))
        with self.assertRaises(Forbidden):
            agent_execution.native_permission(self.session, self.app_model.id, self.editor.id)
        with self.assertRaises(Forbidden):
            agent_execution.deny_native(self.app_model.id, session=self.session)
        with self.assertRaises(Conflict):
            agent_execution.protect_source(self.session, app_id=self.app_model.id)

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

    def test_queued_claim_is_once_and_preserves_real_actor(self):
        agent = self.register(); self.grant(agent)
        attempt = self.launch(agent)
        claimed, definition = agent_execution.claim(self.session, attempt['id'])
        self.assertEqual(claimed['actor_id'], self.reader.id)
        self.assertEqual(definition['workflow_id'], self.workflow.id)
        self.assertIsNone(agent_execution.claim(self.session, attempt['id']))

    def test_queued_revoked_grant_blocks_execution(self):
        agent = self.register(); self.grant(agent)
        attempt = self.launch(agent)
        agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            agent['id'], dict(expected_revision=2, grants=[]), str(uuid4()))
        self.assertIsNone(agent_execution.claim(self.session, attempt['id']))
        _, _, attempts = agents.tables(self.session)
        self.assertEqual(self.session.scalar(sa.select(attempts.c.status).where(attempts.c.id == attempt['id'])), 'blocked')

    def test_changed_published_content_is_not_executed(self):
        agent = self.register(); self.grant(agent)
        attempt = self.launch(agent)
        self.workflow._features = '{"changed":true}'; self.session.flush()
        self.assertIsNone(agent_execution.claim(self.session, attempt['id']))

    def test_engine_boundary_requires_private_capability_and_exact_run(self):
        agent = self.register(); self.grant(agent)
        attempt = self.launch(agent)
        agent_execution.claim(self.session, attempt['id'])
        with patch.object(agent_execution, 'Session', side_effect=lambda *_args, **_kwargs: nullcontext(self.session)):
            args = (self.workspace_a.id, self.app_model.id, self.workflow.id, self.reader.id)
            with self.assertRaises(Forbidden):
                agent_execution.assert_execution(*args, run_id=attempt['id'])
            token = agent_execution._execution.set((attempt['id'], self.app_model.id, self.workflow.id, self.reader.id))
            try:
                agent_execution.assert_execution(*args, run_id=attempt['id'])
                with self.assertRaises(Forbidden):
                    agent_execution.assert_execution(*args, run_id=str(uuid4()))
                with self.assertRaises(Forbidden):
                    agent_execution.assert_execution(self.workspace_a.id, self.app_model.id, self.workflow.id, self.editor.id)
                agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
                    agent['id'], dict(expected_revision=2, grants=[]), str(uuid4()))
                with self.assertRaises(Forbidden):
                    agent_execution.assert_execution(*args, run_id=attempt['id'])
            finally:
                agent_execution._execution.reset(token)

    def test_native_edit_and_publish_require_both_permissions(self):
        agent = self.register()
        with self.assertRaises(Forbidden):
            agent_execution.native_permission(self.session, self.app_model.id, self.editor.id)
        self.grant(agent, target=self.editor, actions=['edit_definition'])
        agent_execution.native_permission(self.session, self.app_model.id, self.editor.id)
        with self.assertRaises(Forbidden):
            agent_execution.native_permission(self.session, self.app_model.id, self.editor.id, 'publish_definition')
        self.grant(agent, target=self.reader, actions=['edit_definition', 'publish_definition'], expected=2)
        with self.assertRaises(Forbidden):
            agent_execution.native_permission(self.session, self.app_model.id, self.reader.id)

    def test_managed_native_paths_and_sources_are_denied_but_old_apps_are_unchanged(self):
        agent_execution.deny_native(self.app_model.id, session=self.session)
        agent_execution.native_permission(self.session, self.app_model.id, self.reader.id)
        self.register()
        with self.assertRaises(Forbidden):
            agent_execution.deny_native(self.app_model.id, session=self.session)
        for kwargs in ({'app_id': self.app_model.id}, {'workflow_id': self.workflow.id}):
            with self.assertRaises(Conflict):
                agent_execution.protect_source(self.session, **kwargs)

    def test_managed_runs_do_not_expose_logs_through_legacy_inbox(self):
        from company_projects.inbox import run_conditions
        self.register()
        query = sa.select(WorkflowRun.id).where(
            *run_conditions(self.session, self.workspace_a.id, self.project_owner))
        self.assertEqual(list(self.session.scalars(query)), [])

    def test_idempotency_key_is_shared_across_agent_mutations(self):
        key = str(uuid4()); agent = self.register(key=key); self.grant(agent, target=self.project_owner)
        with self.assertRaises(Conflict):
            self.launch(agent, key=key, actor=self.project_owner)

    def test_real_web_factory_installs_guard(self):
        self.assertIn('guard_managed_app', [function.__name__ for function in self.app.before_request_funcs.get(None, [])])

    def test_http_boundary_denies_managed_debug_node_stop_and_delete(self):
        from flask import Flask
        from types import SimpleNamespace
        application = Flask('agent-boundary-test')
        application.add_url_rule('/apps/<uuid:app_id>/<path:action>', view_func=lambda **_: 'untouched', methods=['GET', 'POST', 'DELETE'])
        agent_execution.install_http_guard(application)
        self.register()
        with patch.object(agent_execution, 'db', SimpleNamespace(engine=self.connection.engine)), \
                patch.object(agent_execution, 'Session', side_effect=lambda *_args, **_kwargs: nullcontext(self.session)):
            client = application.test_client()
            for suffix in ('workflows/draft/run', 'workflows/draft/nodes/start/run', 'workflows/draft/loop/nodes/loop/run', 'tasks/test/stop', 'workflows/draft/trigger/run-all'):
                self.assertEqual(client.post(f'/apps/{self.app_model.id}/{suffix}', json={'actor_id': self.project_owner.id}).status_code, 403)
            self.assertEqual(client.delete(f'/apps/{self.app_model.id}/definition').status_code, 403)
            self.assertEqual(client.post(f'/apps/{uuid4()}/workflows/draft/run').status_code, 200)
