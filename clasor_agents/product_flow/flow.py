"""PA-04 -> TL mapping and offline preflight against authenticated Kara reads."""
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4
from clasor_agents.pa04.contract import ContractError, canonical, digest
from clasor_agents.pa04.inputs import check_preview
from clasor_agents.pa04.workflow import build as analysis_workflow
from clasor_agents.tl_planner.workflow import build as planning_workflow
from clasor_agents.tl_planner.handoff import prepare
from clasor_agents.tl_planner.transport import build_inputs

ROOT = Path(__file__).parent
VERSION = '0.1.0'
INITIAL_FEEDBACK = 'هنوز بازخوردی ثبت نشده است.'


def template():
    def constant(value): return dict(source='constant', value=value)
    def stage(key,title,role,inputs):
        return dict(key=key,title=title,agent_id=None,executor_id=None,executor_membership_id=None,
                    finalizer_id=None,finalizer_membership_id=None,decision_role=role,inputs=inputs)
    return dict(name='تحلیل و برنامه‌ریزی کلاسور',description='تحلیل با PO و برنامه‌ریزی با TL؛ تصمیم‌ها انسانی‌اند.',
        expected_revision=1,stages=[
            stage('analysis','تحلیل درخواست','po',dict(request=dict(source='request'),
                mode=constant('analyze'),source_context=constant(canonical(dict(sources=[],previous_analysis=None))),
                feedback_context=constant(INITIAL_FEEDBACK))),
            stage('planning','برنامه‌ریزی فنی','tl',dict(request=dict(source='request'),
                analysis=dict(source='stage',stage_key='analysis',output='analysis'),
                planning_context=constant('{}'),expected_input_sha256=constant('0'*64),
                feedback_context=constant(INITIAL_FEEDBACK)))])


def contracts(workflow):
    """Same public Start/End projection used by Kara registration; no private graph."""
    nodes = workflow['workflow']['graph']['nodes']
    start = next(n['data'] for n in nodes if n['data']['type']=='start')
    inputs = [dict(variable=v['variable'],label=v['label'],type=v['type'],required=v['required'],
                   max_length=v.get('max_length'),options=v.get('options',[])) for v in start['variables']]
    outputs = sorted({v['variable'] for n in nodes if n['data']['type']=='end' for v in n['data']['outputs']})
    return sorted(inputs,key=lambda v:v['variable']),outputs


def bind(options, selections):
    """Select IDs from fresh /flows/options; workflow IDs are independent import pins.

    options and the pinned selections are trusted caller data, never model output.
    This prepares a draft body only; native publication rechecks all permissions.
    """
    try:
        if set(selections) != {'analysis','planning'}:
            raise ContractError('flow_selection_fields')
        result=template()
        for stage,workflow in zip(result['stages'],(analysis_workflow(),planning_workflow())):
            chosen=selections[stage['key']]
            if set(chosen) != {'agent_id','workflow_id','account_id','membership_id'}:
                raise ContractError('flow_selection_fields')
            if any(str(UUID(v)) != v for v in chosen.values()):
                raise ContractError('flow_selection_id')
            agents=[a for a in options['agents'] if a['id']==chosen['agent_id']]
            members=[m for m in options['members'] if m['account_id']==chosen['account_id']]
            if len(agents)!=1 or len(members)!=1:
                raise ContractError('flow_selection_missing')
            agent,member=agents[0],members[0]
            if (agent['workflow_id']!=chosen['workflow_id'] or member['membership_id']!=chosen['membership_id']):
                raise ContractError('flow_selection_stale')
            expected_inputs,expected_outputs=contracts(workflow)
            if (sorted(agent['input_contract'],key=lambda v:v['variable'])!=expected_inputs
                    or agent['output_contract']!=expected_outputs):
                raise ContractError('flow_contract_mismatch')
            if (stage['decision_role'] not in member['roles'] or chosen['account_id'] not in agent['runners']
                    or chosen['account_id'] not in agent['finalizers']):
                raise ContractError('flow_authority_missing')
            stage.update(agent_id=chosen['agent_id'],executor_id=chosen['account_id'],finalizer_id=chosen['account_id'],
                executor_membership_id=chosen['membership_id'],finalizer_membership_id=chosen['membership_id'])
        if result['stages'][0]['agent_id']==result['stages'][1]['agent_id']:
            raise ContractError('flow_agent_conflict')
        return result
    except (KeyError,TypeError,AttributeError,ValueError) as error:
        if isinstance(error,ContractError): raise
        raise ContractError('flow_selection_fields') from None


def _fresh(package, request, instance, stage):
    b=package['expected_binding']; current=request['current']
    for key,expected in [('project_id',b['project_id']),('workspace_id',package['provenance']['workspace_id'])]:
        if any(row[key]!=expected for row in (request,current,instance,stage)):
            raise ContractError('flow_scope_mismatch')
    if (request['id']!=b['request_id'] or current['request_id']!=b['request_id']
            or instance['request_id']!=b['request_id'] or current['id']!=b['request_revision_id']
            or request['current_revision_id']!=current['id'] or instance['request_revision_id']!=current['id']
            or current['digest']!=instance['request_digest']
            or current['digest']!=package['provenance']['request_digest']
            or digest(current['content'])!=b['request_sha256']
            or instance['id']!=package['provenance']['instance_id'] or stage['instance_id']!=instance['id']):
        raise ContractError('flow_request_stale')
    if (any(row['intake_valid'] is not True for row in (request,instance,stage))
            or instance['state']=='cancelled' or stage['state']!='ready' or stage['input_error'] is not None):
        raise ContractError('flow_stage_not_ready')
    if stage['preview_inputs'].get('request')!=current['content']:
        raise ContractError('original_request_changed')


