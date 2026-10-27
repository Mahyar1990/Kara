'use client'

import type { AgentInput } from '@/service/company-agents'
import type { FlowInput, FlowOptions, FlowStage, FlowVersion, TeamFlow } from '@/service/company-flows'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect, useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { flowApi } from '@/service/company-flows'
import { projectApi } from '@/service/company-projects'
import DeleteTeamEntity from './delete-team-entity'
import FormDialog, { FieldHelp } from './form-dialog'
import { DirectoryPage, DirectoryNotice, DirectorySummary, DirectoryToolbar, DirectoryPagination, DirectoryEmpty, directoryButton, directoryField, matchesSearch, resultPage } from './team-directory'

const panel = 'min-w-0 space-y-4 [overflow-wrap:anywhere] rounded-2xl border border-divider-regular bg-background-default p-5'
const button = 'rounded-lg border border-divider-regular px-4 py-2 text-sm disabled:opacity-50'
const primary = `${button} bg-components-button-primary-bg text-components-button-primary-text`
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const number = (value: number) => value.toLocaleString('fa-IR')

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
    catch { setError('اقدام انجام نشد. مجوزها و کامل‌بودن مراحل را بررسی کنید؛ اگر فلو تغییر کرده است، نسخهٔ تازه را دریافت کنید.') }
    finally { setBusy(false) }
  }
  return { busy, error, run }
}

function InputBinding({ item, value, previous, options, change }: { item: AgentInput; value?: FlowInput; previous: FlowStage[]; options: FlowOptions; change: (value?: FlowInput) => void }) {
  const selected = value?.source === 'stage' ? JSON.stringify({ source: 'stage', stage_key: value.stage_key, output: value.output }) : value?.source || ''
  const choose = (text: string) => {
    if (!text) change()
    else if (text === 'request') change({ source: 'request' })
    else if (text === 'constant') change({ source: 'constant', value: item.type === 'number' ? 0 : item.type === 'checkbox' ? false : '' })
    else change(JSON.parse(text) as FlowInput)
  }
  return <div className="space-y-2 rounded-lg border border-divider-regular p-3">
    <label className="block text-sm">منبع {item.label}{item.required && ' *'}<select className={field} value={selected} onChange={event => choose(event.target.value)}>
      <option value="">بدون اتصال</option>
      {['text-input', 'paragraph'].includes(item.type) && <option value="request">متن درخواست</option>}
      <option value="constant">مقدار ثابت</option>
      {previous.flatMap(stage => (options.agents.find(agent => agent.id === stage.agent_id)?.output_contract || []).map(output => <option key={`${stage.key}:${output}`} value={JSON.stringify({ source: 'stage', stage_key: stage.key, output })}>خروجی «{stage.title}»: {output}</option>))}
    </select><FieldHelp>متن درخواست: شرح همان درخواست. مقدار ثابت: دادهٔ مشترک همهٔ اجراهای این نسخهٔ فلو. خروجی مرحلهٔ قبل: نتیجهٔ منتخب و نهایی‌شدهٔ آن مرحله. ورودی الزامی را بدون اتصال نگذارید.</FieldHelp></label>
    {value?.source === 'constant' && <label className="block text-sm">مقدار {item.label}
      {item.type === 'checkbox' ? <input className="ms-3" type="checkbox" checked={Boolean(value.value)} onChange={event => change({ source: 'constant', value: event.target.checked })} />
        : item.type === 'select' ? <select className={field} value={String(value.value ?? '')} onChange={event => change({ source: 'constant', value: event.target.value })}><option value="">انتخاب کنید</option>{item.options.map(option => <option key={option}>{option}</option>)}</select>
          : <textarea className={field} maxLength={item.max_length || undefined} value={String(value.value ?? '')} onChange={event => change({ source: 'constant', value: item.type === 'number' && event.target.value !== '' ? Number(event.target.value) : event.target.value })} />}
    <FieldHelp>این مقدار در همهٔ اجراهای همین نسخه استفاده می‌شود؛ اطلاعات متغیر هر درخواست و رمز را اینجا وارد نکنید.</FieldHelp></label>}
  </div>
}

