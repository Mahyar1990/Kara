import { del, get, post, put } from '@/service/base'
export { gitlabError as sourceError } from './company-gitlab'
export type Repository = { id: string; name: string; url: string; branch: string; revision: number; can_edit: boolean }
export type Component = { key: string; path: string; repository_id: string; connection_id: string; repository_revision?: number; connection_revision?: number; url?: string; branch?: string }
export type Document = { path: string; content: string }
export type Workspace = { id: string; name: string; revision: number; components: Component[]; documents: Document[] }
export type Device = { id: string; name: string; revoked_at: string | null; last_seen_at: string | null }
export type Job = { id: string; source_workspace_id: string; device_id: string; state: string; created_at: string; snapshot_revision: number; result: null | { error?: string; local_directory?: string; components?: { key: string; commit: string }[] } }
const base = (id: string) => `/company/projects/${id}/source-code`
const devices = '/company/me/source-runners'
export const sourceApi = {
  list: (id: string) => get<{ repositories: Repository[]; workspaces: Workspace[]; jobs: Job[] }>(base(id)),
  saveRepo: (id: string, value: Repository | null, body: { name: string; url: string; branch: string; expected_revision: number }) => value ? put<Repository>(`${base(id)}/repositories/${value.id}`, { body }) : post<Repository>(`${base(id)}/repositories`, { body }),
  saveWorkspace: (id: string, value: Workspace | null, body: { name: string; components: Component[]; documents: Document[]; expected_revision: number }) => value ? put<Workspace>(`${base(id)}/workspaces/${value.id}`, { body }) : post<Workspace>(`${base(id)}/workspaces`, { body }),
  remove: (id: string, kind: 'repositories' | 'workspaces', value: Repository | Workspace) => del(`${base(id)}/${kind}/${value.id}`, { body: { expected_revision: value.revision } }),
  prepare: (id: string, value: Workspace, deviceId: string, actionKey: string) => post<Job>(`${base(id)}/workspaces/${value.id}/prepare`, { body: { device_id: deviceId, expected_revision: value.revision, action_key: actionKey } }),
  cancel: (id: string, jobId: string) => post(`${base(id)}/jobs/${jobId}/cancel`),
  devices: () => get<{ data: Device[] }>(devices),
  pairing: (name: string) => post<{ code: string; expires_at: string }>(`${devices}/pairing`, { body: { name } }),
  revoke: (id: string) => post(`${devices}/${id}/revoke`),
  download: () => get<{ filename: string; content: string }>(`${devices}/download`),
}
