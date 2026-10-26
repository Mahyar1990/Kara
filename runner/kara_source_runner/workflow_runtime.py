"""Execute the published graph locally, preserving branch/merge and output contracts."""
import json
import math
import re
import time
from urllib.request import Request,build_opener,ProxyHandler
from .client import NoRedirect
from .model_adapter import Model,ExecutionFailure
from .workflow_contract import validate_graph

MISSING=object()

def stringify(value): return value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,separators=(',',':'))

def compare(value,op,expected):
    if op in ('is','is not'): return (value==expected) if op=='is' else (value!=expected)
    if op in ('empty','not empty'): return (value in (None,'',[],{})) if op=='empty' else (value not in (None,'',[],{}))
    if op in ('null','not null'): return (value is None) if op=='null' else (value is not None)
    if op in ('contains','not contains'): return (expected in value) if op=='contains' else (expected not in value)
    if op in ('start with','end with'): return str(value).startswith(str(expected)) if op=='start with' else str(value).endswith(str(expected))
    if op in ('=','≠','>','<','≥','≤','>=','<='):
        a,b=float(value),float(expected)
        return {'=':a==b,'≠':a!=b,'>':a>b,'<':a<b,'≥':a>=b,'≤':a<=b,'>=':a>=b,'<=':a<=b}[op]
    raise ExecutionFailure('unsupported_definition')

