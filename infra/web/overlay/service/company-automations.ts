import { get, post, put } from '@/service/base'

export type Schedule = { frequency: 'hourly' | 'daily' | 'weekly' | 'monthly'; time: string; minute: number; weekdays: string[]; day: number }
export type Automation = { id: string; app_id: string; name: string; title: string; type: string; status: string; managed: boolean; published: boolean; can_manage: boolean; can_publish: boolean; timezone: string | null; next_run_at: string | null; last_run: { id: string; status: string; created_at: string; run_id: string | null } | null }
export type AutomationSource = { id: string; name: string; workflow_id: string; available: boolean; reason: string; fields: { variable: string; label: string; type: string; required: boolean; options: string[] | null; max_length: number | null }[] }
const base = (project: string) => `/company/projects/${project}/automations`
export const automationApi = {
  list: (project: string, status: string, name: string, page: number) => get<{ data: Automation[]; total: number; page: number; has_more: boolean }>(base(project), { params: { status, name, page } }),
  sources: (project: string) => get<{ data: AutomationSource[] }>(`${base(project)}/sources`),
  preview: (project: string, schedule: Schedule) => post<{ next_run_at: string; timezone: string }>(`${base(project)}/preview`, { body: { schedule } }),
  create: (project: string, body: { name: string; source_app_id: string; source_workflow_id: string; inputs: Record<string, unknown>; schedule: Schedule }) => post<Automation>(base(project), { body }),
  state: (project: string, id: string, enabled: boolean, reviewed = false) => post<Automation>(`${base(project)}/${id}/state`, { body: { enabled, reviewed } }),
  schedule: (project: string, id: string) => get<Schedule>(`${base(project)}/${id}/schedule`),
  updateSchedule: (project: string, id: string, schedule: Schedule) => put(`${base(project)}/${id}/schedule`, { body: { schedule } }),
}
