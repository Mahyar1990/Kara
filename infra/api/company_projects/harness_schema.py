"""Opt-in execution method; old definitions and decisions are never rewritten."""
SQL = """
CREATE TABLE company_harness_policies (
 agent_id uuid NOT NULL REFERENCES company_team_agents(id), workflow_digest varchar(64) NOT NULL,
 revision integer NOT NULL CHECK(revision>0), enabled boolean NOT NULL,
 instructions text NOT NULL, requires_source boolean NOT NULL, updated_by uuid NOT NULL, updated_at timestamptz NOT NULL,
 PRIMARY KEY(agent_id,workflow_digest)
);
CREATE TABLE company_harness_profiles (
 device_id uuid NOT NULL REFERENCES company_source_devices(id), profile_key varchar(64) NOT NULL,
 metadata jsonb NOT NULL, digest varchar(64) NOT NULL, updated_at timestamptz NOT NULL,
 PRIMARY KEY(device_id,profile_key)
);
CREATE TABLE company_harness_attempts (
 attempt_id uuid PRIMARY KEY REFERENCES company_team_agent_attempts(id),
 project_id uuid NOT NULL, workspace_id uuid NOT NULL, account_id uuid NOT NULL REFERENCES accounts(id),
 device_id uuid NOT NULL REFERENCES company_source_devices(id), source_job_id uuid REFERENCES company_source_jobs(id),
 mode varchar(16) NOT NULL CHECK(mode IN ('manual','managed')),
 profile_key varchar(64), profile_digest varchar(64), policy_revision integer NOT NULL,
 snapshot jsonb NOT NULL, snapshot_digest varchar(64) NOT NULL,
 state varchar(20) NOT NULL CHECK(state IN ('pending','running','awaiting_user','succeeded','failed','cancelled','interrupted','blocked')),
 prepared jsonb, result jsonb, completion_digest varchar(64), lease_until timestamptz,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 FOREIGN KEY(project_id,workspace_id) REFERENCES company_project_workspaces(project_id,workspace_id)
);
CREATE INDEX company_harness_device_idx ON company_harness_attempts(device_id,state,created_at);
ALTER TABLE company_team_artifacts DROP CONSTRAINT company_team_artifacts_kind_check;
ALTER TABLE company_team_artifacts ADD CONSTRAINT company_team_artifacts_kind_check CHECK(kind IN ('workflow','human','harness'));
"""
