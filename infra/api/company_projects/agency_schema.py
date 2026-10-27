SQL = """
CREATE TABLE company_agency_adoptions (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, workspace_id uuid NOT NULL,
    actor_id uuid NOT NULL, correlation_id uuid NOT NULL, request_digest varchar(64) NOT NULL,
    template_id varchar(120) NOT NULL, source_commit varchar(40) NOT NULL,
    policy_digest varchar(64) NOT NULL, agent_id uuid REFERENCES agents(id) ON DELETE SET NULL,
    skill_id uuid REFERENCES skills(id) ON DELETE SET NULL, result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, workspace_id, actor_id, correlation_id),
    FOREIGN KEY (project_id, workspace_id) REFERENCES company_project_workspaces(project_id, workspace_id)
);
CREATE INDEX company_agency_adoptions_template_idx ON company_agency_adoptions(workspace_id, template_id, source_commit);
"""
