"""Code runs in a local disposable container, never in the Kara server or Runner process."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from .model_adapter import ExecutionFailure

PYTHON='''import sys,json,contextlib,io
p=json.load(sys.stdin)
ns={"__name__":"__kara_node__"}
with contextlib.redirect_stdout(io.StringIO()):
 exec(compile(p["code"],"<workflow-node>","exec"),ns)
 result=ns["main"](**p["inputs"])
print(json.dumps(result,ensure_ascii=False,allow_nan=False))
'''
JAVASCRIPT='''let text='';process.stdin.on('data',c=>text+=c);process.stdin.on('end',async()=>{try{const p=JSON.parse(text);const fn=new Function(p.code+';return main;')();const r=await fn(p.inputs);process.stdout.write(JSON.stringify(r));}catch(e){process.exit(1)}});'''

class CodeRuntime:
    def __init__(self,job_id,*,python_image='kara/code-python:2.0',javascript_image='node:22-alpine',workspace=None,writable=False):
        self.prefix='kara-'+job_id; self.python_image=python_image; self.javascript_image=javascript_image
        self.workspace=Path(workspace).resolve() if workspace else None; self.writable=writable; self.containers=set(); self.lock=threading.Lock()
    def code(self,language,code,inputs,node_id):
        name=self.prefix+'-'+hashlib.sha256(node_id.encode()).hexdigest()[:10]
        command=['docker','run','--pull=never','--rm','--name',name,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=64','--memory=256m','--cpus=1','--user='+str(os.getuid() if self.workspace else 65534)+':'+str(os.getgid() if self.workspace else 65534),'--tmpfs','/tmp:rw,noexec,nosuid,size=64m','-i']
        if self.workspace:
            if not self.workspace.is_dir(): raise ExecutionFailure('code_failed')
            command+=['--mount','type=bind,src='+str(self.workspace)+',dst=/workspace'+('' if self.writable else ',readonly'),'--workdir','/workspace']
        if language=='python3': command += [self.python_image,'python3','-I','-c',PYTHON]
        elif language=='javascript': command += [self.javascript_image,'node','--max-old-space-size=128','-e',JAVASCRIPT]
        else: raise ExecutionFailure('unsupported_definition')
        with self.lock: self.containers.add(name)
        try:
            return json.loads(run_bounded(command,json.dumps(dict(code=code,inputs=inputs),ensure_ascii=False).encode()))
        except (OSError,ValueError,subprocess.TimeoutExpired): raise ExecutionFailure('code_failed') from None
        finally:
            try: subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
            except (OSError,subprocess.TimeoutExpired): pass
            with self.lock: self.containers.discard(name)
    def cancel(self):
        with self.lock: names=list(self.containers)
        for name in names:
            try: subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
            except (OSError,subprocess.TimeoutExpired): pass

class ProcessCodeRuntime(CodeRuntime):
    """Explicit opt-in only: a separate process with limits, NOT an OS sandbox."""
    def code(self,language,code,inputs,node_id):
        import os,sys,tempfile,resource
        def limits():
            resource.setrlimit(resource.RLIMIT_CPU,(30,30))
            resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576))
            resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
            # macOS Python's virtual mappings can exceed an address-space limit before use.
            if sys.platform.startswith('linux'):resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))
        command=[sys.executable,'-I','-c',PYTHON] if language=='python3' else ['node','--max-old-space-size=256','-e',JAVASCRIPT] if language=='javascript' else None
        if not command:raise ExecutionFailure('unsupported_definition')
        with tempfile.TemporaryDirectory(prefix='kara-code-') as directory:
            env={k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','WINDIR','LANG','TMPDIR')}
            env['HOME']=directory
            if self.workspace:env['KARA_WORKTREE']=str(self.workspace)
            try:
                return json.loads(run_bounded(command,json.dumps(dict(code=code,inputs=inputs),ensure_ascii=False).encode(),cwd=str(self.workspace) if self.workspace and self.writable else directory,env=env,preexec_fn=limits))
            except (OSError,ValueError,subprocess.TimeoutExpired):raise ExecutionFailure('code_failed') from None


def native_limits():
    import resource,sys
    resource.setrlimit(resource.RLIMIT_CPU,(30,30))
    resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576))
    resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
    if sys.platform.startswith('linux'):resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))


def run_bounded(command,payload,**kwargs):
    """Drain with a hard bound so hostile code cannot fill parent memory or disk."""
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True,**kwargs)
    chunks=[];overflow=threading.Event()
    def read():
        size=0
        while True:
            value=process.stdout.read(65536)
            if not value:break
            size+=len(value)
            if size>1048576:
                overflow.set();process.kill();break
            chunks.append(value)
    reader=threading.Thread(target=read,daemon=True);reader.start()
    try:
        process.stdin.write(payload);process.stdin.close();process.wait(timeout=90);reader.join(timeout=5)
        if process.returncode or overflow.is_set() or reader.is_alive():raise ExecutionFailure('code_failed')
        return b''.join(chunks)
    finally:
        if process.poll() is None:
            import os,signal
            os.killpg(process.pid,signal.SIGKILL);process.wait()
        process.stdout.close()
