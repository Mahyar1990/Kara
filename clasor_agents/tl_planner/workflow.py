"""Reproducible TL native DSL using the existing five-node PA-04 graph layout."""
import ast
from pathlib import Path
from clasor_agents.pa04 import workflow as pa04_workflow
from clasor_agents.pa04 import contract as pa04_contract
from .contract import ROOT, VERSION, OUTPUT_SCHEMA
from .handoff import REPOSITORIES
from .transport import INPUT_SCHEMA, FEEDBACK_SCHEMA, HASH_SCHEMA

canonical, digest = pa04_contract.canonical, pa04_contract.digest
REVISION = '0.1.0'
MODEL = 'Clasor TL Planner Pilot v0.1.0'


def definitions(path, names):
    source = path.read_text()
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    if {n.name for n in nodes} != names:
        raise ValueError('sandbox_definition_missing')
    return '\n\n'.join(ast.get_source_segment(source,n) for n in nodes)+'\n'


def runtime_code(include_plan=False):
    # Only owned pure definitions and literal schemas: no imports from the repo,
    # filesystem access, HTTP, dynamic schema downloads or runtime installation.
    result = ('import hashlib,json,math,re\nMAX_BYTES=32768\n'
        + 'SCHEMAS=json.loads('+repr(canonical(pa04_contract.SCHEMAS))+')\n'
        + 'INPUT_SCHEMA=json.loads('+repr(canonical(INPUT_SCHEMA))+')\n'
        + 'FEEDBACK_SCHEMA=json.loads('+repr(canonical(FEEDBACK_SCHEMA))+')\n'
        + 'HASH_SCHEMA=json.loads('+repr(canonical(HASH_SCHEMA))+')\n')
    result += definitions(pa04_contract.ROOT/'contract.py',
        {'ContractError','canonical','digest','parse','shape','bounded'})
    result += definitions(ROOT/'transport.py', {'validate_prepared','decode_inputs'})
    if include_plan:
        result += 'OUTPUT_SCHEMA=json.loads('+repr(canonical(OUTPUT_SCHEMA))+')\n'
        result += 'REPOSITORIES=set('+repr(sorted(REPOSITORIES))+')\n'
        result += definitions(ROOT/'contract.py', {'validate_plan'})
    return result


def prepare_code():
    return runtime_code()+'''
def main(request, analysis, planning_context, expected_input_sha256, feedback_context):
    return decode_inputs(request, analysis, planning_context, expected_input_sha256, feedback_context)
'''


def validator_code():
    return runtime_code(include_plan=True)+'''
def main(text, finish_reason, prepared_input, input_sha256):
    if finish_reason != 'stop':
        raise ContractError('incomplete_output')
    prepared = parse(prepared_input)
    validate_prepared(prepared, input_sha256)
    return dict(plan=canonical(validate_plan(text, prepared, input_sha256)))
'''


def build():
    # build() returns a fresh object; PA-04 assets/graph/prompt are never modified.
    app = pa04_workflow.build()
    app['app'].update(name='برنامه‌ریزی فنی کلاسور · TL',
        description='پیش‌نویس فنی و پوشش AC برای بررسی TL؛ تصمیم و مرج با انسان')
    nodes = {n['id']:n['data'] for n in app['workflow']['graph']['nodes']}
    specs = [('request','متن اصلی درخواست',4000,True),
        ('analysis','تحلیل نهایی منتخب',16000,True),
        ('planning_context','زمینهٔ برنامه‌ریزی',32768,True),
        ('expected_input_sha256','شناسهٔ صحت بستهٔ ورودی',64,True),
        ('feedback_context','بازخورد و خروجی مبنا',8000,False)]
    nodes['start'].update(title='ورودی برنامه‌ریزی',variables=[dict(variable=key,label=label,
        type='paragraph',required=required,max_length=limit) for key,label,limit,required in specs])
    def var(name,selector): return dict(variable=name,value_selector=selector)
    nodes['prepare'].update(code=prepare_code(),
        variables=[var(key,['start',key]) for key,_,_,_ in specs],
        outputs={key:dict(type='string',children=None) for key in ('prompt_data','prepared_input','input_sha256')})
    nodes['llm'].update(title='برنامه‌ریز فنی TL',
        prompt_template=[dict(role='system',text=(ROOT/'prompt.md').read_text()+'\n\nJSON Schema:\n'+canonical(OUTPUT_SCHEMA)),
                         dict(role='user',text='{{#prepare.prompt_data#}}')])
    nodes['llm']['model']['name'] = MODEL
    nodes['validate'].update(title='اعتبارسنجی برنامه',code=validator_code(),
        variables=[var('text',['llm','text']),var('finish_reason',['llm','finish_reason']),
                   var('prepared_input',['prepare','prepared_input']),var('input_sha256',['prepare','input_sha256'])],
        outputs=dict(plan=dict(type='string',children=None)))
    nodes['end']['outputs'] = [dict(variable='plan',value_selector=['validate','plan'],value_type='string')]
    return app


def manifest():
    files = ('prompt.md','contract.py','handoff.py','transport.py','workflow.py',
             'schemas/input.schema.json','schemas/output.schema.json')
    return dict(role_id='TL-PLANNER',workflow_revision=REVISION,prompt_revision=REVISION,
        contract_version=VERSION,artifacts={name:digest((ROOT/name).read_text()) for name in files},
        workflow_sha256=digest(canonical(build())),
        shared_contract_sha256=digest((pa04_contract.ROOT/'contract.py').read_text()),
        graph_builder_sha256=digest(Path(pa04_workflow.__file__).read_text()),
        provider=pa04_workflow.PROVIDER,model_alias=MODEL,model_profile=pa04_workflow.MODEL_PROFILE,
        planned_context_cap=16384,response_cap=4096,automatic_retries=0,
        status='offline-workflow-only',imported=False,published=False,live_model_test=False)
