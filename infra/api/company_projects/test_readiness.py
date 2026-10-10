"""Readiness cannot borrow another project's or another caller's evidence."""
from uuid import uuid4
from werkzeug.exceptions import Forbidden, NotFound
from company_projects.test_access import ProjectDatabaseFixture
from company_projects.readiness import snapshot
from models.model import App
from models.workflow import WorkflowRun


class ReadinessTests(ProjectDatabaseFixture):
    def test_successful_trial_is_scoped_to_project_and_caller(self):
        app = App(tenant_id=self.workspace_a.id, name='Synthetic app', mode='workflow', status='normal',
            created_by=self.editor.id, enable_site=False, enable_api=False, max_active_requests=0)
        self.session.add(app); self.session.flush()
        self.session.add(WorkflowRun(tenant_id=self.workspace_a.id, app_id=app.id, workflow_id=str(uuid4()),
            type='workflow', triggered_from='debugging', version='draft', status='succeeded',
            created_by_role='account', created_by=self.project_owner.id))
        self.session.flush()
        result = snapshot(self.session, self.a['id'], self.workspace_a.id, self.editor)
        self.assertEqual(result['apps'], 1)
        self.assertFalse(next(step for step in result['steps'] if step['id'] == 'test')['complete'])
        owner = snapshot(self.session, self.a['id'], self.workspace_a.id, self.project_owner)
        self.assertTrue(next(step for step in owner['steps'] if step['id'] == 'test')['complete'])
        self.assertIsNone(result['model_name'])
        self.assertFalse(next(step for step in result['steps'] if step['id'] == 'publish')['complete'])

    def test_active_workspace_and_membership_are_required(self):
        with self.assertRaises(Forbidden):
            snapshot(self.session, self.a['id'], self.workspace_b.id, self.editor)
        with self.assertRaises(NotFound):
            snapshot(self.session, self.b['id'], self.workspace_b.id, self.editor)
