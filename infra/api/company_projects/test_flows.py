"""Focused PostgreSQL checks for team flow authoring and immutable publication."""
import copy
import json
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import access, agents, flows, team
from company_projects.test_access import ProjectDatabaseFixture
from company_projects.test_agents import graph
from models.model import App
from models.workflow import Workflow


class FlowTests(ProjectDatabaseFixture):
    def setUp(self):
        super().setUp()
        access.membership(self.session, self.workspace_a.id, self.admin.id).role = 'normal'
        self.agent_ids = []
        for index in range(2):
            app = App(tenant_id=self.workspace_a.id, name=f'Synthetic flow app {index}', mode='workflow',
                status='normal', created_by=self.editor.id, enable_api=False, enable_site=False, max_active_requests=0)
            self.session.add(app); self.session.flush()
            workflow = Workflow.new(tenant_id=self.workspace_a.id, app_id=app.id, type='workflow', version='test-published',
                graph=json.dumps(graph()), features='{}', created_by=self.editor.id,
                environment_variables=[], conversation_variables=[], rag_pipeline_variables=[])
            self.session.add(workflow); self.session.flush(); app.workflow_id = workflow.id; self.session.flush()
            agent = agents.register(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
                dict(app_id=app.id, workflow_id=workflow.id, name=f'Synthetic agent {index}', description='', expected_revision=1), str(uuid4()))
            self.agent_ids.append(agent['id'])
            agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, agent['id'],
                dict(expected_revision=1, grants=[dict(account_id=person.id,
                    membership_id=access.membership(self.session, self.workspace_a.id, person.id).id, actions=actions)
                    for person, actions in ((self.editor, ['view', 'run']), (self.project_owner, ['finalize']))]), str(uuid4()))

    def stage(self, key='analysis', agent=0, source=None):
        return dict(key=key, title=key, agent_id=self.agent_ids[agent], executor_id=self.editor.id,
            executor_membership_id=access.membership(self.session, self.workspace_a.id, self.editor.id).id,
            finalizer_id=self.project_owner.id,
            finalizer_membership_id=access.membership(self.session, self.workspace_a.id, self.project_owner.id).id,
            decision_role=None, inputs={'request': source or {'source': 'request'}})

    def save(self, row=None, stages=None, actor=None, key=None, **changes):
        data = dict(name=row['name'] if row else str(uuid4()), description='', stages=stages if stages is not None else [self.stage()],
            expected_revision=row['revision'] if row else 1)
        data.update(changes)
        return flows.mutate(self.session, self.a['id'], self.workspace_a.id, (actor or self.editor).id,
            data, key or str(uuid4()), row['id'] if row else None)

    def publish(self, row, actor=None, key=None):
        return flows.mutate(self.session, self.a['id'], self.workspace_a.id, (actor or self.editor).id,
            dict(expected_revision=row['revision']), key or str(uuid4()), row['id'], 'publish')

    def test_native_authority_and_draft_visibility(self):
        with self.assertRaises(Forbidden):
            self.save(actor=self.admin)
        row = self.save(actor=self.product_owner)
        self.assertEqual(flows.list_flows(self.session, self.a['id'], self.workspace_a.id, self.admin.id)['data'], [])
        row = self.publish(row)
        result = flows.get_flow(self.session, self.a['id'], self.workspace_a.id, self.admin.id, row['id'])
        self.assertFalse(result['can_edit']); self.assertNotIn('draft_stages', result)
        self.assertEqual(result['published']['version'], 1)

    def test_two_flows_and_old_version_remain_stable_after_draft_and_publish(self):
        row = self.save(stages=[self.stage(), self.stage('review', 1, {'source': 'stage', 'stage_key': 'analysis', 'output': 'answer'})])
        first = self.publish(row); old = copy.deepcopy(first['published'])
        other = self.publish(self.save(stages=[self.stage('different', 1)]))
        self.assertNotEqual(first['id'], other['id'])
        edited = self.save(first, stages=[self.stage('revised', 1)], description='New draft')
        self.assertEqual(edited['published'], old)
        second = self.publish(edited)
        self.assertEqual(second['published']['version'], 2)
        scoped = dict(project_id=self.a['id'], workspace_id=self.workspace_a.id)
        self.assertEqual(flows.version(self.session, scoped, row['id'], old['id']), old)
        self.assertEqual(old['stage_bindings'][1]['depends_on'], ['analysis'])

    def test_incomplete_draft_is_saved_but_never_published(self):
        stage = self.stage(); stage['finalizer_id'] = None
        for stages in ([], [stage], [dict(self.stage(), inputs={})]):
            with self.subTest(stages=stages):
                row = self.save(stages=stages)
                with self.assertRaises(UnprocessableEntity):
                    self.publish(row)

    def test_cycles_forward_missing_and_unknown_output_bindings_rejected(self):
        for source in ({'source': 'stage', 'stage_key': 'analysis', 'output': 'answer'},
                {'source': 'stage', 'stage_key': 'future', 'output': 'answer'},
                {'source': 'stage', 'stage_key': 'missing', 'output': 'answer'}, {'source': 'unknown'}):
            row = self.save(stages=[self.stage(source=source)])
            with self.assertRaises((BadRequest, UnprocessableEntity)):
                self.publish(row)
        row = self.save(stages=[self.stage(), self.stage('review', 1, {'source': 'stage', 'stage_key': 'analysis', 'output': 'missing'})])
        with self.assertRaises(UnprocessableEntity): self.publish(row)

    def test_scope_foreign_members_and_workflow_validity(self):
        row = self.save()
        with self.assertRaises(NotFound):
            flows.get_flow(self.session, self.b['id'], self.workspace_b.id, self.other.id, row['id'])
        stage = self.stage(); stage.update(finalizer_id=self.other.id,
            finalizer_membership_id=access.membership(self.session, self.workspace_b.id, self.other.id).id)
        with self.assertRaises(NotFound): self.publish(self.save(stages=[stage]))
        agent = agents.load(self.session, dict(project_id=self.a['id'], workspace_id=self.workspace_a.id), self.agent_ids[0])
        workflow = self.session.get(Workflow, agent['workflow_id']); workflow.version = 'draft'; self.session.flush()
        with self.assertRaises(UnprocessableEntity): self.publish(row)

    def test_foreign_agent_archived_agent_and_revoked_permission_rejected(self):
        stage = self.stage(); stage['agent_id'] = str(uuid4())
        with self.assertRaises(NotFound): self.publish(self.save(stages=[stage]))
        row = self.save()
        agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, self.agent_ids[0],
            dict(expected_revision=2, grants=[]), str(uuid4()))
        with self.assertRaises(Forbidden): self.publish(row)
        agents.archive(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            self.agent_ids[1], dict(expected_revision=1), str(uuid4()))
        with self.assertRaises(Forbidden): self.publish(self.save(stages=[self.stage(agent=1)]))

    def test_changed_membership_and_business_role_are_checked_at_publication(self):
        stage = self.stage(); stage['decision_role'] = 'po'
        row = self.save(stages=[stage])
        with self.assertRaises(UnprocessableEntity): self.publish(row)
        join = access.membership(self.session, self.workspace_a.id, self.project_owner.id)
        team.set_roles(self.session, self.a['id'], self.workspace_a.id, self.product_owner.id, self.project_owner.id,
            dict(expected_revision=1, expected_membership_id=join.id, roles=['po']), str(uuid4()))
        self.assertEqual(self.publish(row)['published']['stage_bindings'][0]['decision_role'], 'po')
        stage = self.stage(); stage['executor_membership_id'] = str(uuid4())
        with self.assertRaises(Conflict): self.publish(self.save(stages=[stage]))

    def test_replay_conflicts_duplicate_names_and_missing_revision(self):
        key = str(uuid4()); row = self.save(key=key, name='Unique flow')
        self.assertEqual(self.save(key=key, name='Unique flow'), row)
        with self.assertRaises(Conflict): self.save(name=' unique FLOW ')
        pubkey = str(uuid4()); published = self.publish(row, key=pubkey)
        self.assertEqual(self.publish(row, key=pubkey), published)
        with self.assertRaises(Conflict): self.publish(row)
        with self.assertRaises(Conflict): self.save(row, key=key)
        with self.assertRaises(BadRequest): self.save(expected_revision=True)

    def test_immutable_versions_and_archive_preserve_exact_reference(self):
        row = self.publish(self.save()); published = row['published']
        _, versions = flows.tables(self.session)
        for query in (versions.update().where(versions.c.id == published['id']).values(name='overwrite'),
                versions.delete().where(versions.c.id == published['id'])):
            with self.assertRaises(sa.exc.DBAPIError), self.session.begin_nested():
                self.session.execute(query)
        archived = flows.mutate(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            dict(expected_revision=row['revision']), str(uuid4()), row['id'], 'archive')
        self.assertTrue(archived['archived'])
        with self.assertRaises(Conflict): self.save(archived)
        self.assertEqual(flows.get_version(self.session, self.a['id'], self.workspace_a.id,
            self.admin.id, row['id'], published['id']), published)

    def test_input_shapes_duplicate_steps_and_constant_validation(self):
        with self.assertRaises(BadRequest): self.save(stages=[self.stage(), self.stage()])
        with self.assertRaises(BadRequest): self.save(stages=[dict(self.stage(), actor_id=self.project_owner.id)])
        self.publish(self.save(stages=[self.stage(source={'source': 'constant', 'value': 'Synthetic constant'})]))
        with self.assertRaises(BadRequest): self.publish(self.save(stages=[self.stage(source={'source': 'constant', 'value': 123})]))
