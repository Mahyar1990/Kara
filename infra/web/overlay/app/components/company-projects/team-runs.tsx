'use client'

import type { ExecutionChoice } from '@/service/company-harness'
import HarnessChoice from './harness-choice'
import HarnessDelivery from './harness-delivery'
import RuntimeModelPicker from './runtime-model-picker'
import type { AgentInput } from '@/service/company-agents'
import type { AvailableRequest, StageArtifact, TeamInstance, TeamStage } from '@/service/company-stages'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect, useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { useRouter, useSearchParams } from '@/next/navigation'
import { stageStates as states, teamStageHref } from '@/utils/company-team-work'
import { projectApi } from '@/service/company-projects'
import { stageApi } from '@/service/company-stages'
import TeamRecovery from './team-recovery'
import FormDialog from './form-dialog'
import { DirectoryPage, DirectoryNotice, DirectorySummary, DirectoryToolbar, DirectoryPagination, DirectoryEmpty, directoryButton, directoryField, matchesSearch, resultPage } from './team-directory'

const panel = 'min-w-0 space-y-4 [overflow-wrap:anywhere] rounded-2xl border border-divider-regular bg-background-default p-5'
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
  const requestFields = new Set(Object.entries(value.binding.inputs).filter(([, source]) => source.source === 'request').map(([name]) => name))
  const textual = value.binding.input_contract.filter(item => ['text-input', 'paragraph'].includes(item.type) && !requestFields.has(item.variable))
  const [inputs, setInputs] = useState(value.editable_inputs)
  const [parent, setParent] = useState('')
  const [message, setMessage] = useState('')
  const [variable, setVariable] = useState(current.length ? (textual.find(item => item.variable === 'feedback_context') || textual[0])?.variable || '' : '')
  const action = useAction()
  const body = { artifact_id: parent || null, message, inputs, feedback_variable: variable || null }
  return <form className={panel} aria-label="بازخورد و اصلاح ورودی" onSubmit={event => { event.preventDefault(); void action.run(body, key => act('feedback', body, key)) }}>
    <h3 className="font-semibold">بازخورد و اصلاح ورودی</h3><p className="text-sm leading-7">بازخورد دور تازه‌ای می‌سازد و اجرای بعدی با اقدام صریح اجراکننده آغاز می‌شود. بازخورد و خروجی مبنا به ورودی متنی منتخب می‌رسند؛ پیش از اجرا، ورودی نهایی را بررسی کنید.</p>
    <fieldset className="space-y-4" disabled={action.busy}>
      <label className="block text-sm">خروجی مبنای بازخورد<select className={field} required={['awaiting_feedback', 'awaiting_decision'].includes(value.state)} value={parent} onChange={event => setParent(event.target.value)}><option value="">بدون خروجی مبنا</option>{current.map(item => <option key={item.id} value={item.id}>نسخهٔ {num(item.version)} · {item.kind === 'human' ? 'ویرایش انسانی' : item.kind === 'harness' ? 'خروجی هارنس' : 'خروجی اجرا'}</option>)}</select></label>
      <label className="block text-sm">متن بازخورد<textarea className={field} required maxLength={8000} value={message} onChange={event => setMessage(event.target.value)} /></label>
      {value.binding.input_contract.map(item => <fieldset key={item.variable} disabled={requestFields.has(item.variable)}><Input item={item} value={inputs[item.variable]} change={next => setInputs({ ...inputs, [item.variable]: next })} />{requestFields.has(item.variable) && <p className="mt-1 text-xs leading-6 text-text-tertiary">متن اصلی درخواست ثابت است؛ تغییر نیازمندی به نسخهٔ تازه و تصمیم مالک محصول نیاز دارد.</p>}</fieldset>)}
      <label className="block text-sm">ورودی متنی دریافت‌کنندهٔ بازخورد<select className={field} required={!!parent && !!textual.length} value={variable} onChange={event => setVariable(event.target.value)}><option value="">فقط ثبت علت اصلاح مقادیر</option>{textual.map(item => <option key={item.variable} value={item.variable}>{item.label}</option>)}</select></label>
      {!textual.length && <p className="text-sm">برای رساندن بازخورد و خروجی مبنا به اجرای بعد، برنامه باید ورودی متنی جدا از متن اصلی درخواست داشته باشد.</p>}<button disabled={!!parent && !textual.length} className={primary}>ثبت بازخورد و دور تازه</button>
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