function StageEditor({ stage, index, stages, options, change, move, remove }: { stage: FlowStage; index: number; stages: FlowStage[]; options: FlowOptions; change: (value: FlowStage) => void; move: (offset: number) => void; remove: () => void }) {
  const [expanded, setExpanded] = useState(index === 0 || !stage.agent_id)
  const agent = options.agents.find(value => value.id === stage.agent_id)
  const setPerson = (prefix: 'executor' | 'finalizer', id: string) => change({ ...stage, [`${prefix}_id`]: id || null, [`${prefix}_membership_id`]: options.members.find(member => member.account_id === id)?.membership_id || null })
  return <details open={expanded} onToggle={event => setExpanded(event.currentTarget.open)} onInvalidCapture={event => { event.currentTarget.open = true; setExpanded(true) }} className="min-w-0 rounded-xl border border-divider-regular p-4 [overflow-wrap:anywhere]">
    <summary className="cursor-pointer leading-7"><span className="font-semibold">{number(index + 1)}. {stage.title || 'مرحلهٔ بدون عنوان'}</span><span className="mt-1 block text-xs leading-6 text-text-tertiary">{agent?.name || 'ایجنت انتخاب نشده'} · {options.members.find(member => member.account_id === stage.executor_id)?.name || 'مجری انتخاب نشده'} · {options.members.find(member => member.account_id === stage.finalizer_id)?.name || 'نهایی‌کننده انتخاب نشده'}</span></summary>
    <div className="mt-4 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">مرحلهٔ {number(index + 1)}</h3><div className="flex gap-2">
      <button type="button" className={button} disabled={index === 0} onClick={() => move(-1)}>بالا</button><button type="button" className={button} disabled={index === stages.length - 1} onClick={() => move(1)}>پایین</button><button type="button" className={button} onClick={remove}>حذف مرحله</button>
    </div></div>
    <label className="block text-sm">عنوان مرحله<input className={field} required maxLength={120} value={stage.title} onChange={event => change({ ...stage, title: event.target.value })} /><FieldHelp>کاری که در این گام انجام و بررسی می‌شود؛ عنوان در اجرای تیمی و کارتابل اعضا نمایش داده می‌شود.</FieldHelp></label>
    <label className="block text-sm">ایجنت مرحله<select className={field} value={stage.agent_id || ''} onChange={event => change({ ...stage, agent_id: event.target.value || null, executor_id: null, executor_membership_id: null, finalizer_id: null, finalizer_membership_id: null, inputs: {} })}>
      <option value="">انتخاب کنید</option>{options.agents.map(value => <option key={value.id} value={value.id}>{value.name}</option>)}
    </select><FieldHelp>یکی از ایجنت‌های ثبت‌شدهٔ همین پروژه را انتخاب کنید. ورودی‌های آن پس از انتخاب نمایش داده می‌شوند.</FieldHelp></label>
    <div className="grid gap-4 md:grid-cols-2">
      <label className="block text-sm">اجراکننده<select className={field} value={stage.executor_id || ''} onChange={event => setPerson('executor', event.target.value)}><option value="">انتخاب کنید</option>{options.members.filter(member => agent?.runners.includes(member.account_id)).map(member => <option key={member.membership_id} value={member.account_id}>{member.name}</option>)}</select><FieldHelp>عضوی که ورودی‌ها را بررسی، ایجنت را اجرا و خروجی را برای تصمیم آماده می‌کند؛ به مجوز اجرا نیاز دارد.</FieldHelp></label>
      <label className="block text-sm">نقش لازم برای تصمیم<select className={field} value={stage.decision_role || ''} onChange={event => change({ ...stage, decision_role: event.target.value as FlowStage['decision_role'] || null, finalizer_id: null, finalizer_membership_id: null })}><option value="">نقش اضافه لازم نیست</option><option value="po">مالک محصول (PO)</option><option value="tl">راهبر فنی (TL)</option></select><FieldHelp>اگر تصمیم این مرحله باید با PO یا TL باشد، نقش را مشخص کنید. نقش اضافه لازم نیست یعنی مجوز نهایی‌سازی و مسئول منتخب کافی است.</FieldHelp></label>
      <label className="block text-sm">نهایی‌کننده<select className={field} value={stage.finalizer_id || ''} onChange={event => setPerson('finalizer', event.target.value)}><option value="">انتخاب کنید</option>{options.members.filter(member => agent?.finalizers.includes(member.account_id) && (!stage.decision_role || member.roles.includes(stage.decision_role))).map(member => <option key={member.membership_id} value={member.account_id}>{member.name}</option>)}</select><FieldHelp>عضوی که خروجی منتخب را بررسی و با تصمیم صریح تأیید می‌کند؛ باید مجوز نهایی‌سازی و نقش لازم این مرحله را داشته باشد.</FieldHelp></label>
    </div>
    <p className="text-xs leading-6 text-text-tertiary">فقط اعضای دارای مجوز همین ایجنت قابل انتخاب‌اند. مجوزها از بخش ایجنت‌های تیم تنظیم می‌شوند. پس از جابه‌جایی مراحل، اتصال ورودی‌ها را بازبینی کنید.</p>
    {agent?.input_contract.map(item => <InputBinding key={item.variable} item={item} value={stage.inputs[item.variable]} previous={stages.slice(0, index)} options={options} change={value => { const inputs = { ...stage.inputs }; if (value) inputs[item.variable] = value; else delete inputs[item.variable]; change({ ...stage, inputs }) }} />)}
    </div>
  </details>
}

