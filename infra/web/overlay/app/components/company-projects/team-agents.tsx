'use client'

import type { ExecutionChoice } from '@/service/company-harness'
import HarnessChoice from './harness-choice'
import HarnessDelivery from './harness-delivery'
import HarnessPolicyEditor from './harness-policy'
import RuntimeModelPicker from './runtime-model-picker'
import { RUNTIME_MODEL_INPUT } from '@/utils/company-runtime-model'
import type { AgentAction, AgentAttempt, AgentGrants, TeamAgent } from '@/service/company-agents'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect, useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { useSearchParams } from '@/next/navigation'
import { agentApi } from '@/service/company-agents'
import { projectApi } from '@/service/company-projects'
import DeleteTeamEntity from './delete-team-entity'
import FormDialog, { FieldHelp } from './form-dialog'
import { DirectoryPage, DirectoryNotice, DirectorySummary, DirectoryToolbar, DirectoryPagination, DirectoryEmpty, directoryButton, directoryField, matchesSearch, resultPage, number } from './team-directory'

const button = 'rounded-lg border border-divider-regular bg-components-panel-bg px-4 py-2 text-sm text-text-primary disabled:opacity-50'
const primary = `${button} bg-components-button-primary-bg text-components-button-primary-text`
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const panel = 'min-w-0 space-y-4 [overflow-wrap:anywhere] rounded-2xl border border-divider-regular bg-background-default p-5'
const actions: [AgentAction, string][] = [['view', 'مشاهده'], ['run', 'اجرا'], ['feedback', 'بازخورد'], ['finalize', 'نهایی‌سازی'], ['edit_definition', 'ویرایش برنامه'], ['publish_definition', 'انتشار برنامه']]
const states: Record<AgentAttempt['status'], string> = { pending: 'در صف اجرا', running: 'در حال اجرا', succeeded: 'اجرای موفق', failed: 'اجرای ناموفق', blocked: 'اجرا متوقف شد؛ دسترسی یا نسخه تغییر کرده است', interrupted: 'نیازمند بررسی مسئول پروژه' }

