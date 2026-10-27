'use client'

import type { IntakeDraft, TeamRequest } from '@/service/company-requests'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect, useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { useSearchParams } from '@/next/navigation'
import { flowApi } from '@/service/company-flows'
import { projectApi } from '@/service/company-projects'
import { requestApi } from '@/service/company-requests'
import JiraImport from './jira-import'
import { DirectoryPage, DirectoryNotice, DirectorySummary, DirectoryToolbar, DirectoryPagination, DirectoryEmpty, directoryButton, directoryField, matchesSearch, resultPage } from './team-directory'
import FormDialog, { FieldHelp } from './form-dialog'

const panel = 'min-w-0 space-y-4 [overflow-wrap:anywhere] rounded-2xl border border-divider-regular bg-background-default p-5'
const button = 'rounded-lg border border-divider-regular px-4 py-2 text-sm disabled:opacity-50'
const primary = `${button} bg-components-button-primary-bg text-components-button-primary-text`
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const num = (n: number) => n.toLocaleString('fa-IR')
const states: Record<string, string> = { pending: 'در انتظار تصمیم PO', approved: 'ورود تأیید شده', rejected: 'ورود رد شده', deferred: 'ورود به تعویق افتاده', revoked: 'تأیید ورود باطل شده', expired: 'تأیید ورود منقضی شده' }

