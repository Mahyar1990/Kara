"""Two focused checks; all synthetic memberships roll back."""
from unittest.mock import patch
from uuid import uuid4

from werkzeug.exceptions import BadRequest, Forbidden
from company_projects import access, members
from company_projects.test_access import ProjectDatabaseFixture
from models.account import Account, AccountStatus, TenantAccountJoin
from services.account_service import RegisterService


class DirectProjectMemberTests(ProjectDatabaseFixture):
    def central(self, account):
        self.session.add(TenantAccountJoin(tenant_id=self.root.id, account_id=account.id, role='normal'))
        self.session.flush()

    def test_existing_kara_user_is_added_immediately_without_invitation(self):
        self.central(self.other)
        self.central(self.editor)
        choices = members.candidates(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id)
        self.assertEqual([user['id'] for user in choices['data']], [self.other.id])
        with patch.object(RegisterService, 'generate_invite_token') as token, \
                patch('services.account_service.send_invite_member_mail_task.delay') as email:
            result = members.add(self.session, self.a['id'], self.workspace_a.id,
                self.project_owner.id, self.other.id, 'editor')
            self.assertEqual(result['role'], 'editor')
            self.assertNotIn('url', result)
            self.assertEqual(self.other.status, AccountStatus.ACTIVE)
            self.assertEqual(access.membership(self.session, self.workspace_a.id, self.other.id).role, 'editor')
            repeated = members.add(self.session, self.a['id'], self.workspace_a.id,
                self.project_owner.id, self.other.id, 'admin')
            self.assertEqual(repeated['role'], 'editor')
            token.assert_not_called()
            email.assert_not_called()
        self.assertEqual(access.membership(self.session, self.workspace_b.id, self.other.id).role, 'owner')

    def test_unknown_pending_or_unauthorized_additions_and_project_email_invites_are_rejected(self):
        pending = Account(name='Synthetic pending', email=f'{uuid4()}@example.test', status=AccountStatus.PENDING)
        self.session.add(pending)
        self.session.flush()
        self.central(pending)
        self.central(self.other)
        for target, role in ((self.admin.id, 'normal'), (pending.id, 'normal'), (str(uuid4()), 'normal'), (self.other.id, 'owner')):
            with self.subTest(target=target, role=role), self.assertRaises(BadRequest):
                members.add(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, target, role)
        with self.assertRaises(Forbidden):
            members.candidates(self.session, self.a['id'], self.workspace_a.id, self.editor.id)
        with self.assertRaises(Forbidden):
            members.add(self.session, self.a['id'], self.workspace_a.id, self.editor.id, self.other.id, 'normal')
        with self.assertRaises(BadRequest):
            RegisterService.invite_new_member(self.workspace_a, 'unknown@example.test', 'fa-IR',
                'normal', self.project_owner, session=self.session)
