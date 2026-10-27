"""Focused rollback checks; no client, model, SDK, Runner or shell execution."""
from copy import deepcopy
import json
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects.test_personal_agent_sources import PersonalAgentSourceTests
from company_projects.test_runtime_models import runtime_graph, model_schema, setup_models
from company_projects import agents, program_agents as programs, runtime_models, personal_models, personal_agent_sources as library
from models.model import App
from models.workflow import Workflow


class ProgramAgentTests(PersonalAgentSourceTests):
    def role(self):
        return programs.preview(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, self.source.id, self.snapshot.id)

    def create_program(self, key=None, **updates):
        data = dict(name='برنامهٔ آزمایشی', source_id=self.source.id, snapshot_id=self.snapshot.id, source_digest=self.role()['source_digest']) | updates
        return programs.create(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, data, key or str(uuid4()))

    def program_draft(self):
        app = App(tenant_id=self.workspace_a.id, name='Synthetic role target', mode='workflow', status='normal', created_by=self.project_owner.id,
            enable_api=False, enable_site=False, max_active_requests=0)
        self.session.add(app); self.session.flush()
        w = Workflow.new(tenant_id=self.workspace_a.id, app_id=app.id, type='workflow', version='draft', graph=json.dumps(programs.positioned(runtime_graph())),
            features='{}', created_by=self.project_owner.id, environment_variables=[], conversation_variables=[], rag_pipeline_variables=[])
        self.session.add(w); self.session.flush()
        return app, w

    def attach(self, app, w, key=None, **updates):
        data = dict(draft_hash=w.unique_hash, source_id=self.source.id, snapshot_id=self.snapshot.id, source_digest=self.role()['source_digest'],
            bindings=dict(task='{{#start.request#}}', feedback_context='', request_context='Project context')) | updates
        return programs.modify(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, app.id, 'llm', data, key or str(uuid4()))

    def test_program_creation_is_independent_and_uses_each_executors_model(self):
        setup_models(self)
        key = str(uuid4()); before = agents.fingerprint(self.session.get(Workflow, agents.load(self.session,
            dict(project_id=self.a['id'], workspace_id=self.workspace_a.id), self.agent_ids[0])['workflow_id']))
        result = self.create_program(key); self.assertEqual(result, self.create_program(key))
        w = self.session.get(Workflow, result['workflow_id']); app = self.session.get(App, result['app_id'])
        self.assertIsNone(app.workflow_id); self.assertEqual(w.version, 'draft')
        self.assertNotIn('author-reference-must-not-export', w.graph)
        self.assertEqual(runtime_models.policy(w.graph_dict), dict(version=1, capabilities=[]))
        self.assertTrue(all(n['data']['model']['provider'] == runtime_models.PROVIDER for n in runtime_models.llm_nodes(w.graph_dict)))
        self.assertEqual([r['id'] for r in agents.list_agents(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id)['data']], self.agent_ids)
        table = personal_models.table(self.session)
        owner_id, executor_id = str(uuid4()), str(uuid4())
        for actor, identity, name in ((self.project_owner, owner_id, 'creator-model'), (self.editor, executor_id, 'executor-model-different')):
            self.session.execute(table.insert().values(id=identity, account_id=actor.id, name='Synthetic', provider='langgenius/openai_api_compatible/openai_api_compatible',
                model_name=name, model_type='llm', encrypted_credentials='not-read', is_default=True, revision=1, created_at=agents.now(), updated_at=agents.now()))
        with patch.object(runtime_models, 'schema_for', return_value=model_schema()):
            selection = runtime_models.select(self.session, w, self.editor.id, executor_id)
            self.assertEqual(selection['model_name'], 'executor-model-different')
            with self.assertRaises(NotFound): runtime_models.select(self.session, w, self.editor.id, owner_id)
        self.assertEqual(before, agents.fingerprint(self.session.get(Workflow, agents.load(self.session,
            dict(project_id=self.a['id'], workspace_id=self.workspace_a.id), self.agent_ids[0])['workflow_id'])))
        library.validate(self.session, w, self.editor.id)

    def test_attachment_preserves_outputs_replays_and_detaches_without_touching_published(self):
        from models.dataset import Dataset
        dataset = Dataset(tenant_id=self.workspace_a.id, name='Synthetic knowledge', created_by=self.project_owner.id,
            maintainer=self.project_owner.id, provider='vendor', permission='all_team_members', indexing_technique='economy')
        self.session.add(dataset); self.session.flush()
        config = self.config.model_dump(); config['knowledge']['sets'] = [dict(id='knowledge', name='Product evidence', datasets=[dict(id=dataset.id)],
            query=dict(mode='generated_query'), retrieval=dict(mode='multiple', top_k=4, reranking_enable=False))]
        self.snapshot.config_snapshot = self.config.model_validate(config); self.session.flush()
        app, w = self.program_draft(); original = deepcopy(w.graph_dict)
        later = deepcopy(original['nodes'][1]); later['id'] = 'later'; later['data']['prompt_template'] = [dict(role='user', text='{{#llm.text#}}')]
        original['nodes'].insert(2, later); original['nodes'][-1]['data']['outputs'][0]['value_selector'] = ['later', 'text']
        original['edges'][1]['target'] = 'later'; original['edges'].append(dict(id='e3', source='later', target='end', sourceHandle='source', targetHandle='target'))
        programs.positioned(original)
        w.graph = json.dumps(original); self.session.flush()
        key = str(uuid4()); old_hash = w.unique_hash
        result = self.attach(app, w, key)
        self.assertEqual(result, self.attach(app, w, key, draft_hash=old_hash))
        graph = w.graph_dict
        self.assertEqual(next(n['data']['outputs'][0]['value_selector'] for n in graph['nodes'] if n['id'] == 'end'), ['later', 'text'])
        self.assertIn(programs.PIN, next(n['data'] for n in graph['nodes'] if n['id'] == 'llm'))
        self.assertNotIn('author-reference-must-not-export', w.graph)
        with self.assertRaises(Conflict): self.attach(app, w, draft_hash=old_hash)
        with self.assertRaises(Conflict): self.attach(app, w)
        library.validate(self.session, w, self.editor.id)
        from jinja2 import Environment
        adapter = next(n for n in graph['nodes'] if n['data']['type'] == 'template-transform' and n['id'].endswith('_task'))
        self.assertEqual(Environment().from_string(adapter['data']['template']).render(v0='Original request'), 'Original request')
        role = self.role()
        programs.modify(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, app.id, 'later',
            dict(draft_hash=w.unique_hash, source_id=self.source.id, snapshot_id=self.snapshot.id, source_digest=role['source_digest'],
                bindings=dict(task='{{#llm.text#}}', feedback_context='', request_context='Context')), str(uuid4()))
        library.validate(self.session, w, self.editor.id)
        self.assertEqual(len(programs.detail(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, app.id)['nodes']), 2)
        programs.modify(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, app.id, 'llm', dict(draft_hash=w.unique_hash), str(uuid4()), detach=True)
        programs.modify(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, app.id, 'later', dict(draft_hash=w.unique_hash), str(uuid4()), detach=True)
        self.assertEqual({n['id']: n['data'] for n in w.graph_dict['nodes']}, {n['id']: n['data'] for n in original['nodes']})
        self.assertEqual(w.graph_dict['edges'], original['edges'])

    def test_acl_pinned_mutation_and_input_selector_guards(self):
        app, w = self.program_draft()
        with self.assertRaises(Forbidden): programs.detail(self.session, self.a['id'], self.workspace_a.id, self.editor.id, app.id)
        with self.assertRaises(Forbidden): programs.detail(self.session, self.a['id'], self.workspace_b.id, self.project_owner.id, app.id)
        with self.assertRaises(Conflict): self.attach(app, w, source_digest='stale')
        with self.assertRaises(BadRequest): self.attach(app, w, bindings=dict(task='{{#end.result#}}', feedback_context='', request_context=''))
        self.attach(app, w)
        good = w.graph
        graph = w.graph_dict; next(n for n in graph['nodes'] if n['id'] == 'llm')['data']['prompt_template'][0]['text'] = 'unreviewed edit'
        w.graph = json.dumps(graph)
        with self.assertRaises(Conflict): library.validate(self.session, w, self.editor.id)
        w.graph = good
        self.source.status = 'archived'; self.session.flush()
        with self.assertRaises(NotFound): library.validate(self.session, w, self.editor.id)

    def test_library_program_publishes_and_registers_through_existing_team_path(self):
        from services.workflow_service import WorkflowService
        created = self.create_program(); app = self.session.get(App, created['app_id'])
        with patch('services.workflow_service.SystemFeatureService.is_plugin_manager_enabled', return_value=False):
            published = WorkflowService().publish_workflow(session=self.session, app_model=app, account=self.project_owner)
        self.assertNotEqual(published.version, 'draft')
        linked = agents.register(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            dict(app_id=app.id, workflow_id=published.id, name='ایجنت تیمی برنامهٔ کتابخانه', description='', expected_revision=1), str(uuid4()))
        self.assertIsNotNone(linked['runtime_model'])
        self.assertEqual(linked['output_contract'], ['result'])
        self.assertEqual(len(linked['input_contract']), 3)
        self.grants(linked)
        stage = dict(self.stage(), agent_id=linked['id'], inputs={'task': {'source': 'request'}})
        self.assertEqual(self.publish(self.save(stages=[stage]))['published']['stage_bindings'][0]['output_contract'], ['result'])

    def test_missing_author_model_and_agency_published_skills(self):
        config = self.config.model_dump(); config['model'] = None
        self.snapshot.config_snapshot = self.config.model_validate(config); self.session.flush()
        self.assertTrue(self.create_program()['app_id'])
        from company_projects import agency_catalog as agency
        model_id = str(uuid4())
        self.session.execute(personal_models.table(self.session).insert().values(id=model_id, account_id=self.project_owner.id,
            name='Synthetic Agency model', provider='langgenius/openai_api_compatible/openai_api_compatible', model_name='author-only-model',
            model_type='llm', encrypted_credentials='author-secret-must-not-export', is_default=True, revision=1,
            created_at=agents.now(), updated_at=agents.now()))
        item = next(t for t in agency.manifest()['templates'] if t['recommended']); files = {}
        with patch.object(agency.storage, 'save', side_effect=lambda k, b: files.__setitem__(k, b)):
            copied = agency.adopt(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, item['id'],
                dict(name=item['name'], model_connection_id=model_id, model_revision=1, dataset_id=None, definition_digest=agency.definition_digest(item)), str(uuid4()), [])
        with patch.object(agency.storage, 'load', side_effect=lambda k, **kw: iter([files[k]])):
            preview = programs.preview(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, copied['agent_id'], copied['snapshot_id'])
            result = programs.create(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
                dict(name='برنامهٔ Agency', source_id=copied['agent_id'], snapshot_id=copied['snapshot_id'], source_digest=preview['source_digest']), str(uuid4()))
        w = self.session.get(Workflow, result['workflow_id'])
        self.assertIn(agency.policy(), next(n['data']['prompt_template'][0]['text'] for n in w.graph_dict['nodes'] if n['data']['type'] == 'llm'))
        self.assertNotIn('author-only-model', w.graph)
        self.assertNotIn('author-secret-must-not-export', w.graph)
