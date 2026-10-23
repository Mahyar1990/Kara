"""Build the versioned, credential-free PA-04 native Workflow DSL."""
import ast
import json
from pathlib import Path
from .contract import ROOT,SCHEMAS,VERSION,canonical,digest

REVISION='0.1.3'
PROMPT_REVISION='0.1.2'
PROVIDER='langgenius/openai_api_compatible/openai_api_compatible'
PLUGIN='langgenius/openai_api_compatible:0.0.68@ba61c5eccb814be7364117c0bec3710a51e09b20f31e37243e747a00f9377969'
MODEL='Clasor PA04 Pilot v0.1.1'
MODEL_PROFILE=dict(stream_include_usage='disabled',compatibility_mode='extended',agent_thought_support='not_supported')


def runtime_code():
    source=(ROOT/'contract.py').read_text()
    names={'ContractError','digest','canonical','parse','shape','bounded','validate_context','validate_analysis'}
    selected=[ast.get_source_segment(source,n) for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    return 'import hashlib,json,math,re\nMAX_BYTES=32768\nSCHEMAS=json.loads('+repr(canonical(SCHEMAS))+')\n'+'\n\n'.join(selected)+'\n'


def prepare_code():
    return runtime_code()+'''
def main(request, mode, source_context, feedback_context):
    shape(mode, SCHEMAS['input']['properties']['mode'])
    if feedback_context is None:
        feedback_context=''
    shape(feedback_context, SCHEMAS['input']['properties']['feedback_context'])
    context=parse(source_context)
    if type(context) is not dict or set(context)!={'sources','previous_analysis'}:
        raise ContractError('context_fields')
    validate_context(request, context['sources'])
    previous=context['previous_analysis']
    shape(previous, SCHEMAS['input']['properties']['previous_analysis'])
    if previous is not None:
        bounded(parse(previous), SCHEMAS['output'])
    if mode in ('clarify','review_change') and not feedback_context.strip():
        raise ContractError('feedback_required')
    if mode=='review_change' and previous is None:
        raise ContractError('previous_analysis_required')
    data=dict(request=request, mode=mode, sources=context['sources'], previous_analysis=previous,
        feedback_context=feedback_context, request_sha256=digest(request))
    prompt_data=canonical(data)
    if len(prompt_data.encode('utf-8'))>MAX_BYTES:
        raise ContractError('transport_budget')
    return dict(prompt_data=prompt_data)
'''


def validator_code():
    return runtime_code()+'''
def main(text, finish_reason, request, source_context):
    if finish_reason!='stop':
        raise ContractError('incomplete_output')
    context=parse(source_context)
    if type(context) is not dict or set(context)!={'sources','previous_analysis'}:
        raise ContractError('context_fields')
    return dict(analysis=canonical(validate_analysis(text, request, context['sources'])))
'''


def build():
    prompt=(ROOT/'prompt.md').read_text()+'\n\nJSON Schema:\n'+canonical(SCHEMAS['output'])
    def node(key,data,x):return dict(id=key,type='custom',data=data,position=dict(x=x,y=200),width=244,height=100,sourcePosition='right',targetPosition='left')
    def variable(name,selector):return dict(variable=name,value_selector=selector)
    nodes=[node('start',dict(type='start',title='ورودی تحلیل',variables=[
        dict(variable='request',label='متن اصلی نیازمندی',type='paragraph',required=True,max_length=4000),
        dict(variable='mode',label='حالت تحلیل',type='select',options=['analyze','clarify','review_change'],required=True),
        dict(variable='source_context',label='منابع منتخب و تحلیل پیشین',type='paragraph',required=True,max_length=30000),
        dict(variable='feedback_context',label='بازخورد و خروجی مبنا',type='paragraph',required=False,max_length=8000)]),0),
        node('prepare',dict(type='code',title='کنترل ورودی',code_language='python3',code=prepare_code(),
            variables=[variable(k,['start',k]) for k in ('request','mode','source_context','feedback_context')],outputs={'prompt_data':{'type':'string','children':None}}),300),
        node('llm',dict(type='llm',title='تحلیلگر نیازمندی PA-04',context=dict(enabled=False,variable_selector=[]),
            model=dict(provider=PROVIDER,name=MODEL,mode='chat',completion_params=dict(temperature=0.1,max_tokens=4096)),
            prompt_template=[dict(role='system',text=prompt),dict(role='user',text='{{#prepare.prompt_data#}}')],
            vision=dict(enabled=False),retry_config=dict(retry_enabled=False,max_retries=0,retry_interval=1000)),600),
        node('validate',dict(type='code',title='اعتبارسنجی تحلیل',code_language='python3',code=validator_code(),
            kara_output_validator=dict(version=1,candidate_arguments=dict(text='analysis')),
            variables=[variable('text',['llm','text']),variable('finish_reason',['llm','finish_reason']),variable('request',['start','request']),variable('source_context',['start','source_context'])],
            outputs={'analysis':{'type':'string','children':None}}),900),
        node('end',dict(type='end',title='پیش‌نویس برای بررسی انسان',outputs=[dict(variable='analysis',value_selector=['validate','analysis'],value_type='string')]),1200)]
    edges=[dict(id=a+'-'+b,source=a,target=b,sourceHandle='source',targetHandle='target',type='custom',data=dict(sourceType=nodes[i]['data']['type'],targetType=nodes[i+1]['data']['type'])) for i,(a,b) in enumerate(zip(['start','prepare','llm','validate'],['prepare','llm','validate','end']))]
    return dict(kind='app',version='0.4.0',app=dict(name='تحلیل نیازمندی کلاسور · PA-04',description='تحلیل و AC نسخه‌دار؛ تصمیم نهایی با انسان',mode='workflow',icon='🤖',icon_background='#FFEAD5',use_icon_as_answer_icon=False),dependencies=[dict(type='marketplace',value=dict(marketplace_plugin_unique_identifier=PLUGIN))],workflow=dict(environment_variables=[],conversation_variables=[],rag_pipeline_variables=[],features={},graph=dict(nodes=nodes,edges=edges,viewport=dict(x=0,y=0,zoom=0.8))))


def manifest():
    return dict(role_id='PA-04',workflow_revision=REVISION,prompt_revision=PROMPT_REVISION,contract_version=VERSION,
        prompt_sha256=digest((ROOT/'prompt.md').read_text()),workflow_sha256=digest(canonical(build())),
        builder_sha256=digest(Path(__file__).read_text()),adapter_sha256=digest((ROOT/'native.py').read_text()),contract_sha256=digest((ROOT/'contract.py').read_text()),
        model_alias=MODEL,provider=PROVIDER,model_profile=MODEL_PROFILE,context_cap=16384,response_cap=4096,automatic_retries=0)
