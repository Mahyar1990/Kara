"""Migration tests retain IDs/history and abort unsupported dependencies."""
from unittest.mock import patch
import sqlalchemy as sa

from company_projects import access, store
from company_projects.migrate_legacy import migrate
from company_projects.test_access import ProjectDatabaseFixture
from models.model import App
from models.dataset import Dataset
from models.account import Tenant


class LegacyMigrationTests(ProjectDatabaseFixture):
    def setUp(self):
        super().setUp()
        self.session.execute(store.workspaces.delete().where(store.workspaces.c.project_id.in_([self.a['id'], self.b['id']])))
        self.assigned = App(tenant_id=self.root.id, name='Assigned synthetic app', mode='workflow', status='normal',
            created_by=self.product_owner.id, enable_site=False, enable_api=False, max_active_requests=0)
        self.unassigned = App(tenant_id=self.root.id, name='Unassigned synthetic app', mode='workflow', status='normal',
            created_by=self.product_owner.id, enable_site=False, enable_api=False, max_active_requests=0)
        self.session.add_all([self.assigned, self.unassigned])
        self.session.flush()
        store.assign(self.session.connection(), self.root.id, self.a['id'], self.assigned.id)

    def test_legacy_migration_preserves_app_ids_and_original_runtime_workspace(self):
        assigned_id, unassigned_id = self.assigned.id, self.unassigned.id
        root_id = self.root.id
        with patch('services.account_service.generate_key_pair', return_value='Synthetic public key'):
            result = migrate(self.session, copy_models=False)
        self.session.expire_all()
        central_id = str(access.authority(self.session)['tenant_id'])
        self.assertNotEqual(central_id, root_id)
        self.assertEqual(self.session.get(App, unassigned_id).tenant_id, root_id)
        project = access.project_for_account(self.session, self.a['id'], self.product_owner.id)
        self.assertEqual(self.session.get(App, assigned_id).tenant_id, project['workspace_id'])
        self.assertEqual(result['result'], 'migrated')
        self.assertEqual(migrate(self.session, copy_models=False)['result'], 'already_migrated')
        self.assertEqual(len(access.list_for_account(self.session, self.product_owner.id)), 3)

    def test_shared_dependencies_abort_before_new_workspaces(self):
        dataset = Dataset(tenant_id=self.root.id, name='Shared synthetic knowledge', created_by=self.product_owner.id)
        self.session.add(dataset); self.session.flush()
        count = self.session.scalar(sa.select(sa.func.count()).select_from(Tenant))
        with self.assertRaisesRegex(RuntimeError, 'Shared dependency datasets'):
            migrate(self.session, copy_models=False)
        self.assertEqual(self.session.get(App, self.assigned.id).tenant_id, self.root.id)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(Tenant)), count)