function FlowEditor({ project, value, options, saved, cancel, refreshOptions, updatingOptions, optionsFailed }: { project: string; value: TeamFlow | null; options: FlowOptions; saved: (value: TeamFlow) => Promise<unknown>; cancel: () => void; refreshOptions: () => unknown; updatingOptions: boolean; optionsFailed: boolean }) {
  const [name, setName] = useState(value?.name || '')
  const [description, setDescription] = useState(value?.description || '')
  const [stages, setStages] = useState<FlowStage[]>(value?.draft_stages || [])
  const [archiving, setArchiving] = useState(false)
  const action = useAction()
  const changed = !value || name !== value.name || description !== value.description || JSON.stringify(stages) !== JSON.stringify(value.draft_stages)
  const save = () => { const body = { name, description, stages, expected_revision: value?.revision || 1 }; void action.run({ id: value?.id, body }, async key => saved(await flowApi.save(project, value?.id || null, body, key))) }
  const publish = () => { if (value) void action.run({ publish: value.id, revision: value.revision }, async key => saved(await flowApi.publish(project, value.id, value.revision, key))) }
  const add = () => setStages([...stages, { key: `step_${crypto.randomUUID().slice(0, 8)}`, title: `مرحلهٔ ${number(stages.length + 1)}`, agent_id: null, executor_id: null, executor_membership_id: null, finalizer_id: null, finalizer_membership_id: null, decision_role: null, inputs: {} }])
  const move = (index: number, offset: number) => { const current = stages[index]; const other = stages[index + offset]; if (!current || !other) return; const result = [...stages]; result[index] = other; result[index + offset] = current; setStages(result) }
  return <FormDialog open wide title={value ? `ویرایش فلو: ${value.name}` : 'ساخت فلو'} description="فلو، ترتیب همکاری اعضا و ایجنت‌ها را مشخص می‌کند. مراحل، مسئولان و ورودی‌ها را تنظیم و پیش‌نویس را ذخیره کنید؛ پس از تکمیل، نسخه‌ای منتشر کنید. انتشار، اجرای خودکار آغاز نمی‌کند و نسخه‌های قبلی را تغییر نمی‌دهد." busy={action.busy} close={cancel}>
    <form aria-label="ویرایش پیش‌نویس فلو" className="space-y-4" onSubmit={event => { event.preventDefault(); save() }}>
    <fieldset disabled={action.busy || value?.archived} className="space-y-4">
      <label className="block text-sm">نام فلو<input required maxLength={120} className={field} value={name} onChange={event => setName(event.target.value)} /><FieldHelp>نامی یکتا در همین پروژه، متناسب با مسیر رسیدگی یا همکاری تیم انتخاب کنید.</FieldHelp></label>
      <label className="block text-sm">توضیح فلو<textarea maxLength={2000} className={field} value={description} onChange={event => setDescription(event.target.value)} /><FieldHelp>مشخص کنید این مسیر برای چه درخواست‌هایی است و پس از طی مراحل چه نتیجه‌ای باید آماده شود.</FieldHelp></label>
      <div className="rounded-xl bg-background-section p-3 text-sm leading-7"><div className="flex flex-wrap items-center justify-between gap-3"><p>{number(stages.length)} مرحله از حداکثر ۳۰ مرحله</p><button type="button" className={button} disabled={updatingOptions} onClick={() => void refreshOptions()}>{updatingOptions ? 'در حال دریافت…' : 'تازه‌سازی اعضا و ایجنت‌ها'}</button></div><p className="text-xs text-text-secondary">{changed ? 'تغییرات ذخیره‌نشده دارید؛ ابتدا پیش‌نویس را ذخیره کنید.' : 'پیش‌نویس ذخیره شده است؛ پس از بررسی مراحل، نسخهٔ تازه منتشر کنید.'}</p></div>
      {optionsFailed && <p role="alert" className="text-sm leading-7">تازه‌سازی اعضا و ایجنت‌ها موفق نبود؛ اطلاعات قبلی و تغییرات شما حفظ شده‌اند. پیش از انتشار دوباره تازه‌سازی کنید.</p>}
      {stages.map((stage, index) => <StageEditor key={stage.key} stage={stage} index={index} stages={stages} options={options} change={next => setStages(stages.map(value => value.key === stage.key ? next : value))} move={offset => move(index, offset)} remove={() => setStages(stages.filter(value => value.key !== stage.key))} />)}
      <button type="button" className={button} disabled={stages.length >= 30} onClick={add}>افزودن مرحله</button>
      <div className="flex flex-wrap gap-3"><button className={primary} disabled={!changed || !name.trim()}>{action.busy ? 'در حال ثبت…' : 'ذخیرهٔ پیش‌نویس'}</button>{value && <button type="button" className={primary} disabled={changed || !stages.length || optionsFailed} onClick={publish}>انتشار نسخهٔ تازه</button>}</div>
    </fieldset>
    {value && !value.archived && <div className="space-y-3"><button type="button" className={button} disabled={action.busy} onClick={() => setArchiving(!archiving)}>بایگانی فلو</button>{archiving && <div className="space-y-3"><p className="text-sm">ویرایش و انتشار تازه متوقف می‌شود؛ نسخه‌های قبلی حفظ می‌شوند.</p><button type="button" className={button} disabled={action.busy} onClick={() => action.run({ archive: value.id, revision: value.revision }, async key => saved(await flowApi.archive(project, value.id, value.revision, key)))}>تأیید بایگانی فلو</button></div>}</div>}
    {action.error && <p role="alert">{action.error}</p>}<button type="button" className={button} disabled={action.busy} onClick={cancel}>بستن ویرایشگر</button>
    </form>
  </FormDialog>
}

