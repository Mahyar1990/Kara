import type { Device } from './company-source'
import type { TeamStage } from './company-stages'
import { get, post, put } from '@/service/base'
export type ExecutionChoice = { method: 'harness'; mode: 'manual' | 'managed'; device_id: string; source_job_id: string | null; profile_key: string | null }
export type HarnessPolicy = { policy: { revision: number; enabled: boolean; instructions: string; requires_source: boolean }; compatible: boolean; reason: string | null; can_manage: boolean; output_contract: string[]; workflow_digest: string }
export type HarnessInfo = { device_name?: string; profile_name?: string | null; attempt_id: string; mode: 'manual' | 'managed'; state: string; device_id: string; source_job_id: string | null; profile_key: string | null; snapshot_digest: string; prepared: null | { directory: string }; result: null | { origin?: string; evidence?: unknown; error?: string }; actions?: string[]; can_continue?: boolean }
const base = (project: string, agent: string) => `/company/projects/${project}/team/agents/${agent}`
export const harnessApi = {
  policy: (project: string, agent: string) => get<HarnessPolicy>(`${base(project, agent)}/harness-policy`),
  savePolicy: (project: string, agent: string, body: { expected_revision: number; enabled: boolean; instructions: string; requires_source: boolean }) => put<HarnessPolicy>(`${base(project, agent)}/harness-policy`, { body }),
  profiles: () => get<{ devices: (Device & { harnesses: { key: string; name: string; kind: string; version: string }[] })[] }>('/company/me/source-runners/harnesses'),
  detail: (project: string, agent: string, id: string) => get<HarnessInfo>(`${base(project, agent)}/attempts/${id}/harness`),
  bundle: (project: string, agent: string, id: string) => post<Record<string, unknown>>(`${base(project, agent)}/attempts/${id}/harness/bundle`, { body: {} }),
  cancel: (project: string, agent: string, id: string) => post(`${base(project, agent)}/attempts/${id}/harness/cancel`, { body: {} }),
  submit: (project: string, agent: string, id: string, body: Record<string, unknown>) => post(`${base(project, agent)}/attempts/${id}/harness/submit`, { body }),
  submitStage: (project: string, instance: string, stage: string, body: Record<string, unknown>, key: string) => post<TeamStage>(`/company/projects/${project}/team/instances/${instance}/stages/${stage}/harness-submit`, { body, headers: { 'Idempotency-Key': key } }),
}
