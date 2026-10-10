import type { FormInputItem, UserAction } from '@/app/components/workflow/nodes/human-input/types'
import type { HumanInputResolvedValue } from '@/types/workflow'
import { get, post } from '@/service/base'

export type RunSummary = { id: string; app_id: string; app_name: string; status: string; triggered_from: string; created_at: string; finished_at: string | null; elapsed_time: number; total_tokens: number }
export type RunDetail = RunSummary & { inputs: string; outputs: string; error: string; can_read_payload: boolean; truncated: boolean; forms: { id: string; status: string; expiration_time: string; can_submit: boolean; selected_action_id: string | null; submitted_at: string | null }[] }
export type ApprovalDefinition = { id: string; node_id: string; title: string; content: string; inputs: FormInputItem[]; actions: UserAction[]; default_values: Record<string, HumanInputResolvedValue>; expiration_time: string }
const base = (project: string) => `/company/projects/${project}/runs`
export const inboxApi = {
  runs: (project: string, status: string, name: string, page: number) => get<{ data: RunSummary[]; counts: Record<string, number>; total: number; page: number; has_more: boolean }>(base(project), { params: { status, name, page } }),
  run: (project: string, run: string) => get<RunDetail>(`${base(project)}/${run}`),
  form: (project: string, run: string, form: string) => get<ApprovalDefinition>(`${base(project)}/${run}/forms/${form}`),
  submit: (project: string, run: string, form: string, body: { inputs: Record<string, unknown>; action: string }) => post(`${base(project)}/${run}/forms/${form}`, { body }),
}
