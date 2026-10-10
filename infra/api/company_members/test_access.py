"""Integration checks in the API image; synthetic records always roll back."""
import unittest
from uuid import uuid4

from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from app_factory import create_app
from configs import dify_config
from extensions.ext_database import db
from models.account import Account, Tenant, TenantAccountJoin, TenantAccountRole
from services.enterprise.rbac_service import RBACService


class MemberRoleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.app = create_app()

    def setUp(self):
        if dify_config.RBAC_ENABLED:
            self.skipTest('Community compatibility endpoint requires RBAC disabled')
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.connection = db.engine.connect()
        self.addCleanup(self.connection.close)
        self.transaction = self.connection.begin()
        self.addCleanup(self.transaction.rollback)
        self.session = Session(bind=self.connection, join_transaction_mode='create_savepoint')
        self.addCleanup(self.session.close)
        self.tenant = Tenant(name='Member management test')
        self.other = Tenant(name='Other workspace test')
        self.owner = self.account('owner')
        self.admin = self.account('admin')
        self.editor = self.account('editor')
        self.normal = self.account('normal')
        self.outsider = self.account('outsider')
        self.session.add_all([self.tenant, self.other, self.owner, self.admin, self.editor, self.normal, self.outsider])
        self.session.flush()
        for account, role in [(self.owner, 'owner'), (self.admin, 'admin'), (self.editor, 'editor'), (self.normal, 'normal')]:
            self.session.add(TenantAccountJoin(tenant_id=self.tenant.id, account_id=account.id, role=TenantAccountRole(role)))
        self.session.add(TenantAccountJoin(tenant_id=self.other.id, account_id=self.outsider.id))
        self.session.flush()

    def account(self, name):
        return Account(name=name, email=f'{uuid4()}@example.test')

    def change(self, actor, target, roles):
        return RBACService.MemberRoles.replace(self.tenant.id, actor.id, target.id, roles, session=self.session)

    def test_owner_can_update_role_without_changing_identity(self):
        response = self.change(self.owner, self.normal, ['editor'])
        self.assertEqual(response.account_id, self.normal.id)
        self.assertEqual([role.id for role in response.roles], ['editor'])
        self.session.expire_all()
        self.assertEqual(self.session.get(TenantAccountJoin, self.session.query(TenantAccountJoin.id).filter_by(
            tenant_id=self.tenant.id, account_id=self.normal.id).scalar()).role, 'editor')

    def test_non_managers_cannot_change_roles(self):
        for actor in [self.normal, self.editor, self.outsider]:
            with self.subTest(actor=actor.name), self.assertRaises(Forbidden):
                self.change(actor, self.admin, ['normal'])

    def test_cross_workspace_target_rejected(self):
        with self.assertRaises(NotFound):
            self.change(self.owner, self.outsider, ['editor'])

    def test_self_and_owner_changes_rejected(self):
        with self.assertRaises(BadRequest):
            self.change(self.admin, self.admin, ['normal'])
        with self.assertRaises(Forbidden):
            self.change(self.admin, self.owner, ['normal'])
        with self.assertRaises(BadRequest):
            self.change(self.owner, self.admin, ['owner'])

    def test_invalid_or_multiple_roles_rejected(self):
        for roles in [[], ['invalid'], ['editor', 'admin']]:
            with self.subTest(roles=roles), self.assertRaises(BadRequest):
                self.change(self.owner, self.normal, roles)


if __name__ == '__main__':
    unittest.main()
