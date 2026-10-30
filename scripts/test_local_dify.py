"""Readiness must tolerate an upstream closing its socket during startup."""
from contextlib import redirect_stdout
from http.client import RemoteDisconnected
import io
import unittest
from unittest.mock import patch

import local_dify


class ReadinessTests(unittest.TestCase):
    @patch.object(local_dify, 'settings', return_value={'DIFY_HTTP_PORT': '8080'})
    @patch.object(local_dify.time, 'sleep')
    def test_startup_disconnect_is_retried_until_pong(self, _sleep, _settings):
        response = io.BytesIO(b'{"result":"pong"}')
        with patch.object(local_dify, 'local_open',
                          side_effect=[RemoteDisconnected('startup'), response]) as request, redirect_stdout(io.StringIO()):
            local_dify.wait_for_api(timeout=10)
        self.assertEqual(request.call_count, 2)

    @patch.object(local_dify, 'settings', return_value={'DIFY_HTTP_PORT': '8080'})
    @patch.object(local_dify.time, 'sleep')
    def test_repeated_disconnect_still_respects_deadline(self, _sleep, _settings):
        with patch.object(local_dify.time, 'monotonic', side_effect=[0, 0, 11]), \
             patch.object(local_dify, 'local_open', side_effect=RemoteDisconnected('startup')), \
             redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, 'did not become ready'):
            local_dify.wait_for_api(timeout=10)
