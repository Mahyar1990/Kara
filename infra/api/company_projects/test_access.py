"""PostgreSQL checks: native memberships, authority and resource isolation."""
import unittest
from uuid import uuid4
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from app_factory import create_app
from company_projects import access, ownership, store
from extensions.ext_database import db
from models.account import Account, Tenant, TenantAccountJoin, TenantAccountRole
from models.model import App
from models.dataset import Dataset
from services.account_service import TenantService
from services.enterprise.rbac_service import RBACService
from services.dataset_service import DatasetService
from models.skill import Skill
from services.skill_management_service import SkillManagementService, SkillManagementServiceError
from company_projects.controller import visible_app


class ProjectAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.app = create_app()

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.connection = db.engine.connect()
        self.addCleanup(self.connection.close)
        self.transaction = self.connection.begin()
        self.addCleanup(lambda: self.transaction.rollback() if self.transaction.is_active else None)
        self.session = Session(bind=self.connection, join_transaction_mode='create_savepoint')
        self.addCleanup(self.session.close)
        self.initial_tenant_count = self.session.scalar(sa.select(sa.func.count()).select_from(Tenant))
        self.root = Tenant(name='Synthetic product')
        self.workspace_a = Tenant(name='Synthetic project A')
        self.workspace_b = Tenant(name='Synthetic project B')
        self.product_owner, self.project_owner, self.editor, self.admin, self.other = [
            Account(name=name, email=f'{uuid4()}@example.test') for name in ('product', 'owner', 'editor', 'admin', 'other')]
        self.session.add_all([self.root, self.workspace_a, self.workspace_b, self.product_owner, self.project_owner, self.editor, self.admin, self.other])
        self.session.flush()
        self.session.execute(store.product.update().where(store.product.c.id == 1).values(
            tenant_id=self.root.id, account_id=self.product_owner.id))
        for tenant, account, role in [(self.root, self.product_owner, 'owner'),
                (self.workspace_a, self.project_owner, 'owner'), (self.workspace_a, self.product_owner, 'admin'),
                (self.workspace_a, self.editor, 'editor'), (self.workspace_a, self.admin, 'admin'),
                (self.workspace_b, self.other, 'owner'), (self.workspace_b, self.product_owner, 'admin')]:
            self.session.add(TenantAccountJoin(tenant_id=tenant.id, account_id=account.id, role=TenantAccountRole(role)))
        self.session.flush()
        self.a = store.create_project(self.session.connection(), self.root.id, self.product_owner.id, str(uuid4()))
        self.b = store.create_project(self.session.connection(), self.root.id, self.product_owner.id, str(uuid4()))
        self.session.execute(store.workspaces.insert(), [dict(project_id=self.a['id'], workspace_id=self.workspace_a.id),
            dict(project_id=self.b['id'], workspace_id=self.workspace_b.id)])

    def test_only_product_owner_can_create_or_assign_owner(self):
        access.require_product_owner(self.session, self.product_owner.id)
        for actor in [self.project_owner, self.admin, self.editor, self.other]:
            with self.subTest(actor=actor.name), self.assertRaises(Forbidden):
                ownership.create_project(self.session, actor.id, 'forbidden', '', actor.id)
            with self.assertRaises(Forbidden):
                ownership.set_owner(self.session, self.a['id'], actor.id, self.editor.id)

    def test_catalog_and_direct_project_ids_are_scoped(self):
        self.assertEqual(len(access.list_for_account(self.session, self.product_owner.id)), 2)
        self.assertEqual([p['id'] for p in access.list_for_account(self.session, self.editor.id)], [self.a['id']])
        with self.assertRaises(NotFound):
            access.project_for_account(self.session, self.b['id'], self.editor.id)
        with self.assertRaises(Forbidden):
            access.validate_app_project(self.session, self.workspace_b.id, self.a['id'], self.editor.id)

    def test_project_owner_manages_only_their_members(self):
        TenantService.check_member_permission(self.workspace_a, self.project_owner, self.editor, 'add', session=self.session)
        for actor in [self.admin, self.editor, self.other]:
            with self.subTest(actor=actor.name), self.assertRaises(Forbidden):
                TenantService.check_member_permission(self.workspace_a, actor, self.editor, 'remove', session=self.session)
        with self.assertRaises(Forbidden):
            RBACService.MemberRoles.replace(self.workspace_a.id, self.admin.id, self.editor.id, ['admin'], session=self.session)

    def test_owners_are_protected_and_cannot_transfer_product_authority(self):
        for target in [self.product_owner, self.project_owner]:
            with self.assertRaises(Forbidden):
                access.require_member_management(self.session, self.workspace_a.id, self.project_owner.id, target.id, 'remove')
        with self.assertRaises(Forbidden):
            TenantService.update_member_role(self.workspace_a, self.editor, 'owner', self.project_owner, session=self.session)
        ownership.set_owner(self.session, self.a['id'], self.product_owner.id, self.editor.id)
        self.assertEqual(access.owner_of(self.session, self.workspace_a.id).id, self.editor.id)
        self.assertEqual(access.membership(self.session, self.workspace_a.id, self.project_owner.id).role, 'editor')
        self.assertTrue(access.is_product_owner(self.session, self.product_owner.id))

    def test_editor_keeps_agent_knowledge_and_skill_permissions_without_membership_management(self):
        keys = RBACService.MyPermissions.get(self.workspace_a.id, self.editor.id, session=self.session).workspace.permission_keys
        for key in ['app.create_and_management', 'agent.create', 'dataset.create_and_management', 'skill.edit']:
            self.assertIn(key, keys)
        admin_keys = RBACService.MyPermissions.get(self.workspace_a.id, self.admin.id, session=self.session).workspace.permission_keys
        self.assertNotIn('workspace.member.manage', admin_keys)
        self.assertNotIn('workspace.role.manage', admin_keys)

    def test_atomic_creation_rolls_back_native_internal_commits(self):
        # The real native provisioning path commits internally, inside the test savepoint.
        before = self.session.scalar(sa.select(sa.func.count()).select_from(Tenant))
        with patch('services.account_service.generate_key_pair', return_value='Synthetic public key'):
            row = ownership.create_project(self.session, self.product_owner.id, str(uuid4()), '', self.project_owner.id)
        self.assertIsNotNone(row['workspace_id'])
        self.assertEqual(access.owner_of(self.session, row['workspace_id']).id, self.project_owner.id)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(Tenant)), before + 1)
        self.session.close()
        self.transaction.rollback()
        with db.engine.connect() as connection:
            self.assertEqual(connection.scalar(sa.select(sa.func.count()).select_from(Tenant)), self.initial_tenant_count)
        # Even native internal commits were rolled back; no orphan workspace remains.

    def test_reassigning_owner_to_self_remains_single_owner(self):
        ownership.set_owner(self.session, self.a['id'], self.product_owner.id, self.project_owner.id)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(TenantAccountJoin).where(
            TenantAccountJoin.tenant_id == self.workspace_a.id, TenantAccountJoin.role == 'owner')), 1)

    def test_direct_ids_cannot_read_another_projects_app_dataset_or_skill(self):
        app = App(tenant_id=self.workspace_b.id, name='Synthetic app', mode='workflow', status='normal', created_by=self.other.id,
            enable_site=False, enable_api=False, max_active_requests=0)
        dataset = Dataset(tenant_id=self.workspace_b.id, name='Synthetic knowledge', created_by=self.other.id)
        skill = Skill(tenant_id=self.workspace_b.id, name='synthetic-skill', display_name='Synthetic skill')
        self.session.add_all([app, dataset, skill])
        self.session.flush()
        with self.assertRaises(NotFound):
            visible_app(self.session, self.workspace_a.id, self.editor.id, app.id)
        self.assertIsNone(DatasetService.get_dataset_for_tenant(dataset.id, self.workspace_a.id, session=self.session))
        with self.assertRaises(SkillManagementServiceError) as caught:
            SkillManagementService(session=self.session).get_skill(tenant_id=self.workspace_a.id, skill_id=skill.id)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertIsNotNone(DatasetService.get_dataset_for_tenant(dataset.id, self.workspace_b.id, session=self.session))


if __name__ == '__main__':
    unittest.main()
