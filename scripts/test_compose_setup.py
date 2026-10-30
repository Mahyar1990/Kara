"""Bootstrap must preserve private credentials and fail before writes on missing history."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import company_api
import compose_setup


class ComposeSetupTests(unittest.TestCase):
    def test_existing_credentials_survive_repeated_setup_with_custom_ports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docker_dir = root / '.runtime/dify/docker'
            docker_dir.mkdir(parents=True)
            private = docker_dir / '.env'
            original = 'SECRET_KEY=fixture-private\nEXPOSE_NGINX_PORT=8080\n'
            private.write_text(original, encoding='utf-8')
            values = {'DIFY_HTTP_PORT': '9080', 'DIFY_HTTPS_PORT': '9443',
                      'DIFY_PROJECT_NAME': 'company-agent-local'}
            with patch.object(compose_setup, 'ROOT', root), \
                 patch.object(compose_setup.local_dify, 'DOCKER_DIR', docker_dir), \
                 patch.object(compose_setup.local_dify, 'prepare'), \
                 patch.object(compose_setup.local_dify, 'settings', return_value=values), \
                 patch.object(company_api, 'catalog_files'), \
                 patch.object(company_api, 'prepare_source'), \
                 patch.object(company_api, 'fingerprint', return_value='api-revision'), \
                 patch.object(compose_setup.persian_web, 'prepare_source'), \
                 patch.object(compose_setup.persian_web, 'fingerprint', return_value='web-revision'):
                compose_setup.prepare()
                first = (root / '.runtime/compose.env').read_bytes()
                compose_setup.prepare()
            self.assertEqual(private.read_text(), original)
            self.assertEqual((root / '.runtime/compose.env').read_bytes(), first)
            self.assertIn(b'SECRET_KEY=fixture-private\n', first)
            self.assertIn(b'EXPOSE_NGINX_PORT=9080\n', first)
            self.assertIn(b'NEXT_PUBLIC_SOCKET_URL=ws://localhost\n', first)
            generated = json.loads((root / '.runtime/compose.build.json').read_text())
            self.assertEqual(generated['services']['api']['build']['labels'],
                             {'company-agent.projects': 'api-revision'})

    def test_missing_catalog_fails_before_downloads_or_configuration_writes(self):
        with patch.object(company_api, 'catalog_files', side_effect=RuntimeError('missing catalog')), \
             patch.object(compose_setup.local_dify, 'prepare') as prepare, \
             self.assertRaisesRegex(RuntimeError, 'missing catalog'):
            compose_setup.prepare()
        prepare.assert_not_called()
