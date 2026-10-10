"""Native DB tests for automation provenance, inactive creation and isolation."""
import json
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects.test_access import ProjectDatabaseFixture
from company_projects import automations, store
from models.account import Account, TenantAccountJoin
from models.model import App
from models.trigger import AppTrigger, WorkflowSchedulePlan
from models.workflow import Workflow


class AutomationTests(ProjectDatabaseFixture):
    def setUp(self):
        super().setUp()
        self.editor.interface_language = 'fa-IR'
        self.editor.set_tenant_id_with_session(self.workspace_a.id, session=self.session)
        self.source = App(tenant_id=self.workspace_a.id, name='Synthetic source', mode='workflow', status='normal',
            created_by=self.editor.id, maintainer=self.editor.id, enable_site=False, enable_api=False, max_active_requests=0)
        self.session.add(self.source); self.session.flush()
        self.graph = dict(nodes=[dict(id='start', type='custom', position=dict(x=0, y=0), data=dict(type='start', title='شروع', variables=[
            dict(variable='request', type='paragraph', label='درخواست', required=True, max_length=1000)])),
            dict(id='end', type='custom', position=dict(x=300, y=0), data=dict(type='end', title='نتیجه', outputs=[
                dict(variable='result', value_selector=['start', 'request'])]))],
            edges=[dict(id='start-end', source='start', target='end', sourceHandle='source', targetHandle='target', type='custom',
                data=dict(sourceType='start', targetType='end', isInIteration=False, isInLoop=False))])
        self.published = Workflow.new(tenant_id=self.workspace_a.id, app_id=self.source.id, type='workflow', version='synthetic-v1',
            graph=json.dumps(self.graph), features='{}', created_by=self.editor.id, environment_variables=[], conversation_variables=[], rag_pipeline_variables=[])
        self.session.add(self.published); self.session.flush()
        self.source.workflow_id = self.published.id
        self.session.flush()
        self.data = dict(name='Synthetic automation', source_app_id=self.source.id, source_workflow_id=self.published.id,
            schedule=dict(frequency='weekly', time='09:00', weekdays=['sat']), inputs=dict(request='Synthetic data'))

    def test_native_import_uses_published_snapshot_and_keeps_creation_inactive(self):
        result = automations.create_automation(self.session, self.a['id'], self.workspace_a.id, self.editor, self.data)
        self.assertEqual(result['status'], 'disabled'); self.assertFalse(result['published'])
        self.assertIsNone(result['next_run_at']); self.assertNotEqual(result['app_id'], self.source.id)
        copy = self.session.get(App, result['app_id'])
        self.assertEqual(copy.tenant_id, self.workspace_a.id)
        self.assertFalse(copy.enable_api); self.assertFalse(copy.enable_site)
        draft = self.session.scalar(sa.select(Workflow).where(Workflow.app_id == copy.id, Workflow.version == 'draft'))
        self.assertEqual(draft.graph_dict['nodes'][0]['data']['type'], 'code')
        self.assertEqual(draft.graph_dict['nodes'][-1]['data']['timezone'], 'Asia/Tehran')
        self.assertEqual(self.published.graph_dict['nodes'][0]['data']['type'], 'start')
        self.assertEqual(self.session.scalar(sa.select(store.automations.c.source_workflow_id).where(
            store.automations.c.app_id == copy.id)), self.published.id)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(WorkflowSchedulePlan).where(
            WorkflowSchedulePlan.app_id == copy.id)), 0)

    def test_wrong_project_source_and_stale_version_create_nothing(self):
        count = self.session.scalar(sa.select(sa.func.count()).select_from(App))
        with self.assertRaises(NotFound):
            automations.create_automation(self.session, self.b['id'], self.workspace_a.id, self.editor, self.data)
        with self.assertRaises(Forbidden):
            automations.create_automation(self.session, self.b['id'], self.workspace_a.id, self.product_owner, self.data)
        with self.assertRaises(Conflict):
            automations.create_automation(self.session, self.a['id'], self.workspace_a.id, self.editor,
                {**self.data, 'source_workflow_id': str(uuid4())})
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(App)), count)

    def test_activation_requires_review_and_readers_cannot_control(self):
        reader = Account(name='Synthetic reader', email=f'{uuid4()}@example.test')
        self.session.add(reader); self.session.flush()
        self.session.add(TenantAccountJoin(tenant_id=self.workspace_a.id, account_id=reader.id, role='normal'))
        trigger = AppTrigger(tenant_id=self.workspace_a.id, app_id=self.source.id, node_id='start',
            trigger_type='trigger-schedule', title='Synthetic', status='disabled')
        self.session.add(trigger); self.session.flush()
        with self.assertRaises(BadRequest):
            automations.set_enabled(self.session, self.a['id'], self.workspace_a.id, self.editor, trigger.id, dict(enabled=True))
        with self.assertRaises(Forbidden):
            automations.set_enabled(self.session, self.a['id'], self.workspace_a.id, reader, trigger.id, dict(enabled=False))
        with self.assertRaises(NotFound):
            automations.scoped_trigger(self.session, self.b['id'], self.workspace_b.id, self.other, trigger.id)

    def test_reenable_advances_overdue_schedule_and_summary_does_not_expose_payload(self):
        self.published.graph = json.dumps(dict(nodes=[dict(id='schedule', data=dict(type='trigger-schedule'))], edges=[]))
        trigger = AppTrigger(tenant_id=self.workspace_a.id, app_id=self.source.id, node_id='schedule',
            trigger_type='trigger-schedule', title='Synthetic', status='disabled')
        plan = WorkflowSchedulePlan(tenant_id=self.workspace_a.id, app_id=self.source.id, node_id='schedule',
            cron_expression='0 9 * * 6', timezone='Asia/Tehran', next_run_at=datetime(2020, 1, 1))
        self.session.add_all([trigger, plan]); self.session.flush()
        result = automations.set_enabled(self.session, self.a['id'], self.workspace_a.id, self.editor, trigger.id, dict(enabled=True, reviewed=True))
        self.assertEqual(result['status'], 'enabled')
        self.assertGreater(plan.next_run_at.replace(tzinfo=timezone.utc), datetime.now(timezone.utc))
        self.assertFalse({'inputs', 'outputs', 'credentials', 'error', 'webhook_url'} & set(result))
        stopped = automations.set_enabled(self.session, self.a['id'], self.workspace_a.id, self.editor, trigger.id, dict(enabled=False))
        self.assertIsNone(stopped['next_run_at'])

    def test_activation_publishes_native_snapshot_and_creates_native_schedule(self):
        result = automations.create_automation(self.session, self.a['id'], self.workspace_a.id, self.editor, self.data)
        def reconcile(app, **kwargs):
            config = automations.ScheduleService.extract_schedule_config(kwargs['published_workflow'])
            automations.ScheduleService.create_schedule(self.workspace_a.id, app.id, config, session=self.session)
        # Keep native signal writes inside the synthetic rollback transaction.
        with patch('services.workflow_service.app_published_workflow_was_updated.send', side_effect=reconcile):
            active = automations.set_enabled(self.session, self.a['id'], self.workspace_a.id, self.editor,
                result['id'], dict(enabled=True, reviewed=True))
        self.assertTrue(active['published']); self.assertEqual(active['status'], 'enabled')
        self.assertIsNotNone(active['next_run_at'])
        self.assertEqual(self.source.workflow_id, self.published.id)
        self.assertIsNotNone(self.session.get(App, result['app_id']).workflow_id)

    def test_project_member_role_and_resource_rbac_both_gate_controls(self):
        with patch.object(automations.dify_config, 'RBAC_ENABLED', True), patch.object(
                automations.RBACService.CheckAccess, 'check', return_value=False):
            self.assertFalse(automations.allowed(self.session, self.workspace_a.id, self.editor, self.source.id,
                automations.RBACPermission.APP_EDIT))
            with self.assertRaises(Forbidden):
                automations.require_permission(self.session, self.workspace_a.id, self.editor, self.source.id,
                    automations.RBACPermission.APP_EDIT)
