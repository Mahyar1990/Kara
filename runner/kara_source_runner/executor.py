"""Prepare isolated snapshots; never execute repository commands, hooks or Markdown."""
import json
import os
from pathlib import Path
import re
import signal
import shlex
import subprocess
import tempfile
import time
from uuid import UUID
from .contracts import workspace_files, repository_url, branch_name

class RunnerFailure(Exception):
    def __init__(self, code): self.code=code; super().__init__(code)

def git_environment(home, askpass):
    # Do not inherit Git configuration, shell injection options, proxies or trace outputs.
    env={k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','WINDIR','LANG','LC_ALL','TMPDIR','SSL_CERT_FILE','SSL_CERT_DIR')}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home), GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT='0', GIT_ASKPASS=str(askpass), SSH_ASKPASS=str(askpass), GIT_LFS_SKIP_SMUDGE='1')
    return env

def command(args, env, heartbeat, *, timeout=1200):
    options=['-c','credential.helper=','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',
        '-c','http.followRedirects=false','-c','protocol.allow=never','-c','protocol.https.allow=always',
        '-c','submodule.recurse=false','-c','fetch.fsckObjects=true','-c','transfer.fsckObjects=true']
    try:
        process=subprocess.Popen(['git',*options,*args],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
        start=time.monotonic()
        try:
            while True:
                try:
                    output,_=process.communicate(timeout=10)
                    break
                except subprocess.TimeoutExpired:
                    heartbeat()
                    if time.monotonic()-start>timeout: raise RunnerFailure('git_failed')
            if process.returncode: raise RunnerFailure('git_failed')
            return output.decode('ascii',errors='strict').strip()
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL); process.wait()
    except (OSError,UnicodeError): raise RunnerFailure('git_failed') from None

def validate_job(job):
    try:
        if str(UUID(job['id']))!=job['id']: raise ValueError()
        workspace_files(job['components'],job['documents'])
        for part in job['components']:
            if repository_url(part['url'])!=part['url']: raise ValueError()
            branch_name(part['branch'])
        return job
    except (ValueError,KeyError,TypeError): raise RunnerFailure('invalid_job') from None

def materialize(job, credentials, root, heartbeat, *, run=command, owner=None):
    validate_job(job)
    if not isinstance(credentials,dict) or set(credentials)!={p['key'] for p in job['components']}: raise RunnerFailure('invalid_job')
    root=Path(root).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o022:
        raise RunnerFailure('disk_error')
    target=root/job['id']
    try:
        # Exclusive directory prevents retries overwriting even a partially prepared workspace.
        target.mkdir(mode=0o700)
        private=target/'.kara'; private.mkdir(mode=0o700)
        results=[]
        for part in job['components']:
            heartbeat()
            token=credentials[part['key']]
            if not isinstance(token,str) or not token or any(ord(c)<33 or ord(c)>126 for c in token): raise RunnerFailure('invalid_job')
            cache=private/(part['key']+'.git'); destination=target/part['path']
            destination.parent.mkdir(parents=True,exist_ok=True)
            # Temporary private helper is removed on success or failure, outside any repository.
            with tempfile.TemporaryDirectory(prefix='kara-auth-') as temp:
                home=Path(temp); helper=home/'askpass'
                helper.write_text('#!/bin/sh\ncase "$1" in *Username*) printf "%s\\n" oauth2;; *) cat '+shlex.quote(str(home/'secret'))+';; esac\n')
                helper.chmod(0o700); secret=home/'secret'; secret.write_text(token+'\n'); secret.chmod(0o600)
                env=git_environment(home,helper)
                run(['init','--bare','--template=',str(cache)],env,heartbeat)
                run(['--git-dir',str(cache),'fetch','--no-tags','--no-recurse-submodules','--depth=1','--',part['url'],'+refs/heads/'+part['branch']+':refs/kara/source'],env,heartbeat)
                commit=run(['--git-dir',str(cache),'rev-parse','--verify','refs/kara/source^{commit}'],env,heartbeat)
                if not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',commit): raise RunnerFailure('git_failed')
                run(['--git-dir',str(cache),'worktree','add','--detach',str(destination),commit],env,heartbeat)
                results.append(dict(key=part['key'],commit=commit))
        for doc in job['documents']:
            path=target/doc['path']; path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('x',encoding='utf-8') as file: file.write(doc['content'])
        manifest=dict(schema_version=2,owner=owner,job_id=job['id'],revision=job['revision'],components=[dict(key=p['key'],path=p['path'],url=p['url'],branch=p['branch'],commit=r['commit']) for p,r in zip(job['components'],results)],documents=[d['path'] for d in job['documents']])
        (private/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        heartbeat()
        return results
    except RunnerFailure: raise
    except OSError: raise RunnerFailure('disk_error') from None
