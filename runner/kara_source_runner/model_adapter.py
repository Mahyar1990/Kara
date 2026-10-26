"""Model HTTP requests are made exclusively by the user's Runner."""
import json
import os
import hashlib
import tempfile
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from .client import NoRedirect

class ExecutionFailure(Exception):
    def __init__(self,code): self.code=code; super().__init__(code)

def request_json(url,body,headers,timeout=180):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.fragment or any(c.isspace() or ord(c)<32 for c in url): raise ExecutionFailure('model_request_failed')
    try:
        req=Request(url,data=json.dumps(body,ensure_ascii=False,allow_nan=False).encode(),headers={'Content-Type':'application/json','Accept':'application/json',**headers},method='POST')
        with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=timeout) as response:
            data=response.read(16777217)
            if len(data)>16777216: raise ExecutionFailure('model_request_failed')
            return json.loads(data)
    except (HTTPError,URLError,OSError,ValueError): raise ExecutionFailure('model_request_failed') from None

class Model:
    def __init__(self,selection):
        self.value=selection; self.credentials=selection['credentials']
        provider=selection.get('provider','')
        if 'openai' not in provider: raise ExecutionFailure('unsupported_definition')
        self.base=self.credentials.get('endpoint_url') or self.credentials.get('openai_api_base') or 'https://api.openai.com/v1'
        self.base=self.base.rstrip('/')
        self.name=self.credentials.get('endpoint_model_name') or selection['model_name']
        key=self.credentials.get('api_key') or self.credentials.get('openai_api_key')
        if not isinstance(key,str) or any(ord(c)<32 for c in key): raise ExecutionFailure('model_request_failed')
        self.headers={'Authorization':'Bearer '+key}
    def url(self,suffix): return self.base if self.base.endswith('/'+suffix) else self.base+'/'+suffix
    def chat(self,messages,params):
        params=dict(params)
        initial=self.credentials.get('initial_prompt')
        if initial:messages=[dict(role='system',content=initial),*messages]
        if isinstance(params.get('response_format'),str): params['response_format']={'type':params['response_format']}
        if params.get('stop')==[]: params.pop('stop')
        response=request_json(self.url('chat/completions'),dict(params,model=self.name,messages=messages,stream=False),self.headers)
        try:
            choice=response['choices'][0]; message=choice['message']; content=message.get('content')
            if isinstance(content,list): content=''.join(p.get('text','') for p in content if p.get('type')=='text')
            if not isinstance(content,str): raise ValueError()
            usage=response.get('usage') or {}
            return dict(text=content,reasoning_content=message.get('reasoning_content') or '',finish_reason=choice.get('finish_reason'),usage=usage,model=self.value['model_name'],files=[])
        except (KeyError,IndexError,TypeError,ValueError): raise ExecutionFailure('model_request_failed') from None
    def embeddings(self,texts,*,input_type='document',use_cache=True):
        prefix=self.credentials.get('query_prefix' if input_type=='query' else 'document_prefix') or ''
        base=os.environ.get('KARA_EMBEDDING_CACHE') if use_cache else None
        directory=Path(base) if base else None
        if directory:directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        values=[None]*len(texts);paths=[];missing=[]
        for index,text in enumerate(texts):
            key=hashlib.sha256(json.dumps([self.value.get('id'),self.value.get('revision'),self.name,prefix,text],ensure_ascii=False).encode()).hexdigest()
            path=directory/(key+'.json') if directory else None;paths.append(path)
            if path and path.is_file():
                try:values[index]=json.loads(path.read_text())
                except (ValueError,OSError):pass
            if values[index] is None:missing.append(index)
        usage={'total_tokens':0,'prompt_tokens':0}
        if missing:
            response=request_json(self.url('embeddings'),dict(model=self.name,input=[prefix+texts[i] for i in missing],encoding_format='float'),self.headers)
            try:
                data=sorted(response['data'],key=lambda v:v['index'])
                if len(data)!=len(missing):raise ValueError()
                import math
                for index,item in zip(missing,data):
                    vector=item['embedding']
                    if not isinstance(vector,list) or not vector or len(vector)>65536 or any(type(v) not in (int,float) or not math.isfinite(v) for v in vector):raise ValueError()
                    values[index]=vector;path=paths[index]
                    if path:
                        fd,temp=tempfile.mkstemp(dir=directory,prefix='.vector-')
                        try:
                            with os.fdopen(fd,'w') as file:json.dump(vector,file,allow_nan=False)
                            os.replace(temp,path)
                        finally:
                            if os.path.exists(temp):os.unlink(temp)
                usage=response.get('usage') or {}
            except (KeyError,TypeError,ValueError):raise ExecutionFailure('model_request_failed') from None
        return values,usage
    def rerank(self,query,texts,top_n):
        url=self.credentials.get('rerank_endpoint_url') or self.url('rerank')
        response=request_json(url,dict(model=self.name,query=query,documents=texts,top_n=top_n),self.headers)
        values=response.get('results') or response.get('data')
        if not isinstance(values,list): raise ExecutionFailure('model_request_failed')
        return [dict(index=v['index'],score=v.get('relevance_score',v.get('score',0))) for v in values]
