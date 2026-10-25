"""Name-confirmed team removal, authority, replay and preserved native history."""
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import agents, agent_execution, entity_deletion, flows, recovery, stages
from company_projects.test_flows import FlowFixture
from company_projects.test_stages import StageFixture
from models.model import App
from models.workflow import Workflow


class DeletionTests(FlowFixture):
    def remove(self, kind, row, actor=None, key=None, **changes):
        body = dict(expected_revision=row['revision'], confirmation_name=row['name'])
        body.update(changes)
        return entity_deletion.remove(self.session, self.a['id'], self.workspace_a.id,
            (actor or self.project_owner).id, row['id'], body, key or str(uuid4()), kind)

    def agent(self, index=0):
        return agents.load(self.session, dict(project_id=self.a['id'], workspace_id=self.workspace_a.id), self.agent_ids[index])

    def test_full_exact_name_revision_and_authority_are_checked_on_server(self):
        flow = self.save(name='فلو نمونه با نام کامل')
        for kind, row in (('agent', self.agent()), ('flow', flow)):
            for name in ('', row['name'][:-1], row['name']+' ', None, True):
                with self.subTest(kind=kind, name=name), self.assertRaises(BadRequest):
                    self.remove(kind, row, confirmation_name=name)
            with self.assertRaises(Conflict): self.remove(kind, row, expected_revision=row['revision']+1)
            with self.assertRaises(Forbidden): self.remove(kind, row, actor=self.admin)
            with self.assertRaises(NotFound):
                entity_deletion.remove(self.session, self.b['id'], self.workspace_b.id, self.other.id, row['id'],
                    dict(expected_revision=row['revision'], confirmation_name=row['name']), str(uuid4()), kind)
        self.assertEqual(len(agents.list_agents(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id)['data']), 2)
        self.assertEqual(len(flows.list_flows(self.session, self.a['id'], self.workspace_a.id, self.editor.id)['data']), 1)

    def test_agent_removal_is_idempotent_hides_options_and_preserves_program(self):
        row = self.agent(); workflow = self.session.get(Workflow, row['workflow_id']); original = workflow.graph
        key = str(uuid4())
        result = self.remove('agent', row, key=key)
        self.assertEqual(self.remove('agent', row, key=key), result)
        with self.assertRaises(Conflict): self.remove('agent', row, key=key, confirmation_name='different')
        with self.assertRaises(NotFound): self.remove('agent', row)
        self.assertNotIn(row['id'], [x['id'] for x in agents.list_agents(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id)['data']])
        self.assertNotIn(row['id'], [x['id'] for x in flows.options(self.session, self.a['id'], self.workspace_a.id, self.editor.id)['agents']])
        self.assertIsNone(agent_execution.managed(self.session, row['app_id']))
        token = agent_execution._execution.set((str(uuid4()), row['app_id'], row['workflow_id'], self.editor.id))
        try:
            from contextlib import nullcontext
            from unittest.mock import patch
            with patch.object(agent_execution, 'Session', side_effect=lambda *_a, **_k: nullcontext(self.session)):
                with self.assertRaises(Forbidden):
                    agent_execution.assert_execution(self.workspace_a.id, row['app_id'], row['workflow_id'], self.editor.id)
        finally:
            agent_execution._execution.reset(token)
        self.assertIsNotNone(self.session.get(App, row['app_id']))
        self.assertEqual(self.session.get(Workflow, row['workflow_id']).graph, original)
        self.assertTrue(self.agent()['archived'])
        self.assertIsNotNone(self.agent()['deleted_at'])
        with self.assertRaises(Forbidden):
            agents.start(self.session, self.a['id'], self.workspace_a.id, self.editor.id, row['id'],
                dict(expected_revision=2, inputs={'request': 'test'}), str(uuid4()))
        self.assertIsNotNone(agent_execution.managed(self.session, self.agent(1)['app_id']))

    def test_flow_removal_preserves_immutable_versions_and_releases_name(self):
        row = self.publish(self.save(name='فلو قابل حذف'))
        published = row['published']
        key = str(uuid4())
        self.assertEqual(self.remove('flow', row, key=key), self.remove('flow', row, key=key))
        self.assertEqual(flows.list_flows(self.session, self.a['id'], self.workspace_a.id, self.editor.id)['data'], [])
        with self.assertRaises(NotFound): flows.get_flow(self.session, self.a['id'], self.workspace_a.id, self.editor.id, row['id'])
        self.assertEqual(flows.version(self.session, dict(project_id=self.a['id'], workspace_id=self.workspace_a.id), row['id'], published['id']), published)
        replacement = self.save(name=row['name'])
        self.assertNotEqual(replacement['id'], row['id'])
        with self.assertRaises(Conflict): self.publish(row)

    def test_archived_entities_can_be_deleted_with_their_current_name_and_revision(self):
        row = self.agent()
        archived = agents.archive(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            row['id'], dict(expected_revision=row['revision']), str(uuid4()))
        self.assertTrue(self.remove('agent', archived)['deleted'])
        flow = self.save()
        archived = flows.mutate(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            dict(expected_revision=flow['revision']), str(uuid4()), flow['id'], 'archive')
        self.assertTrue(self.remove('flow', archived)['deleted'])

    def test_deleting_one_shared_binding_keeps_the_other_agents_access_control(self):
        original = self.agent()
        sibling = agents.register(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            dict(app_id=original['app_id'], workflow_id=original['workflow_id'], name='Shared binding', description='', expected_revision=1), str(uuid4()))
        self.remove('agent', original)
        self.assertIsNotNone(agent_execution.managed(self.session, original['app_id']))
        with self.assertRaises(Forbidden): agent_execution.deny_native(original['app_id'], session=self.session)
        with self.assertRaises(Forbidden): agent_execution.native_permission(self.session, original['app_id'], self.editor.id)
        self.remove('agent', sibling)
        self.assertIsNone(agent_execution.managed(self.session, original['app_id']))

    def test_pending_attempt_prevents_agent_deletion(self):
        row = self.agent()
        attempt = agents.start(self.session, self.a['id'], self.workspace_a.id, self.editor.id, row['id'],
            dict(expected_revision=row['revision'], inputs={'request': 'test'}), str(uuid4()))
        with self.assertRaises(Conflict): self.remove('agent', row)
        self.assertIsNone(self.agent()['deleted_at'])
        attempts = agents.tables(self.session)[2]
        self.session.execute(attempts.update().where(attempts.c.id == attempt['id']).values(status='failed'))
        self.assertTrue(self.remove('agent', row)['deleted'])
        from contextlib import nullcontext
        from unittest.mock import patch
        with patch.object(agent_execution, 'Session', side_effect=lambda *_a, **_k: nullcontext(self.session)):
            with self.assertRaises(Forbidden):
                agent_execution.assert_execution(self.workspace_a.id, row['app_id'], row['workflow_id'], self.editor.id, attempt['id'])
            agent_execution.assert_execution(self.workspace_a.id, row['app_id'], row['workflow_id'], self.editor.id, str(uuid4()))


class InUseDeletionTests(StageFixture):
    def test_agent_is_protected_until_instance_cancelled_and_deleted_flow_keeps_history(self):
        scope = dict(project_id=self.a['id'], workspace_id=self.workspace_a.id)
        agent = agents.load(self.session, scope, self.agent_ids[0])
        body = dict(expected_revision=agent['revision'], confirmation_name=agent['name'])
        with self.assertRaises(Conflict):
            entity_deletion.remove(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
                agent['id'], body, str(uuid4()), 'agent')
        entity_deletion.remove(self.session, self.a['id'], self.workspace_a.id, self.editor.id, self.flow['id'],
            dict(expected_revision=self.flow['revision'], confirmation_name=self.flow['name']), str(uuid4()), 'flow')
        self.assertEqual(stages.get_stage(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            self.inst['id'], self.first['id'])['state'], 'ready')
        recovery.cancel(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, self.inst['id'],
            dict(expected_revision=self.inst['revision'], reason='Synthetic cancellation'), str(uuid4()))
        self.assertTrue(entity_deletion.remove(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            agent['id'], body, str(uuid4()), 'agent')['deleted'])
