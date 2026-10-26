"""Personal GitLab credentials never leak across users or destinations."""
import json
from unittest.mock import patch
import httpx
from werkzeug.exceptions import BadGateway, BadRequest, Conflict, NotFound, ServiceUnavailable
from company_projects import gitlab_connections as gitlab
from company_projects.test_access import ProjectDatabaseFixture

class GitLabConnectionTests(ProjectDatabaseFixture):
    def create(self, actor=None, **updates):
        data = dict(name='Synthetic GitLab', base_url='https://git.example.test', token='synthetic-secret', expected_revision=1)
        return gitlab.save(self.session, (actor or self.project_owner).id, data | updates)

    def test_personal_encrypted_and_destination_bound(self):
        value = self.create()
        row = gitlab.load(self.session, self.project_owner.id, value['id'])
        self.assertEqual(gitlab.decrypt(row), 'synthetic-secret')
        self.assertNotIn('synthetic-secret', json.dumps(value))
        self.assertNotIn('synthetic-secret', row['encrypted_token'])
        self.assertEqual(gitlab.list_connections(self.session, self.editor.id)['data'], [])
        with self.assertRaises(NotFound): gitlab.load(self.session, self.editor.id, value['id'])
        with self.assertRaises(ServiceUnavailable): gitlab.decrypt(row | dict(account_id=self.editor.id))
        with self.assertRaises(ServiceUnavailable): gitlab.decrypt(row | dict(base_url='https://other.test'))
        data = dict(name=value['name'], base_url=value['base_url'], token='', expected_revision=1)
        self.assertEqual(gitlab.save(self.session, self.project_owner.id, data, value['id'])['revision'], 2)
        with self.assertRaises(Conflict): gitlab.save(self.session, self.project_owner.id, data, value['id'])
        with self.assertRaises(BadRequest): gitlab.save(self.session, self.project_owner.id, data | dict(base_url='https://other.test', expected_revision=2), value['id'])

    def test_validation_and_safe_identity_probe(self):
        for updates in ({'token':''}, {'token':'Bearer token'}, {'token':'bad\nsecret'}, {'base_url':'http://git.test'}, {'base_url':'https://user:secret@git.test'}, {'account_id': self.editor.id}):
            with self.subTest(updates=list(updates)), self.assertRaises(BadRequest): self.create(**updates)
        value = self.create()
        with patch.object(gitlab.ssrf_proxy, 'get', return_value=httpx.Response(200, json={'id':1, 'username':'synthetic'})) as send:
            self.assertTrue(gitlab.test_connection(self.session, self.project_owner.id, value['id'])['connected'])
            self.assertFalse(send.call_args.kwargs['follow_redirects'])
            self.assertTrue(send.call_args.kwargs['ssl_verify'])
            self.assertEqual(send.call_args.kwargs['headers']['PRIVATE-TOKEN'], 'synthetic-secret')
        for response in (httpx.Response(302), httpx.Response(401), httpx.Response(200, content=b'x'*262145)):
            with patch.object(gitlab.ssrf_proxy, 'get', return_value=response), self.assertRaises(BadGateway) as error:
                gitlab.test_connection(self.session, self.project_owner.id, value['id'])
            self.assertNotIn('synthetic-secret', str(error.exception))
