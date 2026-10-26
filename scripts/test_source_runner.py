"""Local Git fixtures prove real detached worktrees and no credential leakage."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runner'))
from kara_source_runner.contracts import branch_name, repository_url, relative_path, workspace_files, repository_on_connection
from kara_source_runner.executor import command, materialize, RunnerFailure, validate_job
from kara_source_runner.client import server_url

class SourceRunnerTests(unittest.TestCase):
    def test_reject_paths_branches_destinations_and_insecure_api(self):
        for value in ('../escape','/tmp/a','a//b','a/.git','a/../b','a\\b'):
            with self.assertRaises(ValueError): relative_path(value)
        for value in ('--upload-pack=evil','a..b','a.lock','a@{1}','a b','a~1'):
            with self.assertRaises(ValueError): branch_name(value)
        for value in ('http://git.test/a/b','https://secret@git.test/a/b','https://git.test/a/b?x=secret'):
            with self.assertRaises(ValueError): repository_url(value)
        with self.assertRaises(ValueError): repository_on_connection('https://git.test/other/repo','https://git.test/installation')
        with self.assertRaises(ValueError): server_url('http://kara.test')
        self.assertEqual(server_url('http://localhost:8080/'),'http://localhost:8080')
        with self.assertRaises(ValueError): workspace_files([dict(key='one',path='app')],[dict(path='app/a.md',content='x')])

    def test_real_two_repo_detached_snapshots_docs_immutable_retry_and_no_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp); repos={}; shas={}
            for key in ('backend','frontend'):
                repo=tmp/key; subprocess.run(['git','init','-q','-b','sandbox',str(repo)],check=True)
                (repo/'README.md').write_text('# '+key)
                subprocess.run(['git','-C',str(repo),'add','README.md'],check=True)
                subprocess.run(['git','-C',str(repo),'-c','user.name=Synthetic','-c','user.email=test@example.test','commit','-qm','fixture'],check=True)
                repos['https://git.example.test/group/'+key+'.git']=repo
                shas[key]=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            job=dict(id=str(uuid4()),revision=1,components=[dict(key=k,path='services/'+k,url=url,branch='sandbox') for url,k in [(u,Path(u).stem) for u in repos]],documents=[dict(path='docs/map.md',content='# backend → frontend')])
            calls=[]
            def fixture_run(args,env,heartbeat):
                calls.append(args)
                if 'fetch' in args:
                    # Fixture replaces only transport; production executor remains HTTPS-only.
                    args=[str(repos.get(a,a)) for a in args]
                    args=['-c','protocol.file.allow=always',*args]
                return command(args,env,heartbeat)
            result=materialize(job,dict(backend='synthetic-secret',frontend='synthetic-secret'),tmp/'workspaces',lambda:None,run=fixture_run)
            target=tmp/'workspaces'/job['id']
            self.assertEqual({r['key']:r['commit'] for r in result},shas)
            for key in ('backend','frontend'):
                repo=target/'services'/key
                self.assertTrue((repo/'.git').is_file())
                self.assertEqual(subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),shas[key])
                self.assertNotEqual(subprocess.run(['git','-C',str(repo),'symbolic-ref','-q','HEAD'],capture_output=True).returncode,0)
            self.assertEqual((target/'docs/map.md').read_text(),'# backend → frontend')
            self.assertNotIn('synthetic-secret',json.dumps(calls))
            for p in (target/'.kara').rglob('*'):
                if p.is_file() and p.suffix in ('.json','.git') or p.name=='config': self.assertNotIn(b'synthetic-secret',p.read_bytes())
            (target/'services/backend/README.md').write_text('local user edit')
            with self.assertRaises(RunnerFailure): materialize(job,dict(backend='secret',frontend='secret'),tmp/'workspaces',lambda:None,run=fixture_run)
            self.assertEqual((target/'services/backend/README.md').read_text(),'local user edit')

    def test_cancellation_heartbeat_stops_before_any_git(self):
        job=dict(id=str(uuid4()),revision=1,components=[dict(key='a',path='a',url='https://git.test/g/a.git',branch='sandbox')],documents=[])
        with tempfile.TemporaryDirectory() as tmp:
            def stop(): raise RuntimeError('cancelled')
            with self.assertRaises(RuntimeError): materialize(job,{'a':'synthetic'},tmp,stop)
            self.assertFalse((Path(tmp)/job['id']/'a').exists())