function Published({ value }: { value: FlowVersion }) {
  return <section aria-label={`نسخهٔ منتشرشده ${value.version}`} className="space-y-4 rounded-lg bg-background-section p-4"><h3 className="font-semibold">نسخهٔ منتشرشدهٔ {number(value.version)} · {value.name}</h3><p className="text-sm text-text-secondary">{value.description}</p><ol className="m-0 list-none space-y-3 p-0">{value.stage_bindings.map((stage, index) => <li key={stage.key} className="space-y-2 rounded-lg border border-divider-regular p-3"><p className="font-medium">{number(index + 1)}. {stage.title} · {stage.agent_name}</p><p className="text-sm text-text-secondary">اجراکننده: {stage.executor.name} · نهایی‌کننده: {stage.finalizer.name}{stage.decision_role && ` · نقش تصمیم: ${stage.decision_role.toUpperCase()}`}</p><details className="text-xs leading-6 text-text-tertiary"><summary className="cursor-pointer">اتصال ورودی‌ها</summary>{Object.entries(stage.inputs).map(([name, source]) => <p key={name}>{name}: {source.source === 'request' ? 'متن درخواست' : source.source === 'constant' ? `مقدار ثابت: ${JSON.stringify(source.value)}` : `خروجی ${source.output} از ${value.stage_bindings.find(value => value.key === source.stage_key)?.title || source.stage_key}`}</p>)}</details></li>)}</ol><details className="text-xs text-text-tertiary"><summary className="cursor-pointer">شناسهٔ نسخه</summary><p className="mt-2 break-all" dir="ltr">{value.id}</p></details></section>
}

