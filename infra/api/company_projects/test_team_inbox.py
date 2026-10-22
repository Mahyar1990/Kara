"""Focused persisted personal work and least-privilege handoff regression checks."""
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from company_projects import agents, stages, team_inbox
from company_projects.test_stages import StageFixture


class TeamInboxTests(StageFixture):
    def inbox(self, actor=None, **kw):
        return team_inbox.list_actions(self.session, self.a['id'], self.workspace_a.id, (actor or self.editor).id, **kw)

    def finalize(self, row):
        row = self.act(row, 'request_decision', artifact_id=row['artifacts'][0]['id'])
        return self.act(row, 'finalize', actor=self.project_owner, artifact_id=row['selected_artifact_id'], reason='human decision')

    def test_personal_actions_match_detail_and_reads_do_not_dispatch_or_decide(self):
        def counts():
            return [self.session.scalar(sa.select(sa.func.count()).select_from(t)) for t in stages.tables(self.session)]
        before = counts()
        for _ in range(2):
            data = self.inbox()['data']; self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['stage_id'], self.first['id']); self.assertEqual(data[0]['kind'], 'run')
            self.assertEqual(data[0]['actions'], self.get()['actions']); self.assertEqual(data[0]['expected_outputs'], ['answer'])
            self.assertNotIn('inputs', data[0]); self.assertNotIn('artifacts', data[0])
            self.assertEqual(self.inbox(self.admin)['data'], [])  # PO is not an executor.
            self.assertEqual(self.inbox(self.project_owner)['data'], [])
        self.assertEqual(before, counts())

    def test_review_decision_progress_and_next_ready_are_human_owned(self):
        row = self.complete()
        self.assertEqual(self.inbox()['data'][0]['kind'], 'request_decision')
        row = self.act(row, 'request_decision', artifact_id=row['artifacts'][0]['id'])
        task = self.inbox(self.project_owner)['data'][0]
        self.assertEqual(task['kind'], 'finalize'); self.assertEqual(task['selected_artifact_id'], row['selected_artifact_id'])
        summary = stages.list_instances(self.session, self.a['id'], self.workspace_a.id, self.editor.id)['data'][0]
        self.assertEqual(summary['responsibility']['person']['account_id'], self.project_owner.id)
        self.act(row, 'finalize', actor=self.project_owner, artifact_id=row['selected_artifact_id'], reason='approved')
        task = self.inbox()['data'][0]; self.assertEqual(task['stage_id'], self.second['id'])
        self.assertEqual(self.get(self.second)['attempts'], [])
        summary = stages.list_instances(self.session, self.a['id'], self.workspace_a.id, self.editor.id)['data'][0]
        self.assertEqual((summary['completed_stages'], summary['total_stages']), (1, 2))
        self.assertEqual(summary['current_stage_id'], self.second['id'])
        self.finalize(self.complete(self.act(self.get(self.second), 'run')))
        self.assertEqual(self.inbox()['total'], 0)
        summary = stages.list_instances(self.session, self.a['id'], self.workspace_a.id, self.editor.id)['data'][0]
        self.assertEqual(summary['responsibility']['kind'], 'completed')

    def test_handoff_selected_version_readable_without_upstream_grants_or_drafts(self):
        row = self.complete(output={'answer': 'selected only'}); selected = row['artifacts'][0]
        row = self.act(row, 'edit_output', artifact_id=selected['id'], content={'answer': 'unselected private draft'}, reason='alternative')
        row = self.act(row, 'request_decision', artifact_id=selected['id'])
        self.act(row, 'finalize', actor=self.project_owner, artifact_id=selected['id'], reason='choose original')
        grants = agents.tables(self.session)[0]
        self.session.execute(grants.delete().where(grants.c.agent_id == self.agent_ids[0], grants.c.account_id == self.editor.id))
        with self.assertRaises(Forbidden): self.get()
        detail = self.get(self.second); handoff = detail['handoffs'][0]
        self.assertEqual(handoff['content'], 'selected only'); self.assertEqual(handoff['artifact_id'], selected['id'])
        self.assertEqual(handoff['digest'], selected['digest']); self.assertEqual(handoff['version'], 1)
        self.assertEqual(handoff['finalized_by'], self.project_owner.id); self.assertFalse(handoff['consumed'])
        self.assertNotIn('unselected private draft', str(detail)); self.assertEqual(detail['attempts'], [])
        detail = self.act(detail, 'run'); self.assertTrue(detail['handoffs'][0]['consumed'])
        self.assertEqual(self.inbox()['total'], 0)  # Running is status, not a new human task.

    def test_fresh_revocation_membership_and_source_invalidate_task_without_hiding_status(self):
        grants = agents.tables(self.session)[0]
        self.session.execute(grants.delete().where(grants.c.agent_id == self.agent_ids[0], grants.c.account_id == self.editor.id))
        self.assertEqual(self.inbox()['total'], 0)
        summary = stages.list_instances(self.session, self.a['id'], self.workspace_a.id, self.admin.id)['data'][0]
        self.assertTrue(summary['responsibility']['reason']); self.assertEqual(summary['stages'][0]['state'], 'ready')
        entity = stages.tables(self.session)[1]; row = self.get(actor=self.project_owner)
        binding = dict(row['binding'], finalizer=dict(row['binding']['finalizer'], membership_id=str(uuid4())))
        self.session.execute(entity.update().where(entity.c.id == self.first['id']).values(binding=binding, state='awaiting_decision'))
        self.assertEqual(self.inbox(self.project_owner)['total'], 0)
        binding = dict(binding, finalizer=row['binding']['finalizer'], decision_role='po')
        self.session.execute(entity.update().where(entity.c.id == self.first['id']).values(binding=binding))
        self.assertEqual(self.inbox(self.project_owner)['total'], 0)
        self.assign_po(self.project_owner); self.assertEqual(self.inbox(self.project_owner)['total'], 1)
        from models.workflow import Workflow
        self.session.get(Workflow, binding['workflow_id']).graph = '{}'; self.session.flush()
        self.assertEqual(self.inbox(self.project_owner)['total'], 0)

    def test_invalidated_intake_removes_actions_and_points_to_po(self):
        self.request(self.req, content='new revision')
        self.assertEqual(self.inbox()['total'], 0)
        summary = stages.list_instances(self.session, self.a['id'], self.workspace_a.id, self.editor.id)['data'][0]
        self.assertEqual(summary['responsibility']['kind'], 'po'); self.assertFalse(summary['intake_valid'])
        self.assertEqual(self.get()['actions'], [])

    def test_project_scope_pagination_and_minimal_metadata(self):
        for page in ('0', '-1', 'bad'):
            with self.assertRaises(BadRequest): self.inbox(page=page)
        self.assertEqual(self.inbox(page='2')['data'], []); self.assertEqual(self.inbox(page='2')['total'], 1)
        with self.assertRaises(NotFound):
            team_inbox.list_actions(self.session, self.b['id'], self.workspace_a.id, self.editor.id)
        data = team_inbox.list_actions(self.session, self.b['id'], self.workspace_b.id, self.other.id)
        self.assertEqual(data['data'], [])

    def test_invalid_inputs_can_be_corrected_but_not_executed(self):
        entity = stages.tables(self.session)[1]
        self.session.execute(entity.update().where(entity.c.id == self.first['id']).values(inputs={'request': 'x' * 3000}, dependencies=[]))
        detail = self.get()
        self.assertTrue(detail['input_error']); self.assertEqual(detail['actions'], ['feedback'])
        self.assertEqual(len(detail['editable_inputs']['request']), 3000)
        self.assertEqual(self.inbox()['data'][0]['kind'], 'feedback')
