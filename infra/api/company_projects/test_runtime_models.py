"""Personal runtime selection through persisted graphs and native admission adapters."""
import json
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from company_projects import agents, agent_execution, personal_models, personal_model_runtime, runtime_models as runtime, stages
from company_projects.test_agents import AgentTests, graph as base_graph
from company_projects.test_personal_models import PersonalModelTests, schema, PROVIDER
from company_projects.test_stages import StageFixture
from core.app.apps.workflow.app_generator import WorkflowAppGenerator
from core.app.llm.model_access import DifyCredentialsProvider, DifyModelFactory, fetch_model_config
from core.model_manager import ModelManager
from core.plugin.impl.model import PluginModelClient
from core.provider_manager import ProviderManager
from graphon.model_runtime.entities.common_entities import I18nObject
from graphon.model_runtime.entities.model_entities import AIModelEntity, FetchFrom, ModelType
from graphon.nodes.llm.entities import ModelConfig
from models.account import TenantAccountJoin
from models.workflow import Workflow
from services.workflow_service import WorkflowService


def runtime_graph():
    value = base_graph()
    value['nodes'][0]['data']['variables'].insert(0, dict(variable=runtime.INPUT, label='مدل اجرای برنامه',
        type='text-input', required=False, max_length=36, kara_model_input=dict(version=1, capabilities=[])))
    value['nodes'].insert(1, dict(id='llm', data=dict(type='llm', title='پاسخ',
        model=dict(provider=runtime.PROVIDER, name='executor-model', mode='chat', completion_params={}),
        prompt_template=[dict(role='user', text='{{#start.request#}}')], context=dict(enabled=False, variable_selector=[]),
        vision=dict(enabled=False))))
    value['edges'] = [dict(id='e1', source='start', target='llm', sourceHandle='source', targetHandle='target'),
        dict(id='e2', source='llm', target='end', sourceHandle='source', targetHandle='target')]
    value['nodes'][-1]['data']['outputs'][0]['value_selector'] = ['llm', 'text']
    return value


def model_schema(features=(), rules=()):
    return AIModelEntity(model='synthetic-model', label=I18nObject(en_US='Synthetic'), model_type=ModelType.LLM,
        fetch_from=FetchFrom.CUSTOMIZABLE_MODEL, model_properties={'mode': 'chat'}, features=list(features), parameter_rules=list(rules))


def setup_models(case):
    for target, name, replacement in ((personal_models, 'schemas', lambda *_: [schema()]),
            (personal_model_runtime, 'Session', lambda *_a, **_k: nullcontext(case.session)),
            (runtime, 'Session', lambda *_a, **_k: nullcontext(case.session)),
            (runtime, 'schema_for', lambda *_: model_schema())):
        active = patch.object(target, name, side_effect=replacement)
        active.start(); case.addCleanup(active.stop)


