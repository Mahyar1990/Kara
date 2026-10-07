import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import prepare_product_context as metadata
import prepare_product_knowledge as knowledge


class ProductKnowledgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.run_git('init', '-q', '-b', 'main')
        self.put('AGENTS.md', '# Rules\nDo not merge. Read PROJECT_MAP.md.\n')
        self.put('PROJECT_MAP.md', '# Map\n## Architecture\nUse adjacent modules.\n')
        self.put('doc/api/example.md', '# Example API\nGET /repositories\nAuthorization: Bearer fixtureSECRET123456\n{"apiToken": "fixture-secret"}\nhttps://fixture-secret.invalid/v1/repositories?token=fixture-secret\n')
        self.put('docs/README.md', '# Index\nSee domain.md\n')
        self.put('.agents/skills/example/SKILL.md', '# Workflow\nNever run live writes.\n')
        self.put('doc/cert.md', '-----BEGIN PRIVATE KEY-----\nfixture-secret\n')
        self.put('doc/table.xlsx', 'not really a spreadsheet')
        self.put('private.txt', 'fixture-secret')
        (self.root / 'doc/outside.md').symlink_to('../private.txt')
        self.run_git('add', '.')
        self.run_git('commit', '-qm', 'fixture')
        self.run_git('update-ref', 'refs/remotes/origin/sandbox', self.run_git('rev-parse', 'HEAD'))
        self.mapping = {'product_id': 'demo', 'repositories': {role: {'path': str(self.root), 'ref': 'origin/sandbox'} for role in ('backend', 'client')}}
        self.context = metadata.collect(self.mapping)

    def run_git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', *args],
                              cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_catalog_uses_pinned_docs_and_excludes_credentials_keys_and_symlinks(self):
        self.put('doc/api/example.md', '# Uncommitted replacement\n')
        result = knowledge.collect_knowledge(self.mapping, self.context)
        by_id = {s['id']: s for s in result['sources']}
        doc = by_id['backend:doc/api/example.md']
        self.assertIn('GET /repositories', doc['content'])
        self.assertNotIn('Uncommitted', doc['content'])
        self.assertNotIn('fixture-secret', json.dumps(result))
        self.assertNotIn('fixtureSECRET', json.dumps(result))
        self.assertEqual(by_id['backend:AGENTS.md']['kind'], 'repository_policy')
        self.assertEqual(by_id['backend:.agents/skills/example/SKILL.md']['kind'], 'workflow')
        self.assertEqual(by_id['backend:doc/cert.md']['status'], 'blocked_key_material')
        self.assertEqual(by_id['backend:doc/table.xlsx']['status'], 'indexed_without_text')
        self.assertNotIn('backend:doc/outside.md', by_id)
        self.assertTrue(result['human_data_review_required'])
        self.assertFalse(result['development_ready'])

    def test_missing_policy_and_limits_are_explicit_and_changed_paths_require_refresh(self):
        with patch.object(knowledge, 'MAX_DOCUMENT_BYTES', 1):
            result = knowledge.collect_knowledge(self.mapping, self.context)
        self.assertTrue(result['issues'])
        self.assertNotIn('content', result['sources'][0])
        self.run_git('rm', 'AGENTS.md')
        self.run_git('commit', '-qm', 'remove policy')
        self.run_git('update-ref', 'refs/remotes/origin/sandbox', self.run_git('rev-parse', 'HEAD'))
        result = knowledge.collect_knowledge(self.mapping, metadata.collect(self.mapping))
        self.assertIn({'role': 'backend', 'path': 'AGENTS.md', 'type': 'required_source_missing'}, result['issues'])
        self.mapping['repositories']['client']['path'] = str(self.root / 'other')
        with self.assertRaises(ValueError):
            knowledge.collect_knowledge(self.mapping, self.context)


if __name__ == '__main__':
    unittest.main()
