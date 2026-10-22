"""Focused persisted intake checks: identity, versions, files and concurrency guards."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import access, agents, flows, requests, team
from company_projects.test_flows import FlowFixture


class RequestFixture(FlowFixture):
    def setUp(self):
        super().setUp()
        self.flow = self.publish(self.save())
        self.assign_po(self.admin)

    def assign_po(self, actor, roles=None):
        current = team.get_roles(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, actor.id)
        return team.set_roles(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, actor.id,
            dict(roles=roles if roles is not None else ['po'], expected_revision=current['revision'],
                expected_membership_id=current['membership_id']), str(uuid4()))

    def request(self, row=None, actor=None, key=None, files=(), **changes):
        data = dict(title='  عنوان اصلی  ', content='\nمتن دقیق\n', attachment_ids=[],
            expected_revision=row['revision'] if row else 1)
        data.update(changes)
        return requests.save(self.session, self.a['id'], self.workspace_a.id, (actor or self.editor).id,
            data, key or str(uuid4()), row['id'] if row else None, files)

    def decision(self, row, actor=None, key=None, **changes):
        data = dict(expected_revision=row['revision'], request_revision_id=row['current_revision_id'],
            flow_id=self.flow['id'], flow_version_id=self.flow['current_version_id'], outcome='approved',
            reason='تصمیم صریح آزمون', expires_at=None)
        data.update(changes)
        return requests.decide(self.session, self.a['id'], self.workspace_a.id, (actor or self.admin).id,
            row['id'], data, key or str(uuid4()))


class RequestTests(RequestFixture):
    def test_any_member_creates_but_manager_and_global_admin_are_not_po(self):
        row = self.request(actor=self.admin)
        self.assertEqual(row['state'], 'pending'); self.assertFalse(row['intake_valid'])
        for actor in (self.editor, self.project_owner, self.product_owner):
            with self.assertRaises(Forbidden):
                self.decision(row, actor=actor)
        self.assertTrue(self.decision(row)['intake_valid'])

    def test_content_is_exact_and_revisions_invalidate_without_losing_decisions(self):
        row = self.request(files=[('input.txt', b'original')]); old = row['current']
        approved = self.decision(row)
        revised = self.request(approved, content='متن تازه', attachment_ids=old['attachment_ids'])
        self.assertEqual(revised['current']['version'], 2); self.assertFalse(revised['intake_valid'])
        self.assertIsNone(revised['decision']); self.assertEqual(len(revised['decisions']), 1)
        self.assertEqual(revised['revisions'][1], old)
        self.assertEqual(old['content'], '\nمتن دقیق\n'); self.assertEqual(old['title'], '  عنوان اصلی  ')
        self.assertEqual(revised['current']['attachments'], old['attachments'])

    def test_only_creator_or_po_revises_not_manager(self):
        row = self.request()
        with self.assertRaises(Forbidden):
            self.request(row, actor=self.project_owner)
        self.assertEqual(self.request(row, actor=self.admin)['current']['version'], 2)

    def test_exact_published_flow_version_survives_new_publication(self):
        row = self.request(); approved = self.decision(row); old = approved['decision']
        self.flow = self.publish(self.save(self.flow, name='نسخهٔ تازه'))
        fresh = requests.get_request(self.session, self.a['id'], self.workspace_a.id, self.editor.id, row['id'])
        self.assertTrue(fresh['intake_valid']); self.assertEqual(fresh['decision'], old)
        self.assertNotEqual(old['flow_version_id'], self.flow['current_version_id'])

    def test_rejected_deferred_revoked_and_expired_never_admit(self):
        row = self.request()
        for outcome in ('rejected', 'deferred'):
            row = self.decision(row, outcome=outcome, flow_id=None, flow_version_id=None)
            self.assertFalse(row['intake_valid']); self.assertEqual(row['state'], outcome)
        until = agents.now() + timedelta(hours=1)
        row = self.decision(row, expires_at=until.isoformat())
        with patch('company_projects.agents.now', return_value=until + timedelta(seconds=1)):
            self.assertFalse(requests.get_request(self.session, self.a['id'], self.workspace_a.id, self.admin.id, row['id'])['intake_valid'])
        row = requests.decide(self.session, self.a['id'], self.workspace_a.id, self.admin.id, row['id'],
            dict(expected_revision=row['revision'], reason='ابطال صریح'), str(uuid4()), row['decision']['id'])
        self.assertEqual(row['state'], 'revoked'); self.assertFalse(row['intake_valid'])
        self.assertEqual(len(row['decisions']), 4)

    def test_replay_conflicts_and_stale_decision_target(self):
        key = str(uuid4()); row = self.request(key=key)
        self.assertEqual(self.request(key=key), row)
        with self.assertRaises(Conflict):
            self.request(key=key, content='different')
        decision_key = str(uuid4()); approved = self.decision(row, key=decision_key)
        self.assertEqual(self.decision(row, key=decision_key), approved)
        with self.assertRaises(Conflict):
            self.decision(row)
        with self.assertRaises(Conflict):
            self.decision(approved, request_revision_id=str(uuid4()))
        with self.assertRaises(Conflict):
            self.request(row)

    def test_po_revocation_blocks_new_actions_and_replays_but_preserves_history(self):
        row = self.request(); key = str(uuid4()); self.decision(row, key=key)
        self.assign_po(self.admin, [])
        with self.assertRaises(Forbidden):
            self.decision(row, key=key)
        fresh = requests.get_request(self.session, self.a['id'], self.workspace_a.id, self.editor.id, row['id'])
        self.assertTrue(fresh['intake_valid'])  # Removing a role does not rewrite a prior human decision.

    def test_missing_archived_foreign_flow_and_missing_source_revision(self):
        row = self.request()
        with self.assertRaises(UnprocessableEntity):
            self.decision(row, flow_id=None, flow_version_id=None)
        with self.assertRaises(NotFound):
            self.decision(row, flow_id=str(uuid4()), flow_version_id=str(uuid4()))
        with self.assertRaises(NotFound):
            self.decision(row, flow_version_id=str(uuid4()))
        flows.mutate(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            dict(expected_revision=self.flow['revision']), str(uuid4()), self.flow['id'], 'archive')
        with self.assertRaises(UnprocessableEntity):
            self.decision(row)

    def test_attachment_scope_size_and_private_download(self):
        row = self.request(files=[('شرح.txt', b'private')]); file_id = row['current']['attachment_ids'][0]
        self.assertEqual(requests.download(self.session, self.a['id'], self.workspace_a.id, self.admin.id,
            row['id'], file_id)['content'], b'private')
        other = self.request()
        with self.assertRaises(NotFound):
            self.request(other, attachment_ids=[file_id])
        with self.assertRaises(NotFound):
            requests.download(self.session, self.a['id'], self.workspace_a.id, self.editor.id, other['id'], file_id)
        with self.assertRaises((NotFound, Forbidden)):
            requests.download(self.session, self.a['id'], self.workspace_b.id, self.other.id, row['id'], file_id)
        for files in ([('../bad', b'a')], [('x', b'')], [('x', b'a' * (requests.MAX_FILE + 1))], [('x', b'a')] * 6):
            with self.subTest(size=len(files)), self.assertRaises(BadRequest):
                self.request(files=files)

    def test_malformed_body_and_expiry_are_rejected(self):
        for changes in (dict(expected_revision=True), dict(content=''), dict(content='\ud800'), dict(title=''), dict(attachment_ids='bad')):
            with self.subTest(changes=changes), self.assertRaises(BadRequest):
                self.request(**changes)
        row = self.request()
        for changes in (dict(outcome='pretend'), dict(expires_at='2026-01-01'), dict(reason=''), dict(flow_id=None)):
            with self.subTest(changes=changes), self.assertRaises(BadRequest):
                self.decision(row, **changes)

    def test_database_rejects_history_mutation_and_foreign_scope_pointer(self):
        row = self.decision(self.request(files=[('input.txt', b'a')]))
        table, revisions, files, decisions = requests.tables(self.session)
        for entity in (revisions, files, decisions):
            for operation in ('update', 'delete'):
                with self.subTest(table=entity.name, operation=operation):
                    with self.assertRaises(sa.exc.DBAPIError), self.session.begin_nested():
                        query = entity.delete() if operation == 'delete' else entity.update().values(id=entity.c.id)
                        self.session.execute(query.where(entity.c.request_id == row['id']))
        other = self.request()
        with self.assertRaises(sa.exc.IntegrityError), self.session.begin_nested():
            self.session.execute(table.update().where(table.c.id == other['id']).values(current_decision_id=row['decision']['id']))
