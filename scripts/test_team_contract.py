"""Behavioral contract tests for KP-00; no API, live database or model is used."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from kara_contracts.team import (
    VERSION, ActionContext, Actor, Agent, AgentAction as A, Artifact, BusinessRole as R,
    ContractError, Grant, Guard as G, IntakeDecision, Membership,
    ProjectAction as P, Scope, Stage, StageEvent as E, StageState as S, VersionRef,
    agent_permission, content_digest, decision_matches, project_permission,
    transition_stage,
)


def uid(number):
    return f'00000000-0000-4000-8000-{number:012d}'


class ContractFixture(unittest.TestCase):
    def setUp(self):
        self.scope = Scope(uid(1), uid(2))
        self.other = Scope(uid(3), uid(4))
        self.po, self.tl = Actor(uid(10)), Actor(uid(11))
        self.member = Membership(self.po.account_id, self.scope, business_roles=frozenset({R.PO}))
        self.tl_member = Membership(self.tl.account_id, self.scope, business_roles=frozenset({R.TL}))
        self.agent = Agent(uid(20), self.scope, uid(21))
        self.grant = Grant(self.po.account_id, self.scope, self.agent.agent_id,
                           frozenset({A.RUN, A.FEEDBACK, A.FINALIZE}))
        self.ready = frozenset({G.PREREQUISITES, G.APPROVAL, G.INPUTS})
        self.all_guards = self.ready | {G.OUTPUT}
        self.binding = content_digest({'request_revision': 1, 'turn': 0})
        self.stage = Stage(uid(30), self.scope, self.agent.agent_id, 1, S.READY,
                           self.binding, self.po.account_id, R.PO)
        self.now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        self.request = VersionRef(self.scope, uid(40), 1, content_digest('متن درخواست'))
        self.flow = VersionRef(self.scope, uid(41), 1, content_digest('فلو آزمایشی'))
        self.approval = IntakeDecision(uid(42), self.po.account_id, self.request, self.flow,
                                      'approved', 'real', self.now - timedelta(minutes=1))

    def permission(self, action, actor=None, member=None, agent=None, grants=None, **kwargs):
        return agent_permission(actor or self.po, member or self.member, agent or self.agent,
                                action, (self.grant,) if grants is None else grants, **kwargs)

    def context(self, actor=None, member=None, agent=None, grants=None):
        return ActionContext(actor or self.po, member or self.member, agent or self.agent,
                             (self.grant,) if grants is None else grants)

    def move(self, stage, event, **kwargs):
        return transition_stage(stage, event, expected_revision=kwargs.pop('expected_revision', stage.revision),
                                **kwargs)

    def draft(self):
        running = self.move(self.stage, E.START, context=self.context(), guards=self.ready, attempt_id=uid(50))
        return self.move(running, E.SUCCEED, system=True, guards=frozenset({G.OUTPUT}), attempt_id=uid(50))

    def reviewed(self):
        return self.move(self.draft(), E.REQUEST_DECISION, context=self.context(), guards=self.all_guards)

    def artifact(self, stage):
        return Artifact(VersionRef(stage.scope, uid(60), 1, content_digest('پیش‌نویس')), stage.stage_id, stage.input_digest)

    def assertCode(self, code, call):
        with self.assertRaises(ContractError) as captured:
            call()
        self.assertEqual(captured.exception.code, code)


class PermissionContractTests(ContractFixture):
    def test_declared_access_scenarios(self):
        path = Path(__file__).resolve().parents[1] / 'fixtures/kara-contracts/access-cases.json'
        fixture = json.loads(path.read_text())
        self.assertTrue(fixture['synthetic'])
        self.assertEqual(fixture['contract_version'], VERSION)
        for case in fixture['cases']:
            with self.subTest(case=case['id']):
                member = replace(self.member, native_role=case['role'],
                                 business_roles=frozenset(R(r) for r in case['business_roles']))
                grant = replace(self.grant, actions=frozenset(A(a) for a in case['grants']))
                result = self.permission(A(case['action']), member=member, grants=(grant,))
                self.assertEqual(result.allowed, case['allowed'])

    def test_grants_are_bound_to_account_project_workspace_and_agent(self):
        changes = [{'account_id': self.tl.account_id}, {'scope': self.other},
                   {'scope': Scope(self.scope.project_id, uid(99))}, {'agent_id': uid(98)}]
        for change in changes:
            with self.subTest(change=change):
                self.assertFalse(self.permission(A.RUN, grants=(replace(self.grant, **change),)).allowed)

    def test_removed_or_inactive_membership_denies_all_operational_actions(self):
        for member in [None, replace(self.member, active=False), replace(self.member, scope=self.other),
                       replace(self.member, account_id=self.tl.account_id)]:
            for action in [A.RUN, A.FEEDBACK, A.FINALIZE, A.VIEW]:
                with self.subTest(member=member, action=action):
                    self.assertFalse(agent_permission(self.po, member, self.agent, action, (self.grant,)).allowed)

    def test_inactive_platform_admin_cannot_manage_access(self):
        actor = replace(self.po, platform_admin=True, active=False)
        self.assertFalse(self.permission(A.MANAGE_ACCESS, actor=actor).allowed)

    def test_admin_manages_but_cannot_execute_or_approve_without_explicit_team_authority(self):
        actor = replace(self.po, platform_admin=True)
        self.assertTrue(agent_permission(actor, None, self.agent, A.MANAGE_ACCESS).allowed)
        self.assertFalse(agent_permission(actor, None, self.agent, A.RUN, (self.grant,)).allowed)
        self.assertFalse(project_permission(actor, None, self.scope, P.APPROVE_INTAKE).allowed)
        member = replace(self.member, native_role='owner', business_roles=frozenset())
        self.assertFalse(project_permission(actor, member, self.scope, P.APPROVE_INTAKE).allowed)

    def test_po_approval_is_project_local_and_does_not_require_editor(self):
        self.assertTrue(project_permission(self.po, self.member, self.scope, P.APPROVE_INTAKE).allowed)
        self.assertFalse(project_permission(self.po, self.member, self.other, P.APPROVE_INTAKE).allowed)
        self.assertFalse(project_permission(self.tl, self.tl_member, self.scope, P.APPROVE_INTAKE).allowed)

    def test_multiple_business_roles_do_not_create_a_run_grant(self):
        member = replace(self.member, business_roles=frozenset({R.PO, R.TL, R.DEVELOPER}))
        self.assertFalse(self.permission(A.RUN, member=member, grants=()).allowed)
        self.assertTrue(project_permission(self.po, member, self.scope, P.APPROVE_INTAKE).allowed)

    def test_editing_requires_both_agent_grant_and_native_permission(self):
        grant = replace(self.grant, actions=frozenset({A.EDIT, A.PUBLISH}))
        for action in [A.EDIT, A.PUBLISH]:
            self.assertFalse(self.permission(action, grants=(grant,)).allowed)
            self.assertFalse(self.permission(action, grants=(), native_permissions=frozenset({action})).allowed)
            self.assertTrue(self.permission(action, grants=(grant,), native_permissions=frozenset({action})).allowed)

    def test_draft_version_cannot_be_used_for_operational_work(self):
        for action in [A.RUN, A.FEEDBACK, A.FINALIZE]:
            self.assertFalse(self.permission(action, agent=replace(self.agent, published=False)).allowed)

    def test_a_grant_cannot_delegate_access_management(self):
        self.assertCode('management_is_not_delegated_by_agent_grant',
                        lambda: replace(self.grant, actions=frozenset({A.MANAGE_ACCESS})))

    def test_project_manager_can_assign_roles_but_editor_cannot(self):
        for role, expected in [('owner', True), ('admin', False), ('editor', False), ('normal', False)]:
            member = replace(self.member, native_role=role)
            self.assertEqual(project_permission(self.po, member, self.scope, P.MANAGE_ROLES).allowed, expected)

    def test_two_users_can_have_independent_grants_for_same_agent(self):
        second = replace(self.grant, account_id=self.tl.account_id)
        self.assertTrue(self.permission(A.RUN, grants=(self.grant, second)).allowed)
        self.assertTrue(agent_permission(self.tl, self.tl_member, self.agent, A.RUN, (self.grant, second)).allowed)
        self.assertFalse(agent_permission(self.tl, self.tl_member, self.agent, A.RUN, (self.grant,)).allowed)


class DecisionVersionTests(ContractFixture):
    def test_exact_stored_real_decision_matches(self):
        self.assertTrue(decision_matches(self.approval, self.request, self.flow, self.now))

    def test_same_number_different_content_and_new_revision_invalidate_decision(self):
        for request in [replace(self.request, digest=content_digest('تغییر متن')),
                        replace(self.request, revision=2), replace(self.request, entity_id=uid(999)),
                        replace(self.request, scope=self.other)]:
            self.assertFalse(decision_matches(self.approval, request, self.flow, self.now))
        self.assertFalse(decision_matches(self.approval, self.request, replace(self.flow, revision=2), self.now))
        self.assertFalse(decision_matches(self.approval, self.request, replace(self.flow, digest=content_digest('تغییر فلو')), self.now))

    def test_trial_rejection_deferral_and_revocation_never_unlock_work(self):
        for change in [{'mode': 'trial'}, {'outcome': 'rejected'}, {'outcome': 'deferred'},
                       {'outcome': 'changes_requested'}, {'revoked': True}]:
            self.assertFalse(decision_matches(replace(self.approval, **change), self.request, self.flow, self.now))

    def test_expiry_boundary_and_future_decision(self):
        expiring = replace(self.approval, expires_at=self.now)
        self.assertFalse(decision_matches(expiring, self.request, self.flow, self.now))
        self.assertTrue(decision_matches(expiring, self.request, self.flow, self.now - timedelta(seconds=1)))
        self.assertFalse(decision_matches(replace(self.approval, decided_at=self.now + timedelta(seconds=1)), self.request, self.flow, self.now))

    def test_json_claim_is_not_a_stored_decision(self):
        self.assertFalse(decision_matches({'outcome': 'approved', 'mode': 'real'}, self.request, self.flow, self.now))
        self.assertCode('cross_project_decision', lambda: replace(self.approval, flow=replace(self.flow, scope=self.other)))

    def test_strict_ids_revisions_booleans_and_timezone(self):
        for revision in [True, False, 0, -1, 1.5, '1']:
            self.assertCode('invalid_revision', lambda: replace(self.request, revision=revision))
        self.assertCode('invalid_boolean', lambda: replace(self.po, platform_admin='true'))
        self.assertCode('invalid_id', lambda: replace(self.po, account_id='PO'))
        self.assertCode('timezone_required', lambda: replace(self.approval, decided_at=self.now.replace(tzinfo=None)))
        self.assertCode('invalid_digest', lambda: replace(self.request, digest='old-hash'))

    def test_hash_preserves_text_and_is_stable_for_object_key_order(self):
        self.assertNotEqual(content_digest('نباید نمایش داده شود'), content_digest('نباید به‌روز شود'))
        self.assertNotEqual(content_digest('متن'), content_digest('متن '))
        self.assertEqual(content_digest({'a': 1, 'b': 'فارسی'}), content_digest({'b': 'فارسی', 'a': 1}))
        for value in [{'value': float('nan')}, {1: 'implicit key'}, ('implicit', 'list'), chr(0xD800)]:
            self.assertCode('invalid_content', lambda: content_digest(value))


class StageLifecycleTests(ContractFixture):
    def test_success_is_only_a_draft_and_never_auto_completes(self):
        draft = self.draft()
        self.assertEqual(draft.state, S.AWAITING_FEEDBACK)
        self.assertIsNone(draft.active_attempt_id)
        self.assertCode('transition_not_allowed', lambda: self.move(draft, E.FINALIZE, context=self.context()))

    def test_unmet_prerequisite_approval_and_stale_input_each_stop_start(self):
        for missing in self.ready:
            self.assertCode('transition_guard_missing', lambda: self.move(
                self.stage, E.START, context=self.context(), guards=self.ready - {missing}, attempt_id=uid(50)))
        self.assertCode('transition_not_allowed', lambda: self.move(replace(self.stage, state=S.BLOCKED), E.START))

    def test_only_system_may_report_the_matching_attempt(self):
        running = self.move(self.stage, E.START, context=self.context(), guards=self.ready, attempt_id=uid(50))
        self.assertCode('system_event_required', lambda: self.move(running, E.SUCCEED, attempt_id=uid(50), guards=frozenset({G.OUTPUT})))
        self.assertCode('attempt_mismatch', lambda: self.move(running, E.SUCCEED, system=True, attempt_id=uid(51), guards=frozenset({G.OUTPUT})))
        self.assertCode('transition_guard_missing', lambda: self.move(running, E.SUCCEED, system=True, attempt_id=uid(50)))
        self.assertEqual(self.move(running, E.FAIL, system=True, attempt_id=uid(50)).state, S.FAILED)

    def test_feedback_requires_a_new_input_binding_and_explicit_new_start(self):
        draft = self.draft()
        self.assertCode('new_input_binding_required', lambda: self.move(draft, E.FEEDBACK,
                        context=self.context(), guards=self.ready, next_input_digest=draft.input_digest))
        ready = self.move(draft, E.FEEDBACK, context=self.context(), guards=self.ready,
                          next_input_digest=content_digest({'feedback': 'اصلاح اول'}))
        self.assertEqual(ready.state, S.READY)
        self.assertIsNone(ready.active_attempt_id)
        self.assertNotEqual(ready.input_digest, draft.input_digest)

    def test_finalization_requires_current_output_designated_person_and_role(self):
        reviewed = self.reviewed()
        artifact = self.artifact(reviewed)
        call = dict(context=self.context(), guards=self.all_guards, artifact=artifact)
        self.assertEqual(self.move(reviewed, E.FINALIZE, **call).state, S.COMPLETED)
        self.assertCode('designated_finalizer_required', lambda: self.move(replace(reviewed, finalizer_id=self.tl.account_id), E.FINALIZE, **call))
        self.assertCode('decision_role_required', lambda: self.move(reviewed, E.FINALIZE, **{**call, 'context': self.context(member=replace(self.member, business_roles=frozenset()))}))
        for invalid in [None, replace(artifact, stage_id=uid(99)), replace(artifact, input_digest=content_digest('old')),
                        replace(artifact, version=replace(artifact.version, scope=self.other))]:
            self.assertCode('current_stage_artifact_required', lambda: self.move(reviewed, E.FINALIZE, **{**call, 'artifact': invalid}))

    def test_foreign_context_wrong_agent_and_json_authority_are_rejected(self):
        for invalid in [None, {'allowed': True}, self.context(agent=replace(self.agent, scope=self.other)),
                        self.context(agent=replace(self.agent, agent_id=uid(99)))]:
            with self.assertRaises(ContractError):
                self.move(self.stage, E.START, context=invalid, guards=self.ready, attempt_id=uid(50))
        self.assertCode('permission_required', lambda: self.move(self.stage, E.START,
                        context=self.context(grants=(replace(self.grant, actions=frozenset({A.FINALIZE})),)),
                        guards=self.ready, attempt_id=uid(50)))

    def test_system_cannot_finalize_for_a_human(self):
        reviewed = self.reviewed()
        self.assertCode('human_action_required', lambda: self.move(reviewed, E.FINALIZE, system=True,
                        context=self.context(), guards=self.all_guards,
                        artifact=self.artifact(reviewed)))

    def test_old_version_and_duplicate_finalize_are_rejected(self):
        reviewed = self.reviewed()
        completed = self.move(reviewed, E.FINALIZE, context=self.context(),
                              guards=self.all_guards, artifact=self.artifact(reviewed))
        self.assertCode('revision_conflict', lambda: self.move(completed, E.FINALIZE, expected_revision=reviewed.revision))
        self.assertCode('transition_not_allowed', lambda: self.move(completed, E.FINALIZE))

    def test_change_invalidates_completed_output_without_automatic_reacceptance(self):
        reviewed = self.reviewed()
        completed = self.move(reviewed, E.FINALIZE, context=self.context(),
                              guards=self.all_guards, artifact=self.artifact(reviewed))
        stale = self.move(completed, E.INVALIDATE, system=True, guards=frozenset({G.INPUTS_CHANGED}))
        self.assertEqual(stale.state, S.STALE)
        self.assertCode('transition_not_allowed', lambda: self.move(stale, E.FINALIZE))
        fresh = self.move(stale, E.REVALIDATE, context=self.context(), guards=self.ready,
                          next_input_digest=content_digest({'request_revision': 2}))
        self.assertEqual(fresh.state, S.READY)
        self.assertEqual(completed.state, S.COMPLETED)  # Historical value is immutable.

    def test_cancelled_or_stale_run_cannot_accept_a_late_result(self):
        running = self.move(self.stage, E.START, context=self.context(), guards=self.ready, attempt_id=uid(50))
        cancelled = self.move(running, E.CANCEL, context=self.context())
        stale = self.move(running, E.INVALIDATE, system=True, guards=frozenset({G.INPUTS_CHANGED}))
        for result in [cancelled, stale]:
            self.assertIsNone(result.active_attempt_id)
            self.assertCode('transition_not_allowed', lambda: self.move(result, E.SUCCEED, system=True,
                            attempt_id=uid(50), guards=frozenset({G.OUTPUT})))

    def test_revoked_grant_requires_reauthorization_before_another_action(self):
        self.assertCode('permission_required', lambda: self.move(self.stage, E.START, context=self.context(grants=()),
                        guards=self.ready, attempt_id=uid(50)))

    def test_current_account_and_membership_are_rechecked_for_each_transition(self):
        for context in [self.context(actor=replace(self.po, active=False)),
                        self.context(member=replace(self.member, active=False))]:
            self.assertCode('permission_required', lambda: self.move(self.stage, E.START,
                            context=context, guards=self.ready, attempt_id=uid(50)))
        reviewed = self.reviewed()
        revoked = self.context(grants=(replace(self.grant, actions=frozenset({A.RUN, A.FEEDBACK})),))
        self.assertCode('permission_required', lambda: self.move(reviewed, E.FINALIZE,
                        context=revoked, guards=self.all_guards, artifact=self.artifact(reviewed)))

    def test_two_role_handoff_keeps_second_stage_blocked_until_finalization(self):
        next_agent = replace(self.agent, agent_id=uid(70), workflow_id=uid(71))
        second = replace(self.stage, stage_id=uid(72), agent_id=next_agent.agent_id, state=S.BLOCKED,
                         finalizer_id=self.tl.account_id, decision_role=R.TL)
        self.assertCode('transition_guard_missing', lambda: self.move(second, E.UNBLOCK, system=True,
                        guards=frozenset({G.APPROVAL, G.INPUTS})))
        reviewed = self.reviewed()
        completed = self.move(reviewed, E.FINALIZE, context=self.context(),
                              guards=self.all_guards, artifact=self.artifact(reviewed))
        self.assertEqual(completed.state, S.COMPLETED)
        ready = self.move(second, E.UNBLOCK, system=True, guards=self.ready)
        self.assertEqual(ready.state, S.READY)  # No automatic execution by the first actor.
        tl_grant = replace(self.grant, account_id=self.tl.account_id, agent_id=next_agent.agent_id)
        tl_context = self.context(actor=self.tl, member=self.tl_member, agent=next_agent, grants=(tl_grant,))
        running = self.move(ready, E.START, context=tl_context, guards=self.ready, attempt_id=uid(73))
        self.assertEqual(running.state, S.RUNNING)
        self.assertFalse(agent_permission(self.po, self.member, next_agent, A.RUN, (tl_grant,)).allowed)


if __name__ == '__main__':
    unittest.main()
