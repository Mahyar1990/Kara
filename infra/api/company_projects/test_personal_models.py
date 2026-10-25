"""Persisted two-user isolation and native model dispatch without external inference."""
import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

import sqlalchemy as sa
from werkzeug.exceptions import BadGateway, BadRequest, Conflict, Forbidden, NotFound, ServiceUnavailable

from company_projects import personal_models as models, personal_model_runtime as runtime
from company_projects.test_access import ProjectDatabaseFixture
from core.app.entities.app_invoke_entities import DifyRunContext, InvokeFrom, UserFrom
from core.model_manager import ModelManager
from core.plugin.impl.model import PluginModelClient
from core.provider_manager import ProviderManager
from graphon.model_runtime.entities.common_entities import I18nObject
from graphon.model_runtime.entities.model_entities import AIModelEntity, FetchFrom, ModelType
from graphon.model_runtime.entities.provider_entities import ConfigurateMethod, ProviderEntity
from models.account import TenantAccountJoin
from models.model import App

PROVIDER = 'langgenius/openai/openai'


def schema():
    return ProviderEntity.model_validate(dict(provider=PROVIDER, label={'en_US': 'Synthetic provider'},
        supported_model_types=['llm'], configurate_methods=['predefined-model'],
        provider_credential_schema={'credential_form_schemas': [
            dict(variable='endpoint_url', label={'en_US': 'Endpoint'}, type='text-input', required=True),
            dict(variable='api_key', label={'en_US': 'Key'}, type='secret-input', required=True)]}))


