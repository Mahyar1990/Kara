"""Background Runner lifecycle, private files, literal argv and packaged CLI regressions."""
import argparse
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runner'))
from kara_source_runner import service
from kara_source_runner.executor import git_environment
from kara_source_runner.package import extras


class RunnerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'private/device.json'
        self.config.parent.mkdir(mode=0o700)
        self.config.write_text(json.dumps({'server': 'https://kara.example.test', 'secret': 'fixture-secret-never-copy'}))
        self.config.chmod(0o600)
        parser = argparse.ArgumentParser()
        parser.add_argument('--config', type=Path, default=self.config)
        service.add_parser(parser.add_subparsers(dest='action', required=True))
        self.parser = parser
        self.args = parser.parse_args(['service', 'install'])
        self.calls = []
        self.active = False
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'settings'), 'PATH': '/usr/bin:/bin'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_command(self, command, **kwargs):
        self.calls.append((command, kwargs))
        code = 0
        if 'is-active' in command:
            code = 0 if self.active else 3
        if 'start' in command or 'restart' in command:
            self.active = True
        if 'stop' in command or 'disable' in command:
            self.active = False
        return subprocess.CompletedProcess(command, code)

    def binaries(self, name):
        return '/usr/bin/' + name if name in ('git', 'systemctl', 'journalctl') else None

    def install(self):
        with patch.object(service.subprocess, 'run', side_effect=self.run_command), patch.object(service.shutil, 'which', side_effect=self.binaries), patch('sys.stdout', new=io.StringIO()):
            service.install(self.args, '/usr/bin/systemctl')

    def test_install_repeat_and_uninstall_preserve_pairing_and_sources(self):
        sources = self.root / 'sources'; sources.mkdir(); (sources / 'local-edit').write_text('keep')
        original = self.config.read_bytes()
        self.install()
        unit = service.unit_path()
        text = unit.read_text()
        self.assertTrue(text.startswith(service.MARKER))
        self.assertEqual(unit.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('fixture-secret', text)
        self.assertIn('Restart=always', text)
        self.assertIn('UMask=0077', text)
        self.assertIn(service.quote(service.absolute(sys.executable), command=True), text)
        self.assertNotIn('sudo', text)
        self.assertFalse(any('loginctl' in call[0] for call in self.calls))
        self.install()  # active managed service is idempotent, no replacement or restart
        self.assertEqual(unit.read_text(), text)
        self.assertFalse(list(unit.parent.glob('*.bak')))
        self.assertFalse(any('restart' in call[0] for call in self.calls))
        args = self.parser.parse_args(['service', 'uninstall'])
        with patch.object(service.subprocess, 'run', side_effect=self.run_command), patch.object(service.shutil, 'which', side_effect=self.binaries), patch.object(service.sys, 'platform', 'linux'), patch.object(service.os, 'getuid', return_value=unit.stat().st_uid or 1000), patch('sys.stdout', new=io.StringIO()):
            # Unit ownership on root CI differs from the explicitly non-root lifecycle guard.
            with patch.object(service, 'existing_unit', return_value=text):
                self.assertEqual(service.manage(args), 0)
        self.assertFalse(unit.exists())
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual((sources / 'local-edit').read_text(), 'keep')

    def test_manual_or_changed_unit_requires_explicit_replace_and_private_backup(self):
        path = service.unit_path(); path.parent.mkdir(parents=True)
        original = '[Service]\nExecStart=/private/old-runner\n'
        path.write_text(original)
        with self.assertRaises(service.ServiceError):
            self.install()
        self.assertEqual(path.read_text(), original)
        self.assertEqual(self.calls, [])
        self.args.replace = True; self.active = True
        self.install()
        backups = list(path.parent.glob('*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
        commands = [c[0] for c in self.calls]
        self.assertIn(['/usr/bin/systemctl', '--user', 'stop', service.UNIT], commands)
        self.assertIn(['/usr/bin/systemctl', '--user', 'restart', service.UNIT], commands)

    def test_symlink_unit_never_overwrites_target_even_with_replace(self):
        path = service.unit_path(); path.parent.mkdir(parents=True)
        target = self.root / 'unrelated'; target.write_text('keep')
        path.symlink_to(target); self.args.replace = True
        with self.assertRaises(service.ServiceError):
            self.install()
        self.assertEqual(target.read_text(), 'keep')
        self.assertTrue(path.is_symlink())
        self.assertEqual(self.calls, [])

    def test_bad_pairing_and_ca_fail_before_mutation_without_secret_in_error(self):
        for content in ('bad json', '{}', '[]', '{"server":123,"secret":"fixture-secret"}', '{"server":"http://remote.example.test","secret":"fixture-secret"}'):
            self.config.write_text(content)
            with self.assertRaises(service.ServiceError) as raised:
                self.install()
            self.assertNotIn('fixture-secret', str(raised.exception))
        self.config.write_text('{"server":"https://kara.example.test","secret":"fixture-secret"}')
        self.config.chmod(0o644)
        with self.assertRaises(service.ServiceError):
            self.install()
        self.config.chmod(0o600)
        self.args.ca_bundle = self.root / 'invalid.pem'; self.args.ca_bundle.write_text('not a cert')
        with self.assertRaises(service.ServiceError):
            self.install()
        self.assertFalse(service.unit_path().exists())
        self.assertEqual(self.calls, [])

    def test_manager_or_docker_failure_creates_no_unit(self):
        with patch.object(service.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)), self.assertRaises(service.ServiceError):
            service.install(self.args, '/usr/bin/systemctl')
        self.args.code_backend = 'docker'
        def fail_docker(command, **kwargs):
            return subprocess.CompletedProcess(command, 1 if 'info' in command else 0)
        with patch.object(service.subprocess, 'run', side_effect=fail_docker), patch.object(service.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name), self.assertRaises(service.ServiceError):
            service.install(self.args, '/usr/bin/systemctl')
        self.assertFalse(service.unit_path().exists())

    def test_root_and_non_linux_commands_are_rejected(self):
        with patch.object(service.sys, 'platform', 'darwin'), self.assertRaises(service.ServiceError):
            service.manage(self.args)
        with patch.object(service.sys, 'platform', 'linux'), patch.object(service.os, 'getuid', return_value=0), self.assertRaises(service.ServiceError):
            service.manage(self.args)

    def test_lock_blocks_second_process_and_releases_after_exit_without_deleting_file(self):
        code = 'from pathlib import Path; from kara_source_runner.service import instance_lock\nwith instance_lock(Path(__import__("sys").argv[1])): pass'
        env = {**os.environ, 'PYTHONPATH': str(Path(service.__file__).parent.parent)}
        with service.instance_lock(self.config):
            result = subprocess.run([sys.executable, '-c', code, str(self.config)], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('already uses this device config', result.stderr)
        result = subprocess.run([sys.executable, '-c', code, str(self.config)], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(self.config.parent.glob('.runner-*.lock'))), 1)

    def test_install_does_not_compete_with_running_manual_process(self):
        with service.instance_lock(self.config), self.assertRaises(service.ServiceError):
            self.install()
        self.assertFalse(service.unit_path().exists())
        self.assertFalse(any('start' in c[0] for c in self.calls))

    def test_literal_paths_and_explicit_privileges_survive_unit_rendering(self):
        self.args.root = self.root / 'space فارسی %h $HOME "quote"'
        self.args.allow_harness = True; self.args.allow_worktree_write = True
        unit = service.render_unit(self.args, {'PATH': '/usr/bin:/bin'})
        self.assertIn('%%h $$HOME', unit)
        self.assertIn('--allow-harness', unit)
        self.assertIn('--allow-worktree-write', unit)
        self.assertNotIn('--allow-local-code', unit)
        self.assertNotIn('fixture-secret', unit)
        self.assertIn('WorkingDirectory=' + str(Path(service.__file__).parent.parent).replace('%', '%%') + '\n', unit)
        self.assertNotIn('WorkingDirectory="', unit)
        with self.assertRaises(service.ServiceError):
            service.quote('bad\nExecStart=evil')
        self.args.root = Path('/tmp/bad\nvalue')
        with self.assertRaises(service.ServiceError):
            service.render_unit(self.args, {})

    def test_group_uses_existing_membership_and_shell_quotes_argv(self):
        import grp
        import pwd
        entry = grp.struct_group(('docker', 'x', 141, [pwd.getpwuid(os.getuid()).pw_name]))
        with patch('grp.getgrnam', return_value=entry), patch.object(service.shutil, 'which', return_value='/usr/bin/sg'):
            command = service.group_command(['/a path/python', '-m', 'module', '/tmp/a; touch nope'], 'docker')
        self.assertEqual(command[:3], ['/usr/bin/sg', 'docker', '-c'])
        self.assertEqual(shlex.split(command[3]), ['exec', '/a path/python', '-m', 'module', '/tmp/a; touch nope'])
        denied = grp.struct_group(('docker', 'x', 999999, []))
        with patch('grp.getgrnam', return_value=denied), self.assertRaises(service.ServiceError):
            service.group_command(['docker', 'info'], 'docker')
        with self.assertRaises(service.ServiceError):
            service.group_command(['docker'], 'docker;evil')

    def test_only_selected_environment_is_persisted_and_ca_reaches_git(self):
        with patch.dict(os.environ, {'API_TOKEN': 'fixture-secret', 'HTTPS_PROXY': 'https://user:secret@proxy', 'SSL_CERT_FILE': '/trusted/ca.pem'}), patch.object(service.ssl, 'create_default_context'):
            env = service.service_environment(self.args)
        self.assertEqual(env['SSL_CERT_FILE'], '/trusted/ca.pem')
        self.assertNotIn('API_TOKEN', env)
        self.assertNotIn('HTTPS_PROXY', env)
        self.args.ca_bundle = Path('/corporate/ca.pem')
        with patch.object(service.ssl, 'create_default_context'):
            env = service.service_environment(self.args)
        self.assertEqual({env[k] for k in ('SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'GIT_SSL_CAINFO')}, {'/corporate/ca.pem'})
        with patch.dict(os.environ, env):
            self.assertEqual(git_environment('/tmp/private', '/tmp/askpass')['GIT_SSL_CAINFO'], '/corporate/ca.pem')

    def test_download_archive_runs_service_help_without_contacting_server(self):
        # Match Download's archive assembly, then execute from only those extracted files.
        archive = self.root / 'runner.zip'
        with zipfile.ZipFile(archive, 'w') as out:
            for file in Path(service.__file__).parent.glob('*.py'):
                out.write(file, 'kara_source_runner/' + file.name)
            for name, content in extras().items():
                out.writestr(name, content)
        target = self.root / 'extracted'; target.mkdir()
        with zipfile.ZipFile(archive) as source:
            source.extractall(target)
        result = subprocess.run([sys.executable, '-m', 'kara_source_runner', 'service', 'install', '--help'], cwd=target, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--ca-bundle', result.stdout)
        self.assertIn('--docker-group', result.stdout)
        self.assertIn('--allow-harness', result.stdout)
        self.assertTrue((target / 'BACKGROUND.md').exists())
        self.assertNotIn('fixture-secret', archive.read_bytes().decode('latin1'))
        dockerfile = (target / 'Dockerfile.code').read_text()
        self.assertIn('type=secret,id=kara_ca', dockerfile)
        self.assertNotIn('trusted-host', dockerfile)
        self.assertNotIn('dotin', dockerfile)
