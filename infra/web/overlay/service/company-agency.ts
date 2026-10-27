import { get, post } from '@/service/base'

export type AgencyTemplate = { id: string; name: string; original_name: string; description: string; category: string; category_label: string; category_original_label: string; recommended: boolean; copy: { agent_id: string; name: string; source_commit: string; policy_digest: string } | null }
export type AgencyCatalog = { data: AgencyTemplate[]; commit: string; policy_digest: string; license: string; can_adopt: boolean; models: { id: string; name: string; model_name: string; provider: string; revision: number; is_default: boolean }[]; datasets: { id: string; name: string }[] }
export type AgencyPreview = { original: string; adapted: string; definition_digest: string; source_url: string; license: string }
export type AgencyCopy = { agent_id: string; skill_id?: string; name: string; created: boolean }
const base = (project: string) => `/company/projects/${project}/agency-agents`
export const agencyApi = {
  list: (project: string) => get<AgencyCatalog>(base(project)),
  preview: (project: string, template: string) => get<AgencyPreview>(`${base(project)}/${template}`),
  copy: (project: string, template: string, body: { name: string; model_connection_id: string; model_revision: number; dataset_id: string | null; definition_digest: string }, key: string) => post<AgencyCopy>(`${base(project)}/${template}/copies`, { body, headers: { 'Idempotency-Key': key } }),
}
