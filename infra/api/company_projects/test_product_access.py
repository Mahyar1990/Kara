"""Product authority remains independent of project technical roles."""
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from repositories.account_activation_repository import SQLAlchemyAccountActivationRepository
from services.entities.account_activation_entities import AccountInvitation
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from company_members.product import available_roles, validate_role
from company_projects import access, ownership, store
from company_projects.test_access import ProjectDatabaseFixture
from models.account import TenantAccountJoin
from services.account_service import RegisterService, TenantService
from services.enterprise.rbac_service import RBACService


class ProductAccessTests(ProjectDatabaseFixture):
    def central_member(self, account, role):
        join = TenantAccountJoin(tenant_id=self.root.id, account_id=account.id, role=role)
        self.session.add(join)
        self.session.flush()
        return join

    def test_only_explicit_product_admin_can_create_project(self):
        self.central_member(self.admin, 'admin')
        self.central_member(self.editor, 'normal')
        self.assertTrue(access.is_product_admin(self.session, self.admin.id))
        self.assertFalse(access.is_product_owner(self.session, self.admin.id))
        for account in (self.editor, self.project_owner, self.other):
            with self.assertRaises(Forbidden):
                ownership.create_project(self.session, account.id, 'denied', '', account.id)
        with patch('services.account_service.generate_key_pair', return_value='Synthetic public key'):
            row = ownership.create_project(self.session, self.admin.id, str(uuid4()), '', self.editor.id)
        self.assertEqual(access.owner_of(self.session, row['workspace_id']).id, self.editor.id)
        self.assertEqual(access.membership(self.session, row['workspace_id'], self.admin.id).role, 'admin')
        with self.assertRaises(NotFound):
            access.project_for_account(self.session, self.b['id'], self.admin.id)

    def test_product_role_change_preserves_project_role_and_demotion_revokes_creation(self):
        self.central_member(self.admin, 'normal')
        RBACService.MemberRoles.replace(self.root.id, self.product_owner.id, self.admin.id, ['admin'], session=self.session)
        self.assertTrue(access.is_product_admin(self.session, self.admin.id))
        self.assertEqual(access.membership(self.session, self.workspace_a.id, self.admin.id).role, 'admin')
        RBACService.MemberRoles.replace(self.root.id, self.product_owner.id, self.admin.id, ['normal'], session=self.session)
        self.assertFalse(access.is_product_admin(self.session, self.admin.id))
        self.assertEqual(access.membership(self.session, self.workspace_a.id, self.admin.id).role, 'admin')
        with self.assertRaises(Forbidden):
            access.require_product_admin(self.session, self.admin.id)

    def test_project_role_change_does_not_grant_product_authority(self):
        self.central_member(self.editor, 'normal')
        TenantService.update_member_role(self.workspace_a, self.editor, 'admin', self.project_owner, session=self.session)
        self.assertFalse(access.is_product_admin(self.session, self.editor.id))
        self.assertEqual(access.membership(self.session, self.root.id, self.editor.id).role, 'normal')

    def test_product_rejects_project_roles_for_invites_and_both_update_routes(self):
        self.central_member(self.editor, 'normal')
        self.assertEqual(available_roles(self.session, self.root.id), ('admin', 'normal'))
        self.assertIn('editor', available_roles(self.session, self.workspace_a.id))
        for role in ('editor', 'dataset_operator', 'owner', 'invalid'):
            with self.subTest(role=role):
                with self.assertRaises(BadRequest):
                    RegisterService.invite_new_member(self.root, 'synthetic@example.test', 'fa-IR', role,
                        self.product_owner, session=self.session)
                with self.assertRaises((BadRequest, Forbidden)):
                    TenantService.update_member_role(self.root, self.editor, role, self.product_owner, session=self.session)
                with self.assertRaises(BadRequest):
                    RBACService.MemberRoles.replace(self.root.id, self.product_owner.id, self.editor.id, [role], session=self.session)
        for role in ('admin', 'normal'):
            validate_role(self.session, self.root.id, role)

    def test_product_admin_manages_central_users_without_project_member_authority(self):
        self.central_member(self.other, 'admin')
        self.central_member(self.editor, 'normal')
        TenantService.check_member_permission(self.root, self.other, self.editor, 'update', session=self.session)
        with self.assertRaises(Forbidden):
            TenantService.check_member_permission(self.workspace_a, self.other, self.editor, 'update', session=self.session)
        for target in (self.product_owner,):
            with self.assertRaises(Forbidden):
                access.require_member_management(self.session, self.root.id, self.other.id, target.id, 'remove')
        with self.assertRaises(Forbidden):
            access.require_member_management(self.session, self.root.id, self.editor.id, self.other.id, 'update')

    def test_legacy_central_roles_migrate_once_without_affecting_projects(self):
        self.session.execute(store.product_access_schema.delete())
        self.central_member(self.admin, 'admin')
        self.central_member(self.editor, 'editor')
        access.initialize(self.session.connection())
        self.session.expire_all()
        self.assertEqual(access.membership(self.session, self.root.id, self.admin.id).role, 'normal')
        self.assertEqual(access.membership(self.session, self.root.id, self.editor.id).role, 'normal')
        self.assertEqual(access.membership(self.session, self.workspace_a.id, self.admin.id).role, 'admin')
        self.assertEqual(access.membership(self.session, self.workspace_a.id, self.editor.id).role, 'editor')
        self.assertTrue(access.is_product_admin(self.session, self.product_owner.id))
        access.membership(self.session, self.root.id, self.admin.id).role = 'admin'
        self.session.flush()
        access.initialize(self.session.connection())
        self.assertTrue(access.is_product_admin(self.session, self.admin.id))

    def test_central_invitation_stores_role_for_existing_active_account_without_email(self):
        with patch('libs.workspace_permission.check_workspace_member_invite_permission'), \
                patch.object(RegisterService, 'generate_invite_token', return_value='synthetic-token'), \
                patch('services.account_service.send_invite_member_mail_task.delay'):
            for account, role in ((self.editor, 'admin'), (self.other, 'normal')):
                RegisterService.invite_new_member(self.root, account.email, 'fa-IR', role,
                    self.product_owner, session=self.session)
                self.assertEqual(access.membership(self.session, self.root.id, account.id).role, role)
        self.assertEqual(access.membership(self.session, self.workspace_a.id, self.editor.id).role, 'editor')

    def test_old_activation_token_cannot_restore_or_upgrade_product_role(self):
        repository = SQLAlchemyAccountActivationRepository(sessionmaker(bind=self.connection,
            join_transaction_mode='create_savepoint'))
        invitation = AccountInvitation(account_id=self.editor.id, account_email=self.editor.email,
            account_status='active', workspace_id=self.root.id, workspace_name=self.root.name,
            role='admin', requires_setup=False)
        self.assertIsNone(repository.activate(invitation, role='admin', setup=None))
        self.assertIsNone(access.membership(self.session, self.root.id, self.editor.id))
        self.central_member(self.editor, 'normal')
        self.assertIsNotNone(repository.activate(invitation, role='admin', setup=None))
        self.session.expire_all()
        self.assertEqual(access.membership(self.session, self.root.id, self.editor.id).role, 'normal')