// Keep the same key after transport failure; changing the payload starts a new operation.
function useAction() {
  const operation = useRef<{ payload: string; key: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async (payload: unknown, action: (key: string) => Promise<unknown>) => {
    if (busy) return
    const serialized = JSON.stringify(payload)
    if (operation.current?.payload !== serialized) operation.current = { payload: serialized, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try { await action(operation.current.key); operation.current = null }
    catch { setError('اقدام انجام نشد. دسترسی و اتصال را بررسی کنید؛ اگر اطلاعات تغییر کرده‌اند، فهرست تازه را دریافت کنید.') }
    finally { setBusy(false) }
  }
  return { busy, error, run }
}

function RegisterAgent({ project, refresh }: { project: string; refresh: () => Promise<unknown> }) {
  const [open, setOpen] = useState(false)
  const sources = useQuery({ queryKey: ['team-agent-sources', project], queryFn: () => agentApi.sources(project), enabled: open })
  const [workflowId, setWorkflowId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [reviewed, setReviewed] = useState(false)
  const action = useAction()
  const source = sources.data?.data.find(value => value.workflow_id === workflowId)
  const save = () => {
    if (!source) return
    const body = { app_id: source.app_id, workflow_id: source.workflow_id, name, description, expected_revision: 1 }
    void action.run(body, async key => { await agentApi.register(project, body, key); setName(''); setDescription(''); setWorkflowId(''); setReviewed(false); setOpen(false); await refresh() })
  }
  return <>
    <Button variant="primary" onClick={() => setOpen(true)}>ایجاد ایجنت</Button>
    <FormDialog open={open} title="ثبت ایجنت تیمی" description="یک نسخهٔ منتشرشدهٔ برنامه را به ایجنت تیم تبدیل کنید. نسخهٔ انتخاب‌شده ثابت می‌ماند و اجرا از مسیر مجوزهای تیمی انجام می‌شود. پس از ثبت، مجوز اعضا را تعیین کنید." busy={action.busy} close={() => setOpen(false)}>
      <form className="space-y-4" aria-label="ثبت ایجنت تیمی" onSubmit={event => { event.preventDefault(); if (source && reviewed) save() }}>
        <fieldset disabled={action.busy} className="space-y-4">
          {sources.isError ? <p role="alert">دریافت برنامه‌ها انجام نشد. <button type="button" className={button} onClick={() => void sources.refetch()}>تلاش دوباره</button></p> : sources.isPending ? <p role="status">در حال دریافت برنامه‌ها…</p> : !sources.data.data.length && <p>ابتدا یک فرایند با شروع دستی و خروجی مشخص در همین پروژه بسازید و منتشر کنید.</p>}
          <label className="block text-sm">نسخهٔ برنامه<select required className={field} value={workflowId} onChange={event => setWorkflowId(event.target.value)}><option value="">انتخاب کنید</option>{sources.data?.data.map(value => <option key={value.workflow_id} value={value.workflow_id}>{value.app_name} · {value.version}</option>)}</select><FieldHelp>از یک برنامه می‌توانید چند ایجنت با مجوزها و سابقهٔ مستقل بسازید. انتشار بعدی برنامه، نسخهٔ متصل به این ایجنت را تغییر نمی‌دهد.</FieldHelp></label>
          <label className="block text-sm">نام ایجنت<input required maxLength={120} className={field} value={name} onChange={event => setName(event.target.value)} /><FieldHelp>نامی متناسب با وظیفهٔ ایجنت بنویسید تا اعضای تیم آن را به‌راحتی پیدا کنند.</FieldHelp></label>
          <label className="block text-sm">توضیح<textarea maxLength={2000} className={field} value={description} onChange={event => setDescription(event.target.value)} /><FieldHelp>کار ایجنت، ورودی مورد نیاز و مسئول بررسی نتیجه را توضیح دهید؛ این متن دستورالعمل اجرای مدل نیست.</FieldHelp></label>
          <label className="flex items-start gap-2 text-sm"><input className="mt-1" type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} /><span>برنامه و نسخه را بررسی کرده‌ام و اجرای آن را به مجوزهای تیمی محدود می‌کنم.<FieldHelp>پس از ثبت، مسیرهای اجرای مستقیم برنامه محدود می‌شوند. مجوزهای هر ایجنت را جدا تعیین کنید؛ ویرایش یا انتشار برنامهٔ مشترک به مجوز مربوط در همهٔ ایجنت‌های فعال متصل نیاز دارد.</FieldHelp></span></label>
        </fieldset>
        {action.error && <p role="alert">{action.error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" disabled={action.busy} onClick={() => setOpen(false)}>انصراف</Button>
          <Button type="submit" variant="primary" disabled={action.busy || !source || !name.trim() || !reviewed}>{action.busy ? 'در حال ثبت…' : 'ثبت ایجنت'}</Button>
        </div>
      </form>
    </FormDialog>
  </>
}

function GrantsForm({ project, agent, value, refresh }: { project: string; agent: TeamAgent; value: AgentGrants; refresh: () => Promise<unknown> }) {
  const [selected, setSelected] = useState<Record<string, AgentAction[]>>(Object.fromEntries(value.grants.map(grant => [grant.account_id, grant.actions])))
  const [saved, setSaved] = useState(false)
  const action = useAction()
  const grants = value.members.filter(member => member.status === 'active').map(member => ({ account_id: member.account_id, membership_id: member.membership_id, actions: selected[member.account_id] || [] }))
  const save = () => {
    const body = { expected_revision: value.revision, grants }
    void action.run(body, async key => { await agentApi.replaceGrants(project, agent.id, body, key); setSaved(true); await refresh() })
  }
  return <form aria-label={`مجوزهای ${agent.name}`} className="space-y-4" onSubmit={event => { event.preventDefault(); save() }}>
    <p className="text-sm leading-7 text-text-secondary">مجوز هر اقدام را برای اعضای مشخص انتخاب کنید. ویرایش و انتشار به سطح دسترسی فنی مناسب نیز نیاز دارند. نقش کاری به‌تنهایی مجوز ایجاد نمی‌کند.</p>
    <fieldset disabled={action.busy || agent.archived}><legend className="mb-3 font-medium">دسترسی اعضا</legend><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="p-3 text-start">عضو</th>{actions.map(([key, label]) => <th key={key} className="whitespace-nowrap p-3">{label}</th>)}</tr></thead><tbody>{value.members.map(member => <tr key={member.membership_id} className="border-t border-divider-regular"><th className="whitespace-nowrap p-3 text-start font-normal">{member.name}{member.status !== 'active' && ' (غیرفعال)'}</th>{actions.map(([key, label]) => <td key={key} className="p-3 text-center"><input type="checkbox" aria-label={`${member.name}: ${label}`} disabled={member.status !== 'active'} checked={(selected[member.account_id] || []).includes(key)} onChange={event => { setSaved(false); setSelected({ ...selected, [member.account_id]: event.target.checked ? [...(selected[member.account_id] || []), key] : (selected[member.account_id] || []).filter(value => value !== key) }) }} /></td>)}</tr>)}</tbody></table></div></fieldset>
    {!agent.archived && <button disabled={action.busy} className={primary}>ذخیرهٔ مجوزها</button>}
    {saved && <p role="status">مجوزها ذخیره شدند.</p>}{action.error && <p role="alert">{action.error}</p>}
  </form>
}

function GrantEditor({ project, agent, refresh }: { project: string; agent: TeamAgent; refresh: () => Promise<unknown> }) {
  const value = useQuery({ queryKey: ['team-agent-grants', project, agent.id, agent.acl_revision], queryFn: () => agentApi.grants(project, agent.id) })
  return <section aria-label="مدیریت مجوزها" className="space-y-4 border-t border-divider-regular pt-4"><h3 className="font-semibold">مدیریت مجوزها</h3>{value.data ? <GrantsForm key={value.data.revision} project={project} agent={agent} value={value.data} refresh={async () => { await value.refetch(); await refresh() }} /> : <p role={value.isError ? 'alert' : 'status'}>{value.isError ? 'دریافت مجوزها انجام نشد.' : 'در حال دریافت مجوزها…'}</p>}{value.isError && value.data && <p role="alert" className="text-sm">تازه‌سازی مجوزها موفق نبود؛ اطلاعات قبلی و انتخاب‌های شما حفظ شده‌اند.</p>}<button className={button} disabled={value.isFetching} onClick={() => value.refetch()}>دریافت مجوزهای تازه</button></section>
}

function RunAgent({ project, agent }: { project: string; agent: TeamAgent }) {
  const params = useSearchParams()
  const incoming = params.get('agent') === agent.id && /^[a-f0-9-]{36}$/.test(params.get('harness_attempt') || '') ? params.get('harness_attempt') : null
  const [inputs, setInputs] = useState<Record<string, unknown>>(() => Object.fromEntries(agent.input_contract.filter(item => item.type === 'checkbox').map(item => [item.variable, false])))
  const [execution, setExecution] = useState<ExecutionChoice | null>(null)
  const [attemptExecution, setAttemptExecution] = useState<ExecutionChoice | null>(incoming ? { method: 'harness', mode: 'manual', device_id: '', source_job_id: null, profile_key: null } : null)
  const [executionReady, setExecutionReady] = useState(true)
  const [attempt, setAttempt] = useState<AgentAttempt | null>(incoming ? { id: incoming, agent_id: agent.id, workflow_id: agent.workflow_id, status: 'running', result: null } : null)
  const action = useAction()
  const result = useQuery({ queryKey: ['team-agent-attempt', project, agent.id, attempt?.id], queryFn: () => agentApi.attempt(project, agent.id, attempt!.id), enabled: !!attempt, refetchInterval: query => query.state.status === 'error' || ['succeeded', 'failed', 'blocked', 'interrupted'].includes(query.state.data?.status || '') ? false : 1500 })
  const current = result.data || attempt
  const running = current?.status === 'pending' || current?.status === 'running'
  const run = () => {
    const body = { inputs: execution ? Object.fromEntries(Object.entries(inputs).filter(([k]) => k !== RUNTIME_MODEL_INPUT)) : inputs, expected_revision: agent.revision, ...(execution ? { execution } : {}) }
    void action.run(body, async key => { setAttempt(await agentApi.run(project, agent.id, body, key)); setAttemptExecution(execution) })
  }
  return <section className="space-y-4 border-t border-divider-regular pt-4"><form aria-label={`اجرای ${agent.name}`} className="space-y-4" onSubmit={event => { event.preventDefault(); run() }}><fieldset disabled={action.busy || running}><legend className="mb-3 font-semibold">اجرای ایجنت</legend><HarnessChoice project={project} agent={agent.id} value={execution} change={setExecution} valid={setExecutionReady} />{!execution && agent.runtime_model && <RuntimeModelPicker value={String(inputs[RUNTIME_MODEL_INPUT] || '')} onChange={value => setInputs({ ...inputs, [RUNTIME_MODEL_INPUT]: value })} capabilities={agent.runtime_model.capabilities} />}{agent.input_contract.map(item => <label key={item.variable} className="mb-4 block text-sm">{item.label}{item.required && ' *'}{item.type === 'paragraph' ? <textarea className={field} required={item.required} maxLength={item.max_length || undefined} value={String(inputs[item.variable] ?? '')} onChange={event => setInputs({ ...inputs, [item.variable]: event.target.value })} /> : item.type === 'select' ? <select className={field} required={item.required} value={String(inputs[item.variable] ?? '')} onChange={event => setInputs({ ...inputs, [item.variable]: event.target.value })}><option value="">انتخاب کنید</option>{item.options.map(option => <option key={option}>{option}</option>)}</select> : item.type === 'checkbox' ? <input className="ms-3" type="checkbox" checked={Boolean(inputs[item.variable])} onChange={event => setInputs({ ...inputs, [item.variable]: event.target.checked })} /> : <input className={field} type={item.type === 'number' ? 'number' : 'text'} step="any" required={item.required} maxLength={item.max_length || undefined} value={String(inputs[item.variable] ?? '')} onChange={event => setInputs({ ...inputs, [item.variable]: item.type === 'number' && event.target.value !== '' ? Number(event.target.value) : event.target.value })} />}</label>)}</fieldset><button disabled={action.busy || running || !executionReady} className={primary}>{running ? 'در انتظار نتیجه…' : current ? 'اجرای تازه' : 'اجرای ایجنت'}</button></form>
    {current && attemptExecution && <HarnessDelivery key={current.id} project={project} agent={agent.id} identity={current.id} outputs={agent.output_contract} changed={async () => { await result.refetch() }} />}
    {action.error && <p role="alert">{action.error}</p>}{current && <div role="status" className="space-y-3 rounded-lg bg-background-section p-4"><p>{states[current.status]}</p><p className="break-all text-xs text-text-tertiary">شناسهٔ اجرا: {current.id}</p>{result.isError ? <p role="alert">دریافت نتیجه انجام نشد؛ دسترسی یا اتصال را بررسی کنید.</p> : <>{current.result?.error && <p>{current.result.error}</p>}{current.result?.outputs && <><p className="text-sm text-text-secondary">خروجی اجرا را بررسی کنید. موفقیت اجرا به معنی تأیید یا نهایی‌شدن کار نیست.</p>{Object.entries(current.result.outputs).map(([name, value]) => <div key={name}><h4 className="font-medium">{name}</h4><pre className="mt-2 whitespace-pre-wrap break-words font-sans text-sm leading-7">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre></div>)}</>}</>}<button className={button} disabled={result.isFetching} onClick={() => result.refetch()}>دریافت وضعیت اجرا</button></div>}
  </section>
}

function AgentCard({ project, agent, canManage, refresh }: { project: string; agent: TeamAgent; canManage: boolean; refresh: () => Promise<unknown> }) {
  const params = useSearchParams()
  const incoming = params.get('agent') === agent.id && /^[a-f0-9-]{36}$/.test(params.get('harness_attempt') || '')
  const [runOpen, setRunOpen] = useState(incoming)
  const [runMounted, setRunMounted] = useState(incoming)
  const [editing, setEditing] = useState(false)
  const [grantsMounted, setGrantsMounted] = useState(false)
  const [configOpen, setConfigOpen] = useState(false)
  const [configMounted, setConfigMounted] = useState(false)
  const [archiving, setArchiving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const action = useAction()
  useEffect(() => { if (incoming) { setRunMounted(true); setRunOpen(true) } }, [incoming])
  return <article className={panel}>
    <header className="flex min-w-0 flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="mb-2 text-xs font-medium text-text-accent">{agent.archived ? 'بایگانی‌شده؛ اجرای تازه غیرفعال است' : agent.actions.includes('run') ? 'مجوز اجرا دارید' : 'دسترسی شما: مشاهده و بررسی'}</p><h2 className="break-words text-xl font-semibold leading-8">{agent.name}</h2></div><span className="text-xs leading-6 text-text-tertiary">{number(agent.input_contract.length)} ورودی · {number(agent.output_contract.length)} خروجی</span></header>
    {agent.description && <p className="line-clamp-2 whitespace-pre-wrap text-sm leading-7 text-text-secondary">{agent.description}</p>}
    <div className="flex flex-wrap items-center gap-2">
      {!agent.archived && agent.actions.includes('run') && <button aria-expanded={runOpen} aria-controls={`agent-run-${agent.id}`} className={primary} onClick={() => { setRunMounted(true); setRunOpen(!runOpen) }}>{runOpen ? 'بستن پنل اجرا' : 'ورودی‌ها و اجرا'}</button>}
      {canManage && <><button className={button} aria-expanded={editing} aria-controls={`agent-grants-${agent.id}`} onClick={() => { setGrantsMounted(true); setEditing(!editing) }}>{editing ? 'بستن مجوزها' : 'مجوزهای اعضا'}</button><details><summary className={`${button} cursor-pointer`}>مدیریت ایجنت</summary><div className="mt-3 flex flex-wrap items-center gap-2">{!agent.archived && <button className={button} disabled={action.busy} onClick={() => setArchiving(!archiving)}>بایگانی ایجنت</button>}<button className={`${button} text-text-destructive-secondary`} disabled={action.busy} onClick={() => setDeleting(true)}>حذف ایجنت</button></div></details></>}
      {!agent.archived && agent.actions.includes('publish_definition') && <button className={button} aria-expanded={configOpen} onClick={() => { setConfigMounted(true); setConfigOpen(!configOpen) }}>{configOpen ? 'بستن تنظیم روش اجرا' : 'اجازهٔ هارنس شخصی'}</button>}
    </div>
    <details className="text-sm"><summary className="cursor-pointer text-text-secondary">شرح، ورودی‌ها و مجوزهای من</summary><div className="mt-3 space-y-3 rounded-xl bg-background-section p-4">{agent.description && <p className="whitespace-pre-wrap leading-7">{agent.description}</p>}<p className="text-xs leading-6 text-text-secondary">مجوزهای شما: {agent.actions.length ? actions.filter(([key]) => agent.actions.includes(key)).map(([, label]) => label).join('، ') : 'مجوز عملیاتی تعیین نشده'}</p><p className="text-xs leading-6">ورودی‌ها: {agent.input_contract.map(item => `${item.label}${item.required ? ' (الزامی)' : ''}`).join('، ') || 'ورودی دستی ندارد'}</p><p className="text-xs leading-6">خروجی‌ها: {agent.output_contract.join('، ') || 'تعریف نشده'}</p><details className="text-xs text-text-tertiary"><summary className="cursor-pointer">شناسهٔ نسخهٔ برنامه</summary><p className="mt-2 break-all" dir="ltr">{agent.workflow_id}</p></details></div></details>
    {archiving && <section className="space-y-3 rounded-xl border border-divider-regular p-4"><p className="text-sm leading-7">با بایگانی، اجرای تازه و دسترسی عملیاتی این ایجنت متوقف می‌شود. سابقه حفظ خواهد شد.</p><div className="flex flex-wrap gap-2"><button disabled={action.busy} className={button} onClick={() => action.run({ archive: agent.id, revision: agent.revision }, async key => { await agentApi.archive(project, agent.id, agent.revision, key); await refresh(); setArchiving(false) })}>تأیید بایگانی</button><button className={button} disabled={action.busy} onClick={() => setArchiving(false)}>انصراف</button></div></section>}
    {action.error && <p role="alert">{action.error}</p>}
    {canManage && grantsMounted && <div id={`agent-grants-${agent.id}`} hidden={!editing}><GrantEditor project={project} agent={agent} refresh={refresh} /></div>}
    {!agent.archived && agent.actions.includes('publish_definition') && configMounted && <div hidden={!configOpen}><HarnessPolicyEditor project={project} agent={agent.id} /></div>}
    {!agent.archived && agent.actions.includes('run') && runMounted && <div id={`agent-run-${agent.id}`} hidden={!runOpen}><RunAgent project={project} agent={agent} /></div>}
    {canManage && deleting && <DeleteTeamEntity project={project} kind="agent" value={agent} close={() => setDeleting(false)} deleted={refresh} />}
  </article>
}

export default function TeamAgents({ projectId }: { projectId: string }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const cache = useQueryClient()
  const params = useSearchParams()
  const linkedAgent = params.get('agent')
  const linkedAttempt = params.get('harness_attempt')
  const focused = useRef('')
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const entered = context.data?.current_project?.id === projectId
  const list = useQuery({ queryKey: ['team-agents', workspace, projectId], queryFn: () => agentApi.list(projectId), enabled: entered })
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('active')
  const [permission, setPermission] = useState('all')
  const [sort, setSort] = useState('registered')
  const [page, setPage] = useState(1)
  useEffect(() => { setQuery(''); setStatus('active'); setPermission('all'); setSort('registered'); setPage(1) }, [workspace, projectId])
  useEffect(() => {
    const marker = `${workspace}:${projectId}:${linkedAgent}:${linkedAttempt}`
    if (!linkedAgent || !list.data || focused.current === marker) return
    const index = list.data.data.findIndex(agent => agent.id === linkedAgent)
    if (index < 0) return
    focused.current = marker; setQuery(''); setStatus('all'); setPermission('all'); setSort('registered'); setPage(Math.floor(index / 8) + 1)
  }, [linkedAgent, linkedAttempt, list.data, workspace, projectId])
  const refresh = async () => { const value = await list.refetch(); void cache.invalidateQueries({ queryKey: ['company-projects', workspace, projectId, 'overview'] }); return value }
  const values = list.data?.data || []
  const ordered = sort === 'name' ? [...values].sort((a, b) => a.name.localeCompare(b.name, 'fa')) : values
  const filtered = ordered.filter(agent => matchesSearch(query, agent.name, agent.description) && (status === 'all' || (status === 'archived' ? agent.archived : !agent.archived)) && (permission === 'all' || (!agent.archived && agent.actions.includes(permission as AgentAction))))
  const results = resultPage(filtered, page)
  const visible = new Set(results.items.map(agent => agent.id))
  const hasFilters = !!query.trim() || status !== 'all' || permission !== 'all' || sort !== 'registered'
  const reset = () => { setQuery(''); setStatus('all'); setPermission('all'); setSort('registered'); setPage(1) }
  return <DirectoryPage project={projectId} title="ایجنت‌های تیم" description="ایجنت مناسب کار خود را پیدا کنید، ورودی‌ها را بررسی و روش اجرا را انتخاب کنید. تنظیم دسترسی اعضا با مدیر پروژه است." actions={<><button className={directoryButton} disabled={!entered || list.isFetching} onClick={() => void refresh()}>{list.isFetching ? 'در حال تازه‌سازی…' : 'تازه‌سازی'}</button>{entered && list.data?.can_manage && <RegisterAgent project={projectId} refresh={refresh} />}</>}>
    <DirectoryNotice project={projectId} entered={!!entered} loading={context.isPending || (!!entered && list.isPending)} error={context.isError || (!!entered && list.isError)} retry={() => context.isError ? context.refetch() : refresh()} />
    {entered && list.data && <>
      {list.isError && <p role="status" className="text-sm leading-7 text-text-secondary">آخرین فهرست دریافت‌شده نمایش داده می‌شود؛ تازه‌سازی موفق نبوده است.</p>}
      <DirectorySummary items={[{ label: 'کل ایجنت‌های در دسترس', count: values.length }, { label: 'غیربایگانی', count: values.filter(agent => !agent.archived).length }, { label: 'دارای مجوز اجرای من', count: values.filter(agent => !agent.archived && agent.actions.includes('run')).length }, { label: 'بایگانی‌شده', count: values.filter(agent => agent.archived).length }]} />
      <DirectoryToolbar query={query} change={value => { setQuery(value); setPage(1) }} placeholder="نام یا توضیح ایجنت" filtered={filtered.length} total={values.length} hasFilters={hasFilters} reset={reset}>
        <label className="min-w-0 flex-1 basis-36 text-sm">وضعیت<select className={directoryField} value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="active">غیربایگانی</option><option value="all">همهٔ ایجنت‌ها</option><option value="archived">بایگانی‌شده</option></select></label>
        <label className="min-w-0 flex-1 basis-40 text-sm">مجوز من<select className={directoryField} value={permission} onChange={event => { setPermission(event.target.value); setPage(1) }}><option value="all">همهٔ موارد در دسترس</option><option value="run">اجرای ایجنت</option><option value="finalize">نهایی‌سازی</option><option value="publish_definition">انتشار برنامه</option></select></label>
        <label className="min-w-0 flex-1 basis-36 text-sm">ترتیب نمایش<select className={directoryField} value={sort} onChange={event => { setSort(event.target.value); setPage(1) }}><option value="registered">ترتیب ثبت</option><option value="name">نام ایجنت</option></select></label>
      </DirectoryToolbar>
      {!results.items.length && <DirectoryEmpty filtered={hasFilters && !!values.length} title="ایجنتی در دسترس شما نیست" reset={reset}>مدیر پروژه، نسخهٔ منتشرشدهٔ برنامه را ثبت و مجوزهای هر ایجنت را برای اعضا مشخص می‌کند.</DirectoryEmpty>}
      <ul aria-label="فهرست ایجنت‌های تیم" className="m-0 list-none space-y-4 p-0">{ordered.map(agent => <li key={`${workspace}:${projectId}:${agent.id}:${agent.revision}`} hidden={!visible.has(agent.id)} className="min-w-0"><AgentCard project={projectId} agent={agent} canManage={list.data.can_manage} refresh={refresh} /></li>)}</ul>
      <DirectoryPagination value={results} change={setPage} />
      <p className="text-xs leading-6 text-text-tertiary">باز کردن پنل، اجرا را شروع نمی‌کند. بستن پنل یا تغییر فیلتر، اجرای در حال انجام را لغو نمی‌کند. برای انجام مرحلهٔ یک فلو، از کارتابل همان مرحله استفاده کنید.</p>
      <Link className="inline-block text-sm text-text-accent" href={`/projects/${projectId}/inbox`}>کارتابل و اقدام‌های من ←</Link>
    </>}
  </DirectoryPage>
}
