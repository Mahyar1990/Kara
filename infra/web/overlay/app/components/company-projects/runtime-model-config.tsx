'use client'

import type { StartNodeType } from '@/app/components/workflow/nodes/start/types'
import { useNodes } from 'reactflow'
import useNodeCrud from '@/app/components/workflow/nodes/_base/hooks/use-node-crud'
import { RUNTIME_MODEL_INPUT, runtimeModelInput } from '@/utils/company-runtime-model'
import type { RuntimeModelInput } from '@/utils/company-runtime-model'

export function useRuntimeProgramPolicy() {
  const nodes = useNodes()
  const start = nodes.find(node => node.data.type === 'start')
  const input = start?.data.variables?.find((item: RuntimeModelInput) => item.variable === RUNTIME_MODEL_INPUT) as RuntimeModelInput | undefined
  if (!input) return null
  const required = new Set(input.kara_model_input?.capabilities || [])
  for (const node of nodes) {
    if (node.data.type !== 'llm') continue
    if (node.data.vision?.enabled) required.add('vision')
    if (node.data.structured_output_enabled) required.add('json')
  }
  return { version: 1 as const, capabilities: [...required].sort() }
}

export function useRuntimeProgramModel() {
  return !!useRuntimeProgramPolicy()
}

export default function RuntimeModelConfig({ id, data, disabled }: { id: string; data: StartNodeType; disabled: boolean }) {
  const { inputs, setInputs } = useNodeCrud<StartNodeType>(id, data)
  const variable = inputs.variables.find(item => item.variable === RUNTIME_MODEL_INPUT) as RuntimeModelInput | undefined
  const change = (enabled: boolean, capabilities = variable?.kara_model_input?.capabilities || []) => {
    const remaining = inputs.variables.filter(item => item.variable !== RUNTIME_MODEL_INPUT)
    setInputs({ ...inputs, variables: enabled ? [runtimeModelInput(capabilities), ...remaining] : remaining })
  }
  return <section dir="rtl" className="mb-4 space-y-3 rounded-lg border border-divider-regular p-3">
    <label className="flex items-start gap-2 text-sm font-medium"><input type="checkbox" disabled={disabled} checked={!!variable} onChange={event => change(event.target.checked)} />انتخاب مدل توسط اجراکننده</label>
    <p className="text-xs leading-6 text-text-tertiary">با فعال‌کردن این گزینه، همهٔ مراحل LLM برنامه از مدل شخصی انتخاب‌شده هنگام اجرا استفاده می‌کنند. برای ساخت و انتشار، انتخاب مدل مشخص لازم نیست.</p>
    {variable && <fieldset disabled={disabled} className="space-y-2"><legend className="mb-2 text-sm">قابلیت‌های لازم مدل</legend>{[['json', 'خروجی JSON'], ['tools', 'فراخوانی ابزار'], ['vision', 'پردازش تصویر']].map(([key, label]) => <label key={key} className="flex items-center gap-2 text-xs"><input type="checkbox" checked={variable.kara_model_input?.capabilities.includes(key) || false} onChange={event => change(true, event.target.checked ? [...(variable.kara_model_input?.capabilities || []), key] : (variable.kara_model_input?.capabilities || []).filter(item => item !== key))} />{label}</label>)}<p className="text-xs leading-6 text-text-tertiary">نیاز به تصویر و خروجی ساختاریافتهٔ مراحل هم خودکار بررسی می‌شود. تنظیمات هر مرحله باید با مدل انتخاب‌شده سازگار باشد.</p></fieldset>}
  </section>
}