function History({ project, flow }: { project: string; flow: TeamFlow }) {
  const versions = useQuery({ queryKey: ['team-flow-versions', project, flow.id, flow.current_version_id], queryFn: () => flowApi.versions(project, flow.id) })
  const [selected, setSelected] = useState(flow.current_version_id)
  const value = versions.data?.data.find(value => value.id === selected) || flow.published
  return <div className="min-w-0 space-y-4 [overflow-wrap:anywhere]">
    {versions.isPending && <p role="status" className="text-sm">در حال دریافت نسخه‌ها…</p>}
    {versions.isError && <div role="alert" className="space-y-2"><p>دریافت تاریخچه انجام نشد؛ نسخهٔ فعلی در ادامه نمایش داده می‌شود.</p><button className={button} onClick={() => void versions.refetch()}>تلاش دوباره</button></div>}
    {versions.isSuccess && <label className="block max-w-md text-sm">نسخهٔ مورد بررسی<select className={field} value={value?.id || ''} onChange={event => setSelected(event.target.value)}>{versions.data.data.map(version => <option value={version.id} key={version.id}>نسخهٔ {number(version.version)} · {version.id === flow.current_version_id ? 'انتشار فعلی' : 'نسخهٔ تاریخی'}</option>)}</select></label>}
    {value && <><p className="text-xs leading-6 text-text-secondary">منتشرشده در {new Date(value.published_at).toLocaleString('fa-IR')} · تغییر پیش‌نویس، محتوای این نسخه را تغییر نمی‌دهد.</p><Published value={value} /></>}
  </div>
}

function FlowCard({ project, flow, canEdit, edit, remove }: { project: string; flow: TeamFlow; canEdit: boolean; edit: () => void; remove: () => void }) {
  const [inspecting, setInspecting] = useState(false)
  const published = flow.published
  const newerDraft = !flow.archived && !!published && flow.revision > published.source_revision + 1
  return <article className={panel}>
    <header><p className="mb-2 text-xs font-medium text-text-accent">{flow.archived ? 'بایگانی‌شده' : published ? `نسخهٔ منتشرشدهٔ ${number(published.version)}` : 'فقط پیش‌نویس؛ قابل شروع برای درخواست نیست'}</p><h2 className="break-words text-xl font-semibold leading-8">{flow.name}</h2></header>
    {flow.description && <p className="line-clamp-2 whitespace-pre-wrap text-sm leading-7 text-text-secondary">{flow.description}</p>}
    <p className="text-xs leading-6 text-text-tertiary">{published ? `${number(published.stage_bindings.length)} مرحله در نسخهٔ منتشرشده` : 'برای استفاده در درخواست‌ها، فلو باید منتشر شود.'}{flow.draft_stages && ` · ${number(flow.draft_stages.length)} مرحله در پیش‌نویس`}</p>
    {newerDraft && <p className="rounded-lg bg-background-section p-3 text-xs leading-6">پس از انتشار فعلی، پیش‌نویس دوباره ذخیره شده است. درخواست‌ها همچنان نسخهٔ منتخب در تصمیم ورود را استفاده می‌کنند.</p>}
    {published && <ol aria-label="پیش‌نمایش مسیر فلو" className="m-0 flex list-none flex-wrap gap-2 p-0">{published.stage_bindings.slice(0, 3).map((stage, index) => <li key={stage.key} className="max-w-full break-words rounded-lg bg-background-section px-3 py-2 text-xs leading-6">{number(index + 1)}. {stage.title}</li>)}{published.stage_bindings.length > 3 && <li className="px-2 py-2 text-xs leading-6 text-text-tertiary">و {number(published.stage_bindings.length - 3)} مرحلهٔ دیگر</li>}</ol>}
    <div className="flex flex-wrap items-center gap-2">{published && <button className={primary} onClick={() => setInspecting(true)}>مراحل و نسخه‌ها</button>}{canEdit && <>{!flow.archived && <button className={button} onClick={edit}>ویرایش فلو</button>}<button className={`${button} text-text-destructive-secondary`} onClick={remove}>حذف فلو</button></>}</div>
    {published && inspecting && <FormDialog open wide title={`مراحل و نسخه‌های ${flow.name}`} description="نسخهٔ منتشرشده، ایجنت‌ها، اجراکننده و نهایی‌کنندهٔ مراحل را بررسی کنید. این صفحه فقط برای مشاهده است و اجرا را شروع نمی‌کند." close={() => setInspecting(false)}><History project={project} flow={flow} /><button className={`${button} mt-5`} onClick={() => setInspecting(false)}>بستن</button></FormDialog>}
  </article>
}

