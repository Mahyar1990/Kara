import type { InputVar } from '@/app/components/workflow/types'
import { InputVarType } from '@/app/components/workflow/types'

export const RUNTIME_MODEL_INPUT = '__kara_model_connection'
export const RUNTIME_MODEL_PROVIDER = 'kara/runtime'
export type RuntimeExecutionPlan = { version: 2; capabilities: string[]; nodes: { id: string; title: string; type: string; capabilities: string[]; runner_required: boolean; requirements: string[] }[] }
export type RuntimeModelPolicy = { version: 1; capabilities: string[] }
export type RuntimeModelInput = InputVar & { kara_model_input?: RuntimeModelPolicy }
export const runtimeModelInput = (capabilities: string[] = []): RuntimeModelInput => ({
  type: InputVarType.textInput, variable: RUNTIME_MODEL_INPUT, label: 'مدل‌ها و Runnerهای هر گام',
  required: false, max_length: 262144, options: capabilities,
  kara_model_input: { version: 1, capabilities },
})

export const hasRuntimeModel = (nodes: { data: { type: string; variables?: { variable: string }[] } }[]) =>
  nodes.some(node => node.data.type === 'start' && node.data.variables?.some(item => item.variable === RUNTIME_MODEL_INPUT))