class WorkflowRuntime:
    def __init__(self,job,secrets,code,knowledge,event,cancelled):
        validate_graph(job['graph']); self.job=job; self.secrets=secrets; self.code=code; self.knowledge=knowledge; self.event=event; self.cancelled=cancelled
        self.pool={'sys':dict(workflow_run_id=job['id'],workflow_id=job.get('workflow_id',''),timestamp=int(time.time()),query=job.get('inputs',{}).get('query',''),user_id=job.get('actor_id',''),app_id=job.get('app_id',''),files=[]),'env':secrets.get('environment',{})}; self.tokens=0; self.steps=0
    def get(self,path,default=None):
        if not isinstance(path,list) or not path: return default
        value=self.pool
        for part in path:
            if isinstance(value,dict) and part in value: value=value[part]
            elif isinstance(value,list) and str(part).isdigit() and int(part)<len(value): value=value[int(part)]
            else: return default
        return value
    def text(self,text,context=''):
        if not isinstance(text,str): raise ExecutionFailure('unsupported_definition')
        def replace(match):
            key=match.group(1)
            if key=='context': return context
            value=self.get(key.split('.'),MISSING)
            if value is MISSING: raise ExecutionFailure('invalid_output')
            return stringify(value)
        return re.sub(r'\{\{#([^#]+)#\}\}',replace,text)
    def check(self):
        if self.cancelled.is_set(): raise ExecutionFailure('execution_failed')
    def run(self):
        if self.job.get('preview'):return self.preview()
        graph=self.job['graph']; nodes={n['id']:n['data'] for n in graph['nodes']}; incoming={n:[] for n in nodes}; outgoing={n:[] for n in nodes}
        for i,e in enumerate(graph.get('edges',[])):
            incoming[e['target']].append((i,e)); outgoing[e['source']].append((i,e))
        root=self.job.get('root_node_id') or next((n for n,d in nodes.items() if d['type']=='start'),None)
        edge_states={}; done=set(); result={}; remaining=set(nodes)
        while remaining:
            ready=[n for n in nodes if n in remaining and all(e['source'] in done for _,e in incoming[n])]
            if not ready: raise ExecutionFailure('unsupported_definition')
            for identity in ready:
                self.check(); remaining.remove(identity); data=nodes[identity]; active=identity==root or (incoming[identity] and any(edge_states.get(i,False) for i,_ in incoming[identity]))
                if not active:
                    for i,e in outgoing[identity]: edge_states[i]=False
                    done.add(identity); continue
                self.event(dict(event='node_started',node_id=identity,node_type=data['type'],title=data.get('title',identity),status='running'))
                started=time.monotonic(); output,branch=self.node(identity,data)
                if not isinstance(output,dict): raise ExecutionFailure('invalid_output')
                self.pool[identity]=output; self.steps+=1
                self.event(dict(event='node_finished',node_id=identity,node_type=data['type'],title=data.get('title',identity),status='succeeded',outputs=output,elapsed_time=time.monotonic()-started,total_tokens=self.tokens))
                if data['type'] in ('end','answer'): result.update(output)
                for i,e in outgoing[identity]: edge_states[i]=branch is None or str(e.get('sourceHandle','source'))==str(branch)
                done.add(identity)
        if not result: raise ExecutionFailure('invalid_output')
        return dict(outputs=result,total_steps=self.steps,total_tokens=self.tokens)
    def preview(self):
        identity=self.job['preview'];data=next(n['data'] for n in self.job['graph']['nodes'] if n['id']==identity)
        def seed(path):
            if len(path)<2:return
            value=self.job['inputs'].get('.'.join(path),self.job['inputs'].get(path[-1],MISSING))
            if value is MISSING:return
            target=self.pool
            for part in path[:-1]:target=target.setdefault(part,{})
            target[path[-1]]=value
        def walk(value):
            if isinstance(value,dict):
                for k,v in value.items():
                    if k in ('value_selector','variable_selector','query_variable_selector') and isinstance(v,list):seed(v)
                    else:walk(v)
            elif isinstance(value,list):
                for item in value:walk(item)
            elif isinstance(value,str):
                for match in re.finditer(r'\{\{#([^#]+)#\}\}',value):seed(match.group(1).split('.'))
        walk(data);self.check();self.event(dict(event='node_started',node_id=identity,node_type=data['type'],title=data.get('title',identity),status='running'))
        result,_=self.node(identity,data);self.event(dict(event='node_finished',node_id=identity,node_type=data['type'],title=data.get('title',identity),status='succeeded',outputs=result,total_tokens=self.tokens))
        return dict(outputs=result,total_steps=1,total_tokens=self.tokens)

    def node(self,identity,data):
        kind=data['type']
        if kind in ('start','trigger-schedule','trigger-webhook'):
            values={}
            for v in data.get('variables',[]):
                key=v['variable']; value=self.job['inputs'].get(key,v.get('default'))
                if v.get('required') and value in (None,''): raise ExecutionFailure('invalid_output')
                values[key]=value
            values.update({k:v for k,v in self.job['inputs'].items() if k not in values})
            return values,None
        if kind=='end': return {v['variable']:self.get(v['value_selector']) for v in data.get('outputs',[])},None
        if kind=='answer': return dict(answer=self.text(data.get('answer',''))),None
        if kind=='code':
            inputs={v['variable']:self.get(v['value_selector']) for v in data.get('variables',[])}
            output=self.code.code(data['code_language'],data['code'],inputs,identity)
            self.output_types(output,data.get('outputs',{})); return output,None
        if kind=='llm':
            context=''
            if data.get('context',{}).get('enabled'):
                values=self.get(data['context'].get('variable_selector',[]),[])
                context='\n\n'.join(v.get('content','') for v in values) if isinstance(values,list) else stringify(values)
            prompts=data.get('prompt_template',[])
            if isinstance(prompts,dict): prompts=[dict(prompts,role='user')]
            messages=[dict(role=p.get('role','user'),content=self.text(p.get('text',''),context)) for p in prompts]
            model=Model(self.secrets['models'][identity]); retry=data.get('retry_config',{}); attempts=min(4,int(retry.get('max_retries',0)))+1 if retry.get('retry_enabled') else 1
            for attempt in range(attempts):
                self.check()
                try: output=model.chat(messages,data['model'].get('completion_params',{})); break
                except ExecutionFailure:
                    if attempt==attempts-1: raise
                    time.sleep(min(10,float(retry.get('retry_interval',1000))/1000))
            self.tokens+=int(output['usage'].get('total_tokens',0)); return output,None
        if kind=='if-else':
            for case in data.get('cases',[]):
                values=[]
                for c in case.get('conditions',[]): values.append(compare(self.get(c['variable_selector']),c['comparison_operator'],self.text(c['value']) if isinstance(c.get('value'),str) else c.get('value')))
                if (any(values) if case.get('logical_operator')=='or' else all(values)): return dict(result=True),case.get('case_id',case['id'])
            return dict(result=False),'false'
        if kind=='variable-aggregator':
            config=data.get('advanced_settings',{})
            groups=config.get('groups',[]) if config.get('group_enabled') else [dict(group_name='output',variables=data.get('variables',[]))]
            output={}
            for group in groups:
                for selector in group.get('variables',[]):
                    value=self.get(selector,MISSING)
                    if value is not MISSING and value is not None: output[group['group_name']]=value; break
                else: output[group['group_name']]=None
            return output,None
        if kind=='knowledge-retrieval': return dict(result=self.retrieve(identity,data)),None
        if kind=='template-transform':
            # Jinja runs in the same local container, with no host/credential mount.
            inputs={v['variable']:self.get(v['value_selector']) for v in data.get('variables',[])}
            code='from jinja2.sandbox import SandboxedEnvironment\ndef main(**kwargs):\n return {"output": SandboxedEnvironment().from_string('+repr(data['template'])+').render(**kwargs)}'
            return self.code.code('python3',code,inputs,identity),None
        if kind=='http-request': return self.http(data),None
        raise ExecutionFailure('unsupported_definition')
    def retrieve(self,identity,data):
        query=str(self.get(data.get('query_variable_selector',[]),'') or ''); docs=[]; cursor=0; spec=None
        while cursor is not None:
            self.check(); page=self.knowledge(identity,cursor); docs.extend(page['data']); cursor=page['next_cursor']; spec=page
        if not docs: return []
        scores={}; by_dataset={}
        for i,d in enumerate(docs): by_dataset.setdefault(d['dataset_id'],[]).append(i)
        for dataset in spec['datasets']:
            indices=by_dataset.get(dataset['id'],[])
            if not indices: continue
            if dataset.get('embedding_key'):
                model=Model(self.secrets['models'][dataset['embedding_key']])
                query_vectors,_=model.embeddings([query],input_type='query'); q=query_vectors[0]
                for offset in range(0,len(indices),32):
                    self.check(); batch=indices[offset:offset+32];values,_=model.embeddings([docs[i]['content'] for i in batch])
                    for index,vector in zip(batch,values):scores[index]=cosine(q,vector)
            else:
                words=set(re.findall(r'\w+',query.casefold()))
                for i in indices:
                    terms=re.findall(r'\w+',docs[i]['content'].casefold()); scores[i]=sum(1 for t in terms if t in words)/max(1,len(terms))
        config=data.get('multiple_retrieval_config',{}); top=min(20,max(1,int(config.get('top_k',4))))
        ranked=sorted(scores,key=scores.get,reverse=True)
        rerank=self.secrets['models'].get(identity+':rerank')
        if rerank:
            values=Model(rerank).rerank(query,[docs[i]['content'] for i in ranked[:100]],top)
            candidates=ranked[:100]; ranked=[candidates[v['index']] for v in values]; scores.update({candidates[v['index']]:v['score'] for v in values})
        threshold=config.get('score_threshold'); output=[]
        for i in ranked:
            if threshold is not None and scores[i]<threshold: continue
            d=docs[i]; output.append(dict(title=d['title'],content=d['content'],metadata=dict(_source='knowledge',dataset_id=d['dataset_id'],dataset_name=d['dataset_name'],document_id=d['document_id'],document_name=d['title'],segment_id=d['id'],segment_position=d['position'],score=scores[i])))
            if len(output)>=top: break
        return output
    def http(self,data):
        url=self.text(data['url']); headers={}; raw=data.get('headers','')
        if isinstance(raw,str):
            for line in self.text(raw).splitlines():
                if ':' in line:
                    k,v=line.split(':',1);headers[k.strip()]=v.strip()
        method=data.get('method','get').upper()
        if method not in ('GET','POST','PUT','PATCH','DELETE','HEAD'): raise ExecutionFailure('unsupported_definition')
        from urllib.parse import urlsplit
        p=urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password: raise ExecutionFailure('network_failed')
        body=data.get('body',{}); content=None
        if body.get('type') not in (None,'none'):
            if body['type'] not in ('raw-text','json'): raise ExecutionFailure('unsupported_definition')
            text=body.get('data',''); text=text[0].get('value','') if isinstance(text,list) and text else text
            content=self.text(text).encode()
        try:
            request=Request(url,data=content,headers=headers,method=method)
            with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=60) as response:
                value=response.read(1048577)
                if len(value)>1048576: raise ExecutionFailure('network_failed')
                return dict(status_code=response.status,headers=dict(response.headers),body=value.decode('utf-8'),files=[])
        except Exception: raise ExecutionFailure('network_failed') from None
    @staticmethod
    def output_types(output,schema):
        if not isinstance(output,dict): raise ExecutionFailure('invalid_output')
        for key,spec in schema.items():
            value=output.get(key,MISSING); kind=spec.get('type'); valid=False
            if kind=='string': valid=isinstance(value,str)
            elif kind=='number': valid=type(value) in (int,float) and math.isfinite(value)
            elif kind=='boolean': valid=type(value) is bool
            elif kind=='object': valid=isinstance(value,dict)
            elif kind and kind.startswith('array'): valid=isinstance(value,list)
            if not valid: raise ExecutionFailure('invalid_output')

def cosine(a,b):
    if not isinstance(a,list) or not isinstance(b,list) or len(a)!=len(b): raise ExecutionFailure('knowledge_failed')
    return sum(x*y for x,y in zip(a,b))/(math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b)) or 1)
