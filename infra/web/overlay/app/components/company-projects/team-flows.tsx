'use client'

import type { AgentInput } from '@/service/company-agents'
import type { FlowInput, FlowOptions, FlowStage, FlowVersion, TeamFlow } from '@/service/company-flows'
import { useQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { flowApi } from '@/service/company-flows'
import { projectApi } from '@/service/company-projects'
import FormDialog, { FieldHelp } from './form-dialog'

const panel = 'space-y-4 rounded-2xl border border-divider-regular bg-background-default p-5'
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
  const agent = options.agents.find(value => value.id === stage.agent_id)
  const setPerson = (prefix: 'executor' | 'finalizer', id: string) => change({ ...stage, [`${prefix}_id`]: id || null, [`${prefix}_membership_id`]: options.members.find(member => member.account_id === id)?.membership_id || null })
  return <section aria-label={`مرحله ${index + 1}`} className="space-y-4 rounded-xl border border-divider-regular p-4">
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
  </section>
}

function FlowEditor({ project, value, options, saved, cancel }: { project: string; value: TeamFlow | null; options: FlowOptions; saved: (value: TeamFlow) => Promise<unknown>; cancel: () => void }) {
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
  return <FormDialog open wide title={value ? 'ویرایش فلو' : 'ساخت فلو'} description="فلو، ترتیب همکاری اعضا و ایجنت‌ها را مشخص می‌کند. مراحل، مسئولان و ورودی‌ها را تنظیم و پیش‌نویس را ذخیره کنید؛ پس از تکمیل، نسخه‌ای منتشر کنید. انتشار، اجرای خودکار آغاز نمی‌کند و نسخه‌های قبلی را تغییر نمی‌دهد." busy={action.busy} close={cancel}>
    <form aria-label="ویرایش پیش‌نویس فلو" className="space-y-4" onSubmit={event => { event.preventDefault(); save() }}>
    <fieldset disabled={action.busy || value?.archived} className="space-y-4">
      <label className="block text-sm">نام فلو<input required maxLength={120} className={field} value={name} onChange={event => setName(event.target.value)} /><FieldHelp>نامی یکتا در همین پروژه، متناسب با مسیر رسیدگی یا همکاری تیم انتخاب کنید.</FieldHelp></label>
      <label className="block text-sm">توضیح فلو<textarea maxLength={2000} className={field} value={description} onChange={event => setDescription(event.target.value)} /><FieldHelp>مشخص کنید این مسیر برای چه درخواست‌هایی است و پس از طی مراحل چه نتیجه‌ای باید آماده شود.</FieldHelp></label>
      {stages.map((stage, index) => <StageEditor key={stage.key} stage={stage} index={index} stages={stages} options={options} change={next => setStages(stages.map(value => value.key === stage.key ? next : value))} move={offset => move(index, offset)} remove={() => setStages(stages.filter(value => value.key !== stage.key))} />)}
      <button type="button" className={button} disabled={stages.length >= 30} onClick={add}>افزودن مرحله</button>
      <div className="flex flex-wrap gap-3"><button className={primary} disabled={!changed}>ذخیرهٔ پیش‌نویس</button>{value && <button type="button" className={primary} disabled={changed || !stages.length} onClick={publish}>انتشار نسخهٔ تازه</button>}</div>
    </fieldset>
    {value && !value.archived && <div className="space-y-3"><button type="button" className={button} disabled={action.busy} onClick={() => setArchiving(!archiving)}>بایگانی فلو</button>{archiving && <div className="space-y-3"><p className="text-sm">ویرایش و انتشار تازه متوقف می‌شود؛ نسخه‌های قبلی حفظ می‌شوند.</p><button type="button" className={button} disabled={action.busy} onClick={() => action.run({ archive: value.id, revision: value.revision }, async key => saved(await flowApi.archive(project, value.id, value.revision, key)))}>تأیید بایگانی فلو</button></div>}</div>}
    {action.error && <p role="alert">{action.error}</p>}<button type="button" className={button} disabled={action.busy} onClick={cancel}>بستن ویرایشگر</button>
    </form>
  </FormDialog>
}

function Published({ value }: { value: FlowVersion }) {
  return <section aria-label={`نسخهٔ منتشرشده ${value.version}`} className="space-y-4 rounded-lg bg-background-section p-4"><h3 className="font-semibold">نسخهٔ منتشرشدهٔ {number(value.version)} · {value.name}</h3><p className="text-sm text-text-secondary">{value.description}</p><ol className="space-y-3">{value.stage_bindings.map((stage, index) => <li key={stage.key} className="space-y-2 rounded-lg border border-divider-regular p-3"><p className="font-medium">{number(index + 1)}. {stage.title} · {stage.agent_name}</p><p className="text-sm text-text-secondary">اجراکننده: {stage.executor.name} · نهایی‌کننده: {stage.finalizer.name}{stage.decision_role && ` · نقش تصمیم: ${stage.decision_role.toUpperCase()}`}</p><details className="text-xs leading-6 text-text-tertiary"><summary className="cursor-pointer">اتصال ورودی‌ها</summary>{Object.entries(stage.inputs).map(([name, source]) => <p key={name}>{name}: {source.source === 'request' ? 'متن درخواست' : source.source === 'constant' ? `مقدار ثابت: ${JSON.stringify(source.value)}` : `خروجی ${source.output} از ${value.stage_bindings.find(value => value.key === source.stage_key)?.title || source.stage_key}`}</p>)}</details></li>)}</ol><details className="text-xs text-text-tertiary"><summary className="cursor-pointer">شناسهٔ نسخه</summary><p className="mt-2 break-all" dir="ltr">{value.id}</p></details></section>
}

