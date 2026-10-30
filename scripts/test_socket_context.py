"""Execute the installed server hook; authorization must retain Flask context."""
import ast
from contextlib import contextmanager
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class SocketContextTests(unittest.TestCase):
    def test_guard_runs_in_context_and_preserves_denial(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'infra/api/install.py').read_text())
        hooks = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                 and isinstance(node.value, str) and 'deny_native(workflow_id)' in node.value]
        self.assertEqual(len(hooks), 1)
        namespace = {}
        exec('def relay(self, mapping):\n' + '\n'.join(line[4:] for line in hooks[0].splitlines())
             + '\n    return user_id\n', namespace)
        active = []
        @contextmanager
        def context():
            active.append(True)
            try:
                yield
            finally:
                active.pop()
        app = SimpleNamespace(_socketio=SimpleNamespace(app=SimpleNamespace(app_context=context)))
        calls = []
        def allow(app_id):
            self.assertTrue(active, 'Database guard needs the Flask application context')
            calls.append(app_id)
        module = SimpleNamespace(deny_native=allow)
        with patch.dict(sys.modules, {'company_projects.agent_execution': module}):
            self.assertEqual(namespace['relay'](app, {'workflow_id': 'app-1', 'user_id': 'user-1'}), 'user-1')
            self.assertEqual(calls, ['app-1'])
            self.assertFalse(active)
            def deny(app_id):
                self.assertTrue(active)
                raise PermissionError('managed workflow')
            module.deny_native = deny
            with self.assertRaisesRegex(PermissionError, 'managed workflow'):
                namespace['relay'](app, {'workflow_id': 'app-1', 'user_id': 'user-1'})
            self.assertFalse(active)
