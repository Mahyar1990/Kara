import { get, post, put } from '@/service/base'
export type ExecutionBinding = { device_id: string; source_job_id: string | null; revision: number }
export type LocalExecution = { kind?: 'workflow' | 'rpc'; id: string; app_id: string; workflow_id: string; device_id: string | null; state: string; created_at: string; result: { error?: string; total_steps?: number; total_tokens?: number } | null }
const base = (id: string) => `/company/projects/${id}/local-execution`
export const executionApi = {
  settings: (id: string) => get<{ binding: ExecutionBinding | null; executions: LocalExecution[] }>(base(id)),
  save: (id: string, body: { device_id: string; source_job_id: string | null; expected_revision: number; expected_binding: ExecutionBinding | null }) => put<ExecutionBinding>(base(id), { body }),
  cancel: (id: string, execution: string) => post(`${base(id)}/${execution}/cancel`),
}