def _responsible(stage, actor, published_binding, key, action):
    if stage['step_key']!=key or stage['binding']!=published_binding:
        raise ContractError('flow_binding_mismatch')
    role='po' if key=='analysis' else 'tl'
    person=published_binding['executor']
    if (published_binding['decision_role']!=role or any(person[k]!=actor[k] for k in ('account_id','membership_id'))):
        raise ContractError('flow_responsible_mismatch')
    finalizer=published_binding['finalizer']
    if any(finalizer[k]!=person[k] for k in ('account_id','membership_id')):
        raise ContractError('flow_responsible_mismatch')
    mapping=template()['stages'][0 if key=='analysis' else 1]['inputs']
    if published_binding['inputs']!=mapping:
        raise ContractError('flow_mapping_mismatch')
    if action not in stage['actions']:
        raise ContractError('flow_action_unavailable')


def analysis_run(package, request, instance, stage, actor, published_binding):
    """Reviewable run body only. Read snapshots under the actual PO session."""
    _fresh(package,request,instance,stage)
    _responsible(stage,actor,published_binding,'analysis','run')
    check_preview(package,stage)
    return dict(expected_revision=stage['revision'])


def planning_setup(package, request, instance, stage, actor, published_binding, receipt, repositories):
    """Prepare first TL input setup via native feedback; never submit it here.

    Stage/decision IDs do not exist at flow definition time. Predict exactly one
    CAS increment, then require a fresh server read before a separate run body.
    """
    _fresh(package,request,instance,stage)
    _responsible(stage,actor,published_binding,'planning','feedback')
    if stage['inputs'] is not None or stage['attempts'] or stage['feedback'] or stage['artifacts']:
        raise ContractError('planning_setup_already_started')
    prospective=deepcopy(stage)
    prospective['revision']+=1
    prepared=prepare(package,prospective,receipt,repositories)
    expected_hash=digest(canonical(prepared))
    inputs=build_inputs(prepared,expected_hash,INITIAL_FEEDBACK)
    return dict(idempotency_key=str(uuid4()),run_idempotency_key=str(uuid4()),
        body=dict(expected_revision=stage['revision'],artifact_id=None,
            message='آماده‌سازی ورودی برنامه‌ریزی از تحلیل منتخب؛ بدون تصمیم یا اجرای مدل.',
            inputs=inputs,feedback_variable=None),
        prepared_input=prepared,expected_input_sha256=expected_hash,
        expectation=dict(stage_id=stage['id'],instance_id=instance['id'],flow_version_id=instance['flow_version_id'],
            revision=prospective['revision'],round=stage['round']+1,binding=deepcopy(published_binding),actor=deepcopy(actor)))


def planning_run(setup, package, request, instance, stage, actor):
    """After setup response/readback: verify CAS, source receipt and effective inputs."""
    _fresh(package,request,instance,stage)
    expected=setup['expectation']
    _responsible(stage,actor,expected['binding'],'planning','run')
    if (actor!=expected['actor'] or stage['id']!=expected['stage_id']
            or instance['id']!=expected['instance_id'] or instance['flow_version_id']!=expected['flow_version_id']
            or stage['revision']!=expected['revision'] or stage['round']!=expected['round']):
        raise ContractError('planning_setup_stale')
    prepared=setup['prepared_input']
    # Re-read selected content/receipt, not upstream drafts or another account's logs.
    fresh=prepare(package,stage,prepared['binding']['finalization'],prepared['repositories'])
    if fresh!=prepared or digest(canonical(fresh))!=setup['expected_input_sha256']:
        raise ContractError('planning_setup_stale')
    expected_inputs=build_inputs(fresh,setup['expected_input_sha256'],INITIAL_FEEDBACK)
    if stage['preview_inputs']!=expected_inputs or stage['inputs']!=expected_inputs:
        raise ContractError('preview_inputs_mismatch')
    history=[f for f in stage['feedback'] if f['round']==expected['round']]
    if (len(history)!=1 or not stage['input_digest'] or history[0]['input_digest']!=stage['input_digest']
            or history[0]['parent_artifact_id'] is not None or history[0]['inputs']['feedback_variable'] is not None
            or history[0]['inputs']['effective']!=expected_inputs or history[0]['inputs']['submitted']!=expected_inputs):
        raise ContractError('planning_setup_receipt_mismatch')
    return dict(expected_revision=stage['revision'])


def manifest():
    return dict(kind='kara-clasor-team-flow',version=VERSION,status='offline-preflight-only',
        template_sha256=digest(canonical(template())),builder_sha256=digest((ROOT/'flow.py').read_text()),
        adapters={name:digest((ROOT.parent/name).read_text()) for name in
            ('pa04/inputs.py','tl_planner/handoff.py','tl_planner/transport.py')},
        workflows={name:digest(canonical(builder())) for name,builder in
            [('analysis',analysis_workflow),('planning',planning_workflow)]},
        published=False,live_acceptance=False,automatic_runs=0)
