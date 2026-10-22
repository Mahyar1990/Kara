"""Persisted stage guards and human feedback; real engine covered by HTTP smoke."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import agents, agent_execution, flows, stages
from company_projects.test_requests import RequestFixture


class StageFixture(RequestFixture):
    def setUp(self):
        super().setUp()
        for agent_id in self.agent_ids:
            row = agents.load(self.session, dict(project_id=self.a['id'], workspace_id=self.workspace_a.id), agent_id)
            grants = agents.grant_snapshot(self.session, row)['grants']
            for grant in grants:
                if grant['account_id'] == self.editor.id:
                    grant['actions'] = ['view', 'run', 'feedback']
            agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, agent_id,
                dict(expected_revision=row['acl_revision'], grants=grants), str(uuid4()))
        self.flow = self.publish(self.save(stages=[self.stage(), self.stage('review', 1,
            {'source': 'stage', 'stage_key': 'analysis', 'output': 'answer'})]))
        self.req = self.decision(self.request())
        self.inst = self.create_instance()
        self.first, self.second = self.inst['stages']

    def create_instance(self, key=None, actor=None, req=None):
        row = req or self.req
        return stages.create(self.session, self.a['id'], self.workspace_a.id, (actor or self.admin).id,
            dict(request_id=row['id'], intake_decision_id=row['current_decision_id'], expected_revision=row['revision']), key or str(uuid4()))

    def get(self, identity=None, actor=None):
        return stages.get_stage(self.session, self.a['id'], self.workspace_a.id, (actor or self.editor).id,
            self.inst['id'], (identity or self.first)['id'])

    def act(self, row, action, actor=None, key=None, **data):
        if action == 'feedback':
            data.setdefault('feedback_variable', 'request' if data.get('artifact_id') else None)
        return stages.mutate(self.session, self.a['id'], self.workspace_a.id, (actor or self.editor).id,
            self.inst['id'], row['id'], action, dict(expected_revision=row['revision'], **data), key or str(uuid4()))

    def complete(self, row=None, output=None, status='succeeded'):
        row = row or self.act(self.get(), 'run')
        attempt_id = row['active_attempt_id']
        if agent_execution.claim(self.session, attempt_id) is None:
            return self.get({'id': row['id']})
        native = stages.table(self.session, 'company_team_agent_attempts')
        self.session.execute(native.update().where(native.c.id == attempt_id).values(status=status,
            result={'outputs': output if output is not None else {'answer': 'native output'}}, finished_at=agents.now()))
        stages.complete_attempt(self.session, attempt_id)
        return self.get({'id': row['id']})


class StageTests(StageFixture):
    def test_create_is_explicit_unique_and_intake_bound(self):
        self.assertEqual([s['state'] for s in self.inst['stages']], ['ready', 'blocked'])
        self.assertEqual(self.get()['attempts'], [])
        with self.assertRaises(Conflict):
            self.create_instance()
        changed = self.request(self.req, content='new request')
        with self.assertRaises(Conflict):
            self.act(self.get(), 'run')
        self.assertFalse(self.get()['intake_valid'])
        self.assertEqual(changed['current']['version'], 2)

    def test_assigned_runner_and_explicit_permissions_no_manager_or_po_promotion(self):
        for actor in (self.admin, self.project_owner, self.product_owner):
            with self.subTest(actor=actor.id), self.assertRaises(Forbidden):
                self.act(self.first, 'run', actor=actor)
        native = self.act(self.get(), 'run')
        attempt = self.session.execute(sa.select(stages.table(self.session, 'company_team_agent_attempts'))
            .where(stages.table(self.session, 'company_team_agent_attempts').c.id == native['active_attempt_id'])).mappings().one()
        self.assertEqual(attempt['actor_id'], self.editor.id)
        self.assertEqual(attempt['workflow_id'], self.get()['binding']['workflow_id'])

    def test_success_is_draft_then_feedback_human_edit_and_explicit_finalize(self):
        row = self.complete()
        self.assertEqual(row['state'], 'awaiting_feedback'); self.assertIsNone(row['selected_artifact_id'])
        old = row['artifacts'][0]
        row = self.act(row, 'feedback', artifact_id=old['id'], message='دقیق‌تر کن', inputs={'request': 'revised input'})
        self.assertEqual(row['round'], 2); self.assertEqual(row['state'], 'ready')
        self.assertEqual(len(row['attempts']), 1); self.assertEqual(len(row['feedback']), 1)
        row = self.complete(self.act(row, 'run'), {'answer': 'second output'})
        with self.assertRaises(Conflict):
            self.act(row, 'request_decision', artifact_id=old['id'])
        parent = row['artifacts'][0]
        row = self.act(row, 'edit_output', artifact_id=parent['id'], content={'answer': 'human correction'}, reason='اصلاح انسانی')
        human = row['artifacts'][0]
        self.assertEqual(human['kind'], 'human'); self.assertEqual(human['parent_id'], parent['id'])
        self.assertEqual(human['author_id'], self.editor.id)
        row = self.act(row, 'request_decision', artifact_id=human['id'])
        with self.assertRaises(Forbidden):
            self.act(row, 'finalize', artifact_id=human['id'], reason='not finalizer')
        row = self.act(row, 'finalize', actor=self.project_owner, artifact_id=human['id'], reason='تصمیم نهایی انسانی')
        self.assertEqual(row['state'], 'completed'); self.assertEqual(len(row['decisions']), 1)
        second = self.get(self.second)
        self.assertEqual(second['state'], 'ready'); self.assertEqual(second['attempts'], [])
        self.assertEqual(second['preview_inputs'], {'request': 'human correction'})

    def test_only_selected_finalized_output_is_handed_on(self):
        row = self.complete(); original = row['artifacts'][0]
        row = self.act(row, 'edit_output', artifact_id=original['id'], content={'answer': 'unselected'}, reason='alternative')
        row = self.act(row, 'request_decision', artifact_id=original['id'])
        row = self.act(row, 'finalize', actor=self.project_owner, artifact_id=original['id'], reason='choose original')
        self.assertEqual(self.get(self.second)['preview_inputs']['request'], 'native output')

    def test_two_feedback_rounds_are_independent_from_attempts(self):
        row = self.complete()
        for text in ('round two', 'round three'):
            row = self.act(row, 'feedback', artifact_id=row['artifacts'][0]['id'], message=text, inputs={'request': text})
            row = self.complete(self.act(row, 'run'), {'answer': text})
        self.assertEqual(row['round'], 3); self.assertEqual(len(row['feedback']), 2)
        self.assertEqual(len(row['attempts']), 3); self.assertEqual(len(row['artifacts']), 3)

    def test_replay_cas_and_duplicate_completion_do_not_duplicate_work(self):
        row = self.get(); key = str(uuid4()); running = self.act(row, 'run', key=key)
        self.assertEqual(self.act(row, 'run', key=key), running)
        with self.assertRaises(Conflict):
            self.act(row, 'run')
        finished = self.complete(running)
        stages.complete_attempt(self.session, running['active_attempt_id'])
        self.assertEqual(self.get(), finished)
        row = self.act(finished, 'feedback', artifact_id=finished['artifacts'][0]['id'], message='new round', inputs={'request': 'new'})
        next_run = self.act(row, 'run')
        stages.complete_attempt(self.session, running['active_attempt_id'])
        self.assertEqual(self.get()['active_attempt_id'], next_run['active_attempt_id'])

    def test_standalone_attempt_cannot_be_precreated_and_attached_to_stage(self):
        from uuid import NAMESPACE_URL, uuid5
        row = self.get(); key = str(uuid4())
        predictable = str(uuid5(NAMESPACE_URL, 'kara.stage.run:' + row['id'] + ':' + key))
        independent = agents.start(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            row['binding']['agent_id'], dict(inputs=row['preview_inputs'], expected_revision=row['binding']['agent_revision']), predictable)
        running = self.act(row, 'run', key=key)
        self.assertNotEqual(running['active_attempt_id'], independent['id'])
        self.assertEqual(len(running['attempts']), 1)
        self.assertEqual(self.complete(running)['state'], 'awaiting_feedback')

    def test_archive_blocks_new_instance_and_preserves_existing_run(self):
        another = self.decision(self.request())
        flows.mutate(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            dict(expected_revision=self.flow['revision']), str(uuid4()), self.flow['id'], 'archive')
        with self.assertRaises(Conflict):
            self.create_instance(req=another)
        self.assertNotIn(another['id'], [row['id'] for row in stages.list_instances(self.session,
            self.a['id'], self.workspace_a.id, self.admin.id)['available_requests']])
        self.assertEqual(self.complete()['state'], 'awaiting_feedback')

    def test_missing_intake_at_worker_claim_blocks_and_stales_stage(self):
        running = self.act(self.get(), 'run')
        self.request(self.req, content='changed while queued')
        self.assertIsNone(agent_execution.claim(self.session, running['active_attempt_id']))
        row = self.get(); self.assertEqual(row['state'], 'stale'); self.assertEqual(row['artifacts'], [])

    def test_expired_intake_cannot_finalize(self):
        until = agents.now() + timedelta(hours=1)
        self.req = self.decision(self.request(), expires_at=until.isoformat())
        self.inst = self.create_instance()
        self.first, self.second = self.inst['stages']
        row = self.complete(); selected = row['artifacts'][0]
        row = self.act(row, 'request_decision', artifact_id=selected['id'])
        with patch('company_projects.agents.now', return_value=until + timedelta(seconds=1)):
            with self.assertRaises(Conflict):
                self.act(row, 'finalize', actor=self.project_owner, artifact_id=selected['id'], reason='too late')

    def test_revoked_run_before_completion_never_makes_artifact(self):
        running = self.act(self.get(), 'run'); attempt_id = running['active_attempt_id']
        self.assertIsNotNone(agent_execution.claim(self.session, attempt_id))
        grants = agents.tables(self.session)[0]
        self.session.execute(grants.delete().where(grants.c.agent_id == self.agent_ids[0], grants.c.account_id == self.editor.id,
            grants.c.action == 'run'))
        native = stages.table(self.session, 'company_team_agent_attempts')
        self.session.execute(native.update().where(native.c.id == attempt_id).values(status='succeeded', result={'outputs': {'answer': 'late'}}))
        stages.complete_attempt(self.session, attempt_id)
        row = self.get(); self.assertEqual(row['state'], 'stale'); self.assertEqual(row['artifacts'], [])

    def test_failure_and_contract_error_need_explicit_retry(self):
        row = self.complete(output={'unexpected': 'bad'})
        self.assertEqual(row['state'], 'failed'); self.assertEqual(row['artifacts'], [])
        row = self.act(row, 'retry'); self.assertEqual(row['state'], 'ready')
        row = self.complete(self.act(row, 'run'))
        self.assertEqual(len(row['attempts']), 2); self.assertEqual(row['feedback'], [])

    def test_changed_source_or_required_business_role_blocks_finalization(self):
        row = self.complete(); selected = row['artifacts'][0]
        row = self.act(row, 'request_decision', artifact_id=selected['id'])
        entity = stages.tables(self.session)[1]
        binding = dict(row['binding'], decision_role='po')
        self.session.execute(entity.update().where(entity.c.id == row['id']).values(binding=binding))
        with self.assertRaises(Forbidden):
            self.act(row, 'finalize', actor=self.project_owner, artifact_id=selected['id'], reason='role missing')
        self.assign_po(self.project_owner)
        from models.workflow import Workflow
        workflow = self.session.get(Workflow, binding['workflow_id']); workflow.graph = '{}'; self.session.flush()
        with self.assertRaises(Conflict):
            self.act(row, 'finalize', actor=self.project_owner, artifact_id=selected['id'], reason='source changed')

    def test_initial_input_revision_and_foreign_artifact_are_rejected_or_recorded(self):
        row = self.get()
        with self.assertRaises(BadRequest):
            self.act(row, 'feedback', artifact_id=None, message='', inputs={'request': 'new'})
        row = self.act(row, 'feedback', artifact_id=None, message='قبل از اجرا اصلاح شد', inputs={'request': 'new'})
        self.assertEqual(row['round'], 2); self.assertEqual(row['attempts'], [])
        row = self.complete(self.act(row, 'run'))
        with self.assertRaises(NotFound):
            self.act(row, 'edit_output', artifact_id=str(uuid4()), content={'answer': 'x'}, reason='x')
        with self.assertRaises(BadRequest):
            self.act(row, 'edit_output', artifact_id=row['artifacts'][0]['id'], content={'wrong': 'x'}, reason='x')

    def test_scope_and_history_immutability(self):
        row = self.complete()
        row = self.act(row, 'feedback', artifact_id=row['artifacts'][0]['id'], message='history', inputs={'request': 'history'})
        row = self.complete(self.act(row, 'run')); output = row['artifacts'][0]
        row = self.act(row, 'request_decision', artifact_id=output['id'])
        row = self.act(row, 'finalize', actor=self.project_owner, artifact_id=output['id'], reason='done')
        with self.assertRaises(Forbidden):
            self.get(actor=self.admin)  # PO with no agent grant cannot read stage outputs.
        with self.assertRaises(NotFound):
            stages.get_stage(self.session, self.b['id'], self.workspace_b.id, self.other.id, self.inst['id'], self.first['id'])
        entities = stages.tables(self.session)
        for index in (0, 2, 3, 4, 5):
            entity = entities[index]
            for query in (entity.update().values(created_at=agents.now()), entity.delete()):
                with self.subTest(table=entity.name), self.assertRaises(sa.exc.DBAPIError), self.session.begin_nested():
                    self.session.execute(query)
