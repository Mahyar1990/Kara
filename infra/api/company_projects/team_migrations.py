"""Additive PostgreSQL migrations, separate from the legacy schema-1 ledger."""
import hashlib

import sqlalchemy as sa


ROLE_SCHEMA = """
ALTER TABLE company_project_workspaces ADD CONSTRAINT company_team_scope_unique UNIQUE (project_id, workspace_id);
CREATE TABLE company_team_member_policies (
    project_id uuid NOT NULL, workspace_id uuid NOT NULL, account_id uuid NOT NULL,
    membership_id uuid NOT NULL, revision integer NOT NULL CHECK (revision > 0),
    PRIMARY KEY (project_id, workspace_id, account_id),
    FOREIGN KEY (project_id, workspace_id) REFERENCES company_project_workspaces(project_id, workspace_id),
    FOREIGN KEY (workspace_id, account_id) REFERENCES tenant_account_joins(tenant_id, account_id) ON DELETE CASCADE
);
CREATE TABLE company_team_roles (
    project_id uuid NOT NULL, workspace_id uuid NOT NULL, account_id uuid NOT NULL,
    business_role varchar(16) NOT NULL CHECK (business_role IN ('po', 'tl', 'designer', 'developer', 'qc')),
    assigned_by uuid NOT NULL, assigned_at timestamptz NOT NULL,
    PRIMARY KEY (project_id, workspace_id, account_id, business_role),
    FOREIGN KEY (project_id, workspace_id, account_id)
        REFERENCES company_team_member_policies(project_id, workspace_id, account_id) ON DELETE CASCADE
);
CREATE TABLE company_team_audit_events (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    actor_id uuid NOT NULL, subject_id uuid NOT NULL, membership_id uuid NOT NULL,
    event_type varchar(80) NOT NULL, occurred_at timestamptz NOT NULL,
    correlation_id uuid NOT NULL, request_digest varchar(64) NOT NULL,
    result jsonb NOT NULL,
    UNIQUE (project_id, workspace_id, actor_id, correlation_id),
    FOREIGN KEY (project_id, workspace_id) REFERENCES company_project_workspaces(project_id, workspace_id)
);
"""
AGENT_SCHEMA = """
CREATE TABLE company_team_agents (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    app_id uuid NOT NULL UNIQUE REFERENCES apps(id), workflow_id uuid NOT NULL REFERENCES workflows(id),
    name varchar(120) NOT NULL, description varchar(2000) NOT NULL,
    workflow_digest varchar(64) NOT NULL, input_contract jsonb NOT NULL, output_contract jsonb NOT NULL,
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    acl_revision integer NOT NULL DEFAULT 1 CHECK (acl_revision > 0),
    archived boolean NOT NULL DEFAULT false, created_by uuid NOT NULL, created_at timestamptz NOT NULL,
    UNIQUE (id, project_id, workspace_id),
    FOREIGN KEY (project_id, workspace_id) REFERENCES company_project_workspaces(project_id, workspace_id)
);
CREATE TABLE company_team_agent_grants (
    agent_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    account_id uuid NOT NULL, membership_id uuid NOT NULL REFERENCES tenant_account_joins(id) ON DELETE CASCADE,
    action varchar(32) NOT NULL CHECK (action IN ('view','run','feedback','finalize','edit_definition','publish_definition')),
    granted_by uuid NOT NULL, granted_at timestamptz NOT NULL,
    PRIMARY KEY (agent_id, account_id, action),
    FOREIGN KEY (agent_id, project_id, workspace_id) REFERENCES company_team_agents(id, project_id, workspace_id),
    FOREIGN KEY (workspace_id, account_id) REFERENCES tenant_account_joins(tenant_id, account_id) ON DELETE CASCADE
);
CREATE TABLE company_team_agent_events (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    actor_id uuid NOT NULL, correlation_id uuid NOT NULL, request_digest varchar(64) NOT NULL,
    event_type varchar(80) NOT NULL, result jsonb NOT NULL, occurred_at timestamptz NOT NULL,
    UNIQUE (project_id, workspace_id, actor_id, correlation_id),
    FOREIGN KEY (project_id, workspace_id) REFERENCES company_project_workspaces(project_id, workspace_id)
);
CREATE TABLE company_team_agent_attempts (
    id uuid PRIMARY KEY, agent_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    actor_id uuid NOT NULL, membership_id uuid NOT NULL, workflow_id uuid NOT NULL REFERENCES workflows(id),
    inputs jsonb NOT NULL, request_digest varchar(64) NOT NULL, correlation_id uuid NOT NULL,
    status varchar(20) NOT NULL CHECK (status IN ('pending','running','succeeded','failed','blocked','interrupted')),
    result jsonb, created_at timestamptz NOT NULL, started_at timestamptz, finished_at timestamptz,
    UNIQUE (project_id, workspace_id, actor_id, correlation_id),
    FOREIGN KEY (agent_id, project_id, workspace_id) REFERENCES company_team_agents(id, project_id, workspace_id)
);
CREATE INDEX company_team_agent_pending_idx ON company_team_agent_attempts(status, created_at);
"""
FLOW_SCHEMA = """
CREATE TABLE company_team_flows (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    name varchar(120) NOT NULL, name_key varchar(360) NOT NULL, description varchar(2000) NOT NULL,
    revision integer NOT NULL CHECK (revision > 0), draft_stages jsonb NOT NULL,
    current_version_id uuid, archived boolean NOT NULL DEFAULT false,
    created_by uuid NOT NULL, created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    UNIQUE (id, project_id, workspace_id), UNIQUE (project_id, workspace_id, name_key),
    FOREIGN KEY (project_id, workspace_id) REFERENCES company_project_workspaces(project_id, workspace_id)
);
-- kara-statement
CREATE TABLE company_team_flow_versions (
    id uuid PRIMARY KEY, flow_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0), source_revision integer NOT NULL CHECK (source_revision > 0),
    contract_version integer NOT NULL CHECK (contract_version = 1), digest varchar(64) NOT NULL,
    name varchar(120) NOT NULL, description varchar(2000) NOT NULL, stage_bindings jsonb NOT NULL,
    published_by uuid NOT NULL, published_at timestamptz NOT NULL,
    UNIQUE (flow_id, version), UNIQUE (id, flow_id, project_id, workspace_id),
    FOREIGN KEY (flow_id, project_id, workspace_id) REFERENCES company_team_flows(id, project_id, workspace_id)
);
-- kara-statement
ALTER TABLE company_team_flows ADD CONSTRAINT company_team_flow_current_version_fk
    FOREIGN KEY (current_version_id, id, project_id, workspace_id)
    REFERENCES company_team_flow_versions(id, flow_id, project_id, workspace_id);
-- kara-statement
CREATE FUNCTION company_team_keep_flow_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Published team flow versions are immutable';
END;
$$;
-- kara-statement
CREATE TRIGGER company_team_flow_version_immutable BEFORE UPDATE OR DELETE ON company_team_flow_versions
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_flow_version();
"""
REQUEST_SCHEMA = """
CREATE TABLE company_team_requests (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision > 0), current_revision_id uuid, current_decision_id uuid,
    created_by uuid NOT NULL, created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    UNIQUE (id, project_id, workspace_id),
    FOREIGN KEY (project_id, workspace_id) REFERENCES company_project_workspaces(project_id, workspace_id)
);
-- kara-statement
CREATE TABLE company_team_request_revisions (
    id uuid PRIMARY KEY, request_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0), title varchar(200) NOT NULL, content text NOT NULL,
    origin varchar(16) NOT NULL CHECK (origin = 'manual'), attachment_ids jsonb NOT NULL,
    digest varchar(64) NOT NULL, author_id uuid NOT NULL, membership_id uuid NOT NULL, created_at timestamptz NOT NULL,
    UNIQUE (request_id, version), UNIQUE (id, request_id, project_id, workspace_id),
    FOREIGN KEY (request_id, project_id, workspace_id) REFERENCES company_team_requests(id, project_id, workspace_id)
);
-- kara-statement
CREATE TABLE company_team_request_attachments (
    id uuid PRIMARY KEY, request_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    name varchar(200) NOT NULL, size integer NOT NULL CHECK (size > 0 AND size <= 2097152),
    digest varchar(64) NOT NULL, content bytea NOT NULL, created_by uuid NOT NULL, created_at timestamptz NOT NULL,
    CHECK (octet_length(content) = size),
    FOREIGN KEY (request_id, project_id, workspace_id) REFERENCES company_team_requests(id, project_id, workspace_id)
);
-- kara-statement
CREATE TABLE company_team_intake_decisions (
    id uuid PRIMARY KEY, request_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    request_revision_id uuid NOT NULL, request_digest varchar(64) NOT NULL,
    flow_id uuid, flow_version_id uuid, flow_digest varchar(64),
    outcome varchar(16) NOT NULL CHECK (outcome IN ('approved','rejected','deferred','revoked')),
    mode varchar(8) NOT NULL CHECK (mode = 'real'), reason varchar(2000) NOT NULL,
    actor_id uuid NOT NULL, membership_id uuid NOT NULL, created_at timestamptz NOT NULL, expires_at timestamptz,
    revokes_id uuid,
    UNIQUE (id, request_id, project_id, workspace_id),
    CHECK ((flow_id IS NULL AND flow_version_id IS NULL AND flow_digest IS NULL) OR
           (flow_id IS NOT NULL AND flow_version_id IS NOT NULL AND flow_digest IS NOT NULL)),
    CHECK (outcome <> 'approved' OR flow_version_id IS NOT NULL),
    CHECK ((outcome = 'revoked') = (revokes_id IS NOT NULL)),
    FOREIGN KEY (request_revision_id, request_id, project_id, workspace_id)
        REFERENCES company_team_request_revisions(id, request_id, project_id, workspace_id),
    FOREIGN KEY (flow_version_id, flow_id, project_id, workspace_id)
        REFERENCES company_team_flow_versions(id, flow_id, project_id, workspace_id),
    FOREIGN KEY (revokes_id, request_id, project_id, workspace_id)
        REFERENCES company_team_intake_decisions(id, request_id, project_id, workspace_id)
);
-- kara-statement
ALTER TABLE company_team_requests ADD CONSTRAINT company_team_request_current_revision_fk
    FOREIGN KEY (current_revision_id, id, project_id, workspace_id)
    REFERENCES company_team_request_revisions(id, request_id, project_id, workspace_id);
-- kara-statement
ALTER TABLE company_team_requests ADD CONSTRAINT company_team_request_current_decision_fk
    FOREIGN KEY (current_decision_id, id, project_id, workspace_id)
    REFERENCES company_team_intake_decisions(id, request_id, project_id, workspace_id);
-- kara-statement
CREATE FUNCTION company_team_keep_request_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Team request history is immutable';
END;
$$;
-- kara-statement
CREATE TRIGGER company_team_request_revision_immutable BEFORE UPDATE OR DELETE ON company_team_request_revisions
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_request_record();
-- kara-statement
CREATE TRIGGER company_team_request_attachment_immutable BEFORE UPDATE OR DELETE ON company_team_request_attachments
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_request_record();
-- kara-statement
CREATE TRIGGER company_team_intake_decision_immutable BEFORE UPDATE OR DELETE ON company_team_intake_decisions
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_request_record();
"""
STAGE_SCHEMA = """
CREATE TABLE company_team_instances (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL, request_id uuid NOT NULL,
    request_revision_id uuid NOT NULL, intake_decision_id uuid NOT NULL UNIQUE,
    flow_id uuid NOT NULL, flow_version_id uuid NOT NULL, request_digest varchar(64) NOT NULL,
    flow_digest varchar(64) NOT NULL, created_by uuid NOT NULL, created_at timestamptz NOT NULL,
    UNIQUE (id, project_id, workspace_id),
    FOREIGN KEY (request_revision_id, request_id, project_id, workspace_id)
        REFERENCES company_team_request_revisions(id, request_id, project_id, workspace_id),
    FOREIGN KEY (intake_decision_id, request_id, project_id, workspace_id)
        REFERENCES company_team_intake_decisions(id, request_id, project_id, workspace_id),
    FOREIGN KEY (flow_version_id, flow_id, project_id, workspace_id)
        REFERENCES company_team_flow_versions(id, flow_id, project_id, workspace_id)
);
-- kara-statement
CREATE TABLE company_team_stages (
    id uuid PRIMARY KEY, instance_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0), step_key varchar(40) NOT NULL, binding jsonb NOT NULL,
    revision integer NOT NULL CHECK (revision > 0), round integer NOT NULL CHECK (round > 0),
    state varchar(24) NOT NULL CHECK (state IN ('blocked','ready','running','awaiting_feedback','awaiting_decision','completed','failed','stale')),
    inputs jsonb, dependencies jsonb, input_digest varchar(64), active_attempt_id uuid, selected_artifact_id uuid,
    updated_at timestamptz NOT NULL,
    CHECK ((state = 'running') = (active_attempt_id IS NOT NULL)),
    UNIQUE (instance_id, ordinal), UNIQUE (instance_id, step_key), UNIQUE (id, project_id, workspace_id),
    FOREIGN KEY (instance_id, project_id, workspace_id) REFERENCES company_team_instances(id, project_id, workspace_id)
);
-- kara-statement
CREATE TABLE company_team_stage_attempts (
    attempt_id uuid PRIMARY KEY REFERENCES company_team_agent_attempts(id), stage_id uuid NOT NULL,
    project_id uuid NOT NULL, workspace_id uuid NOT NULL, round integer NOT NULL, input_digest varchar(64) NOT NULL,
    created_at timestamptz NOT NULL, UNIQUE (attempt_id, stage_id, project_id, workspace_id),
    FOREIGN KEY (stage_id, project_id, workspace_id) REFERENCES company_team_stages(id, project_id, workspace_id)
);
-- kara-statement
CREATE TABLE company_team_artifacts (
    id uuid PRIMARY KEY, stage_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0), round integer NOT NULL CHECK (round > 0),
    input_digest varchar(64) NOT NULL, digest varchar(64) NOT NULL, content jsonb NOT NULL,
    kind varchar(16) NOT NULL CHECK (kind IN ('workflow','human')), attempt_id uuid NOT NULL,
    parent_id uuid, author_id uuid NOT NULL, membership_id uuid NOT NULL, reason varchar(2000) NOT NULL,
    created_at timestamptz NOT NULL, UNIQUE (stage_id, version), UNIQUE (id, stage_id, project_id, workspace_id),
    FOREIGN KEY (stage_id, project_id, workspace_id) REFERENCES company_team_stages(id, project_id, workspace_id),
    FOREIGN KEY (attempt_id, stage_id, project_id, workspace_id)
        REFERENCES company_team_stage_attempts(attempt_id, stage_id, project_id, workspace_id),
    FOREIGN KEY (parent_id, stage_id, project_id, workspace_id) REFERENCES company_team_artifacts(id, stage_id, project_id, workspace_id)
);
-- kara-statement
CREATE TABLE company_team_feedback (
    id uuid PRIMARY KEY, stage_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    base_revision integer NOT NULL, round integer NOT NULL, parent_artifact_id uuid,
    message varchar(8000) NOT NULL, inputs jsonb NOT NULL, input_digest varchar(64) NOT NULL,
    author_id uuid NOT NULL, membership_id uuid NOT NULL, created_at timestamptz NOT NULL,
    UNIQUE (stage_id, round),
    FOREIGN KEY (stage_id, project_id, workspace_id) REFERENCES company_team_stages(id, project_id, workspace_id),
    FOREIGN KEY (parent_artifact_id, stage_id, project_id, workspace_id) REFERENCES company_team_artifacts(id, stage_id, project_id, workspace_id)
);
-- kara-statement
CREATE TABLE company_team_stage_decisions (
    id uuid PRIMARY KEY, stage_id uuid NOT NULL, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    base_revision integer NOT NULL, artifact_id uuid NOT NULL, input_digest varchar(64) NOT NULL,
    actor_id uuid NOT NULL, membership_id uuid NOT NULL, reason varchar(2000) NOT NULL,
    created_at timestamptz NOT NULL, UNIQUE (stage_id, base_revision),
    FOREIGN KEY (artifact_id, stage_id, project_id, workspace_id) REFERENCES company_team_artifacts(id, stage_id, project_id, workspace_id)
);
-- kara-statement
ALTER TABLE company_team_stages ADD CONSTRAINT company_team_stage_active_attempt_fk
    FOREIGN KEY (active_attempt_id, id, project_id, workspace_id)
    REFERENCES company_team_stage_attempts(attempt_id, stage_id, project_id, workspace_id);
-- kara-statement
ALTER TABLE company_team_stages ADD CONSTRAINT company_team_stage_selected_artifact_fk
    FOREIGN KEY (selected_artifact_id, id, project_id, workspace_id)
    REFERENCES company_team_artifacts(id, stage_id, project_id, workspace_id);
-- kara-statement
CREATE TRIGGER company_team_instance_immutable BEFORE UPDATE OR DELETE ON company_team_instances
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_request_record();
-- kara-statement
CREATE TRIGGER company_team_stage_attempt_immutable BEFORE UPDATE OR DELETE ON company_team_stage_attempts
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_request_record();
-- kara-statement
CREATE TRIGGER company_team_artifact_immutable BEFORE UPDATE OR DELETE ON company_team_artifacts
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_request_record();
-- kara-statement
CREATE TRIGGER company_team_feedback_immutable BEFORE UPDATE OR DELETE ON company_team_feedback
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_request_record();
-- kara-statement
CREATE TRIGGER company_team_stage_decision_immutable BEFORE UPDATE OR DELETE ON company_team_stage_decisions
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_request_record();
"""
RECOVERY_SCHEMA = """
ALTER TABLE company_team_stages DROP CONSTRAINT company_team_stages_state_check;
-- kara-statement
ALTER TABLE company_team_stages ADD CONSTRAINT company_team_stages_state_check
    CHECK (state IN ('blocked','ready','running','awaiting_feedback','awaiting_decision','completed','failed','stale','cancelled'));
-- kara-statement
ALTER TABLE company_team_stages ADD COLUMN assignment jsonb,
    ADD COLUMN retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    ADD COLUMN feedback_floor integer NOT NULL DEFAULT 1 CHECK (feedback_floor > 0);
-- kara-statement
CREATE TABLE company_team_cancellations (
    instance_id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    actor_id uuid NOT NULL, membership_id uuid NOT NULL, reason varchar(2000) NOT NULL,
    created_at timestamptz NOT NULL,
    FOREIGN KEY (instance_id, project_id, workspace_id) REFERENCES company_team_instances(id, project_id, workspace_id)
);
-- kara-statement
CREATE TRIGGER company_team_cancellation_immutable BEFORE UPDATE OR DELETE ON company_team_cancellations
    FOR EACH ROW EXECUTE FUNCTION company_team_keep_request_record();
"""
JIRA_SCHEMA = """
ALTER TABLE company_team_request_revisions DROP CONSTRAINT company_team_request_revisions_origin_check;
-- kara-statement
ALTER TABLE company_team_request_revisions ADD CONSTRAINT company_team_request_revisions_origin_check
    CHECK (origin IN ('manual', 'jira'));
-- kara-statement
CREATE TABLE company_team_jira_sources (
    project_id uuid NOT NULL, workspace_id uuid NOT NULL, base_url varchar(512) NOT NULL,
    issue_id varchar(64) NOT NULL, request_id uuid NOT NULL UNIQUE,
    source_updated_at timestamptz NOT NULL, snapshot jsonb NOT NULL,
    applied_digest varchar(64) NOT NULL, needs_review boolean NOT NULL DEFAULT false,
    last_run_id uuid, last_seen_at timestamptz NOT NULL,
    PRIMARY KEY (project_id, workspace_id, base_url, issue_id),
    FOREIGN KEY (request_id, project_id, workspace_id)
        REFERENCES company_team_requests(id, project_id, workspace_id)
);
"""
SHARED_AGENT_APP_SCHEMA = """
ALTER TABLE company_team_agents DROP CONSTRAINT company_team_agents_app_id_key;
CREATE INDEX company_team_agents_app_idx ON company_team_agents(app_id);
"""
PERSONAL_JIRA_SCHEMA = """
CREATE TABLE company_user_jira_connections (
    id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name varchar(120) NOT NULL, base_url varchar(512) NOT NULL, encrypted_token text NOT NULL,
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    UNIQUE (account_id, name)
);
"""
MIGRATIONS = (('001_team_roles', ROLE_SCHEMA), ('002_team_agents', AGENT_SCHEMA), ('003_team_flows', FLOW_SCHEMA),
              ('004_team_requests', REQUEST_SCHEMA), ('005_team_stages', STAGE_SCHEMA), ('006_team_recovery', RECOVERY_SCHEMA),
              ('007_jira_intake', JIRA_SCHEMA), ('008_shared_agent_apps', SHARED_AGENT_APP_SCHEMA),
              ('009_personal_jira_connections', PERSONAL_JIRA_SCHEMA))


