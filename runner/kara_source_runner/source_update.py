"""Merge a remote branch into an existing worktree without deleting local work."""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import stat
import tempfile
from uuid import UUID
from .executor import RunnerFailure, command, git_environment, validate_job


def update(job, credentials, root, heartbeat, *, owner, run=command):
    validate_job(job)
    try:
        root = Path(root).expanduser().resolve()
        directory = str(UUID(job['local_directory']))
        private = root / directory / '.kara'
        if directory != job['local_directory'] or (root / directory).is_symlink() or private.is_symlink():
            raise ValueError()
        # A cancelled/expired server job can still be stopping in another process.
        # The OS releases this lock on crashes; never unlink a live lock file.
        fd = os.open(private / 'update.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'w') as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode): raise ValueError()
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RunnerFailure('workspace_busy') from None
            return _update_locked(job, credentials, root, heartbeat, owner=owner, run=run)
    except (OSError, ValueError, KeyError, TypeError):
        raise RunnerFailure('workspace_update_failed') from None


def _update_locked(job, credentials, root, heartbeat, *, owner, run):
    validate_job(job)
    try:
        directory = str(UUID(job['local_directory']))
        if directory != job['local_directory'] or not owner:
            raise ValueError()
        root = Path(root).expanduser().resolve()
        target = root / directory
        private = target / '.kara'
        mark = private / 'manifest.json'
        def safe(path):
            return (path.resolve().is_relative_to(target.resolve())
                    and all(not p.is_symlink() for p in [path, *path.parents] if p != root and root in p.parents))
        if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o022 or target.is_symlink() or not safe(mark):
            raise ValueError()
        manifest = json.loads(mark.read_text())
        if not isinstance(manifest, dict) or not isinstance(manifest.get('pending_stashes', {}), dict): raise ValueError()
        if manifest.get('owner') != owner or manifest.get('job_id') not in [*job.get('previous_job_ids', [job['update_of']]), job['id']]:
            raise ValueError()
        expected = lambda parts: [(p['key'], p['path'], p['url']) for p in parts]
        if expected(manifest['components']) != expected(job['components']):
            raise ValueError()
        if not isinstance(credentials, dict) or set(credentials) != {p['key'] for p in job['components']}:
            raise ValueError()
        # Invalidate the previous snapshot before any file mutation, also on interruption.
        manifest.update(job_id=job['id'], valid=False)
        temp_mark = private / 'manifest.next'
        if temp_mark.is_symlink(): raise ValueError()
        def save():
            temp_mark.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
            os.replace(temp_mark, mark)
        heartbeat(); save()
        results = []
        for part in job['components']:
            destination = target / part['path']
            cache = private / (part['key'] + '.git')
            if not safe(destination) or not safe(cache) or not safe(destination / '.git'):
                raise ValueError()
            token = credentials[part['key']]
            if not isinstance(token, str) or not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
                raise ValueError()
            with tempfile.TemporaryDirectory(prefix='kara-auth-') as temp:
                home = Path(temp); helper = home / 'askpass'; secret = home / 'secret'
                helper.write_text('#!/bin/sh\ncase "$1" in *Username*) printf "%s\\n" oauth2;; *) cat ' + shlex.quote(str(secret)) + ';; esac\n')
                helper.chmod(0o700); secret.write_text(token + '\n'); secret.chmod(0o600)
                env = git_environment(home, helper)
                git = lambda args: run(['-c', 'user.name=Kara Runner', '-c', 'user.email=kara-runner@localhost', '-c', 'commit.gpgsign=false', '-C', str(destination), *args], env, heartbeat)
                # Refuse a worktree whose .git link was redirected to another repository.
                observed = Path(git(['rev-parse', '--git-common-dir']))
                if not observed.is_absolute(): observed = destination / observed
                if observed.resolve() != cache.resolve() or Path(git(['rev-parse', '--show-toplevel'])).resolve() != destination.resolve(): raise ValueError()
                pending = manifest.setdefault('pending_stashes', {})
                def clear_pending():
                    pending.pop(part['key'], None)
                    save()
                if git(['ls-files', '--unmerged']) or (destination / '.git').is_dir():
                    if part['key'] in pending: clear_pending()
                    raise RunnerFailure('merge_conflict')
                # A previous failed merge must be resolved or aborted by its owner first.
                merge_head = Path(git(['rev-parse', '--git-path', 'MERGE_HEAD']))
                if not merge_head.is_absolute(): merge_head = destination / merge_head
                if merge_head.exists():
                    if part['key'] in pending: clear_pending()
                    raise RunnerFailure('merge_conflict')
                recovery = pending.get(part['key'])
                if recovery:
                    # Recover even a crash between stash push and saving its SHA/ref.
                    recovery_ref = 'refs/kara/backups/' + str(UUID(recovery['job_id'])) + '/stash'
                    sha = git(['for-each-ref', '--format=%(objectname)', recovery_ref])
                    if not sha and git(['for-each-ref', '--format=%(objectname)', 'refs/stash']):
                        entries = git(['reflog', 'show', '--format=%H%x00%gs', 'refs/stash']).splitlines()
                        matches = [entry.split('\0')[0] for entry in entries if entry.endswith('Kara update ' + recovery['job_id'])]
                        if matches: sha = matches[0]
                    if sha:
                        if not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', sha): raise ValueError()
                        git(['update-ref', recovery_ref, sha])
                        try:
                            git(['stash', 'apply', '--index', sha])
                        except RunnerFailure:
                            # Explicit conflict recovery uses the retained stash, as
                            # for a normal merge conflict; never hide it as success.
                            clear_pending()
                            raise RunnerFailure('merge_conflict') from None
                    clear_pending()
                fetch = ['--git-dir', str(cache), 'fetch', '--no-tags', '--no-recurse-submodules']
                if (cache / 'shallow').exists(): fetch += ['--unshallow']
                run([*fetch, '--', part['url'], '+refs/heads/' + part['branch'] + ':refs/kara/source'], env, heartbeat)
                remote = git(['rev-parse', '--verify', 'refs/kara/source^{commit}'])
                if not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', remote): raise ValueError()
                # Keep both commits and dirty/untracked files recoverable under durable refs.
                backup = 'refs/kara/backups/' + job['id']
                git(['update-ref', backup + '/head', 'HEAD'])
                stash = None
                if git(['status', '--porcelain', '--untracked-files=all']):
                    pending[part['key']] = dict(job_id=job['id'])
                    save()
                    git(['stash', 'push', '--include-untracked', '-m', 'Kara update ' + job['id']])
                    stash = git(['rev-parse', 'refs/stash'])
                    git(['update-ref', backup + '/stash', stash])
                heartbeat()
                try:
                    git(['merge', '--no-edit', '--no-verify', '--no-gpg-sign', '--no-overwrite-ignore', remote])
                    if stash:
                        git(['stash', 'apply', '--index', stash])
                        clear_pending()
                except RunnerFailure:
                    # Never reset, clean, abort or drop the recovery stash on conflicts.
                    if part['key'] in pending: clear_pending()
                    raise RunnerFailure('merge_conflict') from None
                results.append(dict(key=part['key'], commit=git(['rev-parse', 'HEAD'])))
        manifest.update(valid=True, revision=job['revision'], components=[dict(key=p['key'], path=p['path'], url=p['url'], branch=p['branch'], commit=r['commit']) for p, r in zip(job['components'], results)])
        heartbeat(); save()
        return results
    except RunnerFailure:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise RunnerFailure('workspace_update_failed') from None
