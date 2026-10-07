import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import prepare_product_context as context


class ProductContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.marker = self.source / "executed"
        package = {"dependencies": {"express": "^4.17.1", "private-lib": "https://fixture-secret.invalid"},
                   "scripts": {"test": "echo fixture-secret", "preinstall": "touch executed"}}
        (self.source / "package.json").write_text(json.dumps(package))
        (self.source / "package-lock.json").write_text(json.dumps({"dependencies": {"express": {"version": "4.17.3"}}}))
        (self.source / ".env").write_text("API_TOKEN=fixture-secret")
        (self.source / "README.md").write_text("fixture-secret")
        (self.source / "Dockerfile").write_text("FROM registry.fixture-secret.invalid/node:18.12.0\nENV TOKEN fixture-secret\n")
        (self.source / "src").mkdir()
        (self.source / "src/index.ts").write_text("import express from 'express'; // fixture-secret")

    def mapping(self):
        return {"product_id": "demo", "repositories": {"backend": {"path": str(self.source), "expected_framework": "nestjs"}}}

    def test_metadata_excludes_source_secrets_and_never_executes_scripts(self):
        result = context.collect(self.mapping())
        backend = result["repositories"]["backend"]
        self.assertEqual(backend["observed_framework"], "express")
        self.assertTrue(backend["framework_mismatch"])
        self.assertEqual(backend["dependencies"]["express"]["locked"], "4.17.3")
        self.assertEqual(backend["git"]["head"], None)
        self.assertEqual(result["repositories"]["newman"]["status"], "not_provided")
        self.assertFalse(result["technical_review_complete"])
        self.assertFalse(result["development_ready"])
        self.assertFalse(self.marker.exists())
        self.assertNotIn("fixture-secret", json.dumps(result) + context.render(result))
        self.assertEqual(backend["node_versions_declared_in_docker"][0]["node_tag"], "18.12.0")

    def test_private_output_requires_ignore_rule_and_uses_restricted_permissions(self):
        platform = self.root / "platform"
        platform.mkdir()
        subprocess.run(["git", "init", "-q", str(platform)], check=True)
        result = context.collect(self.mapping())
        with patch.object(context, "ROOT", platform):
            with self.assertRaises(ValueError):
                context.write_private(self.mapping(), result)
            self.assertFalse((platform / ".runtime").exists())
            (platform / ".gitignore").write_text(".runtime/\n")
            folder = context.write_private(self.mapping(), result)
        self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o700)
        for path in folder.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(json.loads((folder / "technical-context.local.json").read_text()), result)

    def test_source_evidence_changes_context_identity_and_symlink_is_excluded(self):
        previous = context.collect(self.mapping())
        (self.source / "src/index.ts").write_text("export const changed = true;")
        updated = context.collect(self.mapping())
        self.assertNotEqual(previous["context_id"], updated["context_id"])
        outside = self.root / "outside.md"
        outside.write_text("fixture-secret")
        (self.source / "README.md").unlink()
        (self.source / "README.md").symlink_to(outside)
        safe = context.collect(self.mapping())
        self.assertNotIn("README.md", [item["path"] for item in safe["repositories"]["backend"]["evidence"]])

    def test_requested_branch_is_used_instead_of_dirty_checkout_and_missing_ref_fails(self):
        def run(*args):
            return subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
                                  cwd=self.source, capture_output=True, text=True, check=True).stdout.strip()
        run("init", "-q", "-b", "main")
        run("add", "package.json", "package-lock.json", "README.md", "Dockerfile", "src/index.ts")
        run("commit", "-qm", "fixture baseline")
        run("switch", "-qc", "sandbox")
        (self.source / "package.json").write_text(json.dumps({"dependencies": {"@nestjs/core": "^10.0.0"}}))
        run("add", "package.json")
        run("commit", "-qm", "sandbox fixture")
        branch_commit = run("rev-parse", "HEAD")
        run("update-ref", "refs/remotes/origin/sandbox", branch_commit)
        run("switch", "-q", "main")
        checkout_head = run("rev-parse", "HEAD")
        (self.source / "package.json").write_text(json.dumps({"dependencies": {"express": "^4.17.1"}}))
        mapping = self.mapping()
        mapping["repositories"]["backend"]["ref"] = "origin/sandbox"
        result = context.collect(mapping)
        backend = result["repositories"]["backend"]
        self.assertEqual(backend["observed_framework"], "nestjs")
        self.assertFalse(backend["framework_mismatch"])
        self.assertEqual(backend["git"]["head"], branch_commit)
        self.assertEqual(backend["git"]["resolved_ref"], "refs/remotes/origin/sandbox")
        self.assertEqual(backend["git"]["checkout_head"], checkout_head)
        self.assertTrue(backend["git"]["working_tree_modified"])
        self.assertEqual(run("rev-parse", "HEAD"), checkout_head)
        mapping["repositories"]["backend"]["ref"] = "origin/missing"
        with self.assertRaises(ValueError):
            context.collect(mapping)

    def test_postman_requests_and_events_are_counted_without_exporting_values(self):
        collection = {"info": {"name": "fixture-secret", "description": "x" * (context.MAX_METADATA_BYTES + 1)}, "variable": [{"value": "fixture-secret"}],
                      "item": [{"item": [{"request": {"url": "https://fixture-secret.invalid", "header": [{"value": "fixture-secret"}]},
                                          "event": [{"listen": "test", "script": {"exec": ["fixture-secret"]}}]}]}]}
        (self.source / "test.postman_collection.json").write_text(json.dumps(collection))
        mapping = {"product_id": "demo", "repositories": {"newman": {"path": str(self.source)}}}
        result = context.collect(mapping)
        metadata = result["repositories"]["newman"]["postman_collections"][0]
        self.assertEqual(metadata["status"], "inspected")
        self.assertEqual(metadata["request_count"], 1)
        self.assertEqual(metadata["test_event_count"], 1)
        self.assertNotIn("fixture-secret", json.dumps(result) + context.render(result))
        with patch.object(context, "MAX_COLLECTION_BYTES", 1):
            limited = context.collect(mapping)
        self.assertEqual(limited["repositories"]["newman"]["postman_collections"][0]["status"], "unavailable_or_over_size_limit")
        self.assertIn({"role": "newman", "type": "postman_metadata_unavailable"}, limited["issues"])


if __name__ == "__main__":
    unittest.main()