def checksum(sql):
    return hashlib.sha256(sql.encode('utf-8')).hexdigest()


def migrate(engine):
    if engine.dialect.name != 'postgresql':
        raise RuntimeError('Team migrations require PostgreSQL')
    with engine.begin() as connection:
        connection.execute(sa.text('SELECT pg_advisory_xact_lock(210610003)'))
        versions = set(connection.scalars(sa.text('SELECT version FROM company_project_schema')))
        if versions != {1}:
            raise RuntimeError('Unsupported legacy project schema')
        connection.execute(sa.text('''CREATE TABLE IF NOT EXISTS company_team_migrations (
            migration_id varchar(80) PRIMARY KEY, checksum varchar(64) NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)'''))
        applied = list(connection.execute(sa.text(
            'SELECT migration_id, checksum FROM company_team_migrations ORDER BY migration_id')))
        expected = [(name, checksum(sql)) for name, sql in MIGRATIONS]
        if applied != expected[:len(applied)]:
            raise RuntimeError('Unknown or changed team migration; refusing schema drift')
        for name, sql in MIGRATIONS[len(applied):]:
            # Each statement and its marker share this transaction, including DDL.
            # Explicit boundaries allow trigger bodies containing semicolons;
            # the existing 001/002 SQL and their checksums remain unchanged.
            separator = '\n-- kara-statement\n' if '\n-- kara-statement\n' in sql else ';'
            for statement in sql.split(separator):
                if statement.strip():
                    connection.execute(sa.text(statement))
            connection.execute(sa.text('INSERT INTO company_team_migrations (migration_id, checksum) VALUES (:name, :checksum)'),
                               dict(name=name, checksum=checksum(sql)))
