'use client'

import RuntimeModelPicker from './runtime-model-picker'
import type { AgentInput } from '@/service/company-agents'
import type { AvailableRequest, StageArtifact, TeamInstance, TeamStage } from '@/service/company-stages'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect, useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { useSearchParams } from '@/next/navigation'
import { stageStates as states, teamStageHref } from '@/utils/company-team-work'
import { projectApi } from '@/service/company-projects'
import { stageApi } from '@/service/company-stages'
import TeamRecovery from './team-recovery'
import FormDialog from './form-dialog'

const panel = 'space-y-4 rounded-2xl border border-divider-regular bg-background-default p-5'
const button = 'rounded-lg border border-divider-regular px-4 py-2 text-sm disabled:opacity-50'
const primary = `${button} bg-components-button-primary-bg text-components-button-primary-text`
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const num = (value: number) => value.toLocaleString('fa-IR')

const text = (value: unknown): string => typeof value === 'string' ? value : JSON.stringify(value, null, 2) ?? ''

function useAction() {
  const operation = useRef<{ payload: string; key: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async (data: unknown, action: (key: string) => Promise<unknown>) => {
    if (busy) return
    const payload = JSON.stringify(data)
    if (operation.current?.payload !== payload) operation.current = { payload, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try { await action(operation.current.key); operation.current = null }
    catch { setError('اقدام انجام نشد. مجوز، تصمیم ورود، اندازه و نوع ورودی را بررسی کنید؛ اگر مرحله تغییر کرده است، وضعیت تازه را دریافت کنید.') }
    finally { setBusy(false) }
  }
  return { busy, error, run }
}

function Input({ item, value, change }: { item: AgentInput; value: unknown; change: (value: unknown) => void }) {
  return <label className="block text-sm">{item.label}{item.required && ' *'}{item.type === 'checkbox' ? <input className="ms-3" type="checkbox" checked={Boolean(value)} onChange={event => change(event.target.checked)} /> : item.type === 'select' ? <select className={field} required={item.required} value={String(value ?? '')} onChange={event => change(event.target.value)}><option value="">انتخاب کنید</option>{item.options.map(option => <option key={option}>{option}</option>)}</select> : item.type === 'number' ? <input className={field} type="number" step="any" required={item.required} value={String(value ?? '')} onChange={event => change(event.target.value === '' ? '' : Number(event.target.value))} /> : <textarea className={field} required={item.required} maxLength={item.max_length || undefined} value={String(value ?? '')} onChange={event => change(event.target.value)} />}</label>
}

type Act = (action: string, body: Record<string, unknown>, key: string) => Promise<void>

function Feedback({ value, act }: { value: TeamStage; act: Act }) {
  const current = value.artifacts.filter(item => item.round === value.round && item.input_digest === value.input_digest)
  const textual = value.binding.input_contract.filter(item => ['text-input', 'paragraph'].includes(item.type))
  const [inputs, setInputs] = useState(value.editable_inputs)
  const [parent, setParent] = useState('')
  const [message, setMessage] = useState('')
  const [variable, setVariable] = useState(current.length ? textual[0]?.variable || '' : '')
  const action = useAction()
  const body = { artifact_id: parent || null, message, inputs, feedback_variable: variable || null }
  return <form className={panel} aria-label="بازخورد و اصلاح ورودی" onSubmit={event => { event.preventDefault(); void action.run(body, key => act('feedback', body, key)) }}>
    <h3 className="font-semibold">بازخورد و اصلاح ورودی</h3><p className="text-sm leading-7">بازخورد دور تازه‌ای می‌سازد و اجرای بعدی با اقدام صریح اجراکننده آغاز می‌شود. بازخورد و خروجی مبنا به ورودی متنی منتخب می‌رسند؛ پیش از اجرا، ورودی نهایی را بررسی کنید.</p>
    <fieldset className="space-y-4" disabled={action.busy}>
      <label className="block text-sm">خروجی مبنای بازخورد<select className={field} required={['awaiting_feedback', 'awaiting_decision'].includes(value.state)} value={parent} onChange={event => setParent(event.target.value)}><option value="">بدون خروجی مبنا</option>{current.map(item => <option key={item.id} value={item.id}>نسخهٔ {num(item.version)} · {item.kind === 'human' ? 'ویرایش انسانی' : 'خروجی اجرا'}</option>)}</select></label>
      <label className="block text-sm">متن بازخورد<textarea className={field} required maxLength={8000} value={message} onChange={event => setMessage(event.target.value)} /></label>
      {value.binding.input_contract.map(item => <Input key={item.variable} item={item} value={inputs[item.variable]} change={next => setInputs({ ...inputs, [item.variable]: next })} />)}
      <label className="block text-sm">ورودی متنی دریافت‌کنندهٔ بازخورد<select className={field} required={!!parent && !!textual.length} value={variable} onChange={event => setVariable(event.target.value)}><option value="">فقط ثبت علت اصلاح مقادیر</option>{textual.map(item => <option key={item.variable} value={item.variable}>{item.label}</option>)}</select></label>
      {!textual.length && <p className="text-sm">این ایجنت ورودی متنی ندارد؛ اصلاح را در مقادیر ورودی اعمال کنید.</p>}<button className={primary}>ثبت بازخورد و دور تازه</button>
    </fieldset>{action.error && <p role="alert">{action.error}</p>}
  </form>
}

function HumanEdit({ artifact, act, close }: { artifact: StageArtifact; act: Act; close: () => void }) {
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(Object.entries(artifact.content).map(([name, value]) => [name, text(value)])))
  const [reason, setReason] = useState('')
  const [parseError, setParseError] = useState(false)
  const action = useAction()
  const save = () => {
    try {
      const content = Object.fromEntries(Object.entries(values).map(([name, value]) => [name, typeof artifact.content[name] === 'string' ? value : JSON.parse(value)]))
      const body = { artifact_id: artifact.id, content, reason }
      setParseError(false); void action.run(body, async key => { await act('edit_output', body, key); close() })
    }
    catch { setParseError(true) }
  }
  return <form aria-label="ویرایش انسانی خروجی" className="space-y-4" onSubmit={event => { event.preventDefault(); save() }}><fieldset disabled={action.busy} className="space-y-4">{Object.entries(values).map(([name, value]) => <label className="block text-sm" key={name}>ویرایش {name}{typeof artifact.content[name] !== 'string' && ' (دادهٔ ساختاریافته)'}<textarea className={field} value={value} onChange={event => setValues({ ...values, [name]: event.target.value })} /></label>)}<label className="block text-sm">علت ویرایش انسانی<textarea className={field} required maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></label><button className={primary}>ذخیرهٔ ویرایش انسانی</button><button className={`${button} ms-3`} type="button" onClick={close}>بستن ویرایش</button></fieldset>{parseError && <p role="alert">ساختار دادهٔ خروجی معتبر نیست.</p>}{action.error && <p role="alert">{action.error}</p>}</form>
}

function StageContent({ value, act }: { value: TeamStage; act: Act }) {
  const [modelConnection, setModelConnection] = useState('')
  const runBody = value.runtime_model ? { model_connection_id: modelConnection } : {}
  const [editing, setEditing] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const action = useAction()
  const person = (id: string) => id === value.binding.executor.account_id ? value.binding.executor.name : id === value.binding.finalizer.account_id ? value.binding.finalizer.name : id
  const selected = value.artifacts.find(item => item.id === value.selected_artifact_id)
  return <div className="space-y-5">
    <section className={panel}><h2 className="text-xl font-semibold">{value.binding.title} · {value.binding.agent_name}</h2><p role="status">{states[value.state]} · دور {num(value.round)}</p><p className="text-sm leading-7">اجراکننده: {value.binding.executor.name} · نهایی‌کننده: {value.binding.finalizer.name}</p>
      {!value.intake_valid && <p role="alert">تصمیم ورود این اجرا دیگر معتبر نیست؛ سابقه حفظ شده و ادامه به تصمیم تازهٔ PO نیاز دارد.</p>}{value.input_error && value.intake_valid && <p role="status">{value.input_error}</p>}
      <details open className="space-y-3"><summary className="cursor-pointer font-medium">ورودی نهایی مرحله</summary>{Object.entries(value.preview_inputs).map(([name, content]) => <div key={name}><h4 className="text-sm">{value.binding.input_contract.find(item => item.variable === name)?.label || name}</h4><pre className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-background-section p-3 font-sans text-sm leading-7">{text(content)}</pre></div>)}</details>
      {value.runtime_model && value.actions.includes('run') && <RuntimeModelPicker value={modelConnection} onChange={setModelConnection} capabilities={value.runtime_model.capabilities} />}
      <div className="flex flex-wrap gap-3">{value.actions.includes('run') && <button disabled={action.busy} className={primary} onClick={() => action.run({ run: value.id, ...runBody }, key => act('run', runBody, key))}>اجرا با این ورودی‌ها</button>}{value.actions.includes('retry') && <button disabled={action.busy} className={button} onClick={() => action.run({ retry: value.id }, key => act('retry', {}, key))}>آماده‌سازی تلاش مجدد</button>}</div>{action.error && <p role="alert">{action.error}</p>}
    </section>
    {!!value.handoffs.length && <section className={panel} aria-label="خروجی تحویلی از مراحل قبل"><h3 className="text-lg font-semibold">خروجی تحویلی از مراحل قبل</h3><p className="text-sm leading-7">فقط بخش مورد نیاز از خروجی منتخب و نهایی‌شده نمایش داده می‌شود.</p>{value.handoffs.map(item => <article className="space-y-2 border-t border-divider-regular pt-3" key={item.input}><p className="font-medium">{item.stage_title} · نسخهٔ {num(item.version)} · {item.consumed ? 'در ورودی این مرحله ثبت شده' : 'آمادهٔ دریافت در این مرحله'}</p><p className="text-sm">خروجی {item.output} ← ورودی {value.binding.input_contract.find(input => input.variable === item.input)?.label || item.input}</p><pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7">{text(item.content)}</pre><p className="text-xs leading-6">نهایی‌کننده: {person(item.finalized_by)} · {new Date(item.finalized_at).toLocaleString('fa-IR')}</p><details><summary className="cursor-pointer text-sm">شناسه‌های قابل پیگیری تحویل</summary><p className="break-all text-xs leading-7">خروجی: <bdi>{item.artifact_id}</bdi><br />تصمیم: <bdi>{item.decision_id}</bdi><br />اثر انگشت: <bdi>{item.digest}</bdi></p></details></article>)}</section>}
    {value.actions.includes('revalidate') && <form className={panel} aria-label="بررسی مجدد ورودی مرحله" onSubmit={event => { event.preventDefault(); void action.run({ revalidate: value.id, reason }, key => act('revalidate', { reason }, key)) }}><h3 className="font-semibold">بررسی مجدد ورودی مرحله</h3><p className="text-sm leading-7">ورودی تازه و پیش‌نیازها را بررسی کنید. این اقدام فقط مرحله را آماده می‌کند؛ اجرا با انتخاب بعدی شما است و تأیید قدیمی خروجی برنمی‌گردد.</p><label className="block text-sm">علت بررسی مجدد<textarea required maxLength={2000} className={field} value={reason} onChange={event => setReason(event.target.value)} /></label><button disabled={action.busy} className={primary}>تأیید ورودی تازه و آماده‌سازی مرحله</button></form>}
    {value.actions.includes('feedback') && <Feedback key={value.revision} value={value} act={act} />}
    <section className={panel} aria-label="خروجی‌های مرحله"><h3 className="text-lg font-semibold">خروجی‌ها و ویرایش‌های انسانی</h3><p className="text-sm leading-7">موفقیت اجرا خروجی پیش‌نویس می‌سازد. فقط خروجی منتخب و نهایی‌شده به مرحلهٔ بعد می‌رسد.</p>{!value.artifacts.length && <p className="text-sm">هنوز خروجی ثبت نشده است.</p>}{value.artifacts.map(item => {
      const current = item.round === value.round && item.input_digest === value.input_digest
      return <article key={item.id} className="space-y-3 rounded-lg border border-divider-regular p-4"><h4 className="font-semibold">نسخهٔ {num(item.version)} · دور {num(item.round)} · {item.kind === 'human' ? 'ویرایش انسانی' : 'خروجی اجرا'}{!current && ' · دور قبلی'}{selected?.id === item.id && ' · منتخب'}</h4><p className="break-all text-xs text-text-tertiary">ثبت‌کننده: {person(item.author_id)}</p>{Object.entries(item.content).map(([name, content]) => <div key={name}><p className="text-sm font-medium">{name}</p><pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7">{text(content)}</pre></div>)}{item.reason && <p className="text-sm">علت ویرایش: {item.reason}</p>}
        {current && <div className="flex flex-wrap gap-3">{value.actions.includes('edit_output') && <button className={button} onClick={() => setEditing(editing === item.id ? null : item.id)}>ویرایش انسانی این خروجی</button>}{value.actions.includes('request_decision') && <button disabled={action.busy} className={button} onClick={() => action.run({ select: item.id }, key => act('request_decision', { artifact_id: item.id }, key))}>انتخاب این خروجی برای تصمیم نهایی</button>}</div>}{editing === item.id && current && <HumanEdit artifact={item} act={act} close={() => setEditing(null)} />}
      </article>
    })}</section>
    {value.actions.includes('finalize') && selected && <form aria-label="نهایی‌سازی انسانی مرحله" className={panel} onSubmit={event => { event.preventDefault(); void action.run({ finalize: selected.id, reason }, key => act('finalize', { artifact_id: selected.id, reason }, key)) }}><h3 className="font-semibold">تصمیم نهایی برای خروجی منتخب نسخهٔ {num(selected.version)}</h3><label className="block text-sm">علت نهایی‌سازی<textarea required maxLength={2000} className={field} value={reason} onChange={event => setReason(event.target.value)} /></label><button disabled={action.busy} className={primary}>نهایی‌سازی این خروجی</button></form>}
    <details className={panel}><summary className="cursor-pointer">تاریخچهٔ تلاش‌ها، بازخوردها و تصمیم‌ها</summary><p className="text-sm">{num(value.attempts.length)} تلاش فنی · {num(value.feedback.length)} بازخورد انسانی</p>{value.attempts.map(item => <p className="text-sm" key={item.attempt_id}>دور {num(item.round)} · {states[item.status] || item.status} · {person(item.actor_id)}</p>)}{value.feedback.map(item => <p className="whitespace-pre-wrap text-sm leading-7" key={item.id}>بازخورد دور {num(item.round)} · {person(item.author_id)}: {item.message}</p>)}{value.decisions.map(item => <p className="text-sm leading-7" key={item.id}>نهایی‌سازی توسط {person(item.actor_id)}: {item.reason}</p>)}</details>
  </div>
}

function StagePanel({ project, instance, stage, title, changed, close }: { project: string; instance: string; stage: string; title: string; changed: () => Promise<unknown>; close: () => void }) {
  const [busy, setBusy] = useState(false)
  const query = useQuery({ queryKey: ['team-stage', project, instance, stage], queryFn: () => stageApi.detail(project, instance, stage), refetchInterval: query => query.state.data?.state === 'running' ? 2000 : false })
  const act: Act = async (action, data, key) => {
    setBusy(true)
    try {
      if (action === 'revalidate') await stageApi.control(project, instance, stage, action, { ...data, expected_revision: query.data!.revision }, key)
      else await stageApi.act(project, instance, stage, action, { ...data, expected_revision: query.data!.revision }, key)
      const result = await query.refetch(); await changed()
      if (result.isError) throw new Error('Refresh failed')
    }
    finally { setBusy(false) }
  }
  return <FormDialog open wide title="جزئیات مرحلهٔ اجرای تیمی" description="ورودی‌ها و مسئولان همین مرحله را بررسی کنید، ایجنت را اجرا کنید و خروجی را برای تصمیم انسانی آماده کنید. بازخوردها، ویرایش‌ها و تاریخچه در همین دیالوگ در دسترس‌اند." busy={busy} close={close}>
    <section aria-label="جزئیات مرحله" className="space-y-4">
      <h2 className="text-lg font-semibold">درخواست: {title}</h2>
      <fieldset disabled={busy} className="space-y-4">
        {query.isSuccess ? <StageContent key={query.data.revision} value={query.data} act={act} /> : <p role={query.isError ? 'alert' : 'status'}>{query.isError ? 'دریافت محتوای مرحله انجام نشد؛ مجوز ایجنت و پروژه را بررسی کنید.' : 'در حال دریافت مرحله…'}</p>}
      </fieldset>
      <div className="flex flex-wrap justify-end gap-3"><button className={button} disabled={busy || query.isFetching} onClick={() => query.refetch()}>دریافت وضعیت تازهٔ مرحله</button><button type="button" className={button} disabled={busy} onClick={close}>بستن</button></div>
    </section>
  </FormDialog>
}

export default function TeamRuns({ projectId }: { projectId: string }) {
  const cache = useQueryClient()
  const queryStageRefresh = () => cache.invalidateQueries({ queryKey: ['team-stage'] })
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const params = useSearchParams()
  const linkedInstance = params.get('instance'), linkedStage = params.get('stage'), linkedRequest = params.get('request')
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const entered = context.data?.current_project?.id === projectId
  const list = useQuery({ queryKey: ['team-instances', workspace, projectId], queryFn: () => stageApi.list(projectId), enabled: entered })
  const [selection, setSelection] = useState<{ instance: string; stage: string } | null>(null)
  const [controlInstance, setControlInstance] = useState<string | null>(null)
  const [creating, setCreating] = useState<AvailableRequest | null>(null)
  useEffect(() => { setSelection(linkedInstance && linkedStage ? { instance: linkedInstance, stage: linkedStage } : null); setControlInstance(null); setCreating(null) }, [linkedInstance, linkedStage, projectId, workspace])
  const action = useAction()
  const refresh = async () => { const result = await list.refetch(); if (result.isError) throw new Error('Refresh failed') }
  const choose = (value: TeamInstance) => { const first = value.stages.find(stage => stage.state !== 'completed') || value.stages[0]; setControlInstance(null); if (first) setSelection({ instance: value.id, stage: first.id }) }
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto max-w-5xl space-y-6"><Link className="text-sm text-text-accent" href={`/projects/${projectId}`}>نمای کلی پروژه ←</Link><header><h1 className="text-3xl font-bold">اجرای تیمی</h1><p className="mt-3 text-sm leading-7 text-text-secondary">مرحلهٔ خود را اجرا کنید، بازخورد بدهید و خروجی را برای تصمیم انسانی آماده کنید.</p></header>
    {!entered ? <p role="status">ابتدا وارد فضای همین پروژه شوید.</p> : list.isSuccess ? <>
      {!!list.data.available_requests.length && <section className={panel}><h2 className="text-lg font-semibold">درخواست‌های آمادهٔ ورود</h2>{list.data.available_requests.map(request => <div key={request.id} className="flex flex-wrap items-center justify-between gap-3"><p>{request.title}</p><button className={button} disabled={action.busy} onClick={() => setCreating(request)}>ایجاد اجرای تیمی</button></div>)}<p className="text-xs leading-6 text-text-tertiary">ایجاد پرونده، ایجنت را اجرا نمی‌کند؛ شروع هر مرحله با مسئول مجاز آن است.</p></section>}{action.error && <p role="alert">{action.error}</p>}
      {creating && <FormDialog open title="ایجاد اجرای تیمی" description="برای این درخواست، پروندهٔ اجرا بر اساس نسخهٔ فلویی که PO تأیید کرده ساخته می‌شود. ورودی‌ها و مسئولان از همان نسخه گرفته می‌شوند؛ ایجاد پرونده، ایجنت را اجرا نمی‌کند." busy={action.busy} error={action.error} close={() => setCreating(null)}>
        <form className="space-y-4" onSubmit={event => { event.preventDefault(); void action.run(creating, async key => { const value = await stageApi.create(projectId, creating, key); await refresh(); choose(value); setCreating(null) }) }}>
          <p className="text-sm leading-7">درخواست منتخب: <strong>{creating.title}</strong></p>
          <p className="text-xs leading-6 text-text-tertiary">پس از ایجاد، مرحلهٔ خود را باز کنید و ورودی‌ها را پیش از اجرا بررسی کنید.</p>
          <div className="flex justify-end gap-3"><button type="button" className={button} disabled={action.busy} onClick={() => setCreating(null)}>انصراف</button><button className={primary} disabled={action.busy}>{action.busy ? 'در حال ایجاد…' : 'ایجاد اجرای تیمی'}</button></div>
        </form>
      </FormDialog>}
      <section aria-label="اجراهای تیمی" className="space-y-4">{!list.data.data.length && <p className={panel}>هنوز اجرای تیمی ایجاد نشده است؛ درخواست باید تأیید ورود معتبر داشته باشد.</p>}{list.data.data.filter(value => !linkedRequest || value.request_id === linkedRequest).map(value => <article className={panel} key={value.id}><h2 className="text-xl font-semibold">{value.title}</h2><p className="text-sm">{num(value.completed_stages)} از {num(value.total_stages)} مرحله نهایی شده · مسئول فعلی: {value.responsibility.person?.name || (value.responsibility.kind === 'po' ? 'مالک محصول' : value.responsibility.kind === 'cancelled' ? 'فرایند لغو شده است' : 'فرایند تمام شده است')}</p>{value.responsibility.reason && <p className="text-sm">{value.responsibility.reason}</p>}{!value.intake_valid && !value.cancellation && <p className="text-sm">تصمیم ورود نیاز به بررسی مجدد دارد.</p>}<ol className="flex flex-wrap gap-3">{value.stages.map(stage => <li key={stage.id}><Link className={`${button} inline-block`} aria-current={selection?.stage === stage.id ? 'step' : undefined} href={teamStageHref(projectId, value.id, stage.id)} onClick={event => { if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return; event.preventDefault(); setControlInstance(null); setSelection({ instance: value.id, stage: stage.id }) }}>{stage.title} · {states[stage.state]}</Link></li>)}</ol><button className={button} onClick={() => { setSelection(null); setControlInstance(value.id) }}>بازبینی و بازیابی این فرایند</button></article>)}</section>
      {controlInstance && <TeamRecovery key={`${workspace}:${controlInstance}`} projectId={projectId} instanceId={controlInstance} changed={async () => { await refresh(); await queryStageRefresh() }} close={() => setControlInstance(null)} />}
      {selection && <StagePanel key={`${workspace}:${selection.instance}:${selection.stage}`} project={projectId} instance={selection.instance} stage={selection.stage} title={list.data.data.find(value => value.id === selection.instance)?.title || 'در حال دریافت اطلاعات'} changed={refresh} close={() => setSelection(null)} />}
    </> : <p role={list.isError ? 'alert' : 'status'}>{list.isError ? 'دریافت اجراها انجام نشد.' : 'در حال دریافت اجراها…'}</p>}
    <div className="flex flex-wrap gap-3"><button className={button} disabled={!entered || list.isFetching} onClick={() => list.refetch()}>تازه‌سازی اجراهای تیمی</button><Link className={button} href={`/projects/${projectId}/requests`}>درخواست‌های پروژه</Link><Link className={button} href={`/projects/${projectId}/inbox`}>اقدام‌های من و وضعیت تیم</Link></div>
  </div></main>
}
