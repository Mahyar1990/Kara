"""Server deployment configuration: opt-in network and private build inputs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import local_dify
import build_environment


class DeploymentSettingsTests(unittest.TestCase):
    def settings(self, text):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env.local').write_text(text)
            with patch.object(local_dify, 'ROOT', root):
                return local_dify.settings()

    def test_defaults_are_loopback_and_socket_follows_browser_origin(self):
        values = self.settings('')
        self.assertEqual(values['DIFY_BIND_ADDRESS'], '127.0.0.1')
        self.assertEqual(local_dify.public_environment(values)['NEXT_PUBLIC_SOCKET_URL'], 'ws://localhost')

    def test_remote_https_origin_is_consistent(self):
        values = self.settings('DIFY_BIND_ADDRESS=0.0.0.0\nDIFY_PUBLIC_URL=https://kara.example:9443/\n')
        public = local_dify.public_environment(values)
        self.assertEqual(public['NEXT_PUBLIC_SOCKET_URL'], 'wss://kara.example:9443')
        self.assertEqual(public['CONSOLE_API_URL'], 'https://kara.example:9443')

    def test_rejects_network_without_origin_and_unsafe_urls(self):
        for text in ('DIFY_BIND_ADDRESS=0.0.0.0', 'DIFY_BIND_ADDRESS=example.com',
                     'DIFY_PUBLIC_URL=http://user:password@example.com',
                     'DIFY_PUBLIC_URL=https://example.com/path',
                     'KARA_NPM_REGISTRY=http://example.com', 'KARA_TOOLS_IMAGE=x y'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.settings(text)

    def test_ca_is_private_optional_and_never_accepts_a_private_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ca = root / 'ca.crt'
            with patch.object(local_dify, 'ROOT', root), patch.dict('os.environ', {}, clear=True):
                (root / '.env.local').write_text('')
                self.assertEqual(build_environment.ca_bytes(), b'')
                (root / '.env.local').write_text('KARA_CA_BUNDLE=ca.crt\n')
                ca.write_text((Path(__file__).parent / 'fixtures/build-test-ca.pem').read_text())
                self.assertIn(b'BEGIN CERTIFICATE', build_environment.ca_bytes())
                ca.write_text('-----BEGIN PRIVATE KEY-----')
                with self.assertRaises(ValueError):
                    build_environment.ca_bytes()

    def test_rejects_malformed_pem_before_writing_build_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env.local').write_text('KARA_CA_BUNDLE=ca.crt\n')
            (root / 'ca.crt').write_text('-----BEGIN CERTIFICATE-----\nnot-a-certificate\n-----END CERTIFICATE-----')
            output = root / 'build-ca.crt'
            output.write_text('previous validated input')
            with patch.object(local_dify, 'ROOT', root), patch.dict('os.environ', {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'valid PEM'):
                    build_environment.prepare_ca(output)
            self.assertEqual(output.read_text(), 'previous validated input')

    def test_ca_bundle_with_non_ascii_annotations_preserves_bytes_and_trust(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env.local').write_text('KARA_CA_BUNDLE=ca.crt\n')
            certificate = (Path(__file__).parent / 'fixtures/build-test-ca.pem').read_bytes()
            data = b'# Organization annotation: \x82\n' + certificate
            (root / 'ca.crt').write_bytes(data)
            with patch.object(local_dify, 'ROOT', root), patch.dict('os.environ', {}, clear=True):
                self.assertEqual(build_environment.ca_bytes(), data.rstrip() + b'\n')
                build_environment.configure_ca()
                self.assertEqual(build_environment.os.environ['SSL_CERT_FILE'], str(root / 'ca.crt'))
                output = root / 'build-ca.crt'
                build_environment.prepare_ca(output)
                self.assertEqual(output.read_bytes(), data.rstrip() + b'\n')
