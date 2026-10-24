"""Small persisted regression set for offline Jira/Workflow intake."""
import json
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import agents, jira_intake, requests
from company_projects.test_requests import RequestFixture
from models.model import App
from models.workflow import WorkflowRun


class JiraIntakeTests(RequestFixture):
    def response(self, **fields):
        values = dict(summary='Synthetic access request', description='Original requirement',
            updated='2026-10-24T12:00:00+03:30', status={'name': 'Open'})
        values.update(fields)
        return dict(startAt=0, maxResults=1, total=720,
            issues=[dict(id='12345', key='SYN-1', fields=values)])

    def ingest(self, response=None, actor=None, key=None, **data):
        data.setdefault('base_url', 'https://jira.example.test/')
        if 'run_id' not in data:
            data['response'] = response if response is not None else self.response()
        return jira_intake.import_response(self.session, self.a['id'], self.workspace_a.id,
            (actor or self.project_owner).id, data, key or str(uuid4()))

    def detail(self, result):
        return requests.get_request(self.session, self.a['id'], self.workspace_a.id,
            self.project_owner.id, result['data'][0]['request_id'])

    def test_dedup_metadata_and_content_versions_preserve_human_history(self):
        key = str(uuid4())
        created = self.ingest(key=key)
        self.assertEqual(created['data'][0]['outcome'], 'created')
        self.assertTrue(created['has_more'])
        self.assertEqual(self.ingest(key=key), created)
        self.assertEqual(self.ingest()['data'][0]['outcome'], 'unchanged')
        row = self.detail(created)
        self.assertEqual(row['current']['origin'], 'jira')
        self.assertEqual(row['jira']['base_url'], 'https://jira.example.test')
        approved = self.decision(row)
        changed_status = self.response(status={'name': 'Working'}, updated='2026-10-24T13:00:00+03:30')
        self.assertEqual(self.ingest(changed_status)['data'][0]['outcome'], 'metadata_updated')
        row = self.detail(created)
        self.assertEqual(row['current_decision_id'], approved['current_decision_id'])
        self.assertEqual(row['version'], 1)
        changed_text = self.response(description='New requirement', updated='2026-10-24T14:00:00+03:30')
        self.assertEqual(self.ingest(changed_text)['data'][0]['outcome'], 'updated')
        row = self.detail(created)
        self.assertEqual(row['version'], 2)
        self.assertIsNone(row['current_decision_id'])
        self.assertEqual(len(row['decisions']), 1)
        self.assertEqual(row['revisions'][-1]['content'], 'Original requirement')
        self.assertEqual(self.ingest()['data'][0]['outcome'], 'older_ignored')
        with self.assertRaises(Conflict):
            self.ingest(changed_text, key=key)

    def test_manual_edits_are_not_overwritten_and_input_is_validated_before_writes(self):
        created = self.ingest()
        row = self.detail(created)
        self.request(row, actor=self.project_owner, title=row['title'], content='Human refinement')
        self.assertEqual(self.ingest()['data'][0]['outcome'], 'unchanged')
        self.assertFalse(self.detail(created)['jira']['needs_review'])
        update = self.response(description='Changed at source', updated='2026-10-24T13:00:00+03:30')
        self.assertEqual(self.ingest(update)['data'][0]['outcome'], 'needs_review')
        row = self.detail(created)
        self.assertEqual(row['current']['content'], 'Human refinement')
        self.assertTrue(row['jira']['needs_review'])
        self.assertEqual(row['jira']['source_content'], 'Changed at source')
        self.assertEqual(row['version'], 2)
        partial = self.response()
        del partial['issues'][0]['fields']['description']
        for response in ({'errorMessages': ['failure']}, partial, self.response(updated='bad'),
                dict(self.response(), issues=[*self.response()['issues'], *self.response()['issues']]),
                dict(self.response(), received_count=2)):
            with self.subTest(response=response), self.assertRaises(BadRequest):
                self.ingest(response)
        with self.assertRaises(BadRequest):
            self.ingest(base_url='https://user:password@jira.example.test')
        with self.assertRaises(Forbidden):
            self.ingest(actor=self.editor)
        with self.assertRaises((Forbidden, NotFound)):
            jira_intake.import_response(self.session, self.a['id'], self.workspace_b.id, self.other.id,
                dict(base_url='https://jira.example.test', response=self.response()), str(uuid4()))
        empty_description = self.response(description=None)
        empty_description['issues'][0]['id'] = '12346'
        empty_description['issues'][0]['key'] = 'SYN-2'
        row = self.detail(self.ingest(empty_description))
        self.assertEqual(row['current']['content'], '')
        self.assertIsNone(row['jira']['source_content'])

    def test_workflow_import_uses_own_successful_unmanaged_run_in_same_project(self):
        app = App(tenant_id=self.workspace_a.id, name='Synthetic Jira reader', mode='workflow',
            icon_type='emoji', icon='X', icon_background='#fff', description='', enable_site=False, enable_api=False,
            status='normal', created_by=self.project_owner.id, max_active_requests=0)
        self.session.add(app); self.session.flush()
        run = WorkflowRun(tenant_id=self.workspace_a.id, app_id=app.id, workflow_id=str(uuid4()),
            type='workflow', triggered_from='debugging', version='draft', status='succeeded',
            created_by_role='account', created_by=self.project_owner.id, outputs=json.dumps(self.response()))
        self.session.add(run); self.session.flush()
        runs = jira_intake.recent_runs(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id)['data']
        self.assertEqual([value['id'] for value in runs], [run.id])
        result = self.ingest(run_id=run.id)
        self.assertEqual(self.detail(result)['jira']['last_run_id'], run.id)
        with self.assertRaises(NotFound):
            self.ingest(run_id=run.id, actor=self.admin)
        run.status = 'failed'; self.session.flush()
        with self.assertRaises(NotFound):
            self.ingest(run_id=run.id)
        managed = agents.definitions(self.session)
        run.status = 'succeeded'
        run.app_id = self.session.scalar(sa.select(managed.c.app_id).where(managed.c.id == self.agent_ids[0]))
        self.session.flush()
        with self.assertRaises(NotFound):
            self.ingest(run_id=run.id)
