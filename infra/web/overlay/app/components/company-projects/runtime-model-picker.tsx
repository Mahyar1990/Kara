'use client'

import type { RuntimeExecutionPlan } from '@/utils/company-runtime-model'
import { useQuery, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import { modelConnectionApi } from '@/service/company-models'
import { sourceApi } from '@/service/company-source'

const field = 'block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-sm text-text-primary'
function ModelChoice({ value, onChange, capabilities, disabled, label }: { value: string; onChange: (value: string) => void; capabilities: string[]; disabled: boolean; label: string }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const required = [...new Set(capabilities)].sort()
  const models = useQuery({ queryKey: ['personal-runtime-models', profile.id, workspace, required], queryFn: () => modelConnectionApi.runtimeOptions(required) })
  return <div className="space-y-2">
    <select required aria-label={label} className={field} disabled={disabled || !models.isSuccess} value={value} onChange={event => onChange(event.target.value)}>
      <option value="">مدل این گام را انتخاب کنید</option>
      {models.data?.data.map(model => <option key={model.id} value={model.id}>{model.name} · {model.model_name}{model.is_default ? ' · پیش‌فرض شخصی' : ''}</option>)}
    </select>
    {models.isPending && <p role="status" className="text-xs">در حال دریافت مدل‌های شخصی…</p>}
    {models.isError && <p role="alert" className="text-xs">دریافت مدل‌ها انجام نشد. <button type="button" onClick={() => models.refetch()}>تلاش دوباره</button></p>}
    {models.isSuccess && !models.data.data.length && <p role="alert" className="text-xs leading-6">مدل سازگاری ندارید. در «تنظیمات و اتصال‌ها ← اتصال به مدل هوش مصنوعی» اتصال شخصی خودتان را ثبت کنید.</p>}
    {models.isSuccess && value && !models.data.data.some(model => model.id === value) && <p role="alert" className="text-xs">مدل قبلی در فهرست اتصال‌های سازگار نیست؛ دوباره انتخاب کنید.</p>}
  </div>
}

type Choices = { version: 2; models: Record<string, string>; runners: Record<string, { device_id: string; source_job_id: string | null }> }
export default function RuntimeModelPicker({ value, onChange, capabilities = [], disabled = false, plan, project }: {
  value?: string; onChange: (value: string) => void; capabilities?: string[]; disabled?: boolean; plan?: RuntimeExecutionPlan; project?: string
}) {
  const queryClient = useQueryClient()
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  let resolved = plan
  if (!resolved) {
    const encoded = capabilities.find(item => item.startsWith('kara-plan:'))
    try { if (encoded) resolved = JSON.parse(encoded.slice('kara-plan:'.length)) as RuntimeExecutionPlan }
    catch { /* A missing plan is rejected by admission; never guess node identities. */ }
  }
  const overview = useQuery({ queryKey: ['execution-choice-devices', profile.id, workspace], queryFn: sourceApi.overview, enabled: !!resolved })
  const projectId = project || overview.data?.projects.find(item => item.workspace_id === workspace)?.id
  const sources = useQuery({ queryKey: ['execution-choice-sources', profile.id, projectId], queryFn: () => sourceApi.list(projectId!), enabled: !!resolved && !!projectId })
  if (!resolved) return <ModelChoice value={value || ''} onChange={onChange} capabilities={capabilities.filter(item => ['json', 'tools', 'vision'].includes(item))} disabled={disabled} label="مدل اجرای برنامه" />
  let selected: Choices = { version: 2, models: {}, runners: {} }
  try { const parsed = JSON.parse(value || '{}') as Choices; if (parsed.version === 2 && parsed.models && parsed.runners) selected = parsed }
  catch { /* Old singleton selections require explicit choices for the current graph. */ }
  const nodes = resolved.nodes
  const choose = (next: Choices) => onChange(JSON.stringify({ version: 2,
    models: Object.fromEntries(Object.entries(next.models).filter(([id]) => nodes.some(node => node.id === id && node.type === 'llm'))),
    runners: Object.fromEntries(Object.entries(next.runners).filter(([id]) => nodes.some(node => node.id === id && node.runner_required))),
  }))
  return <section dir="rtl" className="space-y-3" aria-label="مدل‌ها و دستگاه‌های اجرای گام‌ها">
    <p className="text-sm font-medium">مدل و دستگاه اجرای هر گام</p>
    <p className="text-xs leading-6 text-text-tertiary">برای هر LLM یک مدل شخصی و برای هر گام اجرایی یک Runner انتخاب کنید. می‌توانید چند گام را روی یک دستگاه اجرا کنید. Runner اولین گام اجرایی، ترتیب اجرای برنامه را هماهنگ می‌کند. همهٔ گام‌های یک دستگاه از سورس آمادهٔ مشترک استفاده می‌کنند.</p>
    {nodes.map(node => <div key={node.id} className="space-y-3 rounded-lg border border-divider-regular p-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-sm font-medium">{node.title}</span><span className="text-xs text-text-tertiary">{node.type === 'llm' ? 'مدل هوش مصنوعی' : node.type === 'code' ? 'اجرای کد' : node.type === 'http-request' ? 'درخواست وب' : node.type === 'knowledge-retrieval' ? 'جست‌وجوی دانش' : node.type === 'template-transform' ? 'قالب متن' : 'کنترل جریان و داده'}</span></div>
      {node.type === 'llm' && <ModelChoice label={`مدل ${node.title}`} value={selected.models[node.id] || ''} capabilities={node.capabilities} disabled={disabled} onChange={id => choose({ ...selected, models: { ...selected.models, [node.id]: id } })} />}
      {node.runner_required ? <div className="grid gap-3 lg:grid-cols-2">
        <label className="space-y-2 text-xs"><span>Runner این گام *</span><select required aria-label={`Runner ${node.title}`} className={field} value={selected.runners[node.id]?.device_id || ''} disabled={disabled || !overview.isSuccess} onChange={event => {
          const device = event.target.value
          const existing = Object.values(selected.runners).find(item => item.device_id === device)
          choose({ ...selected, runners: { ...selected.runners, [node.id]: { device_id: device, source_job_id: existing?.source_job_id || null } } })
        }}><option value="">دستگاه اجرا را انتخاب کنید</option>{overview.data?.devices.filter(device => !device.revoked_at && device.protocol === 2 && device.capabilities?.includes('workflow-v2') && node.requirements.every(cap => device.capabilities?.includes(cap))).map(device => <option key={device.id} value={device.id}>{device.name}</option>)}</select></label>
        <label className="space-y-2 text-xs"><span>سورس آماده روی همین دستگاه</span><select className={field} value={selected.runners[node.id]?.source_job_id || ''} disabled={disabled || !selected.runners[node.id]?.device_id || !sources.isSuccess} onChange={event => {
          const device = selected.runners[node.id].device_id
          choose({ ...selected, runners: Object.fromEntries(Object.entries(selected.runners).map(([id, route]) => [id, route.device_id === device ? { ...route, source_job_id: event.target.value || null } : route])) })
        }}><option value="">این دستگاه برای این اجرا سورس آماده لازم ندارد</option>{sources.data?.jobs.filter(job => job.device_id === selected.runners[node.id]?.device_id && job.state === 'succeeded').map(job => <option key={job.id} value={job.id}>{sources.data?.workspaces.find(item => item.id === job.source_workspace_id)?.name || 'سورس آماده'} · نسخهٔ {job.snapshot_revision.toLocaleString('fa-IR')} · {new Date(job.created_at).toLocaleString('fa-IR')}</option>)}</select></label>
      </div> : <p className="text-xs leading-6 text-text-tertiary">اجرا روی Runner هماهنگ‌کنندهٔ برنامه.</p>}
    </div>)}
    {overview.isError && <p role="alert" className="text-xs">دریافت دستگاه‌ها انجام نشد. <button type="button" onClick={() => overview.refetch()}>تلاش دوباره</button></p>}
    {overview.isSuccess && !overview.data.devices.some(device => !device.revoked_at && device.capabilities?.includes('node-routing-v1')) && <p role="alert" className="text-xs leading-6">Runner سازگار ندارید. نسخهٔ تازهٔ Runner را از تنظیمات دریافت و روی دستگاه خودتان راه‌اندازی کنید.</p>}
    {sources.isError && <p role="alert" className="text-xs">دریافت سورس‌های آماده انجام نشد. <button type="button" onClick={() => sources.refetch()}>تلاش دوباره</button></p>}
    <button type="button" className="text-xs underline" disabled={disabled} onClick={() => { overview.refetch(); if (projectId) sources.refetch(); queryClient.invalidateQueries({ queryKey: ['personal-runtime-models', profile.id, workspace] }) }}>تازه‌کردن مدل‌ها، دستگاه‌ها و سورس‌ها</button>
  </section>
}
