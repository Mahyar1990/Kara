"""Real PostgreSQL role policy, revocation and transaction checks."""
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import access, team
from company_projects.test_access import ProjectDatabaseFixture
from models.account import TenantAccountJoin


class TeamRolesTests(ProjectDatabaseFixture):
    def change(self, actor=None, target=None, roles=None, revision=1, key=None, **extra):
        target = target or self.editor
        join = access.membership(self.session, self.workspace_a.id, target.id)
        data = dict(roles=roles if roles is not None else ['po', 'tl'], expected_revision=revision,
                    expected_membership_id=join.id if join else str(uuid4()), **extra)
        return team.set_roles(self.session, self.a['id'], self.workspace_a.id,
            (actor or self.project_owner).id, target.id, data, key or str(uuid4()))

    def test_manager_and_global_admin_assign_multiple_roles_without_native_changes(self):
        before = access.membership(self.session, self.workspace_a.id, self.editor.id).role
        self.assertEqual(self.change()['roles'], ['po', 'tl'])
        self.assertEqual(self.change(actor=self.product_owner, roles=['qc'], revision=2)['roles'], ['qc'])
        self.assertEqual(access.membership(self.session, self.workspace_a.id, self.editor.id).role, before)
        self.assertEqual(team.get_roles(self.session, self.a['id'], self.workspace_a.id,
            self.editor.id, self.project_owner.id)['roles'], [])

    def test_technical_roles_do_not_grant_business_role_management(self):
        for actor in (self.editor, self.admin, self.other):
            with self.subTest(actor=actor.name), self.assertRaises((Forbidden, NotFound)):
                self.change(actor=actor)

    def test_project_and_membership_boundaries(self):
        with self.assertRaises(Forbidden):
            team.get_roles(self.session, self.a['id'], self.workspace_b.id, self.product_owner.id, self.editor.id)
        with self.assertRaises(NotFound):
            self.change(target=self.other)
        self.assertEqual(len(team.list_roles(self.session, self.a['id'], self.workspace_a.id, self.editor.id)), 4)

    def test_replay_stale_and_changed_action_key(self):
        key = str(uuid4())
        first = self.change(key=key)
        self.assertEqual(self.change(key=key), first)
        with self.assertRaises(Conflict):
            self.change(revision=1)
        with self.assertRaises(Conflict):
            self.change(roles=['qc'], key=key)
        _, _, audit = team.tables(self.session)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(audit).where(
            audit.c.project_id == self.a['id'])), 1)

    def test_invalid_role_revision_and_untrusted_body_are_rejected(self):
        for values in (['owner'], ['po', 'po'], 'po', [None], [['po']]):
            with self.subTest(values=values), self.assertRaises(BadRequest):
                self.change(roles=values)
        for revision in (True, 0, '1'):
            with self.subTest(revision=revision), self.assertRaises(BadRequest):
                self.change(revision=revision)
        with self.assertRaises(BadRequest):
            self.change(platform_admin=True)

    def test_removal_revokes_roles_but_retains_audit_and_old_membership_cannot_replay(self):
        key = str(uuid4())
        old = self.change(key=key)
        self.session.delete(access.membership(self.session, self.workspace_a.id, self.editor.id))
        self.session.flush()
        policies, roles, audit = team.tables(self.session)
        for table in (policies, roles):
            self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(table).where(
                table.c.project_id == self.a['id'])), 0)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(audit).where(
            audit.c.project_id == self.a['id'])), 1)
        join = TenantAccountJoin(tenant_id=self.workspace_a.id, account_id=self.editor.id, role='normal')
        self.session.add(join); self.session.flush()
        self.assertEqual(team.get_roles(self.session, self.a['id'], self.workspace_a.id,
            self.project_owner.id, self.editor.id)['roles'], [])
        with self.assertRaises(Conflict):
            team.set_roles(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
                self.editor.id, dict(roles=old['roles'], expected_revision=1,
                expected_membership_id=old['membership_id']), key)

    def test_scope_constraint_and_audit_failure_roll_back_the_entire_change(self):
        policies, _, _ = team.tables(self.session)
        with self.assertRaises(sa.exc.IntegrityError), self.session.begin_nested():
            self.session.execute(policies.insert().values(project_id=self.a['id'], workspace_id=self.workspace_b.id,
                account_id=self.other.id, membership_id=str(uuid4()), revision=1))
        from unittest.mock import patch
        original = self.session.execute
        def fail_audit(statement, *args, **kwargs):
            if getattr(getattr(statement, 'table', None), 'name', '') == 'company_team_audit_events' and statement.is_insert:
                raise RuntimeError('Synthetic audit failure')
            return original(statement, *args, **kwargs)
        with self.assertRaises(RuntimeError), self.session.begin_nested(), patch.object(self.session, 'execute', side_effect=fail_audit):
            self.change()
        self.assertEqual(team.get_roles(self.session, self.a['id'], self.workspace_a.id,
            self.editor.id, self.editor.id)['revision'], 1)

    def test_native_removal_revokes_and_records_in_same_transaction(self):
        from services.account_service import TenantService
        self.change()
        # Native internal commit remains inside the fixture's outer transaction.
        TenantService.remove_member_from_tenant(self.workspace_a, self.editor, self.project_owner, session=self.session)
        _, roles, audit = team.tables(self.session)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(roles).where(
            roles.c.project_id == self.a['id'])), 0)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(audit).where(
            audit.c.project_id == self.a['id'], audit.c.event_type == 'member.business_roles.revoked')), 1)

    def test_inactive_actor_target_and_noncanonical_action_are_rejected(self):
        from models.account import AccountStatus
        self.project_owner.status = AccountStatus.BANNED
        self.session.flush()
        with self.assertRaises(Forbidden):
            self.change()
        self.project_owner.status = AccountStatus.ACTIVE
        self.editor.status = AccountStatus.PENDING
        self.session.flush()
        with self.assertRaises(BadRequest):
            self.change()
        with self.assertRaises(BadRequest):
            self.change(key='{' + str(uuid4()) + '}')

    def test_nonmember_removal_keeps_native_error(self):
        from services.account_service import TenantService
        from services.errors.account import MemberNotInTenantError
        with self.assertRaises(MemberNotInTenantError):
            TenantService.remove_member_from_tenant(self.workspace_a, self.other, self.project_owner, session=self.session)
