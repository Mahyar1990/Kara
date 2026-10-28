"""A killable local worker plus durable, credential-free event/result outbox."""
import json
import hashlib
import multiprocessing
import os
from pathlib import Path
import signal
import tempfile
import time
from uuid import UUID
from .client import Client,ApiError
from .code_runtime import CodeRuntime,ProcessCodeRuntime
from .model_adapter import ExecutionFailure
from .workflow_runtime import WorkflowRuntime


def owner_id(server,secret):
    return hashlib.sha256((server+'|'+secret.split('.',1)[0]).encode()).hexdigest()

def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        os.chmod(name,0o600)
        with os.fdopen(fd,'w') as file: json.dump(value,file,ensure_ascii=False,allow_nan=False); file.flush(); os.fsync(file.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def worker(job,secrets,config,root,options,directory):
    client=Client(config['server'],config['secret']); prefix=('rpc/' if job.get('kind')=='rpc' else 'execution/')+job['id']+'/'
    directory=Path(directory); sequence=0
    os.environ['KARA_EMBEDDING_CACHE']=str(Path(root)/'.kara-runner'/owner_id(config['server'],config['secret'])/'embeddings')
    workspace=Path(root)/job['source_job_id'] if job.get('source_job_id') else None
    if workspace:
        try:
            if not workspace.resolve().is_relative_to(Path(root).resolve()) or not workspace.is_dir():raise ValueError()
            manifest=json.loads((workspace/'.kara/manifest.json').read_text())
            if manifest.get('owner')!=owner_id(config['server'],config['secret']):raise ValueError()
        except (OSError,ValueError):
            atomic_json(directory/'result.json',dict(state='failed',outputs={},error='code_failed',total_steps=0,total_tokens=0,snapshot_digest=job.get('snapshot_digest')))
            return
    options=dict(options);options.pop('allowed_languages',None);backend=options.pop('backend','docker')
    code=(ProcessCodeRuntime if backend=='process' else CodeRuntime)(job['id'],workspace=workspace,**options)
    def stopped(*args): code.cancel(); raise SystemExit(1)
    signal.signal(signal.SIGTERM,stopped)
    class Cancelled:
        @staticmethod
        def is_set(): return False
    def send_event(event):
        nonlocal sequence
        sequence+=1; body=dict(sequence=sequence,event=event); path=directory/('event-'+str(sequence).zfill(6)+'.json'); atomic_json(path,body)
        # Retrying a persisted sequence never re-executes a node or model request.
        for attempt in range(3):
            try: client.post(prefix+'events',body); path.unlink(missing_ok=True); return
            except ApiError:
                if attempt==2: raise
                time.sleep(1)
    try:
        if job.get('kind')=='rpc':
            if job['method']=='workflow-node':
                runtime=WorkflowRuntime(job['node_job'],secrets,code,lambda node,cursor:client.post(prefix+'knowledge',dict(node_id=node,cursor=cursor)),lambda _:None,Cancelled())
                runtime.pool.update(job['pool']); runtime.pool['env']=secrets.get('environment',{})
                node=next(n for n in job['node_job']['graph']['nodes'] if n['id']==job['node_id'])
                output,branch=runtime.node(node['id'],node['data'])
                value=dict(output=output,branch=branch,total_tokens=runtime.tokens)
            else:
                from .rpc_runtime import call
                value=call(job,secrets,code)
            result=dict(state='succeeded',value=value,error=None)
        else:
            def delegate(node,pool):
                deadline=time.monotonic()+600
                while time.monotonic()<deadline:
                    response=client.post(prefix+'node',dict(node_id=node,pool=pool))
                    if response['state']=='succeeded':return response['result']['value']
                    if response['state'] in ('failed','cancelled','interrupted'):raise ExecutionFailure('execution_failed')
                    time.sleep(1)
                raise ExecutionFailure('execution_failed')
            runtime=WorkflowRuntime(job,secrets,code,lambda node,cursor:client.post(prefix+'knowledge',dict(node_id=node,cursor=cursor)),send_event,Cancelled(),delegate)
            result=runtime.run(); result.update(state='succeeded',error=None,snapshot_digest=job.get('snapshot_digest'))
    except ExecutionFailure as exc:
        result=dict(state='failed',outputs={},error=exc.code,total_steps=0,total_tokens=0,snapshot_digest=job.get('snapshot_digest'))
    except BaseException:
        # Never persist traceback, URL headers, credentials or raw provider errors.
        code.cancel()
        result=dict(state='failed',outputs={},error='execution_failed',total_steps=0,total_tokens=0,snapshot_digest=job.get('snapshot_digest'))
    if job.get('kind')=='rpc' and result.get('state')=='failed':result=dict(state='failed',value=None,error=result['error'])
    atomic_json(directory/'result.json',result)


def flush_outbox(client,root):
    base=Path(root)/'.kara-runner'/owner_id(client.server,client.secret)/'executions'
    if not base.exists(): return
    for directory in sorted(base.iterdir()):
        if not directory.is_dir() or not (directory/'result.json').is_file(): continue
        try:
            if str(UUID(directory.name))!=directory.name: continue
            kind=json.loads((directory/'protocol.json').read_text()).get('kind')
            prefix=('rpc/' if kind=='rpc' else 'execution/')+directory.name+'/'
            for event in sorted(directory.glob('event-*.json')):
                client.post(prefix+'events',json.loads(event.read_text())); event.unlink()
            client.post(prefix+'complete',json.loads((directory/'result.json').read_text()))
            (directory/'result.json').rename(directory/'delivered.json')
        except ApiError as error:
            if getattr(error,'status',None) in (403,404,409):
                (directory/'result.json').rename(directory/'rejected.json')
            # A lease/fence rejection is retained for operator review, never replayed as a new execution.
            continue


def execute(job,secrets,config,root,options):
    if str(UUID(job['id']))!=job['id']: raise ValueError('invalid execution identity')
    allowed=set(options.get('allowed_languages',[]))
    if job.get('kind')=='rpc' and job.get('method')=='raw-code' and job['payload'].get('language') not in allowed:raise ValueError('code execution not authorized on this device')
    if job.get('kind')!='rpc':
        from .workflow_contract import validate_graph
        needed=set(job['requirements']) if job.get('routes') else set(validate_graph(job['graph']))
        if (needed & {'python3','javascript'}) - allowed:raise ValueError('code execution not authorized on this device')
    elif job.get('method')=='workflow-node':
        node=next(n['data'] for n in job['node_job']['graph']['nodes'] if n['id']==job['node_id'])
        language=node.get('code_language') if node['type']=='code' else 'python3' if node['type']=='template-transform' else None
        if language and language not in allowed:raise ValueError('code execution not authorized on this device')
    root=Path(root).expanduser().resolve(); root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if root.stat().st_uid!=os.getuid() or root.stat().st_mode&0o022: raise ValueError('private root required')
    directory=root/'.kara-runner'/owner_id(config['server'],config['secret'])/'executions'/job['id']
    if directory.exists(): raise ValueError('execution already exists locally')
    directory.mkdir(parents=True,mode=0o700)
    atomic_json(directory/'protocol.json',dict(kind=job.get('kind','workflow')))
    client=Client(config['server'],config['secret']); process=multiprocessing.get_context('spawn').Process(target=worker,args=(job,secrets,config,str(root),options,str(directory)))
    process.start(); next_heartbeat=0; deadline=time.monotonic()+3600
    try:
        while process.is_alive():
            if time.monotonic()>deadline: raise ApiError('Execution deadline exceeded')
            if time.monotonic()>=next_heartbeat:
                client.post(('rpc/' if job.get('kind')=='rpc' else 'execution/')+job['id']+'/heartbeat'); next_heartbeat=time.monotonic()+10
            process.join(timeout=1)
        if process.exitcode and not (directory/'result.json').exists():
            value=dict(state='failed',value=None,error='execution_failed') if job.get('kind')=='rpc' else dict(state='failed',outputs={},error='execution_failed',total_steps=0,total_tokens=0,snapshot_digest=job.get('snapshot_digest'))
            atomic_json(directory/'result.json',value)
        flush_outbox(client,root)
    finally:
        if process.is_alive():
            process.terminate(); process.join(timeout=10)
            if process.is_alive(): process.kill(); process.join(timeout=5)
