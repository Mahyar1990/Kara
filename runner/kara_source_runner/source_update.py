"""Merge a remote branch into an existing worktree without deleting local work."""
import json
import os
from pathlib import Path
import re
import shlex
import tempfile
from uuid import UUID
from .executor import RunnerFailure, command, git_environment, validate_job


def update(job, credentials, root, heartbeat, *, owner, run=command):
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
        if manifest.get('owner') != owner or manifest.get('job_id') not in [*job.get('previous_job_ids', [job['update_of']]), job['id']]:
            raise ValueError()
        expected = lambda parts: [(p['key'], p['path'], p['url']) for p in parts]
        if expected(manifest['components']) != expected(job['components']):
            raise ValueError()
        if set(credentials) != {p['key'] for p in job['components']}:
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
                if git(['ls-files', '--unmerged']) or (destination / '.git').is_dir():
                    raise RunnerFailure('merge_conflict')
                # A previous failed merge must be resolved or aborted by its owner first.
                merge_head = Path(git(['rev-parse', '--git-path', 'MERGE_HEAD']))
                if not merge_head.is_absolute(): merge_head = destination / merge_head
                if merge_head.exists(): raise RunnerFailure('merge_conflict')
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
                    git(['stash', 'push', '--include-untracked', '-m', 'Kara update ' + job['id']])
                    stash = git(['rev-parse', 'refs/stash'])
                    git(['update-ref', backup + '/stash', stash])
                heartbeat()
                try:
                    git(['merge', '--no-edit', '--no-verify', '--no-gpg-sign', '--no-overwrite-ignore', remote])
                    if stash: git(['stash', 'apply', '--index', stash])
                except RunnerFailure:
                    # Never reset, clean, abort or drop the recovery stash on conflicts.
                    raise RunnerFailure('merge_conflict') from None
                results.append(dict(key=part['key'], commit=git(['rev-parse', 'HEAD'])))
        manifest.update(valid=True, revision=job['revision'], components=[dict(key=p['key'], path=p['path'], url=p['url'], branch=p['branch'], commit=r['commit']) for p, r in zip(job['components'], results)])
        heartbeat(); save()
        return results
    except RunnerFailure:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise RunnerFailure('workspace_update_failed') from None
