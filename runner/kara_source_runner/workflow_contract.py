"""Versioned, fail-closed workflow contract shared by server and Runner."""
SUPPORTED={'start','end','answer','llm','code','if-else','variable-aggregator','knowledge-retrieval','template-transform','http-request','trigger-schedule','trigger-webhook'}

def validate_graph(graph):
    if not isinstance(graph,dict) or not isinstance(graph.get('nodes'),list) or not graph['nodes'] or len(graph['nodes'])>500: raise ValueError('invalid_graph')
    nodes={}; needs={'workflow-v2'}
    for node in graph['nodes']:
        if not isinstance(node,dict) or not isinstance(node.get('id'),str) or node['id'] in nodes: raise ValueError('invalid_node')
        data=node.get('data',{}); kind=data.get('type')
        if kind not in SUPPORTED: raise ValueError('unsupported_node:'+str(kind))
        nodes[node['id']]=data
        if data.get('error_strategy'): raise ValueError('unsupported_error_strategy')
        if kind=='code':
            language=data.get('code_language')
            if language not in ('python3','javascript'): raise ValueError('unsupported_code_language')
            needs.add(language)
        if kind=='template-transform':needs.add('python3')
        if kind=='http-request': needs.add('http')
        if kind=='llm' and (data.get('vision',{}).get('enabled') or data.get('model',{}).get('mode','chat')!='chat'): raise ValueError('unsupported_llm_mode')
        if kind=='knowledge-retrieval' and data.get('metadata_filtering_mode','disabled')!='disabled': raise ValueError('unsupported_metadata_filter')
    roots=[k for k,v in nodes.items() if v['type'] in ('start','trigger-schedule','trigger-webhook')]
    if not roots: raise ValueError('missing_start')
    edges=graph.get('edges',[]); incoming={n:0 for n in nodes}; outgoing={n:[] for n in nodes}
    if not isinstance(edges,list) or len(edges)>2000: raise ValueError('invalid_edges')
    for e in edges:
        if e.get('source') not in nodes or e.get('target') not in nodes: raise ValueError('invalid_edge')
        incoming[e['target']]+=1; outgoing[e['source']].append(e['target'])
    todo=[n for n,count in incoming.items() if not count]; seen=0
    while todo:
        n=todo.pop(); seen+=1
        for target in outgoing[n]:
            incoming[target]-=1
            if incoming[target]==0: todo.append(target)
    if seen!=len(nodes): raise ValueError('unsupported_cycle')
    return sorted(needs)
