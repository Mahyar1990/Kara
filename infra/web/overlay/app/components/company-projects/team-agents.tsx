'use client'

import { useProgramDialogState } from './program-dialog-state'

import type { ExecutionChoice } from '@/service/company-harness'
import HarnessChoice from './harness-choice'
import HarnessDelivery from './harness-delivery'
import HarnessPolicyEditor from './harness-policy'
import RuntimeModelPicker from './runtime-model-picker'
import { RUNTIME_MODEL_INPUT } from '@/utils/company-runtime-model'
import type { AgentAction, AgentAttempt, AgentGrants, TeamAgent } from '@/service/company-agents'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { useSearchParams } from '@/next/navigation'
import { agentApi } from '@/service/company-agents'
import DeleteTeamEntity from './delete-team-entity'
import { number } from './team-directory'

const button = 'rounded-lg border border-divider-regular bg-components-panel-bg px-4 py-2 text-sm text-text-primary disabled:opacity-50'
const primary = `${button} bg-components-button-primary-bg text-components-button-primary-text`
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const panel = 'min-w-0 space-y-4 [overflow-wrap:anywhere] rounded-2xl border border-divider-regular bg-background-default p-5'
const actions: [AgentAction, string][] = [['view', 'مشاهده'], ['run', 'اجرا'], ['feedback', 'بازخورد'], ['finalize', 'نهایی‌سازی'], ['edit_definition', 'ویرایش برنامه'], ['publish_definition', 'انتشار برنامه']]
const agentActions = (agent: TeamAgent) => actions.filter(([key]) => !agent.personal_source || key !== 'edit_definition').map<[AgentAction, string]>(([key, label]) => [key, agent.personal_source && key === 'publish_definition' ? 'تنظیم هارنس' : label])
const states: Record<AgentAttempt['status'], string> = { pending: 'در صف اجرا', running: 'در حال اجرا', succeeded: 'اجرای موفق', failed: 'اجرای ناموفق', blocked: 'اجرا متوقف شد؛ دسترسی یا نسخه تغییر کرده است', interrupted: 'نیازمند بررسی مسئول پروژه' }

