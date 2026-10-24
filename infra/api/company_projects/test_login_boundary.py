"""Regression for invitation requests made after a regular user's login."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flask import Blueprint, Flask

from company_projects import access


class LoginBoundaryTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        console = Blueprint('console', __name__, url_prefix='/console/api')

        @console.route('/<path:path>', methods=['GET', 'POST'])
        def native_endpoint(path):
            # Reaching the endpoint leaves its native auth/token checks in charge.
            return {'endpoint': path}

        app.register_blueprint(console)
        account = SimpleNamespace(id='regular-user')
        with patch('libs.login.current_account_with_tenant_optional', return_value=(account, 'central')), \
                patch('extensions.ext_database.db', SimpleNamespace(engine=object())):
            access.restrict_central_workspace(app)
        self.client = app.test_client()
        for target, value in [
                ('sqlalchemy.orm.Session', None),
                ('company_projects.access.authority', {'tenant_id': 'central'}),
                ('company_projects.access.is_product_admin', False)]:
            mock = self.enterContext(patch(target))
            if value is not None:
                mock.return_value = value
            if target.endswith('is_product_admin'):
                self.is_admin = mock

    def test_regular_session_can_finish_invitation_and_authenticate(self):
        for method, path in [('GET', '/activate/check'), ('POST', '/activate'),
                ('POST', '/login'), ('POST', '/forgot-password'),
                ('POST', '/email-code-login/validity')]:
            with self.subTest(method=method, path=path):
                response = self.client.open('/console/api' + path, method=method)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['endpoint'], path[1:])

    def test_central_content_stays_private_after_login(self):
        for path in ['/apps', '/workspaces/current/members', '/oauth/data-source/github',
                '/activate/other', '/login/other']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get('/console/api' + path).status_code, 403)
        self.is_admin.return_value = True
        self.assertEqual(self.client.get('/console/api/apps').status_code, 200)


if __name__ == '__main__':
    unittest.main()
