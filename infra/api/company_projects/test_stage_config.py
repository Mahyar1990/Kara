"""Focused persisted checks for stage-only authority, version isolation and handoff."""
import copy
import json
from uuid import uuid4
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity
from company_projects import access, agents, agent_execution, flows, harness, stages, source_code as source
from company_projects.test_stages import StageFixture, feedback_graph
from company_projects.test_harness import EVIDENCE
from models.model import App
from models.workflow import Workflow


class StageConfigTests(StageFixture):
    def setUp(self):
        super().setUp()
        self.source_app = App(tenant_id=self.workspace_a.id, name='Stage-only synthetic program', mode='workflow',
            status='normal', created_by=self.editor.id, enable_api=False, enable_site=False, max_active_requests=0)
        self.session.add(self.source_app); self.session.flush()
        workflow = Workflow.new(tenant_id=self.workspace_a.id, app_id=self.source_app.id, type='workflow', version='published-stage-test',
            graph=json.dumps(feedback_graph()), features='{}', created_by=self.editor.id,
            environment_variables=[], conversation_variables=[], rag_pipeline_variables=[])
        self.session.add(workflow); self.session.flush(); self.source_app.workflow_id = workflow.id; self.session.flush()
        self.workflow = workflow
        self.new_stage = dict(self.stage(), agent_id=None, app_id=self.source_app.id, workflow_id=workflow.id,
            execution=dict(program_enabled=True, enabled=False, instructions='Acceptance for this stage', requires_source=False), participants=[])
        self.flow = self.publish(self.save(stages=[self.new_stage, dict(self.new_stage, key='review', title='Review',
            inputs={'request': {'source': 'stage', 'stage_key': 'analysis', 'output': 'answer'}})]))
        self.req = self.decision(self.request()); self.inst = self.create_instance(actor=self.editor)
        self.first, self.second = self.inst['stages']

    def test_stage_grants_never_enable_standalone_design_or_other_stage(self):
        row = self.get(); binding = row['binding']
        choices = flows.options(self.session, self.a['id'], self.workspace_a.id, self.editor.id)
        self.assertTrue(any(p['workflow_id'] == self.workflow.id for p in choices['programs']))
        self.assertEqual(row['actions'], ['run', 'feedback'])
        self.assertEqual(row['execution_policy']['policy']['instructions'], 'Acceptance for this stage')
        self.assertIsNone(agent_execution.managed(self.session, self.source_app.id))
        self.assertNotIn(binding['agent_id'], [a['id'] for a in agents.list_agents(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id)['data']])
        for action in ('run', 'edit_definition', 'publish_definition'):
            agent = agents.load(self.session, dict(project_id=self.a['id'], workspace_id=self.workspace_a.id), binding['agent_id'], _stage=True)
            self.assertEqual(agents.permissions(self.session, agent, self.editor.id), [])
            with self.assertRaises(Forbidden): agents.require(self.session, agent, self.editor.id, action)
        with self.assertRaises(NotFound):
            agents.start(self.session, self.a['id'], self.workspace_a.id, self.editor.id, binding['agent_id'],
                dict(inputs={'request':'outside'}, expected_revision=1), str(uuid4()))
        with self.assertRaises(Forbidden): self.get(actor=self.admin)
        with self.assertRaises(Forbidden): self.act(row, 'run', actor=self.admin)
        with self.assertRaises(Conflict): self.act(self.get(self.second), 'run')
        running = self.act(row, 'run')
        self.assertIsNotNone(agent_execution.claim(self.session, running['active_attempt_id']))
        self.assertEqual(agents.get_attempt(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            binding['agent_id'], running['active_attempt_id'])['id'], running['active_attempt_id'])
        attempts = agents.tables(self.session)[2]
        attempt = self.session.execute(sa.select(attempts).where(attempts.c.id == running['active_attempt_id'])).mappings().one()
        self.assertEqual(stages.validate_attempt(self.session, attempt)['id'], row['id'])

    def test_new_versions_and_other_flows_cannot_change_active_stage(self):
        before = copy.deepcopy(self.flow['published']); active = self.get()
        changed = dict(self.new_stage, execution=dict(self.new_stage['execution'], instructions='Different acceptance'))
        other = self.publish(self.save(stages=[changed]))
        self.flow = self.publish(self.save(self.flow, stages=[changed]))
        self.assertEqual(self.get()['binding'], active['binding'])
        self.assertEqual(flows.get_version(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            self.flow['id'], before['id']), before)
        self.assertNotEqual(other['published']['stage_bindings'][0]['agent_id'], active['binding']['agent_id'])
        self.assertEqual(self.flow['published']['stage_bindings'][0]['execution']['instructions'], 'Different acceptance')

    def test_participant_feedback_is_stage_scoped_and_handoff_stays_human(self):
        person = dict(account_id=self.admin.id, membership_id=access.membership(self.session, self.workspace_a.id, self.admin.id).id, actions=['view', 'feedback'])
        self.flow = self.publish(self.save(stages=[dict(self.new_stage, participants=[person]), dict(self.new_stage, key='review', title='Review')]))
        self.req = self.decision(self.request()); self.inst = self.create_instance(); self.first, self.second = self.inst['stages']
        self.assertIn('feedback', self.get(actor=self.admin)['actions'])
        with self.assertRaises(Forbidden): self.act(self.get(), 'run', actor=self.admin)
        with self.assertRaises(Forbidden): self.get(self.second, actor=self.admin)
        row = self.complete(); self.assertEqual(row['state'], 'awaiting_feedback')
        chosen = self.act(row, 'request_decision', artifact_id=row['artifacts'][0]['id'])
        with self.assertRaises(Forbidden): self.act(chosen, 'finalize', actor=self.admin, artifact_id=chosen['selected_artifact_id'], reason='Not assigned')
        self.assertEqual(self.get(self.second)['state'], 'blocked')
        done = self.act(chosen, 'finalize', actor=self.project_owner, artifact_id=chosen['selected_artifact_id'], reason='Human accepted')
        self.assertEqual(done['state'], 'completed'); self.assertEqual(self.get(self.second)['state'], 'ready')

    def test_harness_policy_is_frozen_and_program_method_cannot_bypass_it(self):
        spec = dict(self.new_stage, execution=dict(program_enabled=False, enabled=True, instructions='Frozen mission', requires_source=False))
        self.flow = self.publish(self.save(stages=[spec])); self.req = self.decision(self.request()); self.inst = self.create_instance(); self.first = self.inst['stages'][0]
        with self.assertRaises(Forbidden): self.act(self.get(), 'run')
        pair = source.pair(self.session, dict(code=source.pairing(self.session, self.editor.id, dict(name='Synthetic device'))['code']))
        runner = source.authenticate(self.session, pair['secret'])
        selection = dict(method='harness', mode='manual', device_id=str(runner['id']), source_job_id=None, profile_key=None)
        row = self.act(self.get(), 'run', execution=selection)
        job = harness.load(self.session, row['active_attempt_id']); self.assertEqual(harness.bundle(self.session, job)['instructions'], 'Frozen mission')
        # A different flow/version or a shared policy for another source never retires this job.
        self.publish(self.save(stages=[dict(spec, execution=dict(spec['execution'], instructions='New mission'))]))
        harness.expire(self.session, project=self.a['id']); self.assertEqual(harness.load(self.session, job['attempt_id'])['state'], 'awaiting_user')
        result = harness.stage_submit(self.session, self.a['id'], self.workspace_a.id, self.editor.id, self.inst['id'], row['id'],
            dict(expected_revision=row['revision'], attempt_id=job['attempt_id'], snapshot_digest=job['snapshot_digest'],
                outputs={'answer':'Harness output'}, evidence=EVIDENCE, session_id=None, continue_flow=False, reason=''), str(uuid4()))
        self.assertEqual(result['state'], 'awaiting_feedback'); self.assertEqual(result['artifacts'][0]['kind'], 'harness')

    def test_membership_change_fences_queued_attempt_and_reassignment_reauthorizes(self):
        from company_projects import recovery
        row = self.act(self.get(), 'run'); identity = row['active_attempt_id']
        changed = recovery.mutate(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, self.inst['id'], row['id'], 'reassign',
            dict(expected_revision=row['revision'], reason='Move responsibility', executor_id=self.admin.id,
                executor_membership_id=access.membership(self.session, self.workspace_a.id, self.admin.id).id,
                finalizer_id=self.project_owner.id, finalizer_membership_id=access.membership(self.session, self.workspace_a.id, self.project_owner.id).id), str(uuid4()))
        self.assertIsNotNone(changed)
        with self.assertRaises(Forbidden): self.act(self.get(), 'run')
        self.assertIn('revalidate', self.get(actor=self.admin)['actions'])
        self.assertIsNone(agent_execution.claim(self.session, identity))
        latest = self.get(actor=self.admin)
        recovery.mutate(self.session, self.a['id'], self.workspace_a.id, self.admin.id, self.inst['id'], row['id'], 'revalidate',
            dict(expected_revision=latest['revision'], reason='Inputs reviewed'), str(uuid4()))
        fresh = self.act(self.get(actor=self.admin), 'run', actor=self.admin)
        join = access.membership(self.session, self.workspace_a.id, self.admin.id)
        join.id = str(uuid4()); self.session.flush()
        self.assertIsNone(agent_execution.claim(self.session, fresh['active_attempt_id']))

    def test_publish_rejects_scope_escalation_inactive_members_and_invalid_config(self):
        for config in (dict(self.new_stage['execution'], program_enabled=False), dict(self.new_stage['execution'], enabled=True, instructions='')):
            with self.assertRaises(UnprocessableEntity): self.publish(self.save(stages=[dict(self.new_stage, execution=config)]))
        bad = dict(account_id=self.admin.id, membership_id=access.membership(self.session, self.workspace_a.id, self.admin.id).id, actions=['publish_definition'])
        with self.assertRaises(BadRequest): self.save(stages=[dict(self.new_stage, participants=[bad])])
        stage = dict(self.new_stage, executor_membership_id=str(uuid4()))
        with self.assertRaises(Conflict): self.publish(self.save(stages=[stage]))
        from models.account import AccountStatus
        self.project_owner.status = AccountStatus.BANNED; self.session.flush()
        with self.assertRaises(Forbidden): self.publish(self.save(stages=[self.new_stage]))
        self.project_owner.status = AccountStatus.ACTIVE; self.session.flush()
        redundant = dict(account_id=self.editor.id, membership_id=self.new_stage['executor_membership_id'], actions=['view'])
        published = self.publish(self.save(stages=[dict(self.new_stage, participants=[redundant])]))
        self.assertEqual(published['published']['stage_bindings'][0]['participants'], [])
        foreign = dict(self.new_stage, app_id=str(uuid4()))
        with self.assertRaises(UnprocessableEntity): self.publish(self.save(stages=[foreign]))

    def test_publishing_a_stage_reuses_a_published_program_without_editing_it(self):
        scope = dict(project_id=self.a['id'], workspace_id=self.workspace_a.id)
        legacy = agents.load(self.session, scope, self.agent_ids[0])
        workflow = self.session.get(Workflow, legacy['workflow_id'])
        before = agents.fingerprint(workflow)
        for action in ('edit_definition', 'publish_definition'):
            with self.assertRaises(Forbidden):
                agent_execution.native_permission(self.session, legacy['app_id'], self.editor.id, action)
        spec = dict(self.new_stage, app_id=legacy['app_id'], workflow_id=legacy['workflow_id'])
        published = self.publish(self.save(stages=[spec]))
        self.assertEqual(published['published']['stage_bindings'][0]['workflow_id'], legacy['workflow_id'])
        self.assertEqual(agents.fingerprint(workflow), before)
        for action in ('edit_definition', 'publish_definition'):
            with self.assertRaises(Forbidden):
                agent_execution.native_permission(self.session, legacy['app_id'], self.editor.id, action)

    def test_legacy_conversion_preserves_visibility_without_global_execution_grants(self):
        scope = dict(project_id=self.a['id'], workspace_id=self.workspace_a.id)
        row = agents.load(self.session, scope, self.agent_ids[0])
        grants = agents.grant_snapshot(self.session, row)['grants']
        grants.append(dict(account_id=self.admin.id,
            membership_id=access.membership(self.session, self.workspace_a.id, self.admin.id).id, actions=['run']))
        agents.set_grants(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id, row['id'],
            dict(expected_revision=row['acl_revision'], grants=grants), str(uuid4()))
        reads = []
        def observe(conn, cursor, statement, parameters, context, executemany):
            if statement.startswith('SELECT company_team_agent_grants.action'):
                reads.append(1)
        sa.event.listen(self.connection, 'before_cursor_execute', observe)
        try:
            options = flows.options(self.session, self.a['id'], self.workspace_a.id, self.editor.id)
        finally:
            sa.event.remove(self.connection, 'before_cursor_execute', observe)
        print('Legacy per-member grant reads:', len(reads))
        legacy = next(value for value in options['agents'] if value['id'] == row['id'])
        people = {person['account_id']: person for person in legacy['participants']}
        self.assertEqual(people[self.admin.id]['actions'], ['view'])
        self.assertEqual(people[self.project_owner.id]['actions'], ['view'])
        self.assertIn(self.admin.id, legacy['runners'])
        self.assertLessEqual(len(reads), len(options['agents']) + 1)

    def test_invalid_runtime_model_candidate_does_not_hide_valid_programs(self):
        from company_projects.runtime_models import INPUT
        graph = feedback_graph()
        graph['nodes'][0]['data']['variables'].append(dict(variable=INPUT, type='text-input', label='Invalid legacy input'))
        invalid = Workflow.new(tenant_id=self.workspace_a.id, app_id=self.source_app.id, type='workflow', version='invalid-legacy-candidate',
            graph=json.dumps(graph), features='{}', created_by=self.editor.id,
            environment_variables=[], conversation_variables=[], rag_pipeline_variables=[])
        self.session.add(invalid); self.session.flush()
        options = flows.options(self.session, self.a['id'], self.workspace_a.id, self.editor.id)
        identities = [value['workflow_id'] for value in options['programs']]
        self.assertIn(self.workflow.id, identities)
        self.assertNotIn(invalid.id, identities)

    def test_stage_only_program_dispatch_claim_and_result_use_runner_authority(self):
        from company_projects import local_execution as local
        pair = source.pair(self.session, dict(code=source.pairing(self.session, self.editor.id, dict(name='Stage protocol device'))['code']))
        runner = source.authenticate(self.session, pair['secret'])
        local.register(self.session, runner, dict(protocol=2, capabilities=['workflow-v2']))
        local.set_binding(self.session, self.a['id'], self.workspace_a.id, self.editor.id,
            dict(device_id=runner['id'], source_job_id=None, expected_revision=1))
        row = self.act(self.get(), 'run')
        identity = row['active_attempt_id']
        job = local.dispatch_team(self.session, identity)
        self.assertEqual(job['team_attempt_id'], identity)
        claimed = local.claim(self.session, runner)['job']
        self.assertEqual(claimed['id'], identity)
        local.heartbeat(self.session, runner, identity)
        body = dict(state='succeeded', outputs={'answer': self.req['current']['content']}, error=None,
            total_steps=2, total_tokens=0, snapshot_digest=claimed['snapshot_digest'])
        self.assertTrue(local.complete(self.session, runner, identity, body)['recorded'])
        self.assertTrue(local.complete(self.session, runner, identity, body)['recorded'])
        result = self.get()
        self.assertEqual(result['state'], 'awaiting_feedback')
        self.assertEqual(result['artifacts'][0]['kind'], 'workflow')
        self.assertIsNone(result['selected_artifact_id'])
        self.assertEqual(self.get(self.second)['state'], 'blocked')

    def test_stage_only_managed_harness_claim_and_result_preserve_human_decision(self):
        spec = dict(self.new_stage, execution=dict(program_enabled=False, enabled=True, instructions='Managed stage mission', requires_source=False))
        self.flow = self.publish(self.save(stages=[spec, dict(self.new_stage, key='review', title='Review')]))
        self.req = self.decision(self.request()); self.inst = self.create_instance(); self.first, self.second = self.inst['stages']
        pair = source.pair(self.session, dict(code=source.pairing(self.session, self.editor.id, dict(name='Stage managed device'))['code']))
        runner = source.authenticate(self.session, pair['secret'])
        harness.register(self.session, runner, dict(profiles=[dict(key='synthetic', name='Synthetic adapter', kind='custom', version='test', digest='a' * 64)]))
        selection = dict(method='harness', mode='managed', device_id=str(runner['id']), source_job_id=None, profile_key='synthetic')
        row = self.act(self.get(), 'run', execution=selection)
        job = harness.claim(self.session, runner)['job']
        self.assertEqual(job['id'], row['active_attempt_id'])
        self.assertEqual(job['instructions'], 'Managed stage mission')
        harness.prepared(self.session, runner, job['id'], dict(snapshot_digest=job['snapshot_digest']))
        body = dict(snapshot_digest=job['snapshot_digest'], outputs={'answer': 'Synthetic managed output'}, evidence=EVIDENCE, session_id=None)
        self.assertTrue(harness.complete(self.session, runner, job['id'], body)['recorded'])
        self.assertTrue(harness.complete(self.session, runner, job['id'], body)['recorded'])
        result = self.get()
        self.assertEqual(result['harness']['result']['origin'], 'managed_harness')
        self.assertEqual(result['state'], 'awaiting_feedback')
        self.assertIsNone(result['selected_artifact_id'])
        self.assertEqual(self.get(self.second)['state'], 'blocked')

    def test_concurrent_drafts_reject_old_revision_without_overwriting_newer_configuration(self):
        base = copy.deepcopy(self.flow)
        newer = self.save(base, description='Saved by another editor',
            stages=[dict(self.new_stage, title='Newer stage configuration')])
        with self.assertRaises(Conflict):
            self.save(base, description='Unsaved local text', stages=[self.new_stage])
        current = flows.get_flow(self.session, self.a['id'], self.workspace_a.id, self.editor.id, base['id'])
        self.assertEqual(current['revision'], newer['revision'])
        self.assertEqual(current['description'], 'Saved by another editor')
        self.assertEqual(current['draft_stages'][0]['title'], 'Newer stage configuration')
        self.assertEqual(current['published'], base['published'])

    def test_display_name_change_is_not_a_reassignment_and_does_not_interrupt_work(self):
        from company_projects import recovery
        row = self.act(self.get(), 'run')
        self.editor.name = 'Renamed executor'; self.session.flush()
        body = dict(expected_revision=row['revision'], reason='Same people selected',
            executor_id=row['binding']['executor']['account_id'], executor_membership_id=row['binding']['executor']['membership_id'],
            finalizer_id=row['binding']['finalizer']['account_id'], finalizer_membership_id=row['binding']['finalizer']['membership_id'])
        with self.assertRaises(Conflict):
            recovery.mutate(self.session, self.a['id'], self.workspace_a.id, self.project_owner.id,
                self.inst['id'], row['id'], 'reassign', body, str(uuid4()))
        current = self.get()
        self.assertEqual(current['revision'], row['revision'])
        self.assertEqual(current['round'], row['round'])
        self.assertEqual(current['active_attempt_id'], row['active_attempt_id'])
        self.assertEqual(current['state'], 'running')
        attempts = agents.tables(self.session)[2]
        self.assertEqual(self.session.scalar(sa.select(attempts.c.status).where(attempts.c.id == row['active_attempt_id'])), 'pending')