export default function TeamFlows({ projectId }: { projectId: string }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const cache = useQueryClient()
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const entered = context.data?.current_project?.id === projectId
  const list = useQuery({ queryKey: ['team-flows', workspace, projectId], queryFn: () => flowApi.list(projectId), enabled: entered })
  const [selected, setSelected] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState<TeamFlow | null>(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('active')
  const [sort, setSort] = useState('registered')
  const [page, setPage] = useState(1)
  const options = useQuery({ queryKey: ['team-flow-options', workspace, projectId], queryFn: () => flowApi.options(projectId), enabled: entered && !!list.data?.can_edit && editing })
  useEffect(() => { setSelected(null); setEditing(false); setDeleting(null); setQuery(''); setStatus('active'); setSort('registered'); setPage(1) }, [workspace, projectId])
  const value = list.data?.data.find(flow => flow.id === selected) || null
  const refresh = async () => { const result = await list.refetch(); void cache.invalidateQueries({ queryKey: ['company-projects', workspace, projectId, 'overview'] }); return result }
  const saved = async (flow: TeamFlow) => { const fresh = await refresh(); if (fresh.isError) throw new Error('Refresh failed'); setSelected(flow.id); setEditing(!flow.archived); setQuery(''); setStatus(flow.archived ? 'all' : 'active'); setSort('registered'); const index = fresh.data.data.filter(item => flow.archived || !item.archived).findIndex(item => item.id === flow.id); setPage(Math.floor(Math.max(0, index) / 8) + 1) }
  const values = list.data?.data || []
  const ordered = sort === 'name' ? [...values].sort((a, b) => a.name.localeCompare(b.name, 'fa')) : values
  const filtered = ordered.filter(flow => matchesSearch(query, flow.name, flow.description) && (status === 'all' || (status === 'archived' ? flow.archived : !flow.archived && (status === 'active' || (status === 'published' ? !!flow.current_version_id : !flow.current_version_id)))))
  const results = resultPage(filtered, page)
  const hasFilters = !!query.trim() || status !== 'all' || sort !== 'registered'
  const reset = () => { setQuery(''); setStatus('all'); setSort('registered'); setPage(1) }
  return <DirectoryPage project={projectId} title="فلوهای تیم" description="مسیر همکاری تیم را پیدا کنید؛ مراحل و مسئولان نسخهٔ منتشرشده را ببینید یا پیش‌نویس را برای انتشار بعدی ویرایش کنید." actions={<><button className={directoryButton} disabled={!entered || list.isFetching} onClick={() => void refresh()}>{list.isFetching ? 'در حال تازه‌سازی…' : 'تازه‌سازی'}</button>{entered && list.data?.can_edit && <button className={primary} onClick={() => { setSelected(null); setEditing(true) }}>ساخت فلو</button>}</>}>
    <DirectoryNotice project={projectId} entered={!!entered} loading={context.isPending || (!!entered && list.isPending)} error={context.isError || (!!entered && list.isError)} retry={() => context.isError ? context.refetch() : refresh()} />
    {entered && list.data && <>
      {list.isError && <p role="status" className="text-sm leading-7 text-text-secondary">آخرین فهرست دریافت‌شده نمایش داده می‌شود؛ تازه‌سازی موفق نبوده است.</p>}
      <DirectorySummary items={[{ label: 'کل فلوهای در دسترس', count: values.length }, { label: 'منتشرشده و غیربایگانی', count: values.filter(flow => !flow.archived && !!flow.current_version_id).length }, { label: 'فقط پیش‌نویس', count: values.filter(flow => !flow.archived && !flow.current_version_id).length }, { label: 'بایگانی‌شده', count: values.filter(flow => flow.archived).length }]} />
      <DirectoryToolbar query={query} change={value => { setQuery(value); setPage(1) }} placeholder="نام یا توضیح فلو" filtered={filtered.length} total={values.length} hasFilters={hasFilters} reset={reset}>
        <label className="min-w-0 flex-1 basis-48 text-sm">وضعیت فلو<select className={directoryField} value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="active">همهٔ غیربایگانی‌ها</option><option value="published">منتشرشده</option><option value="draft">فقط پیش‌نویس</option><option value="archived">بایگانی‌شده</option><option value="all">همهٔ فلوها</option></select></label>
        <label className="min-w-0 flex-1 basis-36 text-sm">ترتیب نمایش<select className={directoryField} value={sort} onChange={event => { setSort(event.target.value); setPage(1) }}><option value="registered">ترتیب ثبت</option><option value="name">نام فلو</option></select></label>
      </DirectoryToolbar>
      {editing && list.data.can_edit && (selected && !value ? <FormDialog open title="فلو در دسترس نیست" description="فلوی انتخاب‌شده دیگر در فهرست در دسترس نیست. فهرست را تازه کنید و دوباره انتخاب کنید." close={() => setEditing(false)}><button className={button} onClick={() => setEditing(false)}>بستن</button></FormDialog> : options.data ? <FlowEditor key={`${workspace}:${value?.id || 'new'}:${value?.revision || 1}`} project={projectId} value={value} options={options.data} saved={saved} cancel={() => setEditing(false)} refreshOptions={() => options.refetch()} updatingOptions={options.isFetching} optionsFailed={options.isError} /> : <FormDialog open title={selected ? 'ویرایش فلو' : 'ساخت فلو'} description="ایجنت‌ها و اعضای مجاز پروژه برای تنظیم مراحل دریافت می‌شوند." close={() => setEditing(false)}><p role={options.isError ? 'alert' : 'status'}>{options.isError ? 'دریافت ایجنت‌ها و اعضا انجام نشد.' : 'در حال دریافت مسئولان…'}</p>{options.isError && <button className={button} onClick={() => options.refetch()}>تلاش دوباره</button>}</FormDialog>)}
      {!results.items.length ? <DirectoryEmpty filtered={hasFilters && !!values.length} title="فلویی برای نمایش وجود ندارد" reset={reset}>پس از ثبت ایجنت‌ها و تعیین مجوزها، مسیر همکاری را بسازید و نسخهٔ مناسب آن را منتشر کنید.</DirectoryEmpty> : <ul aria-label="فهرست فلوهای تیم" className="m-0 list-none space-y-4 p-0">{results.items.map(flow => <li key={`${workspace}:${flow.id}:${flow.revision}`} className="min-w-0"><FlowCard project={projectId} flow={flow} canEdit={list.data.can_edit} edit={() => { setSelected(flow.id); setEditing(true) }} remove={() => setDeleting(flow)} /></li>)}</ul>}
      <DirectoryPagination value={results} change={setPage} />
      <div className="flex flex-wrap gap-4 text-sm text-text-accent"><Link href={`/projects/${projectId}/team-agents`}>ایجنت‌ها و مجوزهای تیم ←</Link><Link href={`/projects/${projectId}/team-runs`}>اجرای تیمی و پیشرفت درخواست‌ها ←</Link></div>
      <p className="text-xs leading-6 text-text-tertiary">ساخت یا انتشار فلو، اجرا را شروع نمی‌کند. شروع رسیدگی از درخواست پذیرفته‌شده و ادامهٔ مراحل با تصمیم مسئول تعیین‌شده انجام می‌شود.</p>
    </>}
    {deleting && list.data?.can_edit && <DeleteTeamEntity project={projectId} kind="flow" value={deleting} close={() => setDeleting(null)} deleted={async () => { await refresh(); setEditing(false); setSelected(null) }} />}
  </DirectoryPage>
}