// Keep the same key after transport failure; changing the payload starts a new operation.
export function useTeamAction() {
  const { change } = useProgramDialogState()
  const operation = useRef<{ payload: string; key: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async (payload: unknown, action: (key: string) => Promise<unknown>) => {
    if (busy) return
    const serialized = JSON.stringify(payload)
    if (operation.current?.payload !== serialized) operation.current = { payload: serialized, key: crypto.randomUUID() }
    setBusy(true); change(1); setError('')
    try { await action(operation.current.key); operation.current = null }
    catch { setError('اقدام انجام نشد. دسترسی و اتصال را بررسی کنید؛ اگر اطلاعات تغییر کرده‌اند، فهرست تازه را دریافت کنید.') }
    finally { setBusy(false); change(-1) }
  }
  return { busy, error, run }
}

function GrantsForm({ project, agent, value, refresh }: { project: string; agent: TeamAgent; value: AgentGrants; refresh: () => Promise<unknown> }) {
  const [selected, setSelected] = useState<Record<string, AgentAction[]>>(Object.fromEntries(value.grants.map(grant => [grant.account_id, grant.actions])))
  const [saved, setSaved] = useState(false)
  const action = useTeamAction()
  const grants = value.members.filter(member => member.status === 'active').map(member => ({ account_id: member.account_id, membership_id: member.membership_id, actions: selected[member.account_id] || [] }))
  const grantActions = agentActions(agent)
  const save = () => {
    const body = { expected_revision: value.revision, grants }
    void action.run(body, async key => { await agentApi.replaceGrants(project, agent.id, body, key); setSaved(true); await refresh() })
  }
  return <form aria-label={`مجوزهای ${agent.name}`} className="space-y-4" onSubmit={event => { event.preventDefault(); save() }}>
    <p className="text-sm leading-7 text-text-secondary">مجوز هر اقدام را برای اعضای مشخص انتخاب کنید. ویرایش و انتشار به سطح دسترسی فنی مناسب نیز نیاز دارند. نقش کاری به‌تنهایی مجوز ایجاد نمی‌کند.</p>
    {agent.personal_source && <p className="text-sm leading-7 text-text-secondary">مجوز تیمی جایگزین دسترسی منبع کتابخانه و دانش نیست. دستورالعمل را در کتابخانه ویرایش و برنامهٔ تازه‌ای از آن بسازید؛ «تنظیم هارنس» روش اجرای این تسک را مدیریت می‌کند.</p>}
    <fieldset disabled={action.busy || agent.archived}><legend className="mb-3 font-medium">دسترسی اعضا</legend><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="p-3 text-start">عضو</th>{grantActions.map(([key, label]) => <th key={key} className="whitespace-nowrap p-3">{label}</th>)}</tr></thead><tbody>{value.members.map(member => <tr key={member.membership_id} className="border-t border-divider-regular"><th className="whitespace-nowrap p-3 text-start font-normal">{member.name}{member.status !== 'active' && ' (غیرفعال)'}</th>{grantActions.map(([key, label]) => <td key={key} className="p-3 text-center"><input type="checkbox" aria-label={`${member.name}: ${label}`} disabled={member.status !== 'active'} checked={(selected[member.account_id] || []).includes(key)} onChange={event => { setSaved(false); setSelected({ ...selected, [member.account_id]: event.target.checked ? [...(selected[member.account_id] || []), key] : (selected[member.account_id] || []).filter(value => value !== key) }) }} /></td>)}</tr>)}</tbody></table></div></fieldset>
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
  const [inputs, setInputs] = useState<Record<string, unknown>>(() => Object.fromEntries(agent.input_contract.filter(item => item.default != null || item.type === 'checkbox').map(item => [item.variable, item.default ?? false])))
  const [execution, setExecution] = useState<ExecutionChoice | null>(null)
  const [attemptExecution, setAttemptExecution] = useState<ExecutionChoice | null>(incoming ? { method: 'harness', mode: 'manual', device_id: '', source_job_id: null, profile_key: null } : null)
  const [executionReady, setExecutionReady] = useState(true)
  const [attempt, setAttempt] = useState<AgentAttempt | null>(incoming ? { id: incoming, agent_id: agent.id, workflow_id: agent.workflow_id, status: 'running', result: null } : null)
  const action = useTeamAction()
  const result = useQuery({ queryKey: ['team-agent-attempt', project, agent.id, attempt?.id], queryFn: () => agentApi.attempt(project, agent.id, attempt!.id), enabled: !!attempt, refetchInterval: query => query.state.status === 'error' || ['succeeded', 'failed', 'blocked', 'interrupted'].includes(query.state.data?.status || '') ? false : 1500 })
  const current = result.data || attempt
  const running = current?.status === 'pending' || current?.status === 'running'
  const run = () => {
    const body = { inputs: execution ? Object.fromEntries(Object.entries(inputs).filter(([k]) => k !== RUNTIME_MODEL_INPUT)) : inputs, expected_revision: agent.revision, ...(execution ? { execution } : {}) }
    void action.run(body, async key => { setAttempt(await agentApi.run(project, agent.id, body, key)); setAttemptExecution(execution) })
  }
  return <section className="space-y-4 border-t border-divider-regular pt-4"><form aria-label={`اجرای ${agent.name}`} className="space-y-4" onSubmit={event => { event.preventDefault(); run() }}><fieldset disabled={action.busy || running}><legend className="mb-3 font-semibold">اجرای برنامه</legend><HarnessChoice project={project} agent={agent.id} value={execution} change={setExecution} valid={setExecutionReady} />{!execution && agent.runtime_model && <RuntimeModelPicker value={String(inputs[RUNTIME_MODEL_INPUT] || '')} onChange={value => setInputs({ ...inputs, [RUNTIME_MODEL_INPUT]: value })} capabilities={agent.runtime_model.capabilities} />}{agent.input_contract.map(item => <label key={item.variable} className="mb-4 block text-sm">{item.label}{item.required && ' *'}{item.type === 'paragraph' ? <textarea className={field} required={item.required} maxLength={item.max_length || undefined} value={String(inputs[item.variable] ?? '')} onChange={event => setInputs({ ...inputs, [item.variable]: event.target.value })} /> : item.type === 'select' ? <select className={field} required={item.required} value={String(inputs[item.variable] ?? '')} onChange={event => setInputs({ ...inputs, [item.variable]: event.target.value })}><option value="">انتخاب کنید</option>{item.options.map(option => <option key={option}>{option}</option>)}</select> : item.type === 'checkbox' ? <input className="ms-3" type="checkbox" checked={Boolean(inputs[item.variable])} onChange={event => setInputs({ ...inputs, [item.variable]: event.target.checked })} /> : <input className={field} type={item.type === 'number' ? 'number' : 'text'} step="any" required={item.required} maxLength={item.max_length || undefined} value={String(inputs[item.variable] ?? '')} onChange={event => setInputs({ ...inputs, [item.variable]: item.type === 'number' && event.target.value !== '' ? Number(event.target.value) : event.target.value })} />}</label>)}</fieldset><button disabled={action.busy || running || !executionReady} className={primary}>{running ? 'در انتظار نتیجه…' : current ? 'اجرای تازه' : 'اجرای برنامه'}</button></form>
    {current && attemptExecution && <HarnessDelivery key={current.id} project={project} agent={agent.id} identity={current.id} outputs={agent.output_contract} changed={async () => { await result.refetch() }} />}
    {action.error && <p role="alert">{action.error}</p>}{current && <div role="status" className="space-y-3 rounded-lg bg-background-section p-4"><p>{states[current.status]}</p><p className="break-all text-xs text-text-tertiary">شناسهٔ اجرا: {current.id}</p>{result.isError ? <p role="alert">دریافت نتیجه انجام نشد؛ دسترسی یا اتصال را بررسی کنید.</p> : <>{current.result?.error && <p>{current.result.error}</p>}{current.result?.outputs && <><p className="text-sm text-text-secondary">خروجی اجرا را بررسی کنید. موفقیت اجرا به معنی تأیید یا نهایی‌شدن کار نیست.</p>{Object.entries(current.result.outputs).map(([name, value]) => <div key={name}><h4 className="font-medium">{name}</h4><pre className="mt-2 whitespace-pre-wrap break-words font-sans text-sm leading-7">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre></div>)}</>}</>}<button className={button} disabled={result.isFetching} onClick={() => result.refetch()}>دریافت وضعیت اجرا</button></div>}
  </section>
}

export function ProgramSettingsCard({ project, agent, canManage, refresh, compact = false }: { project: string; agent: TeamAgent; canManage: boolean; refresh: () => Promise<unknown>; compact?: boolean }) {
  const panelId = useId()
  type Panel = 'run' | 'grants' | 'harness' | 'info'
  const params = useSearchParams()
  const incoming = params.get('agent') === agent.id && /^[a-f0-9-]{36}$/.test(params.get('harness_attempt') || '')
  const [active, setActive] = useState<Panel | null>(incoming ? 'run' : compact ? canManage ? 'grants' : 'info' : null)
  const [runMounted, setRunMounted] = useState(incoming)
  const [grantsMounted, setGrantsMounted] = useState(compact && canManage)
  const [configMounted, setConfigMounted] = useState(false)
  const [archiving, setArchiving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const action = useTeamAction()
  const titles: Record<Panel, string> = { run: 'ورودی‌ها و اجرای برنامه', grants: 'مجوزهای اعضا', harness: 'اجازهٔ استفاده از هارنس شخصی', info: 'شرح و قرارداد اجرا' }
  const toggle = (next: Panel) => setActive(current => current === next ? null : next)
  const tab = (value: Panel) => `${button} ${active === value ? 'bg-background-section font-semibold text-text-accent ring-1 ring-text-accent' : ''}`
  useEffect(() => { if (incoming) { setRunMounted(true); setActive('run') } }, [incoming])
  return <article className={panel}>
    <header className="flex min-w-0 flex-wrap items-start gap-4"><div className="min-w-0 flex-1"><p className="mb-2 text-xs font-medium text-text-accent">{agent.archived ? 'بایگانی‌شده؛ اجرای تازه غیرفعال است' : agent.actions.includes('run') ? 'مجوز اجرا دارید' : 'دسترسی شما: مشاهده و بررسی'}</p>{!compact && <h2 className="break-words text-xl font-semibold leading-8">{agent.name}</h2>}</div>

    </header>
    {canManage && <details className="text-sm"><summary className="cursor-pointer text-text-tertiary">مدیریت پیشرفته</summary><div className="mt-3">{canManage && <div aria-label={`مدیریت ${agent.name}`} className="ms-auto flex flex-wrap items-center justify-end gap-2">{!agent.archived && <button className={`${button} ${archiving ? 'bg-background-section font-semibold text-text-accent ring-1 ring-text-accent' : ''}`} aria-pressed={archiving} disabled={action.busy} onClick={() => setArchiving(!archiving)}>بایگانی</button>}<button className={`${button} text-text-destructive-secondary`} disabled={action.busy} onClick={() => setDeleting(true)}>حذف</button></div>}</div></details>}
    {agent.personal_source && <p className="text-sm leading-7 text-text-secondary">منبع: ایجنت کتابخانه «{agent.personal_source.name}» · نسخهٔ {number(agent.personal_source.snapshot_version)} · مدل <bdi>{agent.personal_source.model.name}</bdi></p>}
    {agent.description && <p className="line-clamp-2 whitespace-pre-wrap text-sm leading-7 text-text-secondary">{agent.description}</p>}
    <p className="text-xs leading-6 text-text-tertiary">نسخهٔ {agent.workflow_version || agent.workflow_id} · {number(agent.input_contract.length)} ورودی · {number(agent.output_contract.length)} خروجی</p>
    <div aria-label="بخش‌های تنظیم تیمی" className="flex flex-wrap items-center gap-2">
      {!agent.archived && agent.actions.includes('run') && <button aria-pressed={active === 'run'} aria-expanded={active === 'run'} aria-controls={`${panelId}-run`} className={tab('run')} onClick={() => { setRunMounted(true); toggle('run') }}>ورودی‌ها و اجرا</button>}
      {canManage && <button className={tab('grants')} aria-pressed={active === 'grants'} aria-expanded={active === 'grants'} aria-controls={`${panelId}-grants`} onClick={() => { setGrantsMounted(true); toggle('grants') }}>دسترسی اعضا</button>}
      {!agent.archived && agent.actions.includes('publish_definition') && <button className={tab('harness')} aria-pressed={active === 'harness'} aria-expanded={active === 'harness'} aria-controls={`${panelId}-harness`} onClick={() => { setConfigMounted(true); toggle('harness') }}>روش اجرا</button>}
      <button className={tab('info')} aria-pressed={active === 'info'} aria-expanded={active === 'info'} aria-controls={`${panelId}-info`} onClick={() => toggle('info')}>شرح و ورودی‌ها</button>
    </div>
    <section hidden={!active} className="min-w-0 space-y-4 rounded-xl border border-text-accent bg-background-section p-4" aria-label={active ? titles[active] : 'پنل تنظیم تیمی'}>
      <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">{active && titles[active]}</h3><button className={button} aria-label={`بستن بخش باز ${agent.name}`} onClick={() => setActive(null)}>بستن بخش</button></div>
      <div id={`${panelId}-info`} hidden={active !== 'info'} className="space-y-3">{agent.description && <p className="whitespace-pre-wrap text-sm leading-7">{agent.description}</p>}<p className="text-xs leading-6 text-text-secondary">مجوزهای شما: {agentActions(agent).filter(([key]) => agent.actions.includes(key)).map(([, label]) => label).join('، ') || 'مجوز عملیاتی تعیین نشده'}</p><p className="text-xs leading-6">ورودی‌ها: {agent.input_contract.map(item => `${item.label}${item.required ? ' (الزامی)' : ''}`).join('، ') || 'ورودی دستی ندارد'}</p><p className="text-xs leading-6">خروجی‌ها: {agent.output_contract.join('، ') || 'تعریف نشده'}</p><details className="text-xs text-text-tertiary"><summary className="cursor-pointer">شناسهٔ نسخهٔ برنامه</summary><p className="mt-2 break-all" dir="ltr">{agent.workflow_id}</p></details></div>
      {canManage && grantsMounted && <div id={`${panelId}-grants`} hidden={active !== 'grants'}><GrantEditor project={project} agent={agent} refresh={refresh} /></div>}
      {!agent.archived && agent.actions.includes('publish_definition') && configMounted && <div id={`${panelId}-harness`} hidden={active !== 'harness'}><HarnessPolicyEditor embedded project={project} agent={agent.id} /></div>}
      {!agent.archived && agent.actions.includes('run') && runMounted && <div id={`${panelId}-run`} hidden={active !== 'run'}><RunAgent project={project} agent={agent} /></div>}
    </section>
    {archiving && <section className="space-y-3 rounded-xl border border-divider-regular p-4"><p className="text-sm leading-7">با بایگانی تنظیم «{agent.name}»، اجرای تازه و دسترسی عملیاتی آن متوقف می‌شود. سابقه حفظ خواهد شد.</p><div className="flex flex-wrap gap-2"><button disabled={action.busy} className={button} onClick={() => action.run({ archive: agent.id, revision: agent.revision }, async key => { await agentApi.archive(project, agent.id, agent.revision, key); await refresh(); setArchiving(false) })}>تأیید بایگانی</button><button className={button} disabled={action.busy} onClick={() => setArchiving(false)}>انصراف</button></div></section>}
    {action.error && <p role="alert">{action.error}</p>}
    {canManage && deleting && <DeleteTeamEntity project={project} kind="agent" label="تنظیم تیمی" value={agent} close={() => setDeleting(false)} deleted={refresh} />}
  </article>
}
