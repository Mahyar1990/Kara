import type { AgentInput } from './company-agents'
import { get, post, put } from '@/service/base'

export type FlowInput = { source: 'request' } | { source: 'constant'; value: unknown } | { source: 'stage'; stage_key: string; output: string }
export type FlowStage = { key: string; title: string; agent_id: string | null; executor_id: string | null; executor_membership_id: string | null; finalizer_id: string | null; finalizer_membership_id: string | null; decision_role: 'po' | 'tl' | null; inputs: Record<string, FlowInput> }
export type FlowBinding = { app_id?: string; app_name?: string; workflow_version?: string; key: string; title: string; agent_id: string; agent_name: string; workflow_id: string; executor: { account_id: string; name: string }; finalizer: { account_id: string; name: string }; decision_role: string | null; inputs: Record<string, FlowInput>; output_contract: string[] }
export type FlowVersion = { id: string; flow_id: string; version: number; source_revision: number; contract_version: number; digest: string; name: string; description: string; stage_bindings: FlowBinding[]; published_by: string; published_at: string }
export type TeamFlow = { id: string; name: string; description: string; revision: number; archived: boolean; current_version_id: string | null; published: FlowVersion | null; draft_stages?: FlowStage[] }
export type FlowOptions = { agents: { id: string; name: string; app_id: string; app_name: string; workflow_version: string | null; workflow_id: string; input_contract: AgentInput[]; output_contract: string[]; runners: string[]; finalizers: string[] }[]; members: { account_id: string; membership_id: string; name: string; roles: string[] }[] }
export type FlowDraft = { name: string; description: string; stages: FlowStage[]; expected_revision: number }
const base = (project: string) => `/company/projects/${project}/team/flows`
const headers = (key: string) => ({ 'Idempotency-Key': key })
export const flowApi = {
  list: (project: string) => get<{ can_edit: boolean; data: TeamFlow[] }>(base(project)),
  options: (project: string) => get<FlowOptions>(`${base(project)}/options`),
  save: (project: string, id: string | null, body: FlowDraft, key: string) => id ? put<TeamFlow>(`${base(project)}/${id}`, { body, headers: headers(key) }) : post<TeamFlow>(base(project), { body, headers: headers(key) }),
  publish: (project: string, id: string, expected_revision: number, key: string) => post<TeamFlow>(`${base(project)}/${id}/publish`, { body: { expected_revision }, headers: headers(key) }),
  remove: (project: string, id: string, expected_revision: number, confirmation_name: string, key: string) => post<{ id: string; deleted: boolean }>(`${base(project)}/${id}/delete`, { body: { expected_revision, confirmation_name }, headers: headers(key) }),
  archive: (project: string, id: string, expected_revision: number, key: string) => post<TeamFlow>(`${base(project)}/${id}/archive`, { body: { expected_revision }, headers: headers(key) }),
  versions: (project: string, id: string) => get<{ data: FlowVersion[] }>(`${base(project)}/${id}/versions`),
}
