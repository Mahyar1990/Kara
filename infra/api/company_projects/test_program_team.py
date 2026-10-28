"""Rollback-only regression for program-centric team settings; no execution."""
import json
from uuid import uuid4
from werkzeug.exceptions import Forbidden
from company_projects.test_personal_agent_sources import PersonalAgentSourceTests
from company_projects import access, agents, flows, program_team
from models.model import App
from models.workflow import Workflow


class ProgramTeamTests(PersonalAgentSourceTests):
    def second_profile(self):
        scope = dict(project_id=self.a['id'], workspace_id=self.workspace_a.id)
        first = agents.load(self.session, scope, self.agent_ids[0])
        app = self.session.get(App, first['app_id']); original = self.session.get(Workflow, first['workflow_id'])
        w = Workflow.new(tenant_id=app.tenant_id, app_id=app.id, type='workflow', version='second-published',
            marked_name='Version two', graph=original.graph, features='{}', created_by=self.project_owner.id,
            environment_variables=[], conversation_variables=[], rag_pipeline_variables=[])
        self.session.add(w); self.session.flush(); app.workflow_id = w.id
        profile = agents.register(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
            dict(app_id=app.id, workflow_id=w.id, name='Independent team settings', description='', expected_revision=1), str(uuid4()))
        agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, profile['id'],
            dict(expected_revision=1, grants=[dict(account_id=who.id, membership_id=access.membership(self.session, self.workspace_a.id, who.id).id, actions=actions)
                for who, actions in ((self.editor, ['view', 'run']), (self.project_owner, ['view', 'finalize']))]), str(uuid4()))
        return first, profile

    def catalog(self, actor=None):
        return program_team.catalog(self.session, self.a['id'], self.workspace_a.id, (actor or self.project_owner).id)

    def test_program_groups_keep_independent_versions_and_member_scope(self):
        first, second = self.second_profile()
        empty = App(tenant_id=self.workspace_a.id, name='Unconfigured program', mode='workflow', status='normal', created_by=self.project_owner.id,
            enable_site=False, enable_api=False, max_active_requests=0)
        self.session.add(empty); self.session.flush()
        result = self.catalog(); groups = {v['id']: v for v in result['programs']}
        self.assertTrue(result['can_manage'])
        self.assertEqual({p['id'] for p in groups[first['app_id']]['profiles']}, {first['id'], second['id']})
        self.assertEqual({p['workflow_version'] for p in groups[first['app_id']]['profiles']}, {'test-published', 'Version two'})
        self.assertEqual(groups[empty.id]['profiles'], [])
        member = self.catalog(self.editor)
        self.assertFalse(member['can_manage']); self.assertNotIn(empty.id, {g['id'] for g in member['programs']})
        self.assertEqual(self.catalog(self.admin)['programs'], [])
        with self.assertRaises(Forbidden): program_team.catalog(self.session, self.a['id'], self.workspace_b.id, self.project_owner.id)
        archived = agents.archive(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, second['id'], dict(expected_revision=1), str(uuid4()))
        profiles = next(g['profiles'] for g in self.catalog()['programs'] if g['id'] == first['app_id'])
        self.assertTrue(next(p for p in profiles if p['id'] == archived['id'])['archived'])
        self.assertFalse(next(p for p in profiles if p['id'] == first['id'])['archived'])

    def test_hidden_library_adapter_remains_available_without_becoming_editable(self):
        connected = self.connect(); self.grants(connected)
        for actor in (self.project_owner, self.editor):
            group = next(g for g in self.catalog(actor)['programs'] if g['id'] == connected['app_id'])
            self.assertTrue(group['library_adapter']); self.assertTrue(group['available'])
            self.assertEqual(group['profiles'][0]['id'], connected['id'])
            self.assertIsNotNone(group['profiles'][0]['personal_source'])

    def test_flow_chooses_exact_profile_and_old_version_stays_unchanged(self):
        original = self.publish(self.save()); previous = json.dumps(original['published'], sort_keys=True)
        first, second = self.second_profile()
        options = flows.options(self.session, self.a['id'], self.workspace_a.id, self.editor.id)
        selected = next(p for p in options['agents'] if p['id'] == second['id'])
        self.assertEqual((selected['app_id'], selected['workflow_version']), (first['app_id'], 'Version two'))
        changed = self.save(original, stages=[dict(self.stage(), agent_id=second['id'])])
        published = self.publish(changed)
        binding = published['published']['stage_bindings'][0]
        self.assertEqual((binding['agent_id'], binding['app_id'], binding['workflow_id'], binding['workflow_version']),
            (second['id'], first['app_id'], second['workflow_id'], 'Version two'))
        self.assertEqual(binding['app_name'], selected['app_name'])
        scope = dict(project_id=self.a['id'], workspace_id=self.workspace_a.id)
        self.assertEqual(json.dumps(flows.version(self.session, scope, original['id'], original['published']['id']), sort_keys=True), previous)