class RuntimeModelTests(AgentTests):
    def setUp(self):
        super().setUp()
        self.workflow.graph = json.dumps(runtime_graph())
        self.session.flush()
        setup_models(self)

    def save_model(self, actor=None, **updates):
        return PersonalModelTests.save_connection(self, actor=actor, **updates)

    def test_runtime_owned_default_explicit_selection_and_no_other_users_fallback(self):
        with self.assertRaises(BadRequest):
            runtime.select(self.session, self.workflow, self.editor.id)
        own = self.save_model()
        other = self.save_model(actor=self.project_owner, model_name='owners-model')
        self.assertEqual(runtime.select(self.session, self.workflow, self.editor.id)['connection_id'], own['id'])
        self.assertEqual(runtime.select(self.session, self.workflow, self.project_owner.id)['model_name'], 'owners-model')
        with self.assertRaises(NotFound):
            runtime.select(self.session, self.workflow, self.editor.id, other['id'])
        with self.assertRaises(BadRequest):
            runtime.select(self.session, self.workflow, self.editor.id, {'provider': PROVIDER, 'api_key': 'unsafe'})
        with self.assertRaises(BadRequest):
            runtime.select(self.session, self.workflow, self.editor.id, 'not-a-connection')
        self.assertEqual([item['id'] for item in runtime.options(self.session, self.workspace_a.id, self.editor.id, [])['data']], [own['id']])

    def test_runtime_transient_execution_graph_preserves_source_digest_and_business_inputs(self):
        own = self.save_model()
        original, digest = self.workflow.graph, agents.fingerprint(self.workflow)
        resolved, inputs, selected = runtime.prepare(self.workflow, self.editor, {'request': 'Original text', runtime.INPUT: own['id']})
        self.assertEqual(inputs, {'request': 'Original text'})
        self.assertTrue(sa.inspect(resolved).transient)
        self.assertEqual(resolved.id, self.workflow.id)
        self.assertEqual(resolved.graph_dict['nodes'][1]['data']['model']['name'], 'synthetic-model')
        self.assertEqual(resolved.graph_dict['nodes'][0]['data']['kara_runtime_model_used'], selected)
        self.assertNotIn(runtime.INPUT, [item['variable'] for item in resolved.user_input_form()])
        self.assertNotIn('synthetic-key-', resolved.graph)
        self.session.flush()
        self.assertEqual(self.workflow.graph, original)
        self.assertEqual(agents.fingerprint(self.workflow), digest)
        self.assertEqual(agents.contracts(self.workflow)[0][0]['variable'], 'request')
        self.assertEqual(len(agents.contracts(self.workflow)[0]), 1)

    def test_runtime_missing_capability_and_bad_parameters_fail_before_model_dispatch(self):
        self.save_model()
        graph = self.workflow.graph_dict
        graph['nodes'][1]['data']['vision']['enabled'] = True
        graph['nodes'][1]['data']['structured_output_enabled'] = True
        self.workflow.graph = json.dumps(graph)
        self.assertEqual(runtime.policy(graph)['capabilities'], ['json', 'vision'])
        self.assertEqual(runtime.options(self.session, self.workspace_a.id, self.editor.id, ['vision'])['data'], [])
        with self.assertRaises(BadRequest):
            runtime.select(self.session, self.workflow, self.editor.id)
        native = model_schema(features=['vision', 'structured-output', 'tool-call'], rules=[dict(name='temperature', type='float',
            label={'en_US': 'Temperature'}, min=0, max=1, default=0.5)])
        with patch.object(runtime, 'schema_for', return_value=native):
            self.assertIsNotNone(runtime.select(self.session, self.workflow, self.editor.id))
            graph['nodes'][1]['data']['model']['completion_params'] = {'temperature': 2}
            self.workflow.graph = json.dumps(graph)
            with self.assertRaises(BadRequest): runtime.select(self.session, self.workflow, self.editor.id)
            graph['nodes'][1]['data']['model']['completion_params'] = {'temperature': True}
            self.workflow.graph = json.dumps(graph)
            with self.assertRaises(BadRequest): runtime.select(self.session, self.workflow, self.editor.id)
            graph['nodes'][1]['data']['model']['completion_params'] = {'unknown': 1}
            self.workflow.graph = json.dumps(graph)
            with self.assertRaises(BadRequest): runtime.select(self.session, self.workflow, self.editor.id)

    def test_runtime_queue_resume_rechecks_account_connection_revision_and_membership(self):
        own = self.save_model()
        selected = runtime.select(self.session, self.workflow, self.editor.id)
        runner = SimpleNamespace(_workflow=self.workflow, application_generate_entity=SimpleNamespace(user_id=self.editor.id, extras={runtime.EXTRA: selected}))
        runtime.bind_runner(runner)
        self.assertEqual(runner._workflow.graph_dict['nodes'][1]['data']['model']['name'], own['model_name'])
        with self.assertRaises(Forbidden): runtime.execution_workflow(self.workflow, selected, self.project_owner.id)
        self.save_model(old=own, name='Updated')
        with self.assertRaises(Conflict): runtime.execution_workflow(self.workflow, selected, self.editor.id)
        selected = runtime.select(self.session, self.workflow, self.editor.id)
        join = self.session.scalar(sa.select(TenantAccountJoin).where(TenantAccountJoin.tenant_id == self.workspace_a.id, TenantAccountJoin.account_id == self.editor.id))
        self.session.delete(join); self.session.flush()
        with self.assertRaises(NotFound): runtime.execution_workflow(self.workflow, selected, self.editor.id)

    def test_runtime_native_generator_strips_runtime_control_and_overwrites_forged_extras(self):
        own = self.save_model()
        supplied = {'inputs': {'request': 'source', runtime.INPUT: own['id']}, 'files': [],
            '_kara_runtime_selection': {'actor_id': self.project_owner.id}}
        from core.app.entities.app_invoke_entities import InvokeFrom
        with patch.object(WorkflowAppGenerator, '_generate', return_value={'ok': True}) as generate:
            result = WorkflowAppGenerator().generate(app_model=self.app_model, workflow=self.workflow, user=self.editor,
                args=supplied, invoke_from=InvokeFrom.DEBUGGER, streaming=False)
        self.assertEqual(result, {'ok': True})
        entity = generate.call_args.kwargs['application_generate_entity']
        self.assertEqual(entity.inputs, {'request': 'source'})
        self.assertEqual(entity.extras[runtime.EXTRA]['actor_id'], self.editor.id)
        self.assertEqual(entity.extras[runtime.EXTRA]['connection_id'], own['id'])
        self.assertEqual(supplied['inputs'][runtime.INPUT], own['id'])
        self.assertEqual(self.workflow.graph_dict['nodes'][1]['data']['model']['provider'], runtime.PROVIDER)

    def test_runtime_native_iteration_and_loop_keep_server_selection(self):
        own = self.save_model()
        from controllers.console.app.workflow import LoopNodeRunPayload
        from services.workflow_draft_variable_service import WorkflowDraftVariableService
        with patch.object(WorkflowAppGenerator, '_generate', return_value={}) as generate, \
                patch.object(WorkflowDraftVariableService, 'prefill_conversation_variable_default_values'):
            generator = WorkflowAppGenerator()
            generator.single_iteration_generate(app_model=self.app_model, workflow=self.workflow, user=self.editor,
                node_id='iteration', args={'inputs': {runtime.INPUT: own['id']}}, session=self.session)
            entity = generate.call_args.kwargs['application_generate_entity']
            self.assertEqual(entity.single_iteration_run.inputs, {})
            self.assertEqual(entity.extras[runtime.EXTRA]['connection_id'], own['id'])
            generator.single_loop_generate(app_model=self.app_model, workflow=self.workflow, user=self.editor,
                node_id='loop', args=LoopNodeRunPayload(inputs={runtime.INPUT: own['id']}), session=self.session)
            entity = generate.call_args.kwargs['application_generate_entity']
            self.assertEqual(entity.single_loop_run.inputs, {})
            self.assertEqual(entity.extras[runtime.EXTRA]['actor_id'], self.editor.id)

    def test_runtime_publication_without_authors_model_and_legacy_publish_validation(self):
        service = WorkflowService()
        with patch.object(service, '_validate_llm_model_config', side_effect=AssertionError('author model is not a requirement')):
            service._validate_workflow_credentials(self.workflow, session=self.session)
        graph = self.workflow.graph_dict
        graph['nodes'][0]['data']['variables'] = [item for item in graph['nodes'][0]['data']['variables'] if item['variable'] != runtime.INPUT]
        graph['nodes'][1]['data']['model'].update(provider=PROVIDER, name='fixed-model')
        self.workflow.graph = json.dumps(graph)
        with patch.object(service, '_validate_llm_model_config') as validate:
            service._validate_workflow_credentials(self.workflow, session=self.session)
        validate.assert_called_once_with(self.workspace_a.id, PROVIDER, 'fixed-model')
        self.assertIs(runtime.prepare(self.workflow, self.editor, {'request': 'legacy'})[0], self.workflow)

    def test_runtime_resolved_graph_uses_native_model_access_and_final_personal_credential_guard(self):
        self.save_model()
        resolved, _, _ = runtime.prepare(self.workflow, self.editor, {'request': 'source'})
        native = SimpleNamespace(user_id=self.editor.id, fetch_model_providers=lambda: [schema()], get_model_schema=lambda **_: model_schema())
        manager = ProviderManager(model_runtime=native)
        from core.app.entities.app_invoke_entities import DifyRunContext, InvokeFrom, UserFrom
        context = DifyRunContext(tenant_id=self.workspace_a.id, app_id=self.app_model.id, user_id=self.editor.id, user_from=UserFrom.ACCOUNT, invoke_from=InvokeFrom.DEBUGGER)
        provider = DifyCredentialsProvider(run_context=context, provider_manager=manager)
        factory = DifyModelFactory(run_context=context, model_manager=ModelManager(provider_manager=manager))
        instance, config = fetch_model_config(node_data_model=ModelConfig.model_validate(resolved.graph_dict['nodes'][1]['data']['model']), credentials_provider=provider, model_factory=factory)
        self.assertEqual(config.model, 'synthetic-model')
        self.assertEqual(instance.credentials['api_key'], 'synthetic-key-' + self.editor.id)
        client = PluginModelClient()
        with patch.object(client, '_request_with_plugin_daemon_response_stream', return_value=iter(())) as send:
            list(client.invoke_llm(tenant_id=self.workspace_a.id, user_id=self.editor.id, plugin_id='langgenius/openai', provider='openai',
                model=instance.model_name, credentials={'api_key': 'WRONG-KEY'}, prompt_messages=[], model_parameters={}, stream=True))
        self.assertEqual(send.call_args.kwargs['data']['data']['credentials']['api_key'], 'synthetic-key-' + self.editor.id)


