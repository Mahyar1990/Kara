import type { ExecutionChoice } from './company-harness'
import { get, post, put } from '@/service/base'

export type AgentAction = 'view' | 'run' | 'feedback' | 'finalize' | 'edit_definition' | 'publish_definition'
export type AgentInput = { variable: string; label: string; type: 'text-input' | 'paragraph' | 'select' | 'number' | 'checkbox'; required: boolean; max_length: number | null; options: string[]; default?: string | number | boolean | null }
type PersonalSkill = { name: string; version?: number }
export type PersonalSource = { id: string; name: string; snapshot_id: string | null; version: number | null; unavailable_reason: string }
export type PersonalPreview = { available: boolean; reason?: string; source_digest?: string; input_contract?: AgentInput[]; output_contract?: string[]; model?: { provider: string; name: string }; skills?: PersonalSkill[]; knowledge?: string[] }
export type TeamAgent = { app_name: string; workflow_version: string | null; personal_source?: { agent_id: string; name: string; snapshot_id: string; snapshot_version: number; model: { provider: string; name: string }; skills: PersonalSkill[] } | null; runtime_model?: { version: number; capabilities: string[] } | null; id: string; name: string; description: string; app_id: string; workflow_id: string; revision: number; acl_revision: number; archived: boolean; actions: AgentAction[]; input_contract: AgentInput[]; output_contract: string[] }
export type AgentSource = { app_id: string; app_name: string; workflow_id: string; version: string; input_contract: AgentInput[]; output_contract: string[] }
export type AgentGrant = { account_id: string; membership_id: string; actions: AgentAction[] }
export type AgentGrants = { agent_id: string; revision: number; grants: AgentGrant[]; members: { account_id: string; membership_id: string; name: string; status: string }[] }
export type AgentAttempt = { id: string; agent_id: string; workflow_id: string; status: 'pending' | 'running' | 'succeeded' | 'failed' | 'blocked' | 'interrupted'; result: { outputs?: Record<string, unknown>; error?: string } | null }
const base = (project: string) => `/company/projects/${project}/team/agents`
const headers = (key: string) => ({ 'Idempotency-Key': key })
export const agentApi = {
  list: (project: string) => get<{ can_manage: boolean; data: TeamAgent[] }>(base(project)),
  sources: (project: string) => get<{ data: AgentSource[] }>(`${base(project)}/sources`),
  personalSources: (project: string) => get<{ data: PersonalSource[] }>(`${base(project)}/personal-sources`),
  personalPreview: (project: string, source: string, snapshot: string) => get<PersonalPreview>(`${base(project)}/personal-sources/${source}?snapshot_id=${encodeURIComponent(snapshot)}`),
  registerPersonal: (project: string, body: { personal_agent_id: string; snapshot_id: string; source_digest: string; name: string; description: string; expected_revision: number }, key: string) => post<TeamAgent>(`${base(project)}/personal-sources`, { body, headers: headers(key) }),
  register: (project: string, body: { app_id: string; workflow_id: string; name: string; description: string; expected_revision: number }, key: string) => post<TeamAgent>(base(project), { body, headers: headers(key) }),
  grants: (project: string, agent: string) => get<AgentGrants>(`${base(project)}/${agent}/grants`),
  replaceGrants: (project: string, agent: string, body: { expected_revision: number; grants: AgentGrant[] }, key: string) => put<AgentGrants>(`${base(project)}/${agent}/grants`, { body, headers: headers(key) }),
  remove: (project: string, id: string, expected_revision: number, confirmation_name: string, key: string) => post<{ id: string; deleted: boolean }>(`${base(project)}/${id}/delete`, { body: { expected_revision, confirmation_name }, headers: headers(key) }),
  archive: (project: string, agent: string, revision: number, key: string) => post<TeamAgent>(`${base(project)}/${agent}/archive`, { body: { expected_revision: revision }, headers: headers(key) }),
  run: (project: string, agent: string, body: { inputs: Record<string, unknown>; expected_revision: number; execution?: ExecutionChoice }, key: string) => post<AgentAttempt>(`${base(project)}/${agent}/attempts`, { body, headers: headers(key) }),
  attempt: (project: string, agent: string, attempt: string) => get<AgentAttempt>(`${base(project)}/${agent}/attempts/${attempt}`),
}
