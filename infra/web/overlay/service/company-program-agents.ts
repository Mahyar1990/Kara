import { get, post } from '@/service/base'
import type { AgentInput } from './company-agents'

export type RolePreview = { source_digest: string; name: string; version: number; inputs: AgentInput[]; prompt: string; knowledge: string[]; skills: { name: string; version?: number }[] }
export type ProgramRoleNode = { id: string; name: string; role: { name: string; snapshot_version: number } | null; variables: { value: string; label: string }[]; task: string }
export type RoleProgram = { id: string; name: string; hash: string; nodes: ProgramRoleNode[] }
const base = (project: string) => `/company/projects/${project}/program-agents`
const headers = (key: string) => ({ 'Idempotency-Key': key })
export const programAgentApi = {
  catalog: (project: string) => get<{ sources: { id: string; name: string; snapshot_id: string | null; reason: string }[]; programs: { id: string; name: string }[] }>(base(project)),
  preview: (project: string, source: string, snapshot: string) => get<RolePreview>(`${base(project)}/sources/${source}`, { params: { snapshot_id: snapshot } }),
  detail: (project: string, app: string) => get<RoleProgram>(`${base(project)}/programs/${app}`),
  create: (project: string, body: { name: string; source_id: string; snapshot_id: string; source_digest: string }, key: string) => post<{ app_id: string; name: string }>(base(project), { body, headers: headers(key) }),
  attach: (project: string, app: string, node: string, body: { draft_hash: string; source_id: string; snapshot_id: string; source_digest: string; bindings: Record<string, string> }, key: string) => post(`${base(project)}/programs/${app}/nodes/${node}`, { body, headers: headers(key) }),
  detach: (project: string, app: string, node: string, hash: string, key: string) => post(`${base(project)}/programs/${app}/nodes/${node}/detach`, { body: { draft_hash: hash }, headers: headers(key) }),
}
