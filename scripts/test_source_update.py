"""Real local Git merges exercise source updates without contacting any service."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runner'))
from kara_source_runner.executor import command, materialize, RunnerFailure
from kara_source_runner.source_update import update


class SourceUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.upstream = self.root / 'remote'
        self.git(['init', '-q', '-b', 'sandbox', str(self.upstream)])
        (self.upstream / 'base.txt').write_text('base\n')
        (self.upstream / 'dirty.txt').write_text('dirty base\n')
        self.commit(self.upstream, 'initial')
        self.job = dict(id=str(uuid4()), revision=1, components=[dict(key='app', path='app', url='https://git.test/team/app.git', branch='sandbox')], documents=[])
        self.workspaces = self.root / 'workspaces'
        self.calls = []
        self.credentials = dict(app='synthetic-token')
        materialize(self.job, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
        self.target = self.workspaces / self.job['id']; self.local = self.target / 'app'
        self.request = dict(self.job, id=str(uuid4()), update_of=self.job['id'], local_directory=self.job['id'])

    def git(self, args, cwd=None):
        return subprocess.check_output(['git', '-c', 'user.name=Synthetic', '-c', 'user.email=fixture@example.test', *args], cwd=cwd, stderr=subprocess.DEVNULL).decode().strip()

    def commit(self, path, message):
        self.git(['add', '.'], path); self.git(['commit', '-qm', message], path)
        return self.git(['rev-parse', 'HEAD'], path)

    def run_git(self, args, env, heartbeat):
        self.calls.append(args)
        args = [str(self.upstream) if a == 'https://git.test/team/app.git' else a for a in args]
        return command(['-c', 'protocol.file.allow=always', *args], env, heartbeat)

    def test_merges_commits_staged_unstaged_and_untracked_in_same_directory(self):
        (self.local / 'local.txt').write_text('local commit\n'); local_commit = self.commit(self.local, 'local')
        (self.local / 'dirty.txt').write_text('staged\n'); self.git(['add', 'dirty.txt'], self.local)
        (self.local / 'dirty.txt').write_text('staged and unstaged\n')
        (self.local / 'untracked.txt').write_text('keep\n')
        (self.upstream / 'remote.txt').write_text('remote commit\n'); remote_commit = self.commit(self.upstream, 'remote')
        result = update(self.request, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
        head = self.git(['rev-parse', 'HEAD'], self.local)
        self.assertEqual(result, [dict(key='app', commit=head)])
        for sha in [local_commit, remote_commit]: self.git(['merge-base', '--is-ancestor', sha, 'HEAD'], self.local)
        self.assertEqual((self.local / 'dirty.txt').read_text(), 'staged and unstaged\n')
        self.assertEqual(self.git(['show', ':dirty.txt'], self.local), 'staged')
        self.assertEqual((self.local / 'untracked.txt').read_text(), 'keep\n')
        self.assertEqual([p.name for p in self.workspaces.iterdir()], [self.job['id']])
        manifest = json.loads((self.target / '.kara/manifest.json').read_text())
        self.assertTrue(manifest['valid']); self.assertEqual(manifest['job_id'], self.request['id'])
        self.assertNotIn('synthetic-token', json.dumps(self.calls))
        # Subsequent updates reuse the original directory, not the previous request ID.
        second = dict(self.request, id=str(uuid4()), update_of=self.request['id'])
        update(second, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
        self.assertEqual([p.name for p in self.workspaces.iterdir()], [self.job['id']])

    def test_conflicting_commits_preserve_both_heads_and_dirty_stash(self):
        (self.local / 'base.txt').write_text('local version\n'); local = self.commit(self.local, 'local')
        (self.local / 'untracked.txt').write_text('untracked backup\n')
        (self.upstream / 'base.txt').write_text('remote version\n'); remote = self.commit(self.upstream, 'remote')
        with self.assertRaises(RunnerFailure) as failure:
            update(self.request, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
        self.assertEqual(failure.exception.code, 'merge_conflict')
        self.assertEqual(self.git(['rev-parse', 'HEAD'], self.local), local)
        self.assertEqual(self.git(['rev-parse', 'MERGE_HEAD'], self.local), remote)
        ref = 'refs/kara/backups/' + self.request['id'] + '/stash'
        self.assertEqual(self.git(['show', ref + '^3:untracked.txt'], self.local), 'untracked backup')
        self.assertFalse(json.loads((self.target / '.kara/manifest.json').read_text())['valid'])
        self.assertTrue(self.git(['ls-files', '--unmerged'], self.local))
        # Human resolution followed by retry keeps the same folder and can finish.
        (self.local / 'base.txt').write_text('local and remote resolved\n')
        self.commit(self.local, 'resolve conflict')
        self.git(['stash', 'apply', '--index', ref], self.local)
        retry = dict(self.request, id=str(uuid4()), update_of=self.request['id'])
        update(retry, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
        self.assertEqual((self.local / 'untracked.txt').read_text(), 'untracked backup\n')
        self.assertEqual([p.name for p in self.workspaces.iterdir()], [self.job['id']])

    def test_stash_apply_conflict_keeps_original_change_recoverable(self):
        (self.local / 'base.txt').write_text('dirty local\n')
        (self.upstream / 'base.txt').write_text('remote version\n'); self.commit(self.upstream, 'remote')
        with self.assertRaises(RunnerFailure) as failure:
            update(self.request, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
        self.assertEqual(failure.exception.code, 'merge_conflict')
        ref = 'refs/kara/backups/' + self.request['id'] + '/stash'
        self.assertEqual(self.git(['show', ref + ':base.txt'], self.local), 'dirty local')

    def test_ignored_file_is_not_overwritten_by_remote_merge(self):
        (self.local / '.gitignore').write_text('private.txt\n'); self.commit(self.local, 'local ignore')
        (self.local / 'private.txt').write_text('private local content\n')
        (self.upstream / 'private.txt').write_text('remote file\n'); self.commit(self.upstream, 'remote file')
        with self.assertRaises(RunnerFailure):
            update(self.request, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
        self.assertEqual((self.local / 'private.txt').read_text(), 'private local content\n')

    def test_interruption_after_stash_push_recovers_dirty_files_on_retry(self):
        (self.local / 'dirty.txt').write_text('staged change\n'); self.git(['add', 'dirty.txt'], self.local)
        (self.local / 'dirty.txt').write_text('staged plus unstaged\n')
        (self.local / 'untracked.txt').write_text('must return\n')
        (self.upstream / 'new.txt').write_text('new remote\n'); self.commit(self.upstream, 'remote')
        def interrupted(args, env, heartbeat):
            result = self.run_git(args, env, heartbeat)
            if 'stash' in args and 'push' in args: raise RuntimeError('lost connection')
            return result
        with self.assertRaises(RuntimeError):
            update(self.request, self.credentials, self.workspaces, lambda: None, owner='owner', run=interrupted)
        self.assertFalse((self.local / 'untracked.txt').exists())
        retry = dict(self.request, id=str(uuid4()), update_of=self.request['id'])
        update(retry, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
        self.assertEqual((self.local / 'untracked.txt').read_text(), 'must return\n')
        self.assertEqual((self.local / 'dirty.txt').read_text(), 'staged plus unstaged\n')
        self.assertEqual(self.git(['show', ':dirty.txt'], self.local), 'staged change')
        self.assertTrue((self.local / 'new.txt').is_file())
        self.assertFalse(json.loads((self.target / '.kara/manifest.json').read_text())['pending_stashes'])
        self.assertEqual([p.name for p in self.workspaces.iterdir()], [self.job['id']])

    def test_running_local_update_is_exclusive_and_crash_lock_is_reusable(self):
        lock_path = self.target / '.kara/update.lock'
        with lock_path.open('w') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(RunnerFailure) as failure:
                update(self.request, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
            self.assertEqual(failure.exception.code, 'workspace_busy')
            self.assertEqual(json.loads((self.target / '.kara/manifest.json').read_text())['job_id'], self.job['id'])
        update(self.request, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)

    def test_malformed_recovery_metadata_fails_without_touching_worktree(self):
        mark = self.target / '.kara/manifest.json'
        original = json.loads(mark.read_text())
        for malformed in [[], dict(original, pending_stashes=[])]:
            mark.write_text(json.dumps(malformed))
            with self.assertRaises(RunnerFailure) as failure:
                update(self.request, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
            self.assertEqual(failure.exception.code, 'workspace_update_failed')
            self.assertEqual((self.local / 'base.txt').read_text(), 'base\n')

    def test_wrong_owner_symlink_and_cancel_do_not_mutate_files(self):
        with self.assertRaises(RunnerFailure): update(self.request, self.credentials, self.workspaces, lambda: None, owner='other', run=self.run_git)
        def cancel(): raise RuntimeError('cancelled')
        with self.assertRaises(RuntimeError): update(self.request, self.credentials, self.workspaces, cancel, owner='owner', run=self.run_git)
        self.assertEqual(json.loads((self.target / '.kara/manifest.json').read_text())['job_id'], self.job['id'])
        (self.target / 'app').rename(self.target / 'original')
        (self.target / 'app').symlink_to(self.target / 'original', target_is_directory=True)
        with self.assertRaises(RunnerFailure): update(self.request, self.credentials, self.workspaces, lambda: None, owner='owner', run=self.run_git)
        self.assertEqual((self.target / 'original/base.txt').read_text(), 'base\n')
