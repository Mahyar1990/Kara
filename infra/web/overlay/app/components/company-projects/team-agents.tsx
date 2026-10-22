'use client'

import type { AgentAction, AgentAttempt, AgentGrants, TeamAgent } from '@/service/company-agents'
import { useQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { agentApi } from '@/service/company-agents'
import { projectApi } from '@/service/company-projects'

const button = 'rounded-lg border border-divider-regular bg-components-panel-bg px-4 py-2 text-sm text-text-primary disabled:opacity-50'
const primary = `${button} bg-components-button-primary-bg text-components-button-primary-text`
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const panel = 'space-y-4 rounded-2xl border border-divider-regular bg-background-default p-5'
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
  const sources = useQuery({ queryKey: ['team-agent-sources', project], queryFn: () => agentApi.sources(project) })
  const [workflowId, setWorkflowId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [reviewed, setReviewed] = useState(false)
  const action = useAction()
  const source = sources.data?.data.find(value => value.workflow_id === workflowId)
  const save = () => {
    if (!source) return
    const body = { app_id: source.app_id, workflow_id: source.workflow_id, name, description, expected_revision: 1 }
    void action.run(body, async key => { await agentApi.register(project, body, key); setName(''); setDescription(''); setWorkflowId(''); setReviewed(false); await refresh() })
  }
  return <form className={panel} aria-label="ثبت ایجنت تیمی" onSubmit={event => { event.preventDefault(); if (source && reviewed) save() }}>
    <h2 className="text-xl font-semibold">ثبت ایجنت تیمی</h2>
    <p className="text-sm leading-7 text-text-secondary">نسخهٔ منتشرشدهٔ برنامه را انتخاب کنید. پس از ثبت، اجرای این برنامه از بخش «ایجنت‌های تیم» انجام می‌شود و نسخهٔ انتخاب‌شده ثابت می‌ماند.</p>
    {sources.isError ? <p role="alert">دریافت برنامه‌ها انجام نشد.</p> : sources.isPending ? <p role="status">در حال دریافت برنامه‌ها…</p> : !sources.data.data.length && <p>ابتدا یک فرایند با شروع دستی و خروجی مشخص در همین پروژه بسازید و منتشر کنید.</p>}
    <label className="block text-sm">نسخهٔ برنامه<select required className={field} value={workflowId} onChange={event => setWorkflowId(event.target.value)}><option value="">انتخاب کنید</option>{sources.data?.data.map(value => <option key={value.workflow_id} value={value.workflow_id}>{value.app_name} · {value.version}</option>)}</select></label>
    <label className="block text-sm">نام ایجنت<input required maxLength={120} className={field} value={name} onChange={event => setName(event.target.value)} /></label>
    <label className="block text-sm">توضیح<textarea maxLength={2000} className={field} value={description} onChange={event => setDescription(event.target.value)} /></label>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />برنامه و نسخه را بررسی کرده‌ام و اجرای آن را به مجوزهای تیمی محدود می‌کنم.</label>
    <button className={primary} disabled={action.busy || !source || !name.trim() || !reviewed}>ثبت ایجنت</button>
    {action.error && <p role="alert">{action.error}</p>}
  </form>
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
  return <section aria-label="مدیریت مجوزها" className="space-y-4 border-t border-divider-regular pt-4"><h3 className="font-semibold">مدیریت مجوزها</h3>{value.isSuccess ? <GrantsForm key={value.data.revision} project={project} agent={agent} value={value.data} refresh={async () => { await value.refetch(); await refresh() }} /> : <p role={value.isError ? 'alert' : 'status'}>{value.isError ? 'دریافت مجوزها انجام نشد.' : 'در حال دریافت مجوزها…'}</p>}<button className={button} disabled={value.isFetching} onClick={() => value.refetch()}>دریافت مجوزهای تازه</button></section>
}

function RunAgent({ project, agent }: { project: string; agent: TeamAgent }) {
  const [inputs, setInputs] = useState<Record<string, unknown>>(() => Object.fromEntries(agent.input_contract.filter(item => item.type === 'checkbox').map(item => [item.variable, false])))
  const [attempt, setAttempt] = useState<AgentAttempt | null>(null)
  const action = useAction()
  const result = useQuery({ queryKey: ['team-agent-attempt', project, agent.id, attempt?.id], queryFn: () => agentApi.attempt(project, agent.id, attempt!.id), enabled: !!attempt, refetchInterval: query => query.state.status === 'error' || ['succeeded', 'failed', 'blocked', 'interrupted'].includes(query.state.data?.status || '') ? false : 1500 })
  const current = result.data || attempt
  const running = current?.status === 'pending' || current?.status === 'running'
  const run = () => {
    const body = { inputs, expected_revision: agent.revision }
    void action.run(body, async key => { setAttempt(await agentApi.run(project, agent.id, body, key)) })
  }
  return <section className="space-y-4 border-t border-divider-regular pt-4"><form aria-label={`اجرای ${agent.name}`} className="space-y-4" onSubmit={event => { event.preventDefault(); run() }}><fieldset disabled={action.busy || running}><legend className="mb-3 font-semibold">اجرای ایجنت</legend>{agent.input_contract.map(item => <label key={item.variable} className="mb-4 block text-sm">{item.label}{item.required && ' *'}{item.type === 'paragraph' ? <textarea className={field} required={item.required} maxLength={item.max_length || undefined} value={String(inputs[item.variable] ?? '')} onChange={event => setInputs({ ...inputs, [item.variable]: event.target.value })} /> : item.type === 'select' ? <select className={field} required={item.required} value={String(inputs[item.variable] ?? '')} onChange={event => setInputs({ ...inputs, [item.variable]: event.target.value })}><option value="">انتخاب کنید</option>{item.options.map(option => <option key={option}>{option}</option>)}</select> : item.type === 'checkbox' ? <input className="ms-3" type="checkbox" checked={Boolean(inputs[item.variable])} onChange={event => setInputs({ ...inputs, [item.variable]: event.target.checked })} /> : <input className={field} type={item.type === 'number' ? 'number' : 'text'} step="any" required={item.required} maxLength={item.max_length || undefined} value={String(inputs[item.variable] ?? '')} onChange={event => setInputs({ ...inputs, [item.variable]: item.type === 'number' && event.target.value !== '' ? Number(event.target.value) : event.target.value })} />}</label>)}</fieldset><button disabled={action.busy || running} className={primary}>{running ? 'در انتظار نتیجه…' : current ? 'اجرای تازه' : 'اجرای ایجنت'}</button></form>
    {action.error && <p role="alert">{action.error}</p>}{current && <div role="status" className="space-y-3 rounded-lg bg-background-section p-4"><p>{states[current.status]}</p><p className="break-all text-xs text-text-tertiary">شناسهٔ اجرا: {current.id}</p>{result.isError ? <p role="alert">دریافت نتیجه انجام نشد؛ دسترسی یا اتصال را بررسی کنید.</p> : <>{current.result?.error && <p>{current.result.error}</p>}{current.result?.outputs && <><p className="text-sm text-text-secondary">خروجی اجرا را بررسی کنید. موفقیت اجرا به معنی تأیید یا نهایی‌شدن کار نیست.</p>{Object.entries(current.result.outputs).map(([name, value]) => <div key={name}><h4 className="font-medium">{name}</h4><pre className="mt-2 whitespace-pre-wrap break-words font-sans text-sm leading-7">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre></div>)}</>}</>}<button className={button} disabled={result.isFetching} onClick={() => result.refetch()}>دریافت وضعیت اجرا</button></div>}
  </section>
}

function AgentCard({ project, agent, canManage, refresh }: { project: string; agent: TeamAgent; canManage: boolean; refresh: () => Promise<unknown> }) {
  const [editing, setEditing] = useState(false)
  const [archiving, setArchiving] = useState(false)
  const action = useAction()
  return <article className={panel}><header className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">{agent.name}{agent.archived && ' · بایگانی‌شده'}</h2>{canManage && <div className="flex gap-3"><button className={button} onClick={() => setEditing(!editing)}>مجوزهای اعضا</button>{!agent.archived && <button className={button} onClick={() => setArchiving(!archiving)}>بایگانی ایجنت</button>}</div>}</header><p className="whitespace-pre-wrap text-sm leading-7 text-text-secondary">{agent.description}</p><details className="text-xs text-text-tertiary"><summary className="cursor-pointer">نسخهٔ برنامهٔ انتخاب‌شده</summary><p className="mt-2 break-all" dir="ltr">{agent.workflow_id}</p></details><p className="text-sm text-text-secondary">مجوزهای شما: {agent.actions.length ? actions.filter(([key]) => agent.actions.includes(key)).map(([, label]) => label).join('، ') : 'مجوز عملیاتی تعیین نشده'}</p>{archiving && <div className="space-y-3 rounded-lg border border-divider-regular p-4"><p>با بایگانی، اجرای تازه و دسترسی عملیاتی این ایجنت متوقف می‌شود. سابقه حفظ خواهد شد.</p><button disabled={action.busy} className={button} onClick={() => action.run({ archive: agent.id, revision: agent.revision }, async key => { await agentApi.archive(project, agent.id, agent.revision, key); await refresh(); setArchiving(false) })}>تأیید بایگانی</button></div>}{action.error && <p role="alert">{action.error}</p>}{canManage && editing && <GrantEditor project={project} agent={agent} refresh={refresh} />}{!agent.archived && agent.actions.includes('run') && <RunAgent project={project} agent={agent} />}</article>
}

export default function TeamAgents({ projectId }: { projectId: string }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const entered = context.data?.current_project?.id === projectId
  const list = useQuery({ queryKey: ['team-agents', workspace, projectId], queryFn: () => agentApi.list(projectId), enabled: entered })
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto max-w-5xl space-y-6"><Link href={`/projects/${projectId}`} className="text-sm text-text-accent">نمای کلی پروژه ←</Link><header><h1 className="text-3xl font-bold">ایجنت‌های تیم</h1><p className="mt-3 text-sm leading-7 text-text-secondary">ایجنت‌های مجاز خود را با ورودی مشخص اجرا کنید. مدیر پروژه و ادمین کل دسترسی اعضا را تعیین می‌کنند.</p></header>{!entered ? <p role="status">ابتدا وارد فضای همین پروژه شوید.</p> : list.isSuccess ? <>{list.data.can_manage && <RegisterAgent project={projectId} refresh={list.refetch} />}{!list.data.data.length && <p className={panel}>ایجنت قابل دسترسی برای شما ثبت نشده است.</p>}{list.data.data.map(agent => <AgentCard key={`${workspace}:${agent.id}:${agent.revision}`} project={projectId} agent={agent} canManage={list.data.can_manage} refresh={list.refetch} />)}</> : <p role={list.isError ? 'alert' : 'status'}>{list.isError ? 'دریافت ایجنت‌ها انجام نشد.' : 'در حال دریافت ایجنت‌ها…'}</p>}<button className={button} disabled={!entered || list.isFetching} onClick={() => list.refetch()}>دریافت فهرست تازهٔ ایجنت‌ها</button></div></main>
}
