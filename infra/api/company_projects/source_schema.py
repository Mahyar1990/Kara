"""Additive source workspace tables; no existing workflow data is altered."""
SQL = """
CREATE TABLE company_source_repositories (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES company_projects(id), workspace_id uuid NOT NULL,
 created_by uuid NOT NULL REFERENCES accounts(id), name varchar(120) NOT NULL,
 url varchar(1024) NOT NULL, branch varchar(200) NOT NULL, revision integer NOT NULL CHECK(revision>0),
 deleted_at timestamptz, created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 FOREIGN KEY(project_id,workspace_id) REFERENCES company_project_workspaces(project_id,workspace_id)
);
CREATE TABLE company_source_workspaces (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES company_projects(id), workspace_id uuid NOT NULL,
 account_id uuid NOT NULL REFERENCES accounts(id), name varchar(120) NOT NULL, definition jsonb NOT NULL,
 revision integer NOT NULL CHECK(revision>0), deleted_at timestamptz,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 FOREIGN KEY(project_id,workspace_id) REFERENCES company_project_workspaces(project_id,workspace_id)
);
CREATE TABLE company_source_pairings (
 id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts(id), name varchar(120) NOT NULL,
 code_hash varchar(64) NOT NULL, expires_at timestamptz NOT NULL, consumed_at timestamptz
);
CREATE TABLE company_source_devices (
 id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts(id), name varchar(120) NOT NULL,
 secret_hash varchar(64) NOT NULL, created_at timestamptz NOT NULL, last_seen_at timestamptz,
 revoked_at timestamptz
);
CREATE TABLE company_source_jobs (
 id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
 account_id uuid NOT NULL REFERENCES accounts(id), source_workspace_id uuid NOT NULL REFERENCES company_source_workspaces(id),
 device_id uuid NOT NULL REFERENCES company_source_devices(id), action_key uuid NOT NULL,
 snapshot jsonb NOT NULL, state varchar(16) NOT NULL CHECK(state IN ('pending','running','succeeded','failed','cancelled','interrupted')),
 created_at timestamptz NOT NULL, started_at timestamptz, finished_at timestamptz, lease_until timestamptz,
 result jsonb, UNIQUE(account_id,action_key),
 FOREIGN KEY(project_id,workspace_id) REFERENCES company_project_workspaces(project_id,workspace_id)
);
CREATE INDEX company_source_job_device_idx ON company_source_jobs(device_id,state,created_at);
CREATE INDEX company_source_workspace_owner_idx ON company_source_workspaces(account_id,project_id);
"""
