"""Explicitly enabled local harness adapters. No commands or credentials from Kara."""
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import subprocess
import tempfile
import time
from uuid import UUID
from .client import ApiError
from .execution_worker import atomic_json,owner_id
from .executor import command,git_environment,RunnerFailure
from .contracts import workspace_files

class HarnessFailure(Exception):pass

def profiles(path,enabled):
    if not enabled:return {}
    path=Path(path).expanduser()
    if path.is_symlink() or path.stat().st_uid!=os.getuid() or stat.S_IMODE(path.stat().st_mode)&0o077:raise ValueError('private harness config required')
    values=json.loads(path.read_text());result={}
    if not isinstance(values,list) or len(values)>10:raise ValueError('invalid harness config')
    for p in values:
        if not isinstance(p,dict) or set(p)-{'key','name','kind','version','executable','argv','timeout'} or not re.fullmatch('[a-z][a-z0-9_-]{0,63}',p.get('key','')) or p.get('kind') not in ('codex','opencode','custom') or p['key'] in result:raise ValueError('invalid harness profile')
        if not isinstance(p.get('name'),str) or not 1<=len(p['name'])<=120:raise ValueError('invalid harness name')
        if not isinstance(p.get('version',''),str) or len(p.get('version',''))>120:raise ValueError('invalid version')
        if not Path(p.get('executable','')).is_absolute() or not os.access(p['executable'],os.X_OK):raise ValueError('absolute executable required')
        if not isinstance(p.get('argv',[]),list) or len(p.get('argv',[]))>30 or any(not isinstance(v,str) or len(v)>1000 for v in p.get('argv',[])):raise ValueError('invalid local argv')
        if p['kind']!='custom' and p.get('argv'):raise ValueError('argv applies to custom wrappers only')
        if type(p.get('timeout',1800)) is not int or not 30<=p.get('timeout',1800)<=3600:raise ValueError('invalid timeout')
        digest=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        result[p['key']]=dict(p,digest=digest,version=p.get('version',''))
    return result

def registration(values):return [dict(key=p['key'],name=p['name'],kind=p['kind'],version=p['version'],digest=p['digest']) for p in values.values()]

def target_for(job,config,root):
    identity=str(UUID(job['id']))
    root=Path(root).expanduser().resolve();root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if root.stat().st_uid!=os.getuid() or root.stat().st_mode&0o022:raise HarnessFailure('workspace_failed')
    return root/'.kara-harness'/owner_id(config['server'],config['secret'])/identity

def prepare(job,config,root,heartbeat=lambda:None):
    target=target_for(job,config,root);mark=target/'prepared.json'
    if any(p.is_symlink() for p in (target,target.parent,target.parent.parent)):raise HarnessFailure('workspace_failed')
    if target.exists():
        if not mark.is_file() or mark.is_symlink() or json.loads(mark.read_text()).get('snapshot_digest')!=job['snapshot_digest']:raise HarnessFailure('workspace_failed')
        return target
    target.mkdir(parents=True,mode=0o700);worktree=target/'worktree';worktree.mkdir(mode=0o700)
    source=job.get('source');baselines=[]
    with tempfile.TemporaryDirectory(prefix='kara-harness-git-') as home:
        env=git_environment(Path(home),Path(os.devnull))
        if source:
            workspace_files(source['components'],source['documents'])
            original=Path(root).expanduser().resolve()/str(UUID(source['id']))
            manifest=json.loads((original/'.kara/manifest.json').read_text())
            if manifest.get('owner')!=owner_id(config['server'],config['secret']) or manifest.get('job_id')!=source['id']:raise HarnessFailure('workspace_failed')
            commits={p['key']:p['commit'] for p in source['result']['components']}
            observed={p['key']:p for p in manifest['components']}
            for p in source['components']:
                actual=observed[p['key']];sha=commits[p['key']]
                if not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',sha) or actual['commit']!=sha or actual['path']!=p['path'] or actual['url']!=p['url'] or actual['branch']!=p['branch']:raise HarnessFailure('workspace_failed')
                destination=worktree/p['path'];destination.parent.mkdir(parents=True,exist_ok=True)
                repository=original/'.kara'/(p['key']+'.git')
                if not repository.resolve().is_relative_to(original.resolve()):raise HarnessFailure('workspace_failed')
                command(['--git-dir',str(repository),'worktree','add','--detach',str(destination),sha],env,heartbeat)
                baselines.append(dict(key=p['key'],path=p['path'],commit=sha))
            for doc in source['documents']:
                path=worktree/doc['path'];path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('x',encoding='utf-8') as file:file.write(doc['content'])
        # The containing repository gives the harness a task-scoped working root.
        command(['init','--quiet',str(worktree)],env,heartbeat)
    meta=worktree/'.kara-task';meta.mkdir(mode=0o700)
    atomic_json(meta/'task.json',job)
    example=dict(outputs={k:'' for k in job['output_contract']},evidence=dict(summary='',changes=[],tests=dict(status='not_run',summary=''),references=[],diff=''),session_id=None)
    atomic_json(meta/'result.example.json',example)
    (meta/'TASK.md').write_text('''# Kara task
Read task.json: its mission, acceptance criteria, versioned inputs, knowledge and program instructions.
Work only on this task and the explicitly selected repositories. Preserve repository AGENTS.md rules.
Do not commit, push or merge unless the task explicitly requires it. Do not claim tests you did not run.
Return ONLY a JSON object shaped like result.example.json. Use all output_contract names.
Summary and test status are required. Report real changes and limitations. Never include credentials.
Completion is a candidate result; the assigned human must still review/finalize it in Kara.
''',encoding='utf-8')
    atomic_json(mark,dict(snapshot_digest=job['snapshot_digest'],baselines=baselines))
    return target

