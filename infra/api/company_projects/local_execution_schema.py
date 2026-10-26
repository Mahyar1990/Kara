"""Runner execution ledger; immutable program/agent/flow definitions stay intact."""
SQL = """
CREATE TABLE company_runner_capabilities (
 device_id uuid PRIMARY KEY REFERENCES company_source_devices(id), protocol integer NOT NULL,
 capabilities jsonb NOT NULL, updated_at timestamptz NOT NULL
);
CREATE TABLE company_execution_bindings (
 project_id uuid NOT NULL, workspace_id uuid NOT NULL, account_id uuid NOT NULL REFERENCES accounts(id),
 device_id uuid NOT NULL REFERENCES company_source_devices(id), source_job_id uuid REFERENCES company_source_jobs(id),
 revision integer NOT NULL CHECK(revision>0), updated_at timestamptz NOT NULL,
 PRIMARY KEY(project_id,account_id),
 FOREIGN KEY(project_id,workspace_id) REFERENCES company_project_workspaces(project_id,workspace_id)
);
CREATE TABLE company_local_executions (
 id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
 account_id uuid NOT NULL REFERENCES accounts(id), membership_id uuid NOT NULL,
 device_id uuid REFERENCES company_source_devices(id), source_job_id uuid REFERENCES company_source_jobs(id),
 app_id uuid NOT NULL REFERENCES apps(id), workflow_id uuid NOT NULL REFERENCES workflows(id),
 team_attempt_id uuid UNIQUE REFERENCES company_team_agent_attempts(id), trigger_log_id uuid,
 snapshot jsonb NOT NULL, snapshot_digest varchar(64) NOT NULL, inputs jsonb NOT NULL,
 state varchar(16) NOT NULL CHECK(state IN ('pending','running','succeeded','failed','cancelled','interrupted','blocked')),
 created_at timestamptz NOT NULL, started_at timestamptz, finished_at timestamptz, lease_until timestamptz,
 event_sequence integer NOT NULL DEFAULT 0, result jsonb
);
CREATE INDEX company_local_execution_queue_idx ON company_local_executions(device_id,state,created_at);
CREATE INDEX company_local_execution_actor_idx ON company_local_executions(project_id,account_id,created_at);
CREATE TABLE company_local_execution_events (
 execution_id uuid NOT NULL REFERENCES company_local_executions(id), sequence integer NOT NULL,
 event jsonb NOT NULL, digest varchar(64) NOT NULL, created_at timestamptz NOT NULL,
 PRIMARY KEY(execution_id,sequence)
);
"""

RPC_SQL = """
CREATE TABLE company_local_rpc (
 id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
 account_id uuid NOT NULL REFERENCES accounts(id), membership_id uuid NOT NULL,
 device_id uuid REFERENCES company_source_devices(id), method varchar(64) NOT NULL,
 connection_kind varchar(16), connection_id uuid, connection_revision integer,
 payload jsonb NOT NULL, state varchar(16) NOT NULL CHECK(state IN ('pending','running','succeeded','failed','cancelled','interrupted')),
 created_at timestamptz NOT NULL, started_at timestamptz, finished_at timestamptz,
 lease_until timestamptz, result jsonb
);
CREATE INDEX company_local_rpc_device_idx ON company_local_rpc(device_id,state,created_at);
"""
