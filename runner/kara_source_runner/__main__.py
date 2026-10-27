"""Run with python3 -m kara_source_runner; credentials never appear in arguments."""
import argparse
import getpass
import json
import os
from pathlib import Path
import stat
import shutil
import time
from .client import Client, ApiError
from .execution_worker import execute as execute_workflow, flush_outbox, owner_id
from .executor import materialize, RunnerFailure, validate_job
from . import harness_runtime

def save_config(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Never overwrite an existing device registration or follow a symlink.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as file: json.dump(value,file)

def main():
    parser=argparse.ArgumentParser(description='Kara local source Runner (Python 3.10+, Git required).')
    parser.add_argument('--config',type=Path,default=Path.home()/'.config/kara-source-runner/device.json')
    sub=parser.add_subparsers(dest='action',required=True)
    pair=sub.add_parser('pair'); pair.add_argument('--server',required=True)
    run=sub.add_parser('run'); run.add_argument('--root',type=Path,default=Path.home()/'KaraSourceWorkspaces'); run.add_argument('--once',action='store_true'); run.add_argument('--python-image',default='kara/code-python:2.0'); run.add_argument('--javascript-image',default='node:22-alpine'); run.add_argument('--allow-worktree-write',action='store_true'); run.add_argument('--code-backend',choices=['auto','docker','process'],default='auto'); run.add_argument('--allow-local-code',action='store_true')
    run.add_argument('--allow-harness',action='store_true');run.add_argument('--harness-config',type=Path,default=Path.home()/'.config/kara-source-runner/harnesses.json')
    harness=sub.add_parser('harness-prepare');harness.add_argument('--attempt',required=True);harness.add_argument('--root',type=Path,default=Path.home()/'KaraSourceWorkspaces')
    args=parser.parse_args()
    try:
        if args.action=='pair':
            if args.config.exists() or args.config.is_symlink(): raise ValueError('Device config already exists; use another --config path.')
            client=Client(args.server); value=client.post('pair',dict(code=getpass.getpass('One-time pairing code: ')))
            save_config(args.config,dict(server=client.server,secret=value['secret']))
            print('Runner paired. Keep this config private:',args.config); return
        if args.config.is_symlink() or stat.S_IMODE(args.config.stat().st_mode)&0o077: raise ValueError('Device config must be private (chmod 600).')
        config=json.loads(args.config.read_text()); client=Client(config['server'],config['secret'])
        if args.action=='harness-prepare':
            job=client.post('harness/'+args.attempt+'/bundle');target=harness_runtime.prepare(job,config,args.root)
            client.post('harness/'+args.attempt+'/prepared',dict(snapshot_digest=job['snapshot_digest']))
            print('Task directory:',target/'worktree');return
        # Deliver completed work under its original profile before changing registration.
        harness_runtime.flush(client,config,args.root)
        registered=harness_runtime.profiles(args.harness_config,args.allow_harness)
        client.post('harness/register',dict(profiles=harness_runtime.registration(registered)))
        capabilities=['workflow-v2','http','source-v1']
        backend=args.code_backend
        if backend=='auto':backend='docker' if shutil.which('docker') else 'process'
        if backend=='process' and args.allow_local_code:
            capabilities+=['python3']
            if shutil.which('node'):capabilities+=['javascript']
        elif backend=='docker' and shutil.which('docker'):capabilities+=['python3','javascript']
        print('Code execution backend:',backend if 'python3' in capabilities else 'disabled; explicit local-code opt-in or Docker required')
        client.post('execution/register',dict(protocol=2,capabilities=capabilities))
        print('Runner online. Source workspaces:',args.root.expanduser().resolve())
        while True:
            try:
                flush_outbox(client,args.root.expanduser().resolve())
                harness_runtime.flush(client,config,args.root)
                if registered:
                    job=client.post('harness/claim').get('job')
                    if job:
                        harness_runtime.execute(job,config,args.root,registered,client)
                        if args.once:break
                        continue
                rpc=client.post('rpc/claim').get('job')
                if rpc:
                    credentials=client.post('rpc/'+rpc['id']+'/credentials')
                    try:execute_workflow(rpc,credentials,config,args.root,dict(backend=backend,allowed_languages=[v for v in capabilities if v in ('python3','javascript')],python_image=args.python_image,javascript_image=args.javascript_image,writable=args.allow_worktree_write))
                    finally:credentials.clear()
                    if args.once:break
                    continue
                execution=client.post('execution/claim').get('job')
                if execution:
                    credentials=client.post('execution/'+execution['id']+'/credentials')
                    try: execute_workflow(execution,credentials,config,args.root,dict(backend=backend,allowed_languages=[v for v in capabilities if v in ('python3','javascript')],python_image=args.python_image,javascript_image=args.javascript_image,writable=args.allow_worktree_write))
                    finally: credentials.clear()
                    if args.once: break
                    continue
                job=client.post('claim').get('job')
                if job:
                    validate_job(job)
                    path='jobs/'+job['id']+'/'
                    heartbeat=lambda: client.post(path+'heartbeat')
                    credentials={}; values=[]
                    try:
                        values=client.post(path+'credentials')['connections']
                        credentials={v['key']:v['token'] for v in values}
                        parts=materialize(job,credentials,args.root,heartbeat,owner=owner_id(config['server'],config['secret']))
                        credentials.clear(); values.clear()
                        client.post(path+'complete',dict(state='succeeded',components=parts,error=None))
                        print('Prepared:',args.root.expanduser().resolve()/job['id'])
                    except RunnerFailure as exc:
                        client.post(path+'complete',dict(state='failed',components=[],error=exc.code)); print('Preparation failed:',exc.code)
                    except ApiError:
                        # Lost lease/revocation/cancellation: stop current job; do not send source or raw errors.
                        print('Job interrupted; inspect status in Kara.')
                    finally:
                        credentials.clear(); values.clear()
                if args.once: break
                time.sleep(5)
            except ApiError as error:
                if getattr(error,'status',None) in (401,403):raise
                print('Job stopped or connection unavailable; reconnecting without replay.')
                if args.once:break
                time.sleep(5)
    except (ApiError,RunnerFailure,harness_runtime.HarnessFailure,ValueError,OSError,KeyError,TypeError):
        # Do not log config, payloads or upstream Git output.
        print('Runner stopped. Check connection, permissions and local files.'); raise SystemExit(1) from None
    except KeyboardInterrupt: print('\nRunner stopped; unfinished jobs expire in Kara.')

if __name__=='__main__': main()
