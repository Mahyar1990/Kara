import type { AppRedirectionTarget } from '@/utils/app-redirection'
import { del, get, patch, post, put } from '@/service/base'

export type CompanyProject = {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  workspace_id: string | null
  owner: { id: string; name: string; email: string } | null
  role: string | null
  can_manage_members: boolean
  can_edit: boolean
  is_product_owner: boolean
}
export type CompanyContext = { is_product_owner: boolean; is_product_admin: boolean; product_owner_id: string; root_workspace_id: string; current_project: CompanyProject | null; can_manage_members: boolean }
export type ProjectApp = {
  id: string
  name: string
  description: string
  mode: AppRedirectionTarget['mode']
  project: Pick<CompanyProject, 'id' | 'name'> | null
}
export type ProjectAppPage = { data: ProjectApp[]; total: number; page: number; has_more: boolean }
export type ResourceKind = 'all' | 'workflow' | 'agent' | 'other'
const base = '/company/projects'

export type BusinessRole = 'po' | 'tl' | 'designer' | 'developer' | 'qc'
export type MemberBusinessRoles = {
  project_id: string
  workspace_id: string
  account_id: string
  membership_id: string
  revision: number
  roles: BusinessRole[]
}

export const teamApi = {
  list: (projectId: string) => get<{ data: MemberBusinessRoles[] }>(`${base}/${projectId}/team/members`),
  replace: (projectId: string, accountId: string, body: { roles: BusinessRole[]; expected_revision: number; expected_membership_id: string }, actionKey: string) => put<MemberBusinessRoles>(`${base}/${projectId}/team/members/${accountId}/roles`, { body, headers: { 'Idempotency-Key': actionKey } }),
}

// These company endpoints have no upstream generated SDK contract.
export const projectApi = {
  memberCandidates: (id: string) => get<{ data: { id: string; name: string; email: string }[]; roles: { id: string; name: string }[] }>(`${base}/${id}/members/candidates`),
  addMember: (id: string, body: { account_id: string; role: string }) => post(`${base}/${id}/members`, { body }),
  list: () => get<{ data: CompanyProject[]; is_product_owner: boolean; can_create_projects: boolean }>(base),
  context: () => get<CompanyContext>('/company/context'),
  owners: () => get<{ data: { id: string; name: string; email: string }[] }>(`${base}/owners`),
  setOwner: (id: string, owner_id: string) => put<CompanyProject>(`${base}/${id}/owner`, { body: { owner_id } }),
  enter: (id: string) => post(`${base}/${id}/enter`),
  detail: (id: string) => get<CompanyProject>(`${base}/${id}`),
  create: (body: { name: string; description: string; owner_id?: string }) => post<CompanyProject>(base, { body }),
  update: (id: string, body: { name: string; description: string }) => patch<CompanyProject>(`${base}/${id}`, { body }),
  apps: (id: string, kind: ResourceKind, page: number) => get<ProjectAppPage>(`${base}/${id}/apps`, { params: { kind, page } }),
  resources: (name: string, page: number) => get<ProjectAppPage>(`${base}/resources`, { params: { name, page } }),
  createApp: (id: string, body: { name: string; description: string; mode: string }) => post<ProjectApp>(`${base}/${id}/apps`, { body }),
  assign: (id: string, appId: string) => put(`${base}/${id}/apps/${appId}`),
  remove: (id: string, appId: string) => del(`${base}/${id}/apps/${appId}`),
}
