import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import check_company_model as model


class CompanyModelProbeTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "base_url": "https://model.example.com/v1",
            "model": "fixture-model", "api_token": "fixture-secret",
            "extra_headers": {"x-client-id": "fixture-client", "Cookie": "fixture-cookie"},
        }

    def test_non_https_and_authorization_override_are_rejected(self):
        for config in (
            {**self.config, "base_url": "http://model.example.com/v1"},
            {**self.config, "base_url": "https://user:secret@model.example.com/v1"},
            {**self.config, "extra_headers": {"authorization": "wrong"}},
            {**self.config, "extra_headers": {"x-user-id": "value\r\nHost: other.example.com"}},
        ):
            with self.assertRaises(ValueError):
                model.validate_config(config)

    def test_bearer_is_only_in_header_and_response_body_is_not_reported(self):
        body = json.dumps({"choices": [{"message": {"role": "assistant", "content": "fixture-secret"}}]}).encode()
        response = io.BytesIO(body)
        response.status = 200
        with patch.object(model.urllib.request, "build_opener") as create:
            create.return_value.open.return_value = response
            report = model.probe(self.config, 20)
            request = create.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://model.example.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-secret")
        self.assertEqual(request.get_header("X-client-id"), "fixture-client")
        self.assertNotIn(b"fixture-secret", request.data)
        self.assertEqual(report["result"], "ok")
        self.assertNotIn("fixture-secret", json.dumps(report))

    def test_error_body_is_not_reported_and_redirects_are_blocked(self):
        error = urllib.error.HTTPError(self.config["base_url"], 401, "fixture-secret", {}, io.BytesIO(b"fixture-secret"))
        with patch.object(model.urllib.request, "build_opener") as create:
            create.return_value.open.side_effect = error
            self.assertEqual(model.probe(self.config, 20), {"result": "http_error", "http_status": 401})
            handlers = create.call_args.args
        redirect = next(handler for handler in handlers if isinstance(handler, model.NoRedirect))
        self.assertIsNone(redirect.redirect_request(None, None, 307, "redirect", {}, "https://other.example.com"))

    def test_credentials_are_passed_to_container_only_on_stdin(self):
        with patch.object(model.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '{"result":"ok","http_status":200}', "")) as run:
            model.container_probe(self.config, "fixture-container", 20)
        args = run.call_args.args[0]
        self.assertNotIn("fixture-secret", " ".join(args))
        self.assertEqual(json.loads(run.call_args.kwargs["input"])["api_token"], "fixture-secret")

    def test_private_file_is_required_and_public_permissions_are_rejected(self):
        root = Path(model.__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory(dir=root) as folder:
            path = Path(folder) / "connection.local.json"
            path.write_text(json.dumps(self.config))
            path.chmod(0o600)
            self.assertEqual(model.load_private_config(path)["model"], "fixture-model")
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                model.load_private_config(path)
            path.chmod(0o600)
            unignored = path.with_name("connection.json")
            path.rename(unignored)
            with self.assertRaises(ValueError):
                model.load_private_config(unignored)

    def test_worker_starts_from_inline_source_and_hides_invalid_credentials(self):
        config = {**self.config, "base_url": "http://model.example.com/v1"}
        process = subprocess.run(
            [sys.executable, "-c", Path(model.__file__).read_text(), "--worker"],
            input=json.dumps(config), text=True, capture_output=True, timeout=5,
        )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(process.stdout), {"result": "request_error"})
        self.assertNotIn("fixture-secret", process.stdout + process.stderr)

    def test_json_success_without_assistant_message_is_not_a_model_success(self):
        for body in (b'{"result":"ok"}', b'{"choices":[]}', b'{"choices":[{"message":{"role":"assistant","content":""}}]}'):
            response = io.BytesIO(body)
            response.status = 200
            with patch.object(model.urllib.request, "build_opener") as create:
                create.return_value.open.return_value = response
                self.assertEqual(model.probe(self.config, 20)["result"], "invalid_response")


if __name__ == "__main__":
    unittest.main()