class PersonalModelTests(ProjectDatabaseFixture):
    def setUp(self):
        super().setUp()
        self.schemas_patch = patch.object(models, 'schemas', return_value=[schema()])
        self.schemas_patch.start(); self.addCleanup(self.schemas_patch.stop)
        self.session_patch = patch.object(runtime, 'Session', side_effect=lambda *_a, **_k: nullcontext(self.session))
        self.session_patch.start(); self.addCleanup(self.session_patch.stop)

    def save_connection(self, actor=None, old=None, **updates):
        actor = actor or self.editor
        data = dict(name='Personal synthetic model', provider=PROVIDER, model_name='synthetic-model', model_type='llm',
            credentials={'endpoint_url': 'https://model.example.test/v1', 'api_key': 'synthetic-key-' + actor.id},
            is_default=True, expected_revision=old['revision'] if old else 1)
        data.update(updates)
        return models.save(self.session, self.workspace_a.id, actor.id, data, old['id'] if old else None)

    def args(self, actor=None):
        return dict(tenant_id=self.workspace_a.id, user_id=(actor or self.editor).id,
            plugin_id='langgenius/openai', provider='openai', model='synthetic-model', credentials={'api_key': 'SHARED-KEY-MUST-NOT-BE-USED'},
            prompt_messages=[], model_parameters={}, stream=True)

    def test_copy_preserves_only_owned_secrets_and_rejects_changed_destination(self):
        source = self.save_connection()
        original = models.load(self.session, self.editor.id, source['id'])
        draft = dict(name='Copied connection', provider=PROVIDER, model_name='second-model', model_type='llm',
            credentials={'endpoint_url': 'https://model.example.test/v1', 'api_key': ''},
            is_default=False, expected_revision=source['revision'])
        with self.assertRaises(NotFound):
            models.copy_connection(self.session, self.workspace_a.id, self.project_owner.id, source['id'], draft)
        with self.assertRaises(Conflict):
            models.copy_connection(self.session, self.workspace_a.id, self.editor.id, source['id'], dict(draft, expected_revision=99))
        with self.assertRaises(BadRequest):
            models.copy_connection(self.session, self.workspace_a.id, self.editor.id, source['id'],
                dict(draft, credentials={'endpoint_url': 'https://other.example.test/v1', 'api_key': ''}))
        with self.assertRaises(Conflict):
            models.copy_connection(self.session, self.workspace_a.id, self.editor.id, source['id'], dict(draft, model_name='synthetic-model'))
        copied = models.copy_connection(self.session, self.workspace_a.id, self.editor.id, source['id'], draft)
        row = models.load(self.session, self.editor.id, copied['id'])
        self.assertNotEqual(row['id'], source['id'])
        self.assertEqual(models.decrypt(row), models.decrypt(original))
        self.assertNotEqual(row['encrypted_credentials'], original['encrypted_credentials'])
        self.assertEqual(original, models.load(self.session, self.editor.id, source['id']))
        self.assertNotIn('synthetic-key-', json.dumps(copied))
        self.assertFalse(copied['is_default'])
        destination = dict(draft, name='New destination', model_name='third-model',
            credentials={'endpoint_url': 'https://other.example.test/v1', 'api_key': 'synthetic-new-key'})
        changed = models.copy_connection(self.session, self.workspace_a.id, self.editor.id, source['id'], destination)
        self.assertEqual(models.decrypt(models.load(self.session, self.editor.id, changed['id']))['api_key'], 'synthetic-new-key')

    def test_personal_storage_crypto_metadata_update_and_deletion(self):
        first = self.save_connection()
        self.save_connection(actor=self.project_owner)
        self.assertEqual([row['id'] for row in models.list_connections(self.session, self.editor.id)['data']], [first['id']])
        row = models.load(self.session, self.editor.id, first['id'])
        secret = 'synthetic-key-' + self.editor.id
        self.assertNotIn(secret, row['encrypted_credentials'])
        self.assertEqual(models.decrypt(row)['api_key'], secret)
        with self.assertRaises(ServiceUnavailable):
            models.decrypt(dict(row, account_id=self.project_owner.id))
        with self.assertRaises(ServiceUnavailable):
            models.decrypt(dict(row, model_name='other-model'))
        for who in (self.project_owner, self.product_owner, self.other):
            with self.assertRaises(NotFound):
                models.load(self.session, who.id, first['id'])
        detail = models.detail(self.session, self.workspace_a.id, self.editor.id, first['id'])
        self.assertNotIn('api_key', detail['values'])
        self.assertNotIn(secret, json.dumps(detail))
        changed = self.save_connection(old=first, name='Renamed', credentials={'endpoint_url': 'https://model.example.test/v1', 'api_key': ''})
        self.assertEqual(models.decrypt(models.load(self.session, self.editor.id, first['id']))['api_key'], secret)
        with self.assertRaises(BadRequest):
            self.save_connection(old=changed, credentials={'endpoint_url': 'https://other.example.test/v1', 'api_key': ''})
        with self.assertRaises(Conflict):
            self.save_connection(old=first)
        models.delete(self.session, self.editor.id, first['id'], dict(expected_revision=changed['revision']))
        self.assertEqual(models.list_connections(self.session, self.editor.id)['data'], [])

    def test_default_and_native_configuration_never_read_shared_credentials(self):
        first = self.save_connection()
        self.save_connection(actor=self.project_owner, model_name='owners-model')
        native = SimpleNamespace(user_id=self.editor.id, fetch_model_providers=lambda: [schema()],
            get_model_schema=lambda **_kwargs: AIModelEntity(model='synthetic-model', label=I18nObject(en_US='Synthetic'),
                model_type=ModelType.LLM, fetch_from=FetchFrom.CUSTOMIZABLE_MODEL, model_properties={}))
        manager = ProviderManager(model_runtime=native)
        manager._configurations_cache[self.workspace_a.id] = 'SHARED-CACHE-MUST-NOT-BE-USED'
        with patch.object(manager, '_get_all_providers', side_effect=AssertionError('shared credential load')):
            config = manager.get_configurations(self.workspace_a.id)[PROVIDER]
        self.assertEqual([item.model for item in config.custom_configuration.models], ['synthetic-model'])
        self.assertFalse(config.system_configuration.enabled)
        self.assertEqual(config.model_settings, [])
        self.assertEqual([item.model for item in config.get_provider_models(ModelType.LLM)], ['synthetic-model'])
        self.assertEqual(manager.get_default_model(self.workspace_a.id, ModelType.LLM).model, 'synthetic-model')
        model = ModelManager(provider_manager=manager).get_model_instance(self.workspace_a.id, PROVIDER, ModelType.LLM, 'synthetic-model')
        self.assertEqual(model.credentials['api_key'], 'synthetic-key-' + self.editor.id)
        with self.assertRaises(Exception):
            ModelManager(provider_manager=manager).get_model_instance(self.workspace_a.id, PROVIDER, ModelType.LLM, 'owners-model')
        stranger = ProviderManager(model_runtime=SimpleNamespace(user_id=self.admin.id, fetch_model_providers=lambda: [schema()]))
        self.assertIsNone(stranger.get_default_model(self.workspace_a.id, ModelType.LLM))
        self.assertEqual(stranger.get_configurations(self.workspace_a.id)[PROVIDER].custom_configuration.models, [])
        self.assertEqual(first['model_name'], 'synthetic-model')

    def test_real_plugin_dispatch_replaces_shared_input_with_each_users_key(self):
        self.save_connection(); self.save_connection(actor=self.project_owner)
        client = PluginModelClient()
        with patch.object(client, '_request_with_plugin_daemon_response_stream', return_value=iter(())) as send:
            list(client.invoke_llm(**self.args()))
            payload = send.call_args.kwargs['data']
            self.assertEqual(payload['data']['credentials']['api_key'], 'synthetic-key-' + self.editor.id)
            self.assertEqual(payload['user_id'], self.editor.id)
        with patch.object(client, '_request_with_plugin_daemon_response_stream', return_value=iter(())) as send:
            list(client.invoke_llm(**self.args(self.project_owner)))
            self.assertEqual(send.call_args.kwargs['data']['data']['credentials']['api_key'], 'synthetic-key-' + self.project_owner.id)
        with patch.object(client, '_request_with_plugin_daemon_response_stream') as send, self.assertRaises(Forbidden):
            list(client.invoke_llm(**self.args(self.admin)))
        send.assert_not_called()

    def test_cached_stream_rechecks_delete_membership_and_role_before_dispatch(self):
        row = self.save_connection()
        client = PluginModelClient()
        queued = client.invoke_llm(**self.args())
        models.delete(self.session, self.editor.id, row['id'], dict(expected_revision=1))
        with patch.object(client, '_request_with_plugin_daemon_response_stream') as send, self.assertRaises(Forbidden):
            list(queued)
        send.assert_not_called()
        self.save_connection()
        join = self.session.scalar(sa.select(TenantAccountJoin).where(TenantAccountJoin.tenant_id == self.workspace_a.id,
            TenantAccountJoin.account_id == self.editor.id))
        self.session.delete(join); self.session.flush()
        with self.assertRaises(NotFound):
            list(client.invoke_llm(**self.args()))

    def test_console_identity_public_impersonation_and_anonymous_run_are_rejected(self):
        self.save_connection()
        with self.app.test_request_context('/console/api/workspaces/current/models/model-types/llm'), \
                patch('libs.login.current_account_with_tenant', return_value=(self.editor, self.workspace_a.id)):
            self.assertEqual(runtime.actor(self.workspace_a.id), self.editor.id)
            with self.assertRaises(Forbidden):
                runtime.actor(self.workspace_a.id, self.project_owner.id)
        with self.app.test_request_context('/v1/workflows/run'):
            self.assertIsNone(runtime.actor(self.workspace_a.id, self.editor.id))
            with self.assertRaises(Forbidden):
                list(PluginModelClient().invoke_llm(**self.args()))
        context = DifyRunContext(tenant_id=self.workspace_a.id, app_id='synthetic', user_id=self.editor.id,
            user_from=UserFrom.END_USER, invoke_from=InvokeFrom.SERVICE_API)
        with self.assertRaises(Forbidden):
            runtime.require_run_identity(context)
        runtime.require_run_identity(context.model_copy(update={'user_from': UserFrom.ACCOUNT, 'invoke_from': InvokeFrom.EXPLORE}))
        with self.assertRaises(Forbidden):
            runtime.require_account_execution(self.workspace_a.id, SimpleNamespace(id=self.editor.id))

    def test_validation_scope_and_errors_do_not_reveal_provider_payload(self):
        row = self.save_connection()
        arguments = dict(tenant_id=self.workspace_a.id, user_id=self.editor.id, plugin_id='langgenius/openai',
            provider='openai', credentials={'api_key': 'SHARED-KEY'})
        with self.assertRaises(Forbidden):
            runtime.bound_credentials('validate_provider_credentials', arguments)
        with runtime.validation_connection(row['id']):
            runtime.bound_credentials('validate_provider_credentials', arguments)
        self.assertEqual(arguments['credentials']['api_key'], 'synthetic-key-' + self.editor.id)
        fake = SimpleNamespace(validate_provider_credentials=Mock(side_effect=ValueError('synthetic-key-' + self.editor.id)))
        with patch('core.plugin.impl.model_runtime_factory.create_plugin_model_runtime', return_value=fake), self.assertRaises(BadGateway) as failure:
            models.test_connection(self.session, self.workspace_a.id, self.editor.id, row['id'])
        self.assertNotIn('synthetic-key-', str(failure.exception))
        client = PluginModelClient()
        with patch.object(client, '_request_with_plugin_daemon_response_stream',
                side_effect=ValueError('provider echoed synthetic-key-' + self.editor.id)):
            with self.assertRaises(ValueError) as failure:
                list(client.invoke_llm(**self.args()))
            self.assertNotIn('synthetic-key-', str(failure.exception))
            self.assertNotIn('provider echoed', str(failure.exception))

    def test_schedule_uses_creator_instead_of_tenant_owner_and_legacy_settings_are_blocked(self):
        app = App(tenant_id=self.workspace_a.id, name='Synthetic schedule', mode='workflow', status='normal',
            created_by=self.editor.id, enable_site=False, enable_api=False, max_active_requests=0)
        self.session.add(app); self.session.flush()
        schedule = SimpleNamespace(app_id=app.id, tenant_id=self.workspace_a.id)
        self.assertEqual(runtime.schedule_account(self.session, schedule).id, self.editor.id)
        client = self.app.test_client()
        for path in ('/console/api/workspaces/current/model-providers/summary',
                '/console/api/workspaces/current/model-providers/langgenius/openai/openai/credentials',
                '/console/api/workspaces/current/model-providers/langgenius/openai/openai/models/credentials'):
            self.assertEqual(client.get(path).status_code, 403)
        self.assertEqual(client.post('/console/api/workspaces/current/default-model', json={}).status_code, 403)

    def test_invalid_fields_and_cross_account_edit_cannot_save_or_rebind(self):
        row = self.save_connection()
        for updates in ({'credentials': {'endpoint_url': 'http://model.example.test', 'api_key': 'synthetic'}},
                {'account_id': self.project_owner.id}, {'model_type': 'invalid'}, {'credentials': {'unknown': 'value'}}):
            with self.subTest(fields=list(updates)), self.assertRaises(BadRequest):
                self.save_connection(**updates)
        with self.assertRaises(NotFound):
            self.save_connection(actor=self.project_owner, old=row)
        inherited = schema()
        inherited.provider_credential_schema.credential_form_schemas[1].default = 'SHARED-SCHEMA-KEY'
        with patch.object(models, 'schemas', return_value=[inherited]), self.assertRaises(BadRequest):
            self.save_connection(actor=self.project_owner, credentials={'endpoint_url': 'https://model.example.test/v1'})

    def test_onboarding_uses_only_the_current_accounts_model(self):
        from company_projects import readiness
        self.save_connection(actor=self.project_owner, model_name='owners-model')
        status = readiness.snapshot(self.session, self.a['id'], self.workspace_a.id, self.editor)
        self.assertIsNone(status['model_name'])
        self.save_connection()
        status = readiness.snapshot(self.session, self.a['id'], self.workspace_a.id, self.editor)
        self.assertEqual(status['model_name'], 'synthetic-model')
