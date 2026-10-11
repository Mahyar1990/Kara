"""Recipient identity, native submission and competing-decision database checks."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.exceptions import Forbidden, NotFound
from company_projects.test_access import ProjectDatabaseFixture
from company_projects import approval, inbox
from core.repositories.human_input_repository import HumanInputFormSubmissionRepository
from extensions.ext_database import db
from models.account import Account, TenantAccountJoin
from models.human_input import HumanInputForm, HumanInputFormRecipient
from models.model import App
from models.workflow import WorkflowRun
from services.human_input_service import HumanInputService, FormExpiredError, FormSubmittedError, InvalidFormDataError


def synthetic_form(tenant, app_id, run_id):
    expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
    definition = dict(form_content='نظر: {{#$output.comment#}}', rendered_content='نظر: {{#$output.comment#}}',
        inputs=[dict(type='paragraph', output_variable_name='comment')],
        user_actions=[dict(id='approve', title='تأیید', button_style='primary'), dict(id='reject', title='رد', button_style='default')],
        expiration_time=expiry.isoformat(), default_values={}, node_title='بررسی ساختگی', display_in_ui=True)
    return HumanInputForm(tenant_id=tenant, app_id=app_id, workflow_run_id=run_id, node_id='review',
        form_kind='runtime', form_definition=json.dumps(definition), rendered_content=definition['rendered_content'],
        status='waiting', expiration_time=expiry)


class InboxTests(ProjectDatabaseFixture):
    def setUp(self):
        super().setUp()
        self.reader = Account(name='Synthetic reader', email=f'{uuid4()}@example.test')
        self.session.add(self.reader); self.session.flush()
        self.session.add(TenantAccountJoin(tenant_id=self.workspace_a.id, account_id=self.reader.id, role='normal'))
        self.app_model = App(tenant_id=self.workspace_a.id, name='Synthetic review', mode='workflow', status='normal',
            created_by=self.editor.id, enable_site=False, enable_api=False, max_active_requests=0)
        self.session.add(self.app_model); self.session.flush()
        self.run = WorkflowRun(tenant_id=self.workspace_a.id, app_id=self.app_model.id, workflow_id=str(uuid4()),
            type='workflow', triggered_from='debugging', version='draft', status='paused',
            created_by_role='account', created_by=self.editor.id)
        self.session.add(self.run); self.session.flush()
        self.form = synthetic_form(self.workspace_a.id, self.app_model.id, self.run.id)
        self.session.add(self.form); self.session.flush()
        self.recipient = HumanInputFormRecipient(form_id=self.form.id, delivery_id=str(uuid4()), recipient_type='email_member',
            recipient_payload=json.dumps(dict(TYPE='email_member', user_id=self.reader.id, email=self.reader.email)))
        self.session.add(self.recipient); self.session.flush()
        self.maker = sessionmaker(bind=self.connection, expire_on_commit=False, join_transaction_mode='create_savepoint')

    def test_assigned_reader_can_review_but_project_owner_cannot_impersonate_them(self):
        result = inbox.authorized_form(self.session, self.a['id'], self.workspace_a.id, self.reader, self.run.id, self.form.id)
        self.assertEqual(result[1].id, self.recipient.id)
        self.assertFalse(inbox.can_read_payload(self.session, self.workspace_a.id, self.reader, self.app_model.id))
        with self.assertRaises(Forbidden):
            inbox.authorized_form(self.session, self.a['id'], self.workspace_a.id, self.project_owner, self.run.id, self.form.id)

    def test_direct_ids_and_unassigned_private_runs_are_not_accessible(self):
        with self.assertRaises(NotFound):
            inbox.scoped_run(self.session, self.b['id'], self.workspace_b.id, self.editor, self.run.id)
        self.recipient.recipient_payload = json.dumps(dict(TYPE='email_member', user_id=self.admin.id, email=self.admin.email))
        self.session.flush()
        with self.assertRaises(NotFound):
            inbox.scoped_run(self.session, self.a['id'], self.workspace_a.id, self.reader, self.run.id)

    def test_console_fallback_binds_to_initiator_and_external_recipient_is_not_a_member(self):
        self.recipient.recipient_type = 'console'; self.recipient.recipient_payload = '{}'
        self.assertTrue(inbox.intended(self.recipient, self.run, self.editor.id))
        self.assertFalse(inbox.intended(self.recipient, self.run, self.project_owner.id))
        self.recipient.recipient_type = 'email_external'
        self.assertFalse(inbox.intended(self.recipient, self.run, self.editor.id))
        self.recipient.recipient_payload = 'broken'
        self.assertFalse(inbox.intended(self.recipient, self.run, self.editor.id))

    def test_native_submit_records_identity_and_rejects_repeat_without_overwriting(self):
        with patch('core.repositories.human_input_repository.session_factory.create_session', side_effect=self.maker):
            service = HumanInputService(self.maker)
            with patch.object(service, 'enqueue_resume') as resume:
                service.submit_form_by_token(self.recipient.recipient_type, self.recipient.access_token, 'approve',
                    {'comment': 'Synthetic decision'}, submission_user_id=self.reader.id)
                resume.assert_called_once_with(self.run.id)
                with self.assertRaises(FormSubmittedError):
                    service.submit_form_by_token(self.recipient.recipient_type, self.recipient.access_token, 'reject',
                        {'comment': 'Overwrite attempt'}, submission_user_id=self.reader.id)
        self.session.expire(self.form)
        self.assertEqual(self.form.submission_user_id, self.reader.id)
        self.assertEqual(self.form.selected_action_id, 'approve')
        self.assertEqual(json.loads(self.form.submitted_data)['comment'], 'Synthetic decision')

    def test_form_definition_hides_token_and_native_validation_rejects_invalid_or_expired_input(self):
        with patch('core.repositories.human_input_repository.session_factory.create_session', side_effect=self.maker):
            service = HumanInputService(self.maker)
            result = inbox.form_payload(service, self.form, self.recipient)
            self.assertNotIn(self.recipient.access_token, json.dumps(result))
            self.assertEqual(result['inputs'][0]['type'], 'paragraph')
            self.assertEqual(result['inputs'][0]['default'], dict(type='constant', selector=[], value=''))
            with self.assertRaises(InvalidFormDataError):
                service.submit_form_by_token(self.recipient.recipient_type, self.recipient.access_token, 'unknown', {'comment': ''})
            self.form.expiration_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            self.session.flush()
            with self.assertRaises(FormExpiredError):
                inbox.form_payload(service, self.form, self.recipient)

    def test_form_payload_preserves_explicit_paragraph_defaults(self):
        definition = json.loads(self.form.form_definition)
        definition['inputs'][0]['default'] = dict(type='constant', selector=[], value='نظر اولیه')
        self.form.form_definition = json.dumps(definition)
        self.session.flush()
        with patch('core.repositories.human_input_repository.session_factory.create_session', side_effect=self.maker):
            result = inbox.form_payload(HumanInputService(self.maker), self.form, self.recipient)
        self.assertEqual(result['inputs'][0]['default'], definition['inputs'][0]['default'])

    def test_competing_native_submissions_commit_exactly_one_decision(self):
        # Isolated committed rows are necessary for two real PostgreSQL connections.
        form = synthetic_form(str(uuid4()), str(uuid4()), str(uuid4()))
        with Session(db.engine, expire_on_commit=False) as session, session.begin():
            session.add(form); session.flush()
            form_id = form.id
            recipient = HumanInputFormRecipient(form_id=form.id, delivery_id=str(uuid4()), recipient_type='console', recipient_payload='{}')
            session.add(recipient); session.flush(); recipient_id = recipient.id
        first_locked, second_started, release_first = Event(), Event(), Event()
        original = approval.lock_active_form
        def hold_lock(session, form_id):
            if not first_locked.is_set():
                result = original(session, form_id)
                first_locked.set()
                if not release_first.wait(10):
                    raise RuntimeError('Synthetic lock release timeout')
                return result
            second_started.set()
            return original(session, form_id)
        def submit(action):
            with self.app.app_context():
                try:
                    HumanInputFormSubmissionRepository().mark_submitted(form_id=form_id, recipient_id=recipient_id,
                        selected_action_id=action, form_data={'comment': action}, submission_user_id=self.reader.id, submission_end_user_id=None)
                    return action
                except FormSubmittedError:
                    return 'blocked'
        try:
            with patch.object(approval, 'lock_active_form', side_effect=hold_lock), ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(submit, 'approve')
                self.assertTrue(first_locked.wait(10))
                second = pool.submit(submit, 'reject')
                self.assertTrue(second_started.wait(10)); release_first.set()
                self.assertEqual(first.result(10), 'approve'); self.assertEqual(second.result(10), 'blocked')
            with Session(db.engine) as session:
                self.assertEqual(session.get(HumanInputForm, form_id).selected_action_id, 'approve')
        finally:
            release_first.set()
            with Session(db.engine) as session, session.begin():
                session.execute(sa.delete(HumanInputFormRecipient).where(HumanInputFormRecipient.form_id == form_id))
                session.execute(sa.delete(HumanInputForm).where(HumanInputForm.id == form_id))
