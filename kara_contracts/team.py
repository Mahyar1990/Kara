"""KP-00 executable contract, independent of HTTP, storage, Dify and model output.

Identity, membership, native permissions and approvals MUST come from trusted
server adapters. These value objects are not authentication or signed decisions.
Nothing in this module reads a database, changes live permissions or runs tools.
"""
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
import hashlib
import json
from types import MappingProxyType
from uuid import UUID

VERSION = '1.0.0'


class ContractError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _uuid(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ContractError('invalid_id') from None


def _revision(value):
    if type(value) is not int or value < 1:
        raise ContractError('invalid_revision')


def _bool(value):
    if type(value) is not bool:
        raise ContractError('invalid_boolean')


def _digest(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ContractError('invalid_digest')


def _enum(value, kind):
    if not isinstance(value, kind):
        raise ContractError('invalid_enum')


def _set(values, kind):
    if not isinstance(values, frozenset) or any(not isinstance(v, kind) for v in values):
        raise ContractError('invalid_set')


def _time(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractError('timezone_required')


def content_digest(value):
    """Hash exact content using canonical JSON; reject NaN and implicit coercion."""
    def check(item):
        if item is None or type(item) in {str, int, float, bool}:
            return
        if type(item) is list:
            for child in item:
                check(child)
        elif type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                check(child)
        else:
            raise ContractError('invalid_content')
    try:
        check(value)
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise ContractError('invalid_content') from None
    return hashlib.sha256(raw).hexdigest()


class BusinessRole(StrEnum):
    PO = 'po'
    TL = 'tl'
    DESIGNER = 'designer'
    DEVELOPER = 'developer'
    QC = 'qc'


class AgentAction(StrEnum):
    VIEW = 'view'
    RUN = 'run'
    FEEDBACK = 'feedback'
    FINALIZE = 'finalize'
    EDIT = 'edit_definition'
    PUBLISH = 'publish_definition'
    MANAGE_ACCESS = 'manage_access'


class ProjectAction(StrEnum):
    MANAGE_ROLES = 'manage_roles'
    MANAGE_FLOW = 'manage_flow'
    SUBMIT_REQUEST = 'submit_request'
    APPROVE_INTAKE = 'approve_intake'
    CANCEL_INSTANCE = 'cancel_instance'
    REASSIGN_STAGE = 'reassign_stage'


@dataclass(frozen=True)
class Scope:
    project_id: str
    workspace_id: str

    def __post_init__(self):
        _uuid(self.project_id)
        _uuid(self.workspace_id)


@dataclass(frozen=True)
class Actor:
    account_id: str
    active: bool = True
    platform_admin: bool = False

    def __post_init__(self):
        _uuid(self.account_id)
        _bool(self.active)
        _bool(self.platform_admin)


@dataclass(frozen=True)
class Membership:
    account_id: str
    scope: Scope
    native_role: str = 'normal'
    business_roles: frozenset[BusinessRole] = frozenset()
    active: bool = True

    def __post_init__(self):
        _uuid(self.account_id)
        if not isinstance(self.scope, Scope):
            raise ContractError('invalid_scope')
        if not isinstance(self.native_role, str) or self.native_role not in {'owner', 'admin', 'editor', 'normal', 'dataset_operator'}:
            raise ContractError('invalid_native_role')
        _set(self.business_roles, BusinessRole)
        _bool(self.active)


@dataclass(frozen=True)
class Agent:
    agent_id: str
    scope: Scope
    workflow_id: str
    published: bool = True

    def __post_init__(self):
        _uuid(self.agent_id)
        _uuid(self.workflow_id)
        if not isinstance(self.scope, Scope):
            raise ContractError('invalid_scope')
        _bool(self.published)


@dataclass(frozen=True)
class Grant:
    account_id: str
    scope: Scope
    agent_id: str
    actions: frozenset[AgentAction]

    def __post_init__(self):
        _uuid(self.account_id)
        _uuid(self.agent_id)
        if not isinstance(self.scope, Scope):
            raise ContractError('invalid_scope')
        _set(self.actions, AgentAction)
        if AgentAction.MANAGE_ACCESS in self.actions:
            raise ContractError('management_is_not_delegated_by_agent_grant')


@dataclass(frozen=True)
class Permission:
    account_id: str
    scope: Scope
    target_id: str
    action: AgentAction | ProjectAction
    allowed: bool
    reason: str


def _member(actor, membership, scope):
    return bool(membership and membership.active and membership.account_id == actor.account_id and membership.scope == scope)


def _manager(actor, membership, scope):
    return actor.platform_admin or (_member(actor, membership, scope) and membership.native_role == 'owner')


def agent_permission(actor, membership, agent, action, grants=(), native_permissions=frozenset()):
    """Resolve only managed-agent policy; never infer native permissions from a title."""
    _enum(action, AgentAction)
    _set(native_permissions, AgentAction)
    reason = 'not_granted'
    allowed = False
    if not actor.active:
        reason = 'inactive_account'
    elif action == AgentAction.MANAGE_ACCESS:
        allowed = bool(_manager(actor, membership, agent.scope))
        reason = 'project_manager_required' if not allowed else 'management_authority'
    elif not _member(actor, membership, agent.scope):
        reason = 'active_project_membership_required'
    else:
        actions = set()
        for grant in grants:
            if (grant.account_id == actor.account_id and grant.scope == agent.scope and grant.agent_id == agent.agent_id):
                actions.update(grant.actions)
        if action == AgentAction.VIEW:
            # Minimal role/input description only, not private logs or credentials.
            allowed = bool(actions)
        else:
            allowed = action in actions
        if allowed and action in {AgentAction.EDIT, AgentAction.PUBLISH} and action not in native_permissions:
            allowed, reason = False, 'native_permission_required'
        elif allowed and action in {AgentAction.RUN, AgentAction.FEEDBACK, AgentAction.FINALIZE} and not agent.published:
            allowed, reason = False, 'published_version_required'
        elif allowed:
            reason = 'explicit_agent_grant'
    return Permission(actor.account_id, agent.scope, agent.agent_id, action, bool(allowed), reason)


def project_permission(actor, membership, scope, action):
    _enum(action, ProjectAction)
    allowed, reason = False, 'project_permission_required'
    if not actor.active:
        reason = 'inactive_account'
    elif action in {ProjectAction.MANAGE_ROLES, ProjectAction.REASSIGN_STAGE}:
        allowed = bool(_manager(actor, membership, scope))
    elif action == ProjectAction.CANCEL_INSTANCE:
        allowed = bool(_manager(actor, membership, scope) or (
            _member(actor, membership, scope) and BusinessRole.PO in membership.business_roles))
    elif _member(actor, membership, scope):
        if action == ProjectAction.SUBMIT_REQUEST:
            allowed = True
        elif action == ProjectAction.APPROVE_INTAKE:
            allowed = BusinessRole.PO in membership.business_roles
        elif action == ProjectAction.MANAGE_FLOW:
            allowed = membership.native_role in {'owner', 'admin', 'editor'}
    if allowed:
        reason = 'project_authority'
    return Permission(actor.account_id, scope, scope.project_id, action, bool(allowed), reason)


@dataclass(frozen=True)
class ActionContext:
    """Fresh transaction-local server facts. Do not cache across user actions."""
    actor: Actor
    membership: Membership | None
    agent: Agent
    grants: tuple[Grant, ...] = ()
    native_permissions: frozenset[AgentAction] = frozenset()

    def __post_init__(self):
        if not isinstance(self.actor, Actor) or not isinstance(self.agent, Agent):
            raise ContractError('invalid_action_context')
        if self.membership is not None and not isinstance(self.membership, Membership):
            raise ContractError('invalid_action_context')
        if not isinstance(self.grants, tuple) or any(not isinstance(g, Grant) for g in self.grants):
            raise ContractError('invalid_action_context')
        _set(self.native_permissions, AgentAction)


@dataclass(frozen=True)
class VersionRef:
    scope: Scope
    entity_id: str
    revision: int
    digest: str

    def __post_init__(self):
        if not isinstance(self.scope, Scope):
            raise ContractError('invalid_scope')
        _uuid(self.entity_id)
        _revision(self.revision)
        _digest(self.digest)


@dataclass(frozen=True)
class IntakeDecision:
    """Value read from a trusted decision store; never accept this from an API client."""
    decision_id: str
    account_id: str
    request: VersionRef
    flow: VersionRef
    outcome: str
    mode: str
    decided_at: datetime
    revoked: bool = False
    expires_at: datetime | None = None

    def __post_init__(self):
        _uuid(self.decision_id)
        _uuid(self.account_id)
        if not isinstance(self.request, VersionRef) or not isinstance(self.flow, VersionRef):
            raise ContractError('invalid_version_reference')
        if self.request.scope != self.flow.scope:
            raise ContractError('cross_project_decision')
        if not isinstance(self.outcome, str) or self.outcome not in {'approved', 'changes_requested', 'rejected', 'deferred'}:
            raise ContractError('invalid_decision')
        if not isinstance(self.mode, str) or self.mode not in {'real', 'trial'}:
            raise ContractError('invalid_mode')
        _time(self.decided_at)
        _bool(self.revoked)
        if self.expires_at is not None:
            _time(self.expires_at)
            if self.expires_at <= self.decided_at:
                raise ContractError('invalid_decision_expiry')


def decision_matches(decision, request, flow, now):
    """Check stored decision validity; caller separately checks PO at submission."""
    _time(now)
    return bool(isinstance(decision, IntakeDecision) and decision.outcome == 'approved' and
                decision.mode == 'real' and not decision.revoked and decision.request == request and
                decision.flow == flow and decision.decided_at <= now and
                (decision.expires_at is None or now < decision.expires_at))


class StageState(StrEnum):
    BLOCKED = 'blocked'
    READY = 'ready'
    RUNNING = 'running'
    AWAITING_FEEDBACK = 'awaiting_feedback'
    AWAITING_DECISION = 'awaiting_decision'
    COMPLETED = 'completed'
    FAILED = 'failed'
    STALE = 'stale'
    CANCELLED = 'cancelled'


class StageEvent(StrEnum):
    UNBLOCK = 'unblock'
    START = 'start'
    SUCCEED = 'attempt_succeeded'
    FAIL = 'attempt_failed'
    FEEDBACK = 'feedback'
    REQUEST_DECISION = 'request_decision'
    FINALIZE = 'finalize'
    RETRY = 'retry'
    INVALIDATE = 'invalidate'
    REVALIDATE = 'revalidate'
    CANCEL = 'cancel'


class Guard(StrEnum):
    PREREQUISITES = 'prerequisites_finalized'
    APPROVAL = 'intake_decision_valid'
    INPUTS = 'inputs_current'
    OUTPUT = 'output_contract_valid'
    INPUTS_CHANGED = 'consumed_inputs_changed'


@dataclass(frozen=True)
class Stage:
    stage_id: str
    scope: Scope
    agent_id: str
    workflow_id: str
    revision: int
    state: StageState
    input_digest: str
    finalizer_id: str
    decision_role: BusinessRole | None = None
    active_attempt_id: str | None = None

    def __post_init__(self):
        for value in (self.stage_id, self.agent_id, self.workflow_id, self.finalizer_id):
            _uuid(value)
        if not isinstance(self.scope, Scope):
            raise ContractError('invalid_scope')
        _revision(self.revision)
        _enum(self.state, StageState)
        _digest(self.input_digest)
        if self.decision_role is not None:
            _enum(self.decision_role, BusinessRole)
        if self.active_attempt_id is not None:
            _uuid(self.active_attempt_id)
        if (self.state == StageState.RUNNING) != (self.active_attempt_id is not None):
            raise ContractError('attempt_state_mismatch')


@dataclass(frozen=True)
class Artifact:
    version: VersionRef
    stage_id: str
    input_digest: str

    def __post_init__(self):
        if not isinstance(self.version, VersionRef):
            raise ContractError('invalid_version_reference')
        _uuid(self.stage_id)
        _digest(self.input_digest)


@dataclass(frozen=True)
class Transition:
    target: StageState
    action: AgentAction | ProjectAction | None
    guards: frozenset[Guard]


_READY_GUARDS = frozenset({Guard.PREREQUISITES, Guard.APPROVAL, Guard.INPUTS})
_FINAL_GUARDS = _READY_GUARDS | {Guard.OUTPUT}
TRANSITIONS = {
    (StageState.BLOCKED, StageEvent.UNBLOCK): Transition(StageState.READY, None, _READY_GUARDS),
    (StageState.READY, StageEvent.START): Transition(StageState.RUNNING, AgentAction.RUN, _READY_GUARDS),
    (StageState.RUNNING, StageEvent.SUCCEED): Transition(StageState.AWAITING_FEEDBACK, None, frozenset({Guard.OUTPUT})),
    (StageState.RUNNING, StageEvent.FAIL): Transition(StageState.FAILED, None, frozenset()),
    (StageState.AWAITING_FEEDBACK, StageEvent.FEEDBACK): Transition(StageState.READY, AgentAction.FEEDBACK, _READY_GUARDS),
    (StageState.AWAITING_DECISION, StageEvent.FEEDBACK): Transition(StageState.READY, AgentAction.FEEDBACK, _READY_GUARDS),
    (StageState.AWAITING_FEEDBACK, StageEvent.REQUEST_DECISION): Transition(StageState.AWAITING_DECISION, AgentAction.FEEDBACK, _FINAL_GUARDS),
    (StageState.AWAITING_DECISION, StageEvent.FINALIZE): Transition(StageState.COMPLETED, AgentAction.FINALIZE, _FINAL_GUARDS),
    (StageState.FAILED, StageEvent.RETRY): Transition(StageState.READY, AgentAction.RUN, _READY_GUARDS),
    (StageState.STALE, StageEvent.REVALIDATE): Transition(StageState.READY, AgentAction.RUN, _READY_GUARDS),
}
for _state in StageState:
    if _state not in {StageState.STALE, StageState.CANCELLED}:
        TRANSITIONS[(_state, StageEvent.INVALIDATE)] = Transition(StageState.STALE, None, frozenset({Guard.INPUTS_CHANGED}))
    if _state not in {StageState.COMPLETED, StageState.CANCELLED}:
        TRANSITIONS[(_state, StageEvent.CANCEL)] = Transition(StageState.CANCELLED, ProjectAction.CANCEL_INSTANCE, frozenset())


TRANSITIONS = MappingProxyType(TRANSITIONS)


def transition_stage(stage, event, *, expected_revision, guards=frozenset(), context=None,
                     system=False, attempt_id=None, artifact=None, next_input_digest=None):
    """Validate a proposed transition. Persistence/CAS/transactions are KP-05/07.

    `system` and `guards` are facts resolved by trusted server code, not request
    fields. This pure reference does not authenticate callbacks or serialize writes.
    """
    _enum(event, StageEvent)
    _revision(expected_revision)
    _bool(system)
    _set(guards, Guard)
    if stage.revision != expected_revision:
        raise ContractError('revision_conflict')
    rule = TRANSITIONS.get((stage.state, event))
    if rule is None:
        raise ContractError('transition_not_allowed')
    if rule.action is None:
        if not system:
            raise ContractError('system_event_required')
    else:
        if system:
            raise ContractError('human_action_required')
        if not isinstance(context, ActionContext):
            raise ContractError('action_context_required')
        if (context.agent.scope != stage.scope or context.agent.agent_id != stage.agent_id or
                context.agent.workflow_id != stage.workflow_id):
            raise ContractError('permission_scope_mismatch')
        if isinstance(rule.action, ProjectAction):
            permission = project_permission(context.actor, context.membership, stage.scope, rule.action)
        else:
            permission = agent_permission(context.actor, context.membership, context.agent, rule.action,
                                          context.grants, context.native_permissions)
        if not permission.allowed:
            raise ContractError('permission_required')
    if not rule.guards <= guards:
        raise ContractError('transition_guard_missing')
    next_digest = stage.input_digest
    if event in {StageEvent.FEEDBACK, StageEvent.REVALIDATE}:
        _digest(next_input_digest)
        if next_input_digest == stage.input_digest:
            raise ContractError('new_input_binding_required')
        next_digest = next_input_digest
    next_attempt = None
    if event == StageEvent.START:
        _uuid(attempt_id)
        next_attempt = attempt_id
    elif event in {StageEvent.SUCCEED, StageEvent.FAIL}:
        if attempt_id != stage.active_attempt_id:
            raise ContractError('attempt_mismatch')
    if event == StageEvent.FINALIZE:
        if context.actor.account_id != stage.finalizer_id:
            raise ContractError('designated_finalizer_required')
        membership = context.membership
        if not _member(context.actor, membership, stage.scope):
            raise ContractError('active_project_membership_required')
        if stage.decision_role and stage.decision_role not in membership.business_roles:
            raise ContractError('decision_role_required')
        if (not isinstance(artifact, Artifact) or artifact.version.scope != stage.scope or
                artifact.stage_id != stage.stage_id or artifact.input_digest != stage.input_digest):
            raise ContractError('current_stage_artifact_required')
    return replace(stage, state=rule.target, revision=stage.revision + 1,
                   active_attempt_id=next_attempt, input_digest=next_digest)
