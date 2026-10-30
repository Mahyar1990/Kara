"""Resolve the real migration override in both launch paths, without a daemon."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import local_dify


class MigrationEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.compose = local_dify.compose_command()
        except RuntimeError as error:
            raise unittest.SkipTest(str(error))

    def test_private_database_settings_reach_migration_in_both_launch_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docker = root / '.runtime/dify/docker'
            docker.mkdir(parents=True)
            (root / 'infra').mkdir()
            override = root / 'infra/compose.local.yaml'
            override.write_bytes(local_dify.OVERRIDE.read_bytes())
            expected = dict(DB_HOST='db_postgres', DB_PORT='5432', DB_TYPE='postgresql',
                            DB_DATABASE='synthetic_database', DB_USERNAME='synthetic_user',
                            DB_PASSWORD='synthetic-private-password')
            private = '\n'.join(f'{key}={value}' for key, value in expected.items())
            private += '\nSANDBOX_API_KEY=synthetic-sandbox-key\n'
            (docker / '.env').write_text(private)
            (root / '.runtime/compose.env').write_text(private)
            # The override's extends resolves against its own api entry, not
            # the complete upstream api environment after files are merged.
            services = {name: {'image': 'busybox:latest'} for name in (
                'api', 'worker', 'worker_beat', 'api_websocket', 'nginx',
                'plugin_daemon', 'web', 'weaviate', 'db_postgres', 'redis')}
            services['api']['environment'] = {key: '${' + key + '}' for key in expected}
            services['db_postgres']['healthcheck'] = {'test': ['CMD', 'true']}
            base = docker / 'docker-compose.yaml'
            base.write_text(json.dumps({'services': services}))
            # Exercise the actual include/project_directory definition too.
            (root / 'compose.yaml').write_bytes((local_dify.ROOT / 'compose.yaml').read_bytes())
            (root / 'infra/compose.build.yaml').write_text('{}')
            (root / '.runtime/compose.build.json').write_text('{}')
            paths = {
                'include': ['-f', str(root / 'compose.yaml')],
                'make': ['--project-directory', str(docker), '--env-file', str(docker / '.env'),
                         '-f', str(base), '-f', str(override)],
            }
            for name, args in paths.items():
                with self.subTest(path=name):
                    result = subprocess.run(self.compose + ['-p', 'kara-migration-test'] + args
                                            + ['config', '--format', 'json'],
                                            cwd=root, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    resolved = json.loads(result.stdout)['services']
                    migration = resolved['migration']
                    for key, value in expected.items():
                        self.assertEqual(migration.get('environment', {}).get(key), value,
                                         f'{name}: migration setting missing: {key}')
                    self.assertEqual(migration['image'], 'langgenius/dify-api:1.17.1')
                    self.assertNotIn('build', migration)
                    for role in ('api', 'worker', 'worker_beat', 'api_websocket'):
                        self.assertEqual(resolved[role]['depends_on']['migration']['condition'],
                                         'service_completed_successfully')
