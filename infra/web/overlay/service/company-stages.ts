import type { AgentInput } from './company-agents'
import { get, post } from '@/service/base'

type Person = { account_id: string; membership_id: string; name: string }
export type StageSummary = { id: string; key: string; title: string; state: string; revision: number; executor: Person; finalizer: Person }
export type TeamInstance = { id: string; request_id: string; request_revision_id: string; intake_decision_id: string; flow_version_id: string; title: string; intake_valid: boolean; state: string; stages: StageSummary[] }
export type StageArtifact = { id: string; version: number; round: number; input_digest: string; content: Record<string, unknown>; kind: 'workflow' | 'human'; parent_id: string | null; attempt_id: string; author_id: string; reason: string }
export type TeamStage = { id: string; instance_id: string; state: string; revision: number; round: number; intake_valid: boolean; input_digest: string | null; selected_artifact_id: string | null; active_attempt_id: string | null; actions: string[]; input_error: string | null; preview_inputs: Record<string, unknown>; editable_inputs: Record<string, unknown>; binding: { title: string; agent_name: string; executor: Person; finalizer: Person; input_contract: AgentInput[] }; attempts: { attempt_id: string; round: number; status: string; actor_id: string }[]; feedback: { id: string; round: number; message: string; author_id: string; inputs: { submitted: Record<string, unknown>; effective: Record<string, unknown>; feedback_variable: string | null } }[]; artifacts: StageArtifact[]; decisions: { id: string; actor_id: string; artifact_id: string; reason: string }[] }
export type AvailableRequest = { id: string; title: string; revision: number; intake_decision_id: string }
const base = (project: string) => `/company/projects/${project}/team/instances`
export const stageApi = {
  list: (project: string) => get<{ data: TeamInstance[]; available_requests: AvailableRequest[] }>(base(project)),
  create: (project: string, request: AvailableRequest, key: string) => post<TeamInstance>(base(project), { body: { request_id: request.id, expected_revision: request.revision, intake_decision_id: request.intake_decision_id }, headers: { 'Idempotency-Key': key } }),
  detail: (project: string, instance: string, stage: string) => get<TeamStage>(`${base(project)}/${instance}/stages/${stage}`),
  act: (project: string, instance: string, stage: string, action: string, body: Record<string, unknown>, key: string) => post<TeamStage>(`${base(project)}/${instance}/stages/${stage}/${action}`, { body, headers: { 'Idempotency-Key': key } }),
}