function StageContent({ value, act, project, changed }: { value: TeamStage; act: Act; project: string; changed: () => Promise<unknown> }) {
  const [modelConnection, setModelConnection] = useState('')
  const [execution, setExecution] = useState<ExecutionChoice | null>(null)
  const [executionReady, setExecutionReady] = useState(true)
  const runBody = execution ? { execution } : value.runtime_model ? { model_connection_id: modelConnection } : {}
  const [editing, setEditing] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const action = useAction()
  const person = (id: string) => id === value.binding.executor.account_id ? value.binding.executor.name : id === value.binding.finalizer.account_id ? value.binding.finalizer.name : id
  const selected = value.artifacts.find(item => item.id === value.selected_artifact_id)
  return <div className="space-y-5">
    <section className={panel}><h2 className="text-xl font-semibold">{value.binding.title} · {value.binding.app_name || value.binding.agent_name}{value.binding.workflow_version && ` · ${value.binding.workflow_version}`}</h2><p role="status">{states[value.state]} · دور {num(value.round)}</p><p className="text-sm leading-7">اجراکننده: {value.binding.executor.name} · نهایی‌کننده: {value.binding.finalizer.name}</p>
      {!value.intake_valid && <p role="alert">تصمیم ورود این اجرا دیگر معتبر نیست؛ سابقه حفظ شده و ادامه به تصمیم تازهٔ PO نیاز دارد.</p>}{value.input_error && value.intake_valid && <p role="status">{value.input_error}</p>}
      <details open className="space-y-3"><summary className="cursor-pointer font-medium">ورودی نهایی مرحله</summary>{Object.entries(value.preview_inputs).map(([name, content]) => <div key={name}><h4 className="text-sm">{value.binding.input_contract.find(item => item.variable === name)?.label || name}</h4><pre className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-background-section p-3 font-sans text-sm leading-7">{text(content)}</pre></div>)}</details>
      {value.binding.execution?.instructions && <section className="rounded-lg bg-background-section p-3"><h3 className="text-sm font-semibold">شرح کار و معیار پذیرش</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-7">{value.binding.execution.instructions}</p></section>}
      {value.actions.includes('run') && <HarnessChoice project={project} agent={value.binding.agent_id} stagePolicy={value.execution_policy} value={execution} change={setExecution} valid={setExecutionReady} />}
      {!execution && value.runtime_model && value.actions.includes('run') && <RuntimeModelPicker value={modelConnection} onChange={setModelConnection} capabilities={value.runtime_model.capabilities} />}
      <div className="flex flex-wrap gap-3">{value.actions.includes('run') && <button disabled={action.busy || !executionReady} className={primary} onClick={() => action.run({ run: value.id, ...runBody }, key => act('run', runBody, key))}>{execution ? 'شروع تسک با هارنس شخصی' : 'اجرا با این ورودی‌ها'}</button>}{value.actions.includes('retry') && <button disabled={action.busy} className={button} onClick={() => action.run({ retry: value.id }, key => act('retry', {}, key))}>آماده‌سازی تلاش مجدد</button>}</div>{action.error && <p role="alert">{action.error}</p>}
    </section>
    {value.harness && <HarnessDelivery project={project} agent={value.binding.agent_id} identity={value.harness.attempt_id} outputs={value.binding.output_contract} stage={value} info={value.harness} changed={changed} />}
    {!!value.handoffs.length && <section className={panel} aria-label="خروجی تحویلی از مراحل قبل"><h3 className="text-lg font-semibold">خروجی تحویلی از مراحل قبل</h3><p className="text-sm leading-7">فقط بخش مورد نیاز از خروجی منتخب و نهایی‌شده نمایش داده می‌شود.</p>{value.handoffs.map(item => <article className="space-y-2 border-t border-divider-regular pt-3" key={item.input}><p className="font-medium">{item.stage_title} · نسخهٔ {num(item.version)} · {item.consumed ? 'در ورودی این مرحله ثبت شده' : 'آمادهٔ دریافت در این مرحله'}</p><p className="text-sm">خروجی {item.output} ← ورودی {value.binding.input_contract.find(input => input.variable === item.input)?.label || item.input}</p><pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7">{text(item.content)}</pre><p className="text-xs leading-6">نهایی‌کننده: {person(item.finalized_by)} · {new Date(item.finalized_at).toLocaleString('fa-IR')}</p><details><summary className="cursor-pointer text-sm">شناسه‌های قابل پیگیری تحویل</summary><p className="break-all text-xs leading-7">خروجی: <bdi>{item.artifact_id}</bdi><br />تصمیم: <bdi>{item.decision_id}</bdi><br />اثر انگشت: <bdi>{item.digest}</bdi></p></details></article>)}</section>}
    {value.actions.includes('revalidate') && <form className={panel} aria-label="بررسی مجدد ورودی مرحله" onSubmit={event => { event.preventDefault(); void action.run({ revalidate: value.id, reason }, key => act('revalidate', { reason }, key)) }}><h3 className="font-semibold">بررسی مجدد ورودی مرحله</h3><p className="text-sm leading-7">ورودی تازه و پیش‌نیازها را بررسی کنید. این اقدام فقط مرحله را آماده می‌کند؛ اجرا با انتخاب بعدی شما است و تأیید قدیمی خروجی برنمی‌گردد.</p><label className="block text-sm">علت بررسی مجدد<textarea required maxLength={2000} className={field} value={reason} onChange={event => setReason(event.target.value)} /></label><button disabled={action.busy} className={primary}>تأیید ورودی تازه و آماده‌سازی مرحله</button></form>}
    {value.actions.includes('feedback') && <Feedback key={value.revision} value={value} act={act} />}
    <section className={panel} aria-label="خروجی‌های مرحله"><h3 className="text-lg font-semibold">خروجی‌ها و ویرایش‌های انسانی</h3><p className="text-sm leading-7">موفقیت اجرا خروجی پیش‌نویس می‌سازد. فقط خروجی منتخب و نهایی‌شده به مرحلهٔ بعد می‌رسد.</p>{!value.artifacts.length && <p className="text-sm">هنوز خروجی ثبت نشده است.</p>}{value.artifacts.map(item => {
      const current = item.round === value.round && item.input_digest === value.input_digest
      return <article key={item.id} className="space-y-3 rounded-lg border border-divider-regular p-4"><h4 className="font-semibold">نسخهٔ {num(item.version)} · دور {num(item.round)} · {item.kind === 'human' ? 'ویرایش انسانی' : item.kind === 'harness' ? 'خروجی هارنس' : 'خروجی اجرا'}{!current && ' · دور قبلی'}{selected?.id === item.id && ' · منتخب'}</h4><p className="break-all text-xs text-text-tertiary">ثبت‌کننده: {person(item.author_id)}</p>{Object.entries(item.content).map(([name, content]) => <div key={name}><p className="text-sm font-medium">{name}</p><pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7">{text(content)}</pre></div>)}{item.reason && <p className="text-sm">علت ویرایش: {item.reason}</p>}
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
  return <FormDialog open wide title="جزئیات مرحلهٔ اجرای تیمی" description="ورودی‌ها و مسئولان همین مرحله را بررسی کنید، برنامه را اجرا کنید و خروجی را برای تصمیم انسانی آماده کنید. بازخوردها، ویرایش‌ها و تاریخچه در همین دیالوگ در دسترس‌اند." busy={busy} close={close}>
    <section aria-label="جزئیات مرحله" className="space-y-4">
      <h2 className="text-lg font-semibold">درخواست: {title}</h2>
      <fieldset disabled={busy} className="space-y-4">
        {query.isSuccess ? <StageContent key={query.data.revision} value={query.data} act={act} project={project} changed={async () => { await query.refetch(); await changed() }} /> : <p role={query.isError ? 'alert' : 'status'}>{query.isError ? 'دریافت محتوای مرحله انجام نشد؛ مجوز برنامه و پروژه را بررسی کنید.' : 'در حال دریافت مرحله…'}</p>}
      </fieldset>
      <div className="flex flex-wrap justify-end gap-3"><button className={button} disabled={busy || query.isFetching} onClick={() => query.refetch()}>دریافت وضعیت تازهٔ مرحله</button><button type="button" className={button} disabled={busy} onClick={close}>بستن</button></div>
    </section>
  </FormDialog>
}

export default function TeamRuns({ projectId }: { projectId: string }) {
  const cache = useQueryClient()
  const router = useRouter()
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
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState(linkedRequest ? 'all' : 'active')
  const [page, setPage] = useState(1)
  const [readyPage, setReadyPage] = useState(1)
  useEffect(() => { setSelection(linkedInstance && linkedStage ? { instance: linkedInstance, stage: linkedStage } : null); setControlInstance(null); setCreating(null) }, [linkedInstance, linkedStage, projectId, workspace])
  useEffect(() => { setQuery(''); setStatus(linkedRequest ? 'all' : 'active'); setPage(1); setReadyPage(1) }, [linkedRequest, workspace, projectId])
  const action = useAction()
  const refresh = async () => { const result = await list.refetch(); void cache.invalidateQueries({ queryKey: ['company-projects', workspace, projectId, 'overview'] }); if (!result.isSuccess) throw new Error('Refresh failed') }
  const choose = (value: TeamInstance) => { const stage = value.stages.find(stage => stage.id === value.current_stage_id) || value.stages.find(stage => stage.state !== 'completed') || value.stages[value.stages.length - 1]; setControlInstance(null); if (stage) setSelection({ instance: value.id, stage: stage.id }) }
  const values = list.data?.data || []
  const needsReview = (value: TeamInstance) => value.state === 'active' && (!value.intake_valid || value.stages.some(stage => stage.id === value.current_stage_id && ['failed', 'stale', 'interrupted'].includes(stage.state)))
  const filtered = values.filter(value => (!linkedRequest || value.request_id === linkedRequest) && matchesSearch(query, value.title, value.responsibility.person?.name) && (status === 'all' || (status === 'attention' ? needsReview(value) : value.state === status)))
  const results = resultPage(filtered, page)
  const ready = list.data?.available_requests || []
  const readyResults = resultPage(ready.filter(value => (!linkedRequest || value.id === linkedRequest) && matchesSearch(query, value.title)), readyPage)
  const hasFilters = !!query.trim() || status !== 'all' || !!linkedRequest
  const reset = () => { setQuery(''); setStatus('all'); setPage(1); setReadyPage(1); if (linkedRequest) router.replace(`/projects/${projectId}/team-runs`) }
  return <DirectoryPage project={projectId} title="اجرای تیمی" description="وضعیت رسیدگی به درخواست‌ها، مسئول ادامهٔ کار و مرحلهٔ بعد را پیگیری کنید. هر مرحله با اقدام صریح مسئول مجاز آن اجرا یا نهایی می‌شود." actions={<><button className={directoryButton} disabled={!entered || list.isFetching} onClick={() => void refresh().catch(() => {})}>{list.isFetching ? 'در حال تازه‌سازی…' : 'تازه‌سازی'}</button><Link className={directoryButton} href={`/projects/${projectId}/inbox`}>اقدام‌های من</Link></>}>
    <DirectoryNotice project={projectId} entered={!!entered} loading={context.isPending || (!!entered && list.isPending)} error={context.isError || (!!entered && list.isError)} retry={() => context.isError ? context.refetch() : refresh()} />
    {entered && list.data && <>
      {list.isError && <p role="status" className="text-sm">آخرین فهرست دریافت‌شده نمایش داده می‌شود؛ دریافت اطلاعات تازه موفق نبود.</p>}
      <DirectorySummary items={[{ label: 'کل اجراهای تیمی', count: values.length }, { label: 'اجرای باز', count: values.filter(value => value.state === 'active').length }, { label: 'نهایی‌شده', count: values.filter(value => value.state === 'completed').length }, { label: 'درخواست آمادهٔ شروع با دسترسی من', count: ready.length }]} />
      <DirectoryToolbar query={query} change={value => { setQuery(value); setPage(1); setReadyPage(1) }} placeholder="عنوان درخواست یا مسئول فعلی" filtered={filtered.length} total={values.length} hasFilters={hasFilters} reset={reset}><label className="min-w-0 flex-1 basis-48 text-sm">وضعیت اجرا<select className={directoryField} value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="active">اجراهای باز</option><option value="attention">نیازمند بررسی ورودی یا خطا</option><option value="completed">نهایی‌شده</option><option value="cancelled">لغوشده</option><option value="all">همهٔ اجراها</option></select></label></DirectoryToolbar>
      {linkedRequest && <p className="rounded-xl bg-background-section p-3 text-sm leading-7">فهرست به درخواست انتخاب‌شده محدود است. <button className="text-text-accent" onClick={reset}>نمایش همهٔ درخواست‌ها</button></p>}
      {!!readyResults.total && <section id="ready-team-requests" className={`${panel} space-y-4`}><header><h2 className="text-lg font-semibold">درخواست‌های آمادهٔ شروع</h2><p className="mt-2 text-xs leading-6 text-text-secondary">ایجاد پرونده، برنامه را اجرا نمی‌کند. مرحلهٔ اول پس از ایجاد، ورودی‌ها و مسئول مشخص خواهد داشت.</p></header><ul className="m-0 list-none divide-y divide-divider-regular p-0">{readyResults.items.map(request => <li key={request.id} className="flex min-w-0 flex-wrap items-center justify-between gap-3 py-3"><p className="min-w-0 break-words text-sm font-medium">{request.title}</p><button className={button} disabled={action.busy} onClick={() => setCreating(request)}>بررسی و ایجاد اجرا</button></li>)}</ul><DirectoryPagination value={readyResults} change={setReadyPage} /></section>}
      {action.error && <p role="alert">{action.error}</p>}
      {creating && <FormDialog open title="ایجاد اجرای تیمی" description="پرونده بر اساس نسخهٔ فلویی که مالک محصول تأیید کرده ساخته می‌شود؛ این اقدام هیچ برنامه‌ای را اجرا نمی‌کند." busy={action.busy} error={action.error} close={() => setCreating(null)}><form className="space-y-4" onSubmit={event => { event.preventDefault(); void action.run(creating, async key => { const value = await stageApi.create(projectId, creating, key); await refresh(); setQuery(''); setStatus('active'); choose(value); setCreating(null) }) }}><p className="text-sm leading-7">درخواست منتخب: <strong>{creating.title}</strong></p><div className="flex justify-end gap-3"><button type="button" className={button} disabled={action.busy} onClick={() => setCreating(null)}>انصراف</button><button className={primary} disabled={action.busy}>{action.busy ? 'در حال ایجاد…' : 'ایجاد پروندهٔ اجرا'}</button></div></form></FormDialog>}
      {!results.items.length ? <DirectoryEmpty filtered={hasFilters && !!values.length} title="اجرای تیمی‌ای برای نمایش وجود ندارد" reset={reset}>درخواست باید تأیید ورود معتبر داشته باشد. درخواست‌های آماده از همین صفحه وارد رسیدگی می‌شوند.</DirectoryEmpty> : <ul aria-label="اجراهای تیمی" className="m-0 list-none space-y-4 p-0">{results.items.map(value => {
        const current = value.stages.find(stage => stage.id === value.current_stage_id)
        return <li key={value.id}><article className={panel}><header><p className="mb-2 text-xs font-medium text-text-accent">{value.state === 'completed' ? 'نهایی‌شده' : value.state === 'cancelled' ? 'لغوشده' : current ? states[current.state] || 'در حال رسیدگی' : 'نیاز به بررسی'}</p><h2 className="break-words text-xl font-semibold leading-8">{value.title}</h2></header><progress className="h-2 w-full accent-current text-text-accent" max={value.total_stages || 1} value={value.completed_stages} aria-label={`پیشرفت ${value.title}`} /><p className="text-sm leading-7">{num(value.completed_stages)} از {num(value.total_stages)} مرحله نهایی‌شده · مسئول ادامه: {value.responsibility.person?.name || (value.responsibility.kind === 'po' ? 'مالک محصول' : value.state === 'cancelled' ? 'فرایند لغوشده' : value.state === 'completed' ? 'کار تمام شده' : 'نیاز به بررسی')}</p>{value.responsibility.reason && <p className="rounded-xl bg-background-section p-3 text-sm leading-7">{value.responsibility.reason}</p>}{!value.intake_valid && !value.cancellation && <p className="text-sm leading-7">تصمیم ورود نیاز به بررسی مجدد مالک محصول دارد.</p>}<details><summary className="cursor-pointer text-sm text-text-secondary">همهٔ مراحل ({num(value.total_stages)})</summary><ol className="m-0 mt-4 flex list-none flex-wrap gap-3 p-0">{value.stages.map(stage => <li key={stage.id}><Link className={`${button} inline-block ${selection?.stage === stage.id ? 'bg-background-section font-semibold text-text-accent ring-1 ring-text-accent' : ''}`} aria-current={selection?.stage === stage.id ? 'step' : undefined} href={teamStageHref(projectId, value.id, stage.id)} onClick={event => { if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return; event.preventDefault(); setControlInstance(null); setSelection({ instance: value.id, stage: stage.id }) }}>{stage.title} · {states[stage.state] || 'نیاز به بررسی'}</Link></li>)}</ol></details><footer className="flex flex-wrap gap-2 border-t border-divider-regular pt-5"><button className={primary} onClick={() => choose(value)}>{value.state === 'active' ? 'بررسی مرحلهٔ فعلی' : 'مشاهدهٔ مراحل و نتیجه'}</button><button className={button} onClick={() => { setSelection(null); setControlInstance(value.id) }}>بازبینی و بازیابی</button><Link className={button} href={`/projects/${projectId}/requests?request=${encodeURIComponent(value.request_id)}`}>درخواست و تصمیم ورود</Link></footer></article></li>
      })}</ul>}
      <DirectoryPagination value={results} change={setPage} />
      {controlInstance && <TeamRecovery key={`${workspace}:${controlInstance}`} projectId={projectId} instanceId={controlInstance} changed={async () => { await refresh(); await queryStageRefresh() }} close={() => setControlInstance(null)} />}
      {selection && <StagePanel key={`${workspace}:${selection.instance}:${selection.stage}`} project={projectId} instance={selection.instance} stage={selection.stage} title={values.find(value => value.id === selection.instance)?.title || 'مرحلهٔ انتخاب‌شده'} changed={refresh} close={() => setSelection(null)} />}
      <Link className="text-sm text-text-accent" href={`/projects/${projectId}/requests`}>درخواست‌های پروژه ←</Link>
    </>}
  </DirectoryPage>
}
