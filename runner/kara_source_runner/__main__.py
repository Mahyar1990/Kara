"""Run with python3 -m kara_source_runner; credentials never appear in arguments."""
import argparse
import getpass
import json
import os
from pathlib import Path
import stat
import time
from .client import Client, ApiError
from .executor import materialize, RunnerFailure, validate_job

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
    run=sub.add_parser('run'); run.add_argument('--root',type=Path,default=Path.home()/'KaraSourceWorkspaces'); run.add_argument('--once',action='store_true')
    args=parser.parse_args()
    try:
        if args.action=='pair':
            if args.config.exists() or args.config.is_symlink(): raise ValueError('Device config already exists; use another --config path.')
            client=Client(args.server); value=client.post('pair',dict(code=getpass.getpass('One-time pairing code: ')))
            save_config(args.config,dict(server=client.server,secret=value['secret']))
            print('Runner paired. Keep this config private:',args.config); return
        if args.config.is_symlink() or stat.S_IMODE(args.config.stat().st_mode)&0o077: raise ValueError('Device config must be private (chmod 600).')
        config=json.loads(args.config.read_text()); client=Client(config['server'],config['secret'])
        print('Runner online. Source workspaces:',args.root.expanduser().resolve())
        while True:
            job=client.post('claim').get('job')
            if job:
                validate_job(job)
                path='jobs/'+job['id']+'/'
                heartbeat=lambda: client.post(path+'heartbeat')
                credentials={}; values=[]
                try:
                    values=client.post(path+'credentials')['connections']
                    credentials={v['key']:v['token'] for v in values}
                    parts=materialize(job,credentials,args.root,heartbeat)
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
    except (ApiError,RunnerFailure,ValueError,OSError,KeyError):
        # Do not log config, payloads or upstream Git output.
        print('Runner stopped. Check connection, permissions and local files.'); raise SystemExit(1) from None
    except KeyboardInterrupt: print('\nRunner stopped; unfinished jobs expire in Kara.')

if __name__=='__main__': main()
