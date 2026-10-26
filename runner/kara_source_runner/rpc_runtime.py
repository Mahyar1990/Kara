"""Local implementations for scoped model and service connection calls."""
import json
import time
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
from .client import NoRedirect
from .model_adapter import Model,ExecutionFailure


def call(job,secrets,code):
    method=job['method'];p=job['payload'];connection=secrets.get('connection');started=time.monotonic()
    if method=='raw-code':
        language=p['language'];raw=p.get('preload','')+'\n'+p['code']
        # Native CodeExecutor templates write their serialized output to stdout.
        from .code_runtime import run_bounded,ProcessCodeRuntime,native_limits
        import sys,subprocess
        if isinstance(code,ProcessCodeRuntime):command=[sys.executable,'-I','-'] if language=='python3' else ['node','-']
        else:
            name=code.prefix+'-raw';code.containers.add(name)
            command=['docker','run','--pull=never','--rm','--name',name,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=64','--memory=256m','--cpus=1','--user=65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=64m','-i',code.python_image if language=='python3' else code.javascript_image,'python3' if language=='python3' else 'node','-']
        try:return run_bounded(command,raw.encode('utf-8'),**({'preexec_fn':native_limits} if isinstance(code,ProcessCodeRuntime) else {})).decode('utf-8')
        finally:code.cancel()
    if method=='connection-http':
        base=connection['base_url'];path=p['path']
        allowed={'jira':{'/rest/api/2/search','/rest/api/2/myself'},'gitlab':{'/api/v4/user'}}
        if path not in allowed.get(connection['kind'],set()):raise ExecutionFailure('network_failed')
        from .contracts import https_url
        base=https_url(base)
        headers={'Accept':'application/json','Accept-Encoding':'identity'}
        headers.update({'Authorization':'Bearer '+connection['token']} if connection['kind']=='jira' else {'PRIVATE-TOKEN':connection['token']})
        body=json.dumps(p['body']).encode() if p.get('body') is not None else None
        if body:headers['Content-Type']='application/json'
        try:
            with build_opener(ProxyHandler({}),NoRedirect()).open(Request(base+path,data=body,headers=headers),timeout=30) as response:
                value=response.read(2097153)
                if len(value)>2097152:raise ExecutionFailure('network_failed')
                return dict(status=response.status,body=json.loads(value))
        except HTTPError as exc:return dict(status=exc.code,body={})
        except (OSError,ValueError):raise ExecutionFailure('network_failed') from None
    model=Model(connection)
    if method.startswith('validate_'):
        if connection['model_type']=='llm':model.chat([dict(role='user',content='Reply OK.')],dict(max_tokens=8,temperature=0))
        elif connection['model_type']=='text-embedding':model.embeddings(['connection test'],use_cache=False)
        elif connection['model_type']=='rerank':model.rerank('test',['test'],1)
        else:raise ExecutionFailure('unsupported_definition')
        return True
    if method=='invoke_llm':
        messages=[]
        for message in p.get('prompt_messages',[]):
            role=message.get('role','user');content=message.get('content','')
            messages.append(dict(role=role,content=content))
        params=p.get('model_parameters',{})
        if p.get('stop'):params=dict(params,stop=p['stop'])
        if p.get('tools'):params=dict(params,tools=p['tools'])
        result=model.chat(messages,params);u=result['usage'];usage=dict(prompt_tokens=u.get('prompt_tokens',0),completion_tokens=u.get('completion_tokens',0),total_tokens=u.get('total_tokens',0),currency='USD',latency=time.monotonic()-started)
        usage.update({k:'0' for k in ('prompt_unit_price','prompt_price_unit','prompt_price','completion_unit_price','completion_price_unit','completion_price','total_price')})
        return [dict(model=connection['model_name'],prompt_messages=p.get('prompt_messages',[]),delta=dict(index=0,message=dict(role='assistant',content=result['text']),usage=usage,finish_reason=result['finish_reason']))]
    if method=='invoke_text_embedding':
        values,usage=model.embeddings(p['texts'],input_type=p.get('input_type','document'))
        return dict(model=connection['model_name'],embeddings=values,usage=dict(tokens=usage.get('prompt_tokens',usage.get('total_tokens',0)),total_tokens=usage.get('total_tokens',0),unit_price='0',price_unit='0',total_price='0',currency='USD',latency=time.monotonic()-started))
    if method=='invoke_rerank':
        docs=p['docs'];values=model.rerank(p['query'],docs,p.get('top_n') or len(docs))
        return dict(model=connection['model_name'],docs=[dict(index=v['index'],text=docs[v['index']],score=v['score']) for v in values if p.get('score_threshold') is None or v['score']>=p['score_threshold']])
    if method in ('get_llm_num_tokens','get_text_embedding_num_tokens'):
        try:import tiktoken
        except ImportError:raise ExecutionFailure('unsupported_definition') from None
        try:encoding=tiktoken.encoding_for_model(connection['model_name'])
        except KeyError:encoding=tiktoken.get_encoding('cl100k_base')
        texts=p.get('texts') or [json.dumps(v,ensure_ascii=False) for v in p.get('prompt_messages',[])]
        return sum(len(encoding.encode(text)) for text in texts)
    raise ExecutionFailure('unsupported_definition')