function useAction() {
  const operation = useRef<{ payload: string; key: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async (body: unknown, action: (key: string) => Promise<unknown>) => {
    if (busy) return
    const payload = JSON.stringify(body)
    if (operation.current?.payload !== payload) operation.current = { payload, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try { await action(operation.current.key); operation.current = null }
    catch { setError('ثبت انجام نشد. مجوز، پیوست‌ها و نسخهٔ انتخابی را بررسی کنید؛ اگر درخواست تغییر کرده است، نسخهٔ تازه را دریافت کنید.') }
    finally { setBusy(false) }
  }
  return { busy, error, run }
}

function RequestEditor({ project, value, saved, cancel }: { project: string; value: TeamRequest | null; saved: (value: TeamRequest) => Promise<void>; cancel: () => void }) {
  const [title, setTitle] = useState(value?.current.title || '')
  const [content, setContent] = useState(value?.current.content || '')
  const [retained, setRetained] = useState(value?.current.attachments || [])
  const [files, setFiles] = useState<File[]>([])
  const [selection, setSelection] = useState('')
  const action = useAction()
  const save = () => {
    const body = { title, content, attachment_ids: retained.map(file => file.id), expected_revision: value?.revision || 1 }
    void action.run({ id: value?.id, body, selection }, async key => saved(await requestApi.save(project, value?.id || null, body, files, key)))
  }
  return <FormDialog open title={value ? 'اصلاح درخواست' : 'ثبت درخواست تازه'} description="نیاز یا مشکل را با عنوان روشن، شرح و پیوست‌های لازم ثبت کنید. درخواست پس از ثبت برای تصمیم ورود PO آماده می‌شود؛ ثبت درخواست، ایجنتی را اجرا نمی‌کند." busy={action.busy} close={cancel}>
    <form aria-label="فرم درخواست" className="space-y-4" onSubmit={event => { event.preventDefault(); save() }}>
    {value && <p className="text-sm leading-7">با ذخیرهٔ اصلاح، نسخهٔ تازه ساخته می‌شود و تصمیم قبلی برای آن معتبر نخواهد بود. متن و پیوست‌های نسخه‌های قبل حفظ می‌شوند.</p>}
    <fieldset disabled={action.busy} className="space-y-4">
      <label className="block text-sm">عنوان درخواست<input className={field} required maxLength={200} value={title} onChange={event => setTitle(event.target.value)} /><FieldHelp>یک عنوان کوتاه و مشخص برای نیاز یا مشکل بنویسید؛ حداکثر ۲۰۰ نویسه.</FieldHelp></label>
      <label className="block text-sm">متن نیازمندی<textarea className={`${field} min-h-40`} required value={content} onChange={event => setContent(event.target.value)} /><FieldHelp>نیاز یا مشکل، رفتار فعلی و نتیجهٔ مورد انتظار را شرح دهید؛ اگر بخشی نامشخص است، همان ابهام را ذکر کنید.</FieldHelp></label>
      <label className="block text-sm">پیوست‌ها<input className={field} type="file" multiple onChange={event => { setFiles(Array.from(event.target.files || [])); setSelection(crypto.randomUUID()) }} /><FieldHelp>اسناد و تصاویر مرتبط را اضافه کنید. حداکثر پنج فایل، هر فایل دو مگابایت و مجموع هر نسخه پنج مگابایت؛ پیوست‌ها برای اعضای همین پروژه قابل دریافت‌اند.</FieldHelp></label>
      {retained.map(file => <div className="flex items-center gap-3 text-sm" key={file.id}><span>{file.name}</span><button type="button" className={button} onClick={() => setRetained(retained.filter(value => value.id !== file.id))}>حذف از نسخهٔ تازه</button></div>)}
      <button className={primary}>ذخیرهٔ درخواست</button>
    </fieldset>
    {action.error && <p role="alert">{action.error}</p>}<button type="button" className={button} disabled={action.busy} onClick={cancel}>بستن فرم</button>
    </form>
  </FormDialog>
}

function Intake({ project, value, saved, busyChanged }: { project: string; value: TeamRequest; saved: (value: TeamRequest) => Promise<void>; busyChanged: (busy: boolean) => void }) {
  const flows = useQuery({ queryKey: ['intake-flows', project], queryFn: () => flowApi.list(project) })
  const [flowId, setFlowId] = useState('')
  const versions = useQuery({ queryKey: ['intake-versions', project, flowId], queryFn: () => flowApi.versions(project, flowId), enabled: !!flowId })
  const [versionId, setVersionId] = useState('')
  const [outcome, setOutcome] = useState<IntakeDraft['outcome']>('approved')
  const [reason, setReason] = useState('')
  const [until, setUntil] = useState('')
  const action = useAction()
  const run = async (body: unknown, operation: (key: string) => Promise<unknown>) => {
    if (action.busy) return
    busyChanged(true)
    try { await action.run(body, operation) }
    finally { busyChanged(false) }
  }
  const decide = () => {
    const body: IntakeDraft = { expected_revision: value.revision, request_revision_id: value.current_revision_id, flow_id: flowId || null, flow_version_id: versionId || null, outcome, reason, expires_at: until ? new Date(until).toISOString() : null }
    void run(body, async key => saved(await requestApi.decide(project, value.id, body, key)))
  }
  return <form aria-label="تصمیم ورود PO" className={panel} onSubmit={event => { event.preventDefault(); decide() }}>
    <h3 className="text-lg font-semibold">تصمیم ورود PO</h3><p className="text-sm leading-7">این تصمیم برای نسخهٔ {num(value.version)} همین درخواست ثبت می‌شود. تأیید ورود، تأیید نهایی نیازمندی یا اجرای خودکار ایجنت‌ها نیست.</p>
    <fieldset disabled={action.busy} className="space-y-4">
      <label className="block text-sm">نوع تصمیم<select className={field} value={outcome} onChange={event => setOutcome(event.target.value as IntakeDraft['outcome'])}><option value="approved">تأیید ورود</option><option value="rejected">رد ورود</option><option value="deferred">تعویق ورود</option></select><FieldHelp>تأیید، اجازهٔ ورود به فلوی منتخب است. رد یا تعویق، اجازهٔ ورود ایجاد نمی‌کند. تصمیم برای نسخهٔ جاری درخواست ثبت می‌شود.</FieldHelp></label>
      <label className="block text-sm">فلو منتخب<select className={field} disabled={!flows.isSuccess} required={outcome === 'approved'} value={flowId} onChange={event => { setFlowId(event.target.value); setVersionId('') }}><option value="">انتخاب کنید</option>{flows.data?.data.filter(flow => !flow.archived && flow.published).map(flow => <option key={flow.id} value={flow.id}>{flow.published?.name}</option>)}</select><FieldHelp>مسیر منتشرشدهٔ مناسب رسیدگی به این درخواست را از فلوهای همین پروژه انتخاب کنید.</FieldHelp></label>
      <label className="block text-sm">نسخهٔ فلو<select className={field} disabled={!flowId || !versions.isSuccess} required={!!flowId || outcome === 'approved'} value={versionId} onChange={event => setVersionId(event.target.value)}><option value="">انتخاب کنید</option>{versions.data?.data.map(version => <option key={version.id} value={version.id}>نسخهٔ {num(version.version)} · {version.name}</option>)}</select><FieldHelp>این تصمیم به همین نسخه متصل می‌ماند؛ انتشار بعدی فلو، نسخهٔ منتخب این تصمیم را تغییر نمی‌دهد.</FieldHelp></label>
      {(flows.isPending || (!!flowId && versions.isPending)) && <p role="status" className="text-xs text-text-tertiary">در حال دریافت فلوها و نسخه‌ها…</p>}{flows.isSuccess && !flows.data.data.some(flow => !flow.archived && flow.published) && <p className="text-sm leading-7">فلوی منتشرشده‌ای برای تأیید ورود وجود ندارد. ابتدا فلو را از بخش فلوهای تیم منتشر کنید.</p>}{(flows.isError || versions.isError) && <div role="alert" className="space-y-2"><p>دریافت فلو یا نسخه‌ها انجام نشد.</p><button type="button" className={button} onClick={() => { if (flows.isError) void flows.refetch(); if (flowId) void versions.refetch() }}>تلاش دوباره</button></div>}
      <label className="block text-sm">علت تصمیم<textarea required maxLength={2000} className={field} value={reason} onChange={event => setReason(event.target.value)} /><FieldHelp>دلیل تأیید، رد، تعویق یا ابطال را بنویسید؛ این متن همراه تصمیم شما در تاریخچه حفظ می‌شود.</FieldHelp></label>
      <label className="block text-sm">انقضا (اختیاری، زمان محلی)<input className={field} type="datetime-local" value={until} onChange={event => setUntil(event.target.value)} /><FieldHelp>در صورت نیاز، زمان آینده را بر اساس ساعت محلی مرورگر تعیین کنید. خالی‌گذاشتن یعنی انقضای زمانی تعیین نمی‌شود.</FieldHelp></label>
      <div className="flex flex-wrap gap-3"><button className={primary} disabled={action.busy || !reason.trim() || (outcome === 'approved' && (!flowId || !versionId || !flows.isSuccess || !versions.isSuccess))}>{action.busy ? 'در حال ثبت تصمیم…' : 'ثبت تصمیم ورود'}</button>{value.decision?.outcome === 'approved' && <button type="button" className={button} disabled={!reason.trim()} onClick={() => run({ revoke: value.current_decision_id, revision: value.revision, reason }, async key => saved(await requestApi.revoke(project, value, reason, key)))}>ابطال تأیید جاری با این علت</button>}</div>
    </fieldset>{action.error && <p role="alert">{action.error}</p>}
  </form>
}

function RequestDetail({ project, value, saved, edit, close }: { project: string; value: TeamRequest; saved: (value: TeamRequest) => Promise<void>; edit: () => void; close: () => void }) {
  const [version, setVersion] = useState(value.current_revision_id)
  const [busy, setBusy] = useState(false)
  const current = value.revisions?.find(item => item.id === version) || value.current
  return <FormDialog open wide title={`درخواست: ${value.title}`} description="متن، نسخه‌ها، پیوست‌ها و تاریخچهٔ درخواست را اینجا بررسی کنید. اگر نقش PO دارید، تصمیم ورود نسخهٔ جاری به فلو را در همین دیالوگ ثبت کنید." busy={busy} close={close}>
    <section aria-label="جزئیات درخواست" className="space-y-5">
    {value.jira && <section className={panel} aria-label="منشأ جیرا">
      <a className="text-text-accent" href={`${value.jira.base_url}/browse/${encodeURIComponent(value.jira.key)}`} target="_blank" rel="noreferrer">جیرا: <span dir="ltr">{value.jira.key}</span></a>
      <p className="mt-2 text-sm">وضعیت جیرا: {value.jira.status || 'نامشخص'} · اولویت جیرا: {value.jira.priority || 'نامشخص'} · مسئول جیرا: {value.jira.assignee || 'تعیین نشده یا در پاسخ موجود نیست'}</p>
      <p className="mt-2 text-xs text-text-tertiary">آخرین دریافت: {new Date(value.jira.last_seen_at).toLocaleString('fa-IR')} · نوع درخواست هنوز باید مشخص شود.</p>
      {value.jira.needs_review && <div role="alert" className="mt-4 space-y-2 text-sm"><p>متن کارا جداگانه ویرایش شده است؛ تغییر جیرا خودکار جایگزین نشد. PO باید دو متن را بررسی و نسخهٔ مناسب را با «اصلاح درخواست» ثبت کند.</p><h3 className="font-semibold">آخرین عنوان جیرا: {value.jira.source_title}</h3><p className="whitespace-pre-wrap leading-7">{value.jira.source_content ?? 'توضیحات در جیرا موجود نیست.'}</p></div>}
    </section>}
    <article className={panel}><div className="flex flex-wrap justify-between gap-3"><h2 className="text-xl font-semibold">{value.title}</h2>{value.can_edit && <button className={button} disabled={busy} onClick={edit}>اصلاح نسخهٔ جاری</button>}</div><p role="status">{states[value.state] || value.state}</p>
      <label className="block max-w-sm text-sm">نسخهٔ مورد نمایش<select className={field} value={current.id} onChange={event => setVersion(event.target.value)}>{(value.revisions || [value.current]).map(item => <option key={item.id} value={item.id}>نسخهٔ {num(item.version)}{item.id === value.current_revision_id ? " · نسخهٔ جاری" : " · نسخهٔ تاریخی"}</option>)}</select></label>
      <h3 className="font-semibold">نسخهٔ {num(current.version)} · {current.title}</h3><p className="whitespace-pre-wrap text-sm leading-8">{current.content}</p>
      <ul className="space-y-2">{current.attachments.map(file => <li key={file.id}><a className="text-sm text-text-accent" href={requestApi.attachment(project, value.id, file.id)} download>{file.name} · {num(file.size)} بایت</a></li>)}</ul>
      <details className="text-xs text-text-tertiary"><summary>مشخصات نسخه</summary><p className="mt-2 break-all" dir="ltr">{current.id}<br />{current.digest}<br />{current.author_id}</p></details>
    </article>
    {value.can_decide && <><div hidden={current.id !== value.current_revision_id}><Intake key={value.revision} project={project} value={value} saved={saved} busyChanged={setBusy} /></div>{current.id !== value.current_revision_id && <section className={panel}><p className="text-sm leading-7">نسخهٔ تاریخی را مشاهده می‌کنید. تصمیم ورود باید پس از بررسی نسخهٔ جاری درخواست ثبت شود.</p><button className={button} onClick={() => setVersion(value.current_revision_id)}>نمایش نسخهٔ جاری و تصمیم ورود</button></section>}</>}
    <section className={panel} aria-label="تاریخچه تصمیم‌ها"><h3 className="text-lg font-semibold">تاریخچهٔ تصمیم‌ها</h3>{!value.decisions?.length && <p className="text-sm">هنوز تصمیمی ثبت نشده است.</p>}{value.decisions?.map(decision => <article className="space-y-2 rounded-lg border border-divider-regular p-3 text-sm" key={decision.id}><p className="font-medium">{states[decision.outcome]} · {new Date(decision.created_at).toLocaleString('fa-IR')}</p><p className="whitespace-pre-wrap leading-7">{decision.reason}</p><details className="text-xs text-text-tertiary"><summary>حساب تصمیم‌گیرنده و مراجع دقیق</summary><p className="mt-2 break-all" dir="ltr">حساب PO: {decision.actor_id}<br />درخواست: {decision.request_revision_id}<br />فلو: {decision.flow_version_id || '—'}<br />{decision.expires_at && `انقضا: ${decision.expires_at}`}</p></details></article>)}</section>
      <div className="flex justify-end"><button type="button" className={button} disabled={busy} onClick={close}>بستن</button></div>
    </section>
  </FormDialog>
}

export default function TeamRequests({ projectId }: { projectId: string }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const cache = useQueryClient()
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const entered = context.data?.current_project?.id === projectId
  const list = useQuery({ queryKey: ['team-requests', workspace, projectId], queryFn: () => requestApi.list(projectId), enabled: entered })
  const params = useSearchParams()
  const linkedRequest = params.get('request')
  const [selected, setSelected] = useState<string | null>(linkedRequest)
  const [editing, setEditing] = useState(false)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [origin, setOrigin] = useState('all')
  const [page, setPage] = useState(1)
  useEffect(() => { setSelected(linkedRequest); setEditing(false) }, [linkedRequest, workspace, projectId])
  useEffect(() => { setQuery(''); setStatus('all'); setOrigin('all'); setPage(1) }, [workspace, projectId])
  const detail = useQuery({ queryKey: ['team-request', workspace, projectId, selected], queryFn: () => requestApi.detail(projectId, selected!), enabled: entered && !!selected })
  const invalidateOverview = () => cache.invalidateQueries({ queryKey: ['company-projects', workspace, projectId, 'overview'] })
  const saved = async (value: TeamRequest) => { const fresh = await list.refetch(); void invalidateOverview(); if (fresh.isError) throw new Error('Refresh failed'); setSelected(value.id); setEditing(false); if (selected === value.id) { const result = await detail.refetch(); if (result.isError) throw new Error('Refresh failed') } }
  const refresh = async () => { await list.refetch(); void invalidateOverview(); if (selected) await detail.refetch() }
  const values = list.data?.data || []
  const filtered = values.filter(value => matchesSearch(query, value.title, value.jira?.key) && (status === 'all' || (status === 'jira_review' ? value.jira?.needs_review : value.state === status)) && (origin === 'all' || (origin === 'jira' ? !!value.jira : !value.jira)))
  const results = resultPage(filtered, page)
  const hasFilters = !!query.trim() || status !== 'all' || origin !== 'all'
  const reset = () => { setQuery(''); setStatus('all'); setOrigin('all'); setPage(1) }
  return <DirectoryPage project={projectId} title="درخواست‌های پروژه" description="نیازمندی‌ها را پیدا و بررسی کنید؛ تصمیم مالک محصول، نسخهٔ مشخصی از درخواست را به نسخهٔ مشخصی از فلو متصل می‌کند." actions={<><button className={directoryButton} disabled={!entered || list.isFetching} onClick={() => void refresh()}>{list.isFetching ? 'در حال تازه‌سازی…' : 'تازه‌سازی'}</button>{entered && list.isSuccess && <><button className={primary} onClick={() => { setSelected(null); setEditing(true) }}>ثبت درخواست</button>{list.data.can_import_jira && <JiraImport projectId={projectId} saved={refresh} />}</>}</>}>
    <DirectoryNotice project={projectId} entered={!!entered} loading={context.isPending || (!!entered && list.isPending)} error={context.isError || (!!entered && list.isError)} retry={() => context.isError ? context.refetch() : list.refetch()} />
    {entered && list.isSuccess && <>
      <DirectorySummary items={[{ label: 'کل درخواست‌ها', count: values.length }, { label: 'منتظر تصمیم مالک محصول', count: values.filter(value => value.state === 'pending').length }, { label: 'ورود تأیید شده', count: values.filter(value => value.intake_valid).length }, { label: 'تغییر جیرا نیازمند بررسی', count: values.filter(value => value.jira?.needs_review).length }]} />
      <DirectoryToolbar query={query} change={value => { setQuery(value); setPage(1) }} placeholder="عنوان درخواست یا کلید جیرا" filtered={filtered.length} total={values.length} hasFilters={hasFilters} reset={reset}>
        <label className="min-w-0 flex-1 basis-48 text-sm">وضعیت تصمیم<select className={directoryField} value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="all">همهٔ وضعیت‌ها</option>{Object.entries(states).map(([key, label]) => <option key={key} value={key}>{label}</option>)}<option value="jira_review">تغییر جیرا نیازمند بررسی</option></select></label>
        <label className="min-w-0 flex-1 basis-36 text-sm">منشأ درخواست<select className={directoryField} value={origin} onChange={event => { setOrigin(event.target.value); setPage(1) }}><option value="all">همهٔ منشأها</option><option value="manual">ثبت دستی</option><option value="jira">جیرا</option></select></label>
      </DirectoryToolbar>
      {editing && (!selected || detail.data?.can_edit) && <RequestEditor key={`${workspace}:${selected || 'new'}:${detail.data?.revision || 1}`} project={projectId} value={selected ? detail.data || null : null} saved={saved} cancel={() => setEditing(false)} />}
      {selected && !editing && (detail.isSuccess ? <RequestDetail key={`${workspace}:${selected}:${detail.data.revision}`} project={projectId} value={detail.data} saved={saved} edit={() => setEditing(true)} close={() => setSelected(null)} /> : <FormDialog open wide title="مشاهدهٔ درخواست" description="اطلاعات و تاریخچهٔ درخواست انتخاب‌شده در حال دریافت است." close={() => setSelected(null)}><p role={detail.isError ? 'alert' : 'status'}>{detail.isError ? 'دریافت درخواست انجام نشد.' : 'در حال دریافت درخواست…'}</p>{detail.isError && <button className={button} onClick={() => detail.refetch()}>تلاش دوباره</button>}</FormDialog>)}
      {!results.items.length ? <DirectoryEmpty filtered={hasFilters && !!values.length} title="هنوز درخواستی ثبت نشده است" reset={reset}>با «ثبت درخواست» نیازمندی را اضافه کنید یا درخواست‌ها را از جیرا وارد کنید.</DirectoryEmpty> : <ul aria-label="فهرست درخواست‌ها" className="m-0 grid list-none grid-cols-1 gap-4 p-0 lg:grid-cols-2">{results.items.map(value => <li key={value.id} className="min-w-0"><article className={`${panel} flex h-full flex-col`}>
        <header><p className="mb-2 text-xs font-medium text-text-accent">{states[value.state] || 'نیاز به بررسی'}</p><h2 className="break-words text-lg font-semibold leading-8">{value.title}</h2></header>
        <p className="line-clamp-2 whitespace-pre-wrap text-sm leading-7 text-text-secondary">{value.current.content}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs leading-6 text-text-tertiary"><span>{value.jira ? <><bdi>{value.jira.key}</bdi> · جیرا</> : 'ثبت دستی'}</span><span>نسخهٔ {num(value.version)}</span><span>زمان نسخه: {new Date(value.current.created_at).toLocaleDateString('fa-IR')}</span></div>
        {value.jira?.needs_review && <p className="rounded-lg bg-background-section p-3 text-xs leading-6">تغییر متن جیرا نیاز به بررسی و ثبت نسخهٔ مناسب دارد.</p>}
        <div className="mt-auto flex flex-wrap items-center gap-2 pt-2"><button className={primary} onClick={() => { setSelected(value.id); setEditing(false) }}>{value.can_decide ? 'بررسی و تصمیم ورود' : 'مشاهدهٔ درخواست'}</button><Link className={button} href={`/projects/${projectId}/team-runs?request=${encodeURIComponent(value.id)}`}>پیگیری اجرا</Link></div>
      </article></li>)}</ul>}
      <DirectoryPagination value={results} change={setPage} />
      <p className="text-xs leading-6 text-text-tertiary">تأیید ورود، اجازهٔ شروع رسیدگی است؛ پیشرفت و نتیجهٔ نهایی در اجرای تیمی و کارتابل پیگیری می‌شوند.</p>
    </>}
  </DirectoryPage>
}