class RuntimeStageTests(StageFixture):
    def setUp(self):
        with patch('company_projects.test_stages.graph', runtime_graph):
            super().setUp()
        setup_models(self)

    def test_runtime_stage_choice_is_separate_from_immutable_business_handoff(self):
        selected = PersonalModelTests.save_connection(self)
        from company_projects import local_execution as local, source_code as source
        code = source.pairing(self.session, self.editor.id, dict(name='Stage device'))['code']
        device = source.authenticate(self.session, source.pair(self.session, dict(code=code))['secret'])
        local.register(self.session, device, dict(protocol=2, capabilities=['workflow-v2', 'node-routing-v1']))
        choice = json.dumps(dict(version=2, models={'llm': selected['id']}, runners={'llm': dict(device_id=device['id'], source_job_id=None)}))
        stage = self.get()
        self.assertIsNotNone(stage['runtime_model'])
        self.assertNotIn(runtime.INPUT, stage['preview_inputs'])
        row = stages.mutate(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            self.inst['id'], stage['id'], 'run', dict(expected_revision=stage['revision'], model_connection_id=choice), str(uuid4()))
        attempts = agents.tables(self.session)[2]
        attempt = self.session.execute(sa.select(attempts).where(attempts.c.id == row['active_attempt_id'])).mappings().one()
        self.assertEqual(json.loads(attempt['inputs'][runtime.INPUT])['models']['llm'], selected['id'])
        self.assertEqual(runtime.business_inputs(attempt['inputs']), stage['preview_inputs'])
        self.assertIsNotNone(agent_execution.claim(self.session, attempt['id']))
        self.assertEqual(stages.validate_attempt(self.session, attempt)['id'], stage['id'])
