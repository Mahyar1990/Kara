import { del, get, post, put } from '@/service/base'

export type JiraConnection = { id: string; name: string; base_url: string; token_configured: boolean; revision: number; created_at: string; updated_at: string }
export type JiraConnectionDraft = { name: string; base_url: string; token: string; expected_revision: number }
const base = '/company/me/jira-connections'
export const jiraApi = {
  list: () => get<{ data: JiraConnection[] }>(base),
  save: (id: string | null, body: JiraConnectionDraft) => id ? put<JiraConnection>(`${base}/${id}`, { body }) : post<JiraConnection>(base, { body }),
  remove: (value: JiraConnection) => del<{ deleted: boolean }>(`${base}/${value.id}`, { body: { expected_revision: value.revision } }),
  test: (id: string) => post<{ connected: boolean; message: string }>(`${base}/${id}/test`),
}

export async function jiraError(error: unknown, fallback: string) {
  if (error instanceof Response) {
    try {
      const value: unknown = await error.clone().json()
      if (value && typeof value === 'object' && 'message' in value && typeof value.message === 'string') return value.message
    } catch {}
  }
  return fallback
}
