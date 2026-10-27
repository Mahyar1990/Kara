"""Focused rollback tests: no model, client, shell, harness or upstream script execution."""
from unittest.mock import patch
from uuid import uuid4
import json

import sqlalchemy as sa
from werkzeug.exceptions import Conflict, Forbidden, NotFound

from company_projects.test_access import ProjectDatabaseFixture
from company_projects import agency_catalog as agency, agents, personal_models, personal_agent_sources
from models.agent import Agent, AgentConfigSnapshot
from models.skill import Skill, SkillDraftFile
from models.tools import ToolFile
from models.model import App, Tag, TagBinding
from services.agent.roster_service import AgentRosterService


class AgencyCatalogTests(ProjectDatabaseFixture):
    def setUp(self):
        super().setUp()
        self.item = next(item for item in agency.manifest()['templates'] if item['recommended'])
        self.model_id = str(uuid4())
        self.session.execute(personal_models.table(self.session).insert().values(id=self.model_id,
            account_id=self.project_owner.id, name='Synthetic Agency model',
            provider='langgenius/openai_api_compatible/openai_api_compatible', model_name='synthetic-agency-model',
            model_type='llm', encrypted_credentials='agency-private-secret-must-not-export', is_default=True,
            revision=1, created_at=agents.now(), updated_at=agents.now()))
        self.files = {}
        self.save = patch('company_projects.agency_catalog.storage.save', side_effect=lambda key, data: self.files.__setitem__(key, data))
        self.save.start(); self.addCleanup(self.save.stop)

    def body(self, **kw):
        result = dict(name=self.item['name'], model_connection_id=self.model_id, model_revision=1,
            dataset_id=None, definition_digest=agency.definition_digest(self.item))
        return result | kw

    def adopt(self, data=None, key=None, actor=None, project=None, workspace=None):
        return agency.adopt(self.session, project or self.a['id'], workspace or self.workspace_a.id,
            (actor or self.project_owner).id, self.item['id'], data or self.body(), key or str(uuid4()), [])

    def test_complete_pinned_catalog_and_safe_adaptations(self):
        catalog = agency.manifest()
        self.assertEqual((len(catalog['templates']), len(catalog['files'])), (283, 332))
        self.assertEqual(sum(t['recommended'] for t in catalog['templates']), 8)
        self.assertEqual(sum(p.endswith('.md') for p in catalog['files']), 330)
        self.assertEqual(len({t['category'] for t in catalog['templates']}), 18)
        for item in catalog['templates']:
            original, adapted = agency.contents(item)
            self.assertTrue(item['name'].startswith('ایجنت '))
            self.assertNotIn('{{#', adapted)
            self.assertIn(agency.policy(), adapted)
            self.assertLess(len(adapted.encode()), 1048576)
            self.assertIn(catalog['commit'], adapted)
            self.assertTrue(item['category_original_label'])
        self.assertEqual(len({t['id'] for t in catalog['templates']}), 283)

    def test_private_native_copies_replay_and_team_source_compatibility(self):
        key = str(uuid4()); created = self.adopt(key=key)
        again = self.adopt(key=key)
        self.assertEqual(created['agent_id'], again['agent_id'])
        self.assertFalse(again['created'])
        repeated = self.adopt()
        self.assertEqual(repeated['agent_id'], created['agent_id'])
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(Agent).where(Agent.tenant_id == self.workspace_a.id)), 1)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(Skill).where(Skill.tenant_id == self.workspace_a.id)), 1)
        source = self.session.get(Agent, created['agent_id'])
        app = AgentRosterService(self.session).get_agent_app_model(tenant_id=self.workspace_a.id, agent_id=source.id)
        self.assertEqual((app.id, app.mode), (source.app_id, 'agent'))
        self.assertFalse(app.enable_api or app.enable_site)
        tagged = self.session.execute(sa.select(Tag.type, Tag.name, TagBinding.target_id).join(TagBinding, TagBinding.tag_id == Tag.id)
            .where(Tag.tenant_id == self.workspace_a.id)).all()
        self.assertEqual(set(tagged), {(kind, name, target) for kind, target in (('app', app.id), ('skill', created['skill_id']))
            for name in ('Agency Agents', 'Agency: ' + self.item['category_original_label'])})
        snapshot = self.session.get(AgentConfigSnapshot, source.active_config_snapshot_id)
        self.assertNotIn('agency-private-secret-must-not-export', json.dumps(snapshot.config_snapshot_dict))
        self.assertEqual(snapshot.config_snapshot_dict['tools'], dict(dify_tools=[], cli_tools=[]))
        with patch('extensions.ext_storage.storage.load', side_effect=lambda key, **kw: iter([self.files[key]])):
            checked = personal_agent_sources.preview(self.session, self.a['id'], self.workspace_a.id,
                self.project_owner.id, source.id, snapshot.id)
            self.assertTrue(checked['available'])
            self.assertEqual(len(checked['skills']), 1)
        listing = agency.listing(self.session, self.a['id'], self.workspace_a.id, self.editor.id)
        self.assertFalse(listing['can_adopt']); self.assertEqual(listing['models'], [])
        self.assertEqual(next(t for t in listing['data'] if t['id'] == self.item['id'])['copy']['agent_id'], source.id)
        self.assertIsNone(self.session.scalar(sa.select(Agent.id).where(Agent.tenant_id == self.workspace_b.id)))
        self.session.add(SkillDraftFile(skill_id=created['skill_id'], path='draft-only.md', kind='file', storage='text', content_text='private later edit'))
        self.session.flush()
        with self.assertRaises(Conflict): self.adopt(key=key, data=self.body(name='different payload'))

    def test_authority_stale_definition_and_storage_failure_leave_no_copy(self):
        with self.assertRaises(Forbidden): self.adopt(actor=self.editor)
        with self.assertRaises(Forbidden): self.adopt(workspace=self.workspace_b.id)
        with self.assertRaises(NotFound): self.adopt(actor=self.other, project=self.b['id'], workspace=self.workspace_b.id)
        with self.assertRaises(Conflict): self.adopt(data=self.body(definition_digest='changed'))
        for model in (Agent, App, Skill, ToolFile, Tag, TagBinding):
            self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(model).where(model.tenant_id == self.workspace_a.id)), 0)
        with self.assertRaises(RuntimeError):
            with self.session.begin_nested():
                with patch('company_projects.agency_catalog.storage.save', side_effect=RuntimeError('synthetic storage failure')):
                    self.adopt()
        for model in (Agent, App, Skill, ToolFile, Tag, TagBinding):
            self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(model).where(model.tenant_id == self.workspace_a.id)), 0)
        adoptions = agency.adoptions(self.session)
        self.assertEqual(self.session.scalar(sa.select(sa.func.count()).select_from(adoptions).where(adoptions.c.project_id == self.a['id'])), 0)
