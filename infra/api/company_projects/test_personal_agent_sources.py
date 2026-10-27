"""Rollback-only checks for roster delegation; no SDK, Runner or model is executed."""
import hashlib
import io
import zipfile
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4

import sqlalchemy as sa
from werkzeug.exceptions import Conflict, Forbidden, NotFound, UnprocessableEntity

from company_projects import agents, agent_execution, flows, local_execution, personal_agent_sources as personal
from company_projects.test_flows import FlowFixture
from models.agent import Agent, AgentConfigSnapshot
from models.agent_config_entities import AgentSoulConfig
from models.model import App
from models.skill import AgentSkillBindingSnapshot, Skill, SkillVersion, SkillVersionManifest
from models.tools import ToolFile
from models.workflow import Workflow


class PersonalAgentSourceTests(FlowFixture):
    def test_custom_query_selectors_and_skill_budget(self):
        from jinja2 import Environment
        rendered, variables = personal.query_template('Find {{#sys.query#}} / {{none}} / {{request_context}}', {'task', 'none', 'request_context'})
        values = {'task': 'task text', 'none': 'named value', 'request_context': 'context'}
        self.assertEqual(Environment().from_string(rendered).render(**{v['variable']: values[v['value_selector'][1]] for v in variables}),
            'Find task text / named value / context')
        for value in ('{% include "file" %}', '{# comment #}', '{{unknown}}'):
            with self.assertRaises(UnprocessableEntity): personal.query_template(value, {'task'})
        config = self.config.model_dump()
        config['config_skills'] = [dict(name=f'skill-{i}', file_kind='tool_file', file_id=str(uuid4())) for i in range(21)]
        self.snapshot.config_snapshot = AgentSoulConfig.model_validate(config); self.session.flush()
        with patch.object(personal, 'package_text', side_effect=AssertionError('must reject before storage reads')):
            with self.assertRaises(UnprocessableEntity): personal.skills(self.session, self.source, self.snapshot, self.project_owner.id)

    def setUp(self):
        super().setUp()
        self.source = Agent(tenant_id=self.workspace_a.id, name='Synthetic personal agent', scope='roster',
            source='roster', status='active')
        self.session.add(self.source); self.session.flush()
        self.config = AgentSoulConfig.model_validate(dict(prompt=dict(system_prompt='Read {{request_context}} and answer the task.'),
            model=dict(plugin_id='synthetic', model_provider='langgenius/openai_api_compatible/openai_api_compatible',
                model='synthetic-model', credential_ref=dict(type='personal', id='author-reference-must-not-export')),
            app_variables=[dict(name='request_context', type='string', default='default context')]))
        self.snapshot = AgentConfigSnapshot(tenant_id=self.workspace_a.id, agent_id=self.source.id, version=1,
            config_snapshot=self.config, created_by=self.project_owner.id)
        self.session.add(self.snapshot); self.session.flush()
        self.source.active_config_snapshot_id = self.snapshot.id; self.source.active_config_has_model = True
        self.session.flush()

    def preview(self, actor=None):
        return personal.preview(self.session, self.a['id'], self.workspace_a.id, (actor or self.project_owner).id,
            self.source.id, self.snapshot.id)

    def connect(self, key=None, preview=None, **changes):
        data = dict(personal_agent_id=self.source.id, snapshot_id=self.snapshot.id,
            source_digest=(preview or self.preview())['source_digest'], name='ایجنت شخصی تیم', description='', expected_revision=1)
        data.update(changes)
        return personal.register(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, data, key or str(uuid4()))

    def grants(self, connected):
        from company_projects import access
        agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, connected['id'],
            dict(expected_revision=1, grants=[dict(account_id=person.id,
                membership_id=access.membership(self.session, self.workspace_a.id, person.id).id, actions=actions)
                for person, actions in ((self.editor, ['view', 'run', 'feedback']), (self.project_owner, ['view', 'finalize']))]), str(uuid4()))

    def test_atomic_pin_delegation_local_snapshot_and_flow_contract(self):
        before = self.session.scalar(sa.select(sa.func.count()).select_from(App))
        key = str(uuid4()); checked = self.preview(); connected = self.connect(key=key, preview=checked)
        self.assertEqual(self.connect(key=key, preview=checked), connected)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(App)), before + 1)
        self.assertEqual(connected['actions'], [])
        workflow = self.session.get(Workflow, connected['workflow_id'])
        self.assertNotIn('author-reference-must-not-export', str(workflow.graph_dict) + str(workflow.features_dict))
        self.assertEqual(connected['output_contract'], ['result'])
        self.assertNotIn(workflow.id, [r['workflow_id'] for r in agents.sources(
            self.session, self.a['id'], self.workspace_a.id, self.project_owner.id)['data']])
        with self.assertRaises(Forbidden):
            agent_execution.deny_native(connected['app_id'], session=self.session)
        self.grants(connected)
        attempt = agents.start(self.session, self.a['id'], self.workspace_a.id, self.editor.id, connected['id'],
            dict(inputs={'task': 'synthetic task'}, expected_revision=1), str(uuid4()))
        attempts = agents.tables(self.session)[2]
        stored = self.session.execute(sa.select(attempts).where(attempts.c.id == attempt['id'])).mappings().one()
        self.assertEqual(stored['inputs']['request_context'], 'default context')
        self.assertEqual(stored['inputs']['feedback_context'], '')
        with patch('company_projects.personal_models.resolve', return_value=dict(id=str(uuid4()), revision=1,
                provider=self.config.model.model_provider, model_name='synthetic-model')) as resolve:
            snapshot = local_execution.build_snapshot(self.session, workflow, self.editor.id, {'task': 'synthetic task'})
            self.assertEqual(resolve.call_args.args[1], self.editor.id)
            self.assertEqual(snapshot['requirements'], ['workflow-v2'])
        stage = dict(self.stage(), agent_id=connected['id'], inputs={'task': {'source': 'request'}})
        published = self.publish(self.save(stages=[stage]))
        self.assertEqual(published['published']['stage_bindings'][0]['output_contract'], ['result'])
        other = AgentConfigSnapshot(tenant_id=self.workspace_a.id, agent_id=self.source.id, version=2,
            config_snapshot=AgentSoulConfig.model_validate(dict(prompt={'system_prompt': 'changed later'}, model=self.config.model.model_dump())),
            created_by=self.project_owner.id)
        self.session.add(other); self.session.flush(); self.source.active_config_snapshot_id = other.id; self.session.flush()
        personal.validate(self.session, workflow, self.editor.id)
        self.assertEqual(personal.metadata(workflow)['snapshot_id'], self.snapshot.id)
        self.source.status = 'archived'; self.session.flush()
        with self.assertRaises(NotFound): agents.require(self.session, agents.load(self.session,
            dict(project_id=self.a['id'], workspace_id=self.workspace_a.id), connected['id']), self.editor.id, 'run')
        agents.require(self.session, agents.load(self.session,
            dict(project_id=self.a['id'], workspace_id=self.workspace_a.id), connected['id']), self.editor.id, 'view')

    def test_authority_scope_unsupported_and_rollback_have_no_orphan(self):
        with self.assertRaises(Forbidden): self.preview(actor=self.editor)
        with self.assertRaises(NotFound): personal.load(self.session, self.workspace_b.id, self.source.id, self.snapshot.id)
        with patch('company_projects.personal_agent_sources.permission', side_effect=Forbidden()):
            self.assertEqual(personal.sources(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id)['data'], [])
        from configs import dify_config
        with patch.object(dify_config, 'RBAC_ENABLED', True), patch(
                'controllers.common.agent_access.resolve_agent_access_filter', return_value=SimpleNamespace(accessible_agent_ids=set())), patch(
                'services.enterprise.rbac_service.RBACService.CheckAccess.check', return_value=True):
            with self.assertRaises(Forbidden): personal.permission(self.session, self.workspace_a.id, self.editor.id, self.source.id)
        original = self.snapshot.config_snapshot
        config = self.config.model_dump(); config['tools']['cli_tools'] = [dict(command='echo test', name='test')]
        self.snapshot.config_snapshot = AgentSoulConfig.model_validate(config); self.session.flush()
        self.assertFalse(self.preview()['available'])
        self.snapshot.config_snapshot = original; self.session.flush()
        checked = self.preview(); before = self.session.scalar(sa.select(sa.func.count()).select_from(App))
        with self.assertRaises(Conflict): self.connect(preview=checked, source_digest='changed-after-review')
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(App)), before)
        with self.assertRaises(RuntimeError):
            with self.session.begin_nested():
                with patch('company_projects.agents.register', side_effect=RuntimeError('synthetic failure')):
                    self.connect(preview=checked)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(App)), before)

    def test_text_skill_freeze_and_rejection_of_executable_archive(self):
        def archive(files):
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w') as z:
                for name, content in files.items(): z.writestr(name, content)
            return output.getvalue()
        raw = archive({'SKILL.md': '# Synthetic\nFollow the evidence.', 'references/context.md': 'Only known facts.'})
        file = ToolFile(user_id=self.project_owner.id, tenant_id=self.workspace_a.id, conversation_id=None,
            file_key='synthetic-skill-never-read-from-real-storage', mimetype='application/zip', size=len(raw))
        skill = Skill(tenant_id=self.workspace_a.id, name='synthetic-team-skill', display_name='Synthetic skill')
        self.session.add_all([file, skill]); self.session.flush()
        version = SkillVersion(skill_id=skill.id, version_number=1, archive_tool_file_id=file.id,
            archive_size=len(raw), hash_code='synthetic-version-1', manifest=SkillVersionManifest(files=[]))
        self.session.add(version); self.session.flush(); skill.latest_published_version_id = version.id
        self.session.add(AgentSkillBindingSnapshot(tenant_id=self.workspace_a.id, agent_id=self.source.id,
            config_snapshot_id=self.snapshot.id, skill_id=skill.id, priority=0)); self.session.flush()
        with patch('extensions.ext_storage.storage.load', side_effect=lambda *a, **kw: iter([raw])):
            checked = self.preview(); connected = self.connect(preview=checked)
        workflow = self.session.get(Workflow, connected['workflow_id'])
        self.assertIn('Follow the evidence.', str(workflow.graph_dict))
        self.assertEqual(personal.metadata(workflow)['skills'][0]['archive_digest'], hashlib.sha256(raw).hexdigest())
        skill.latest_published_version_id = None; self.session.flush()
        personal.validate(self.session, workflow)  # Pin remains valid when current publication changes.
        for bad in ({'SKILL.md': 'text', 'scripts/run.py': 'pass'}, {'../SKILL.md': 'text'}):
            binary = archive(bad)
            with patch('extensions.ext_storage.storage.load', side_effect=lambda *a, **kw: iter([binary])):
                with self.assertRaises(UnprocessableEntity): personal.package_text(self.session, self.workspace_a.id, file.id)
        version.hash_code = 'tampered'; self.session.flush()
        with self.assertRaises(Conflict): personal.validate(self.session, workflow)

    def test_knowledge_compilation_pins_scope_and_rejects_unsupported_policy(self):
        from models.dataset import Dataset
        dataset = Dataset(tenant_id=self.workspace_a.id, name='Synthetic internal knowledge', created_by=self.project_owner.id,
            maintainer=self.project_owner.id, provider='vendor', permission='all_team_members', indexing_technique='economy')
        self.session.add(dataset); self.session.flush()
        config = self.config.model_dump()
        group = dict(id='knowledge', name='Product evidence', datasets=[dict(id=dataset.id)],
            query=dict(mode='generated_query'), retrieval=dict(mode='multiple', top_k=4, reranking_enable=False))
        config['knowledge']['sets'] = [group]
        self.snapshot.config_snapshot = AgentSoulConfig.model_validate(config); self.session.flush()
        connected = self.connect(); workflow = self.session.get(Workflow, connected['workflow_id'])
        with patch('company_projects.personal_models.resolve', return_value=dict(id=str(uuid4()), revision=1,
                provider=self.config.model.model_provider, model_name='synthetic-model')):
            snapshot = local_execution.build_snapshot(self.session, workflow, self.editor.id, {'task': 'synthetic'})
        self.assertEqual(snapshot['knowledge']['knowledge_0']['datasets'][0]['id'], dataset.id)
        group['metadata_filtering'] = dict(mode='automatic')
        self.snapshot.config_snapshot = AgentSoulConfig.model_validate(config); self.session.flush()
        self.assertFalse(self.preview()['available'])
