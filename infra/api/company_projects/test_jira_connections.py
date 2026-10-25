"""Personal secret isolation, safe outbound requests and native import regression."""
import json
from unittest.mock import patch
from uuid import uuid4

import httpx
import sqlalchemy as sa
from werkzeug.exceptions import BadGateway, BadRequest, Conflict, Forbidden, NotFound, ServiceUnavailable

from company_projects import jira_connections as jira, jira_intake, requests
from company_projects.test_requests import RequestFixture


class JiraConnectionTests(RequestFixture):
    def make_connection(self, actor=None, **updates):
        data = dict(name='Synthetic Jira', base_url='https://jira.example.test/jira/',
            token='synthetic-personal-token', expected_revision=1)
        data.update(updates)
        return jira.save(self.session, (actor or self.project_owner).id, data)

    def response(self):
        return dict(startAt=0, total=1, issues=[dict(id='12345', key='SYN-1', fields=dict(
            summary='Synthetic request', description='Original requirement', updated='2026-10-25T12:00:00Z'))])

    def fetch(self, connection, actor=None, key=None, **updates):
        data = dict(connection_id=connection['id'], jql='project = SYN ORDER BY key DESC', start_at=0, max_results=50)
        data.update(updates)
        return jira.fetch(self.session, self.a['id'], self.workspace_a.id,
            (actor or self.project_owner).id, data, key or str(uuid4()))

    def test_encryption_personal_visibility_and_cross_account_denial(self):
        first = self.make_connection()
        self.make_connection(actor=self.editor, token='synthetic-other-token')
        self.assertEqual([row['id'] for row in jira.list_connections(self.session, self.project_owner.id)['data']], [first['id']])
        self.assertNotIn('token', first)
        self.assertNotIn('encrypted_token', first)
        row = jira.load(self.session, self.project_owner.id, first['id'])
        self.assertNotIn('synthetic-personal-token', row['encrypted_token'])
        self.assertEqual(jira.decrypt(row), 'synthetic-personal-token')
        with self.assertRaises(ServiceUnavailable):
            jira.decrypt(dict(row, account_id=self.editor.id))
        with self.assertRaises(ServiceUnavailable):
            jira.decrypt(dict(row, base_url='https://other.example.test'))
        for actor in (self.editor, self.product_owner, self.other):
            with self.assertRaises(NotFound):
                jira.load(self.session, actor.id, first['id'])
            with self.assertRaises(NotFound):
                jira.delete(self.session, actor.id, first['id'], dict(expected_revision=1))
            with self.assertRaises(NotFound):
                jira.test_connection(self.session, actor.id, first['id'])

    def test_update_requires_new_token_when_destination_changes_and_delete_preserves_requests(self):
        connection = self.make_connection()
        data = dict(name='Renamed', base_url=connection['base_url'], token='', expected_revision=1)
        changed = jira.save(self.session, self.project_owner.id, data, connection['id'])
        self.assertEqual(changed['revision'], 2)
        self.assertEqual(jira.decrypt(jira.load(self.session, self.project_owner.id, connection['id'])), 'synthetic-personal-token')
        with self.assertRaises(Conflict):
            jira.save(self.session, self.project_owner.id, data, connection['id'])
        data.update(expected_revision=2, base_url='https://other.example.test')
        with self.assertRaises(BadRequest):
            jira.save(self.session, self.project_owner.id, data, connection['id'])
        data['token'] = 'synthetic-replacement-token'
        changed = jira.save(self.session, self.project_owner.id, data, connection['id'])
        row = jira.load(self.session, self.project_owner.id, connection['id'])
        self.assertEqual(jira.decrypt(row), data['token'])
        result = jira.import_selected(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            dict(connection_id=connection['id'], response=self.response()), str(uuid4()))
        jira.delete(self.session, self.project_owner.id, connection['id'], dict(expected_revision=changed['revision']))
        imported = requests.get_request(self.session, self.a['id'], self.workspace_a.id,
            self.project_owner.id, result['data'][0]['request_id'])
        self.assertEqual(imported['jira']['base_url'], data['base_url'])

    def test_invalid_settings_are_rejected_and_no_client_actor_or_url_override(self):
        for updates in ({'token': ''}, {'token': 'Bearer token'}, {'token': 'line\nbreak'},
                {'base_url': 'http://jira.example.test'}, {'base_url': 'https://user:pass@jira.example.test'},
                {'base_url': 'https://jira.example.test?token=secret'}, {'name': ''}, {'account_id': self.editor.id}):
            with self.subTest(fields=list(updates)), self.assertRaises(BadRequest):
                self.make_connection(**updates)
        connection = self.make_connection()
        with self.assertRaises(Conflict):
            self.make_connection()
        with self.assertRaises(BadRequest):
            jira.import_selected(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
                dict(base_url='https://override.example.test', response=self.response()), str(uuid4()))
        with self.assertRaises(NotFound):
            self.fetch(connection, actor=self.admin)
        with self.assertRaises(Forbidden):
            self.fetch(connection, actor=self.editor)

    def test_fetch_sends_only_selected_users_token_and_replay_does_not_call_again(self):
        connection = self.make_connection()
        self.make_connection(actor=self.admin, token='synthetic-po-token')
        key = str(uuid4())
        with patch.object(jira.ssrf_proxy, 'post', return_value=httpx.Response(200, json=self.response())) as send:
            result = self.fetch(connection, key=key)
            self.assertEqual(result['data'][0]['outcome'], 'created')
            self.assertEqual(self.fetch(connection, key=key), result)
            self.assertEqual(send.call_count, 1)
            args, options = send.call_args
            self.assertEqual(args[0], 'https://jira.example.test/jira/rest/api/2/search')
            self.assertEqual(options['headers']['Authorization'], 'Bearer synthetic-personal-token')
            self.assertTrue(options['ssl_verify'])
            self.assertFalse(options['follow_redirects'])
            self.assertEqual(options['max_retries'], 0)
            self.assertIn('description', options['json']['fields'])
            self.assertNotIn('token', json.dumps(result))
        po = jira.list_connections(self.session, self.admin.id)['data'][0]
        with patch.object(jira.ssrf_proxy, 'post', return_value=httpx.Response(200, json=self.response())) as send:
            self.assertEqual(self.fetch(po, actor=self.admin)['data'][0]['outcome'], 'unchanged')
            self.assertEqual(send.call_args.kwargs['headers']['Authorization'], 'Bearer synthetic-po-token')

    def test_upstream_auth_permissions_redirect_and_network_errors_are_sanitized_and_atomic(self):
        connection = self.make_connection()
        entity = jira_intake.table(self.session)
        before = self.session.scalar(sa.select(sa.func.count()).select_from(entity))
        for status in (400, 401, 403, 404, 429, 500, 302):
            with self.subTest(status=status), patch.object(jira.ssrf_proxy, 'post',
                    return_value=httpx.Response(status, json={'errorMessages': ['synthetic-personal-token']})):
                with self.assertRaises(BadGateway) as failure:
                    self.fetch(connection)
                self.assertIn(str(status), failure.exception.description)
                self.assertNotIn('synthetic-personal-token', failure.exception.description)
        with patch.object(jira.ssrf_proxy, 'post', side_effect=httpx.ConnectError('synthetic-personal-token')):
            with self.assertRaises(BadGateway) as failure:
                self.fetch(connection)
            self.assertNotIn('synthetic-personal-token', failure.exception.description)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(entity)), before)

    def test_test_endpoint_and_response_bounds_and_pagination(self):
        connection = self.make_connection()
        with patch.object(jira.ssrf_proxy, 'get', return_value=httpx.Response(200, json={'name': 'synthetic-jira-user'})) as send:
            result = jira.test_connection(self.session, self.project_owner.id, connection['id'])
            self.assertTrue(result['connected'])
            self.assertNotIn('synthetic-jira-user', json.dumps(result))
            self.assertEqual(send.call_args.args[0], 'https://jira.example.test/jira/rest/api/2/myself')
        for response in (httpx.Response(200, content=b'x' * (jira.MAX_BYTES + 1)),
                httpx.Response(200, content=b'<html>login</html>'),
                httpx.Response(200, json=dict(self.response(), startAt=1, total=2))):
            with patch.object(jira.ssrf_proxy, 'post', return_value=response), self.assertRaises(BadGateway):
                self.fetch(connection)
        for changes in ({'start_at': True}, {'max_results': 101}, {'jql': ''}, {'actor_id': self.admin.id}):
            with self.assertRaises(BadRequest):
                self.fetch(connection, **changes)