function History({ project, flow }: { project: string; flow: TeamFlow }) {
  const versions = useQuery({ queryKey: ['team-flow-versions', project, flow.id, flow.current_version_id], queryFn: () => flowApi.versions(project, flow.id) })
  const [selected, setSelected] = useState(flow.current_version_id)
  const value = versions.data?.data.find(value => value.id === selected) || flow.published
  return <div className="space-y-4">{versions.isError && <p role="alert">دریافت تاریخچه انجام نشد.</p>}<div className="flex flex-wrap gap-2" aria-label="نسخه‌های فلو">{versions.data?.data.map(version => <button type="button" className={button} aria-pressed={value?.id === version.id} key={version.id} onClick={() => setSelected(version.id)}>نمایش نسخهٔ {number(version.version)}</button>)}</div>{value && <Published value={value} />}</div>
}

export default function TeamFlows({ projectId }: { projectId: string }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const entered = context.data?.current_project?.id === projectId
  const list = useQuery({ queryKey: ['team-flows', workspace, projectId], queryFn: () => flowApi.list(projectId), enabled: entered })
  const options = useQuery({ queryKey: ['team-flow-options', workspace, projectId], queryFn: () => flowApi.options(projectId), enabled: entered && !!list.data?.can_edit })
  const [selected, setSelected] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const value = list.data?.data.find(flow => flow.id === selected) || null
  const saved = async (flow: TeamFlow) => { const fresh = await list.refetch(); if (fresh.isError) throw new Error('Refresh failed'); setSelected(flow.id); setEditing(!flow.archived) }
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto max-w-5xl space-y-6">
    <Link href={`/projects/${projectId}`} className="text-sm text-text-accent">نمای کلی پروژه ←</Link>
    <header><h1 className="text-3xl font-bold">فلوهای تیم</h1><p className="mt-3 text-sm leading-7 text-text-secondary">ترتیب مراحل، ایجنت‌ها و مسئول هر مرحله را مشخص کنید. نسخهٔ منتشرشده، برنامهٔ ثابت همکاری تیم خواهد بود.</p></header>
    {!entered ? <p role="status">ابتدا وارد فضای همین پروژه شوید.</p> : list.isSuccess ? <>
      {list.data.can_edit && <div className="flex flex-wrap gap-3"><button className={primary} onClick={() => { setSelected(null); setEditing(true) }}>ساخت فلو</button><Link className={button} href={`/projects/${projectId}/team-agents`}>ایجنت‌ها و مجوزهای تیم</Link><button className={button} disabled={options.isFetching} onClick={() => options.refetch()}>دریافت مسئولان تازه</button></div>}
      {editing && list.data.can_edit && (options.isSuccess ? <FlowEditor key={`${workspace}:${value?.id || 'new'}:${value?.revision || 1}`} project={projectId} value={value} options={options.data} saved={saved} cancel={() => setEditing(false)} /> : <FormDialog open title={selected ? 'ویرایش فلو' : 'ساخت فلو'} description="ایجنت‌ها و اعضای مجاز پروژه برای تنظیم مراحل دریافت می‌شوند." close={() => setEditing(false)}><p role={options.isError ? 'alert' : 'status'}>{options.isError ? 'دریافت ایجنت‌ها و اعضا انجام نشد.' : 'در حال دریافت مسئولان…'}</p>{options.isError && <button className={button} onClick={() => options.refetch()}>تلاش دوباره</button>}</FormDialog>)}
      {!list.data.data.length && <p className={panel}>هنوز فلویی برای نمایش وجود ندارد.</p>}
      {list.data.data.map(flow => <article key={flow.id} className={panel}><header className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">{flow.name}{flow.archived && ' · بایگانی‌شده'}</h2>{list.data.can_edit && !flow.archived && <button className={button} onClick={() => { setSelected(flow.id); setEditing(true) }}>ویرایش فلو</button>}</header><p className="text-sm text-text-secondary">{flow.description}</p>{flow.published ? <History key={flow.current_version_id} project={projectId} flow={flow} /> : <p className="text-sm text-text-tertiary">پیش‌نویس · هنوز منتشر نشده است</p>}</article>)}
    </> : <p role={list.isError ? 'alert' : 'status'}>{list.isError ? 'دریافت فلوها انجام نشد.' : 'در حال دریافت فلوها…'}</p>}
    <button className={button} disabled={!entered || list.isFetching} onClick={() => { setEditing(false); void list.refetch() }}>دریافت فهرست تازهٔ فلوها</button>
  </div></main>
}