def read_candidate(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>524288:raise HarnessFailure('invalid_result')
    value=json.loads(path.read_text())
    if not isinstance(value,dict) or set(value)-{'outputs','evidence','session_id'} or not {'outputs','evidence'}<=set(value):raise HarnessFailure('invalid_result')
    return value

def run_cli(job,profile,target,heartbeat):
    worktree=target/'worktree';meta=worktree/'.kara-task';candidate=target/'candidate.json';stdout=target/'output.events'
    prompt='Read .kara-task/TASK.md and .kara-task/task.json. Complete the mission. Return ONLY the JSON result described in .kara-task/result.example.json.'
    executable=profile['executable']
    if profile['kind']=='codex':argv=[executable,'exec','--sandbox','workspace-write','--output-last-message',str(candidate),'-'];input_text=prompt
    elif profile['kind']=='opencode':argv=[executable,'run','--standalone','--format','json','--file',str(meta/'task.json'),'--',prompt];input_text=''
    else:
        tokens={'{bundle}':str(meta/'task.json'),'{result}':str(candidate),'{worktree}':str(worktree)}
        argv=[executable,*[tokens.get(v,v) for v in profile.get('argv',[])]];input_text=prompt
    # Harness uses the user's own login/configuration; the Runner token is never in env/argv.
    env={k:v for k,v in os.environ.items() if not k.startswith('KARA_')}
    process=None
    def stopped(*args):raise KeyboardInterrupt()
    previous=signal.signal(signal.SIGTERM,stopped)
    try:
        with stdout.open('xb') as log:
            os.chmod(stdout,0o600)
            process=subprocess.Popen(argv,cwd=worktree,env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.DEVNULL,start_new_session=True)
            process.stdin.write(input_text.encode());process.stdin.close()
            deadline=time.monotonic()+profile.get('timeout',1800);next_heartbeat=0
            while process.poll() is None:
                if time.monotonic()>deadline or stdout.stat().st_size>4194304:raise HarnessFailure('harness_failed')
                if time.monotonic()>=next_heartbeat:heartbeat();next_heartbeat=time.monotonic()+10
                time.sleep(1)
            if process.returncode:raise HarnessFailure('harness_failed')
        if profile['kind']=='opencode':
            messages=[];session=None
            for line in stdout.read_text().splitlines():
                try:event=json.loads(line)
                except ValueError:continue
                if event.get('type')=='text' and isinstance(event.get('part',{}).get('text'),str):messages.append(event['part']['text'])
                if isinstance(event.get('sessionID'),str):session=event['sessionID']
            value=json.loads(''.join(messages));value.setdefault('session_id',session);atomic_json(candidate,value)
        return read_candidate(candidate)
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        stdout.unlink(missing_ok=True)
        signal.signal(signal.SIGTERM,previous)

def capture_changes(target,value,heartbeat):
    mark=json.loads((target/'prepared.json').read_text());changes=[];diffs=[]
    with tempfile.TemporaryDirectory(prefix='kara-harness-diff-') as home:
        env=git_environment(Path(home),Path(os.devnull))
        for part in mark['baselines']:
            cwd=target/'worktree'/part['path']
            paths=command(['-C',str(cwd),'status','--porcelain','--untracked-files=normal'],env,heartbeat)
            changes.extend((part['key']+': '+line)[:512] for line in paths.splitlines())
            # Limit retained diff bytes. The full source stays on the user's device.
            p=subprocess.Popen(['git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-C',str(cwd),'diff','--no-ext-diff','--no-textconv',part['commit'],'--'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
            try:
                chunks=[];size=0;deadline=time.monotonic()+30;next_heartbeat=0
                while size<65536 and time.monotonic()<deadline:
                    if time.monotonic()>=next_heartbeat:heartbeat();next_heartbeat=time.monotonic()+5
                    if not select.select([p.stdout],[],[],1)[0]:continue
                    chunk=os.read(p.stdout.fileno(),min(8192,65536-size))
                    if not chunk:break
                    chunks.append(chunk);size+=len(chunk)
                output=b''.join(chunks).decode('utf-8',errors='replace');diffs.append(part['key']+'\n'+output)
            finally:
                p.stdout.close()
                if p.poll() is None:p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()
    value['evidence']['changes']=changes[:500];value['evidence']['diff']='\n'.join(diffs)[:32000]
    return value

def deliver(client,target):
    pending=target/'delivery.json'
    if not pending.is_file():return
    value=json.loads(pending.read_text());identity=str(UUID(target.name))
    try:
        client.post('harness/'+identity+'/'+value['action'],value['body']);pending.rename(target/'delivered.json')
    except ApiError as error:
        if getattr(error,'status',None) in (400,422) and value['action']=='complete':
            client.post('harness/'+identity+'/fail',dict(snapshot_digest=value['body']['snapshot_digest'],error='invalid_result'))
            pending.rename(target/'invalid-result.json')
        elif getattr(error,'status',None) in (403,404,409):pending.rename(target/'rejected.json')
        else:raise

def flush(client,config,root):
    base=Path(root).expanduser().resolve()/'.kara-harness'/owner_id(config['server'],config['secret'])
    if base.exists():
        for target in base.iterdir():
            if not target.is_symlink() and target.is_dir() and (target/'delivery.json').is_file():deliver(client,target)

def execute(job,config,root,registered,client):
    profile=registered.get(job['profile_key'])
    if not profile or profile['digest']!=job['profile_digest']:raise ValueError('harness not authorized locally')
    target=target_for(job,config,root)
    if (target/'started.json').exists():raise ValueError('harness execution cannot be replayed')
    def heartbeat():client.post('harness/'+job['id']+'/heartbeat')
    try:
        target=prepare(job,config,root,heartbeat)
        client.post('harness/'+job['id']+'/prepared',dict(snapshot_digest=job['snapshot_digest']))
        atomic_json(target/'started.json',dict(snapshot_digest=job['snapshot_digest']))
        value=capture_changes(target,run_cli(job,profile,target,heartbeat),heartbeat)
        value['snapshot_digest']=job['snapshot_digest'];value.setdefault('session_id',None)
        atomic_json(target/'delivery.json',dict(action='complete',body=value))
    except ApiError:raise
    except (HarnessFailure,RunnerFailure,OSError,ValueError,KeyError,TypeError) as error:
        target.mkdir(parents=True,exist_ok=True,mode=0o700)
        code=error.args[0] if isinstance(error,HarnessFailure) else 'harness_failed'
        atomic_json(target/'delivery.json',dict(action='fail',body=dict(snapshot_digest=job['snapshot_digest'],error=code)))
    deliver(client,target)
