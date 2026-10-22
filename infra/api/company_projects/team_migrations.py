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
MIGRATIONS = (('001_team_roles', ROLE_SCHEMA), ('002_team_agents', AGENT_SCHEMA))


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
            for statement in sql.split(';'):
                if statement.strip():
                    connection.execute(sa.text(statement))
            connection.execute(sa.text('INSERT INTO company_team_migrations (migration_id, checksum) VALUES (:name, :checksum)'),
                               dict(name=name, checksum=checksum(sql)))
