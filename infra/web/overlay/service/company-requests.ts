import { API_PREFIX } from '@/config'
import { get, post } from '@/service/base'

export type RequestAttachment = { id: string; name: string; size: number; digest: string }
export type RequestRevision = { id: string; version: number; title: string; content: string; origin: 'manual' | 'jira'; digest: string; author_id: string; created_at: string; attachment_ids: string[]; attachments: RequestAttachment[] }
export type IntakeDecision = { id: string; outcome: 'approved' | 'rejected' | 'deferred' | 'revoked'; reason: string; actor_id: string; membership_id: string; request_revision_id: string; request_digest: string; flow_id: string | null; flow_version_id: string | null; flow_digest: string | null; expires_at: string | null; created_at: string; revokes_id: string | null }
export type JiraSource = { base_url: string; issue_id: string; key: string; status: string | null; priority: string | null; assignee: string | null; updated_at: string; last_seen_at: string; needs_review: boolean; source_title?: string; source_content?: string | null; last_run_id?: string | null }
export type TeamRequest = { id: string; title: string; version: number; revision: number; current_revision_id: string; current_decision_id: string | null; created_by: string; can_edit: boolean; can_decide: boolean; intake_valid: boolean; state: string; current: RequestRevision; decision: IntakeDecision | null; revisions?: RequestRevision[]; decisions?: IntakeDecision[]; jira: JiraSource | null }
export type JiraRun = { id: string; app_name: string; created_at: string; received_count: number; total: number; start_at: number }
export type JiraImportResult = { data: { request_id: string; key: string; outcome: 'created' | 'updated' | 'metadata_updated' | 'unchanged' | 'older_ignored' | 'needs_review' }[]; received_count: number; total: number; start_at: number; has_more: boolean }
export type RequestDraft = { title: string; content: string; attachment_ids: string[]; expected_revision: number }
export type IntakeDraft = { expected_revision: number; request_revision_id: string; flow_id: string | null; flow_version_id: string | null; outcome: 'approved' | 'rejected' | 'deferred'; reason: string; expires_at: string | null }
const base = (project: string) => `/company/projects/${project}/team/requests`
const headers = (key: string) => ({ 'Idempotency-Key': key })
export const requestApi = {
  list: (project: string) => get<{ can_decide: boolean; can_import_jira: boolean; data: TeamRequest[] }>(base(project)),
  jiraRuns: (project: string) => get<{ data: JiraRun[] }>(`${base(project)}/jira/runs`),
  importJira: (project: string, body: { base_url: string; run_id: string } | { base_url: string; response: unknown }, key: string) => post<JiraImportResult>(`${base(project)}/jira/import`, { body, headers: headers(key) }),
  detail: (project: string, id: string) => get<TeamRequest>(`${base(project)}/${id}`),
  save: (project: string, id: string | null, body: RequestDraft, files: File[], key: string) => {
    const url = id ? `${base(project)}/${id}/revisions` : base(project)
    if (!files.length) return post<TeamRequest>(url, { body, headers: headers(key) })
    const data = new FormData(); data.append('data', JSON.stringify(body)); files.forEach(file => data.append('files', file))
    return post<TeamRequest>(url, { body: data, headers: headers(key) }, { bodyStringify: false, deleteContentType: true })
  },
  decide: (project: string, id: string, body: IntakeDraft, key: string) => post<TeamRequest>(`${base(project)}/${id}/intake-decisions`, { body, headers: headers(key) }),
  revoke: (project: string, value: TeamRequest, reason: string, key: string) => post<TeamRequest>(`${base(project)}/${value.id}/intake-decisions/${value.current_decision_id}/revocations`, { body: { expected_revision: value.revision, reason }, headers: headers(key) }),
  attachment: (project: string, id: string, file: string) => `${API_PREFIX}${base(project)}/${id}/attachments/${file}`,
}
