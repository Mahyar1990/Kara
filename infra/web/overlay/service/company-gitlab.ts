import { del, get, post, put } from '@/service/base'

export type GitLabConnection = { id: string; name: string; base_url: string; token_configured: boolean; revision: number; created_at: string; updated_at: string }
export type GitLabConnectionDraft = { name: string; base_url: string; token: string; expected_revision: number }
const base = '/company/me/gitlab-connections'
export const gitlabApi = {
  list: () => get<{ data: GitLabConnection[] }>(base),
  save: (id: string | null, body: GitLabConnectionDraft) => id ? put<GitLabConnection>(`${base}/${id}`, { body }) : post<GitLabConnection>(base, { body }),
  remove: (value: GitLabConnection) => del<{ deleted: boolean }>(`${base}/${value.id}`, { body: { expected_revision: value.revision } }),
  test: (id: string) => post<{ connected: boolean; message: string }>(`${base}/${id}/test`),
}

export async function gitlabError(error: unknown, fallback: string) {
  if (error instanceof Response) {
    try {
      const value: unknown = await error.clone().json()
      if (value && typeof value === 'object' && 'message' in value && typeof value.message === 'string') return value.message
    } catch {}
  }
  return fallback
}
