'use client'

import type { IntakeDraft, TeamRequest } from '@/service/company-requests'
import { useQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { flowApi } from '@/service/company-flows'
import { projectApi } from '@/service/company-projects'
import { requestApi } from '@/service/company-requests'

const panel = 'space-y-4 rounded-2xl border border-divider-regular bg-background-default p-5'
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
  return <form aria-label="فرم درخواست" className={panel} onSubmit={event => { event.preventDefault(); save() }}>
    <h2 className="text-xl font-semibold">{value ? 'اصلاح درخواست' : 'درخواست تازه'}</h2>
    {value && <p className="text-sm leading-7">با ذخیرهٔ اصلاح، نسخهٔ تازه ساخته می‌شود و تصمیم قبلی برای آن معتبر نخواهد بود. متن و پیوست‌های نسخه‌های قبل حفظ می‌شوند.</p>}
    <fieldset disabled={action.busy} className="space-y-4">
      <label className="block text-sm">عنوان درخواست<input className={field} required maxLength={200} value={title} onChange={event => setTitle(event.target.value)} /></label>
      <label className="block text-sm">متن نیازمندی<textarea className={`${field} min-h-40`} required value={content} onChange={event => setContent(event.target.value)} /></label>
      <label className="block text-sm">پیوست‌ها<input className={field} type="file" multiple onChange={event => { setFiles(Array.from(event.target.files || [])); setSelection(crypto.randomUUID()) }} /></label>
      <p className="text-xs leading-6 text-text-tertiary">حداکثر پنج فایل؛ هر فایل تا دو مگابایت و مجموع هر نسخه تا پنج مگابایت. پیوست‌ها فقط برای اعضای همین پروژه قابل دریافت‌اند.</p>
      {retained.map(file => <div className="flex items-center gap-3 text-sm" key={file.id}><span>{file.name}</span><button type="button" className={button} onClick={() => setRetained(retained.filter(value => value.id !== file.id))}>حذف از نسخهٔ تازه</button></div>)}
      <button className={primary}>ذخیرهٔ درخواست</button>
    </fieldset>
    {action.error && <p role="alert">{action.error}</p>}<button type="button" className={button} disabled={action.busy} onClick={cancel}>بستن فرم</button>
  </form>
}

function Intake({ project, value, saved }: { project: string; value: TeamRequest; saved: (value: TeamRequest) => Promise<void> }) {
  const flows = useQuery({ queryKey: ['intake-flows', project], queryFn: () => flowApi.list(project) })
  const [flowId, setFlowId] = useState('')
  const versions = useQuery({ queryKey: ['intake-versions', project, flowId], queryFn: () => flowApi.versions(project, flowId), enabled: !!flowId })
  const [versionId, setVersionId] = useState('')
  const [outcome, setOutcome] = useState<IntakeDraft['outcome']>('approved')
  const [reason, setReason] = useState('')
  const [until, setUntil] = useState('')
  const action = useAction()
  const decide = () => {
    const body: IntakeDraft = { expected_revision: value.revision, request_revision_id: value.current_revision_id, flow_id: flowId || null, flow_version_id: versionId || null, outcome, reason, expires_at: until ? new Date(until).toISOString() : null }
    void action.run(body, async key => saved(await requestApi.decide(project, value.id, body, key)))
  }
  return <form aria-label="تصمیم ورود PO" className={panel} onSubmit={event => { event.preventDefault(); decide() }}>
    <h3 className="text-lg font-semibold">تصمیم ورود PO</h3><p className="text-sm leading-7">این تصمیم برای نسخهٔ {num(value.version)} همین درخواست ثبت می‌شود. تأیید ورود، تأیید نهایی نیازمندی یا اجرای خودکار ایجنت‌ها نیست.</p>
    <fieldset disabled={action.busy} className="space-y-4">
      <label className="block text-sm">نوع تصمیم<select className={field} value={outcome} onChange={event => setOutcome(event.target.value as IntakeDraft['outcome'])}><option value="approved">تأیید ورود</option><option value="rejected">رد ورود</option><option value="deferred">تعویق ورود</option></select></label>
      <label className="block text-sm">فلو منتخب<select className={field} required={outcome === 'approved'} value={flowId} onChange={event => { setFlowId(event.target.value); setVersionId('') }}><option value="">انتخاب کنید</option>{flows.data?.data.filter(flow => !flow.archived && flow.published).map(flow => <option key={flow.id} value={flow.id}>{flow.published?.name}</option>)}</select></label>
      <label className="block text-sm">نسخهٔ فلو<select className={field} required={!!flowId || outcome === 'approved'} value={versionId} onChange={event => setVersionId(event.target.value)}><option value="">انتخاب کنید</option>{versions.data?.data.map(version => <option key={version.id} value={version.id}>نسخهٔ {num(version.version)} · {version.name}</option>)}</select></label>
      {(flows.isError || versions.isError) && <p role="alert">دریافت نسخه‌های فلو انجام نشد؛ فهرست را تازه کنید.</p>}
      <label className="block text-sm">علت تصمیم<textarea required maxLength={2000} className={field} value={reason} onChange={event => setReason(event.target.value)} /></label>
      <label className="block text-sm">انقضا (اختیاری، زمان محلی)<input className={field} type="datetime-local" value={until} onChange={event => setUntil(event.target.value)} /></label>
      <div className="flex flex-wrap gap-3"><button className={primary}>ثبت تصمیم</button>{value.decision?.outcome === 'approved' && <button type="button" className={button} disabled={!reason.trim()} onClick={() => action.run({ revoke: value.current_decision_id, revision: value.revision, reason }, async key => saved(await requestApi.revoke(project, value, reason, key)))}>ابطال تأیید جاری با این علت</button>}</div>
    </fieldset>{action.error && <p role="alert">{action.error}</p>}
  </form>
}

function RequestDetail({ project, value, saved, edit }: { project: string; value: TeamRequest; saved: (value: TeamRequest) => Promise<void>; edit: () => void }) {
  const [version, setVersion] = useState(value.current_revision_id)
  const current = value.revisions?.find(item => item.id === version) || value.current
  return <section aria-label="جزئیات درخواست" className="space-y-5">
    <article className={panel}><div className="flex flex-wrap justify-between gap-3"><h2 className="text-xl font-semibold">{value.title}</h2>{value.can_edit && <button className={button} onClick={edit}>اصلاح درخواست</button>}</div><p role="status">{states[value.state] || value.state}</p>
      <div aria-label="نسخه‌های درخواست" className="flex flex-wrap gap-2">{value.revisions?.map(item => <button className={button} aria-pressed={current.id === item.id} key={item.id} onClick={() => setVersion(item.id)}>نمایش نسخهٔ {num(item.version)}</button>)}</div>
      <h3 className="font-semibold">نسخهٔ {num(current.version)} · {current.title}</h3><p className="whitespace-pre-wrap text-sm leading-8">{current.content}</p>
      <ul className="space-y-2">{current.attachments.map(file => <li key={file.id}><a className="text-sm text-text-accent" href={requestApi.attachment(project, value.id, file.id)} download>{file.name} · {num(file.size)} بایت</a></li>)}</ul>
      <details className="text-xs text-text-tertiary"><summary>مشخصات نسخه</summary><p className="mt-2 break-all" dir="ltr">{current.id}<br />{current.digest}<br />{current.author_id}</p></details>
    </article>
    {value.can_decide && <Intake key={value.revision} project={project} value={value} saved={saved} />}
    <section className={panel} aria-label="تاریخچه تصمیم‌ها"><h3 className="text-lg font-semibold">تاریخچهٔ تصمیم‌ها</h3>{!value.decisions?.length && <p className="text-sm">هنوز تصمیمی ثبت نشده است.</p>}{value.decisions?.map(decision => <article className="space-y-2 rounded-lg border border-divider-regular p-3 text-sm" key={decision.id}><p className="font-medium">{states[decision.outcome]} · {new Date(decision.created_at).toLocaleString('fa-IR')}</p><p className="whitespace-pre-wrap leading-7">{decision.reason}</p><details className="text-xs text-text-tertiary"><summary>حساب تصمیم‌گیرنده و مراجع دقیق</summary><p className="mt-2 break-all" dir="ltr">حساب PO: {decision.actor_id}<br />درخواست: {decision.request_revision_id}<br />فلو: {decision.flow_version_id || '—'}<br />{decision.expires_at && `انقضا: ${decision.expires_at}`}</p></details></article>)}</section>
  </section>
}

export default function TeamRequests({ projectId }: { projectId: string }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const entered = context.data?.current_project?.id === projectId
  const list = useQuery({ queryKey: ['team-requests', workspace, projectId], queryFn: () => requestApi.list(projectId), enabled: entered })
  const [selected, setSelected] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const detail = useQuery({ queryKey: ['team-request', workspace, projectId, selected], queryFn: () => requestApi.detail(projectId, selected!), enabled: entered && !!selected })
  const saved = async (value: TeamRequest) => { const fresh = await list.refetch(); if (fresh.isError) throw new Error('Refresh failed'); setSelected(value.id); setEditing(false); if (selected === value.id) { const result = await detail.refetch(); if (result.isError) throw new Error('Refresh failed') } }
  const refresh = async () => { setEditing(false); await list.refetch(); if (selected) await detail.refetch() }
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto max-w-5xl space-y-6">
    <Link className="text-sm text-text-accent" href={`/projects/${projectId}`}>نمای کلی پروژه ←</Link><header><h1 className="text-3xl font-bold">درخواست‌های تیم</h1><p className="mt-3 text-sm leading-7 text-text-secondary">نیازمندی را ثبت کنید، اصلاحات را نگه دارید و تصمیم ورود را به نسخهٔ مشخص یک فلو متصل کنید.</p></header>
    {!entered ? <p role="status">ابتدا وارد فضای همین پروژه شوید.</p> : list.isSuccess ? <>
      <div className="flex flex-wrap gap-3"><button className={primary} onClick={() => { setSelected(null); setEditing(true) }}>ثبت درخواست تازه</button><Link className={button} href={`/projects/${projectId}/team-flows`}>فلوهای تیم</Link></div>
      {editing && (!selected || detail.data?.can_edit) && <RequestEditor key={`${workspace}:${selected || 'new'}:${detail.data?.revision || 1}`} project={projectId} value={selected ? detail.data || null : null} saved={saved} cancel={() => setEditing(false)} />}
      {selected && !editing && (detail.isSuccess ? <RequestDetail key={`${workspace}:${selected}:${detail.data.revision}`} project={projectId} value={detail.data} saved={saved} edit={() => setEditing(true)} /> : <p role={detail.isError ? 'alert' : 'status'}>{detail.isError ? 'دریافت درخواست انجام نشد.' : 'در حال دریافت درخواست…'}</p>)}
      <section aria-label="فهرست درخواست‌ها" className="space-y-3">{!list.data.data.length && <p className={panel}>هنوز درخواستی ثبت نشده است.</p>}{list.data.data.map(value => <article key={value.id} className={panel}><h2 className="text-lg font-semibold">{value.title}</h2><p className="text-sm">نسخهٔ {num(value.version)} · {states[value.state] || value.state}</p><button className={button} onClick={() => { setSelected(value.id); setEditing(false) }}>مشاهدهٔ درخواست</button></article>)}</section>
    </> : <p role={list.isError ? 'alert' : 'status'}>{list.isError ? 'دریافت درخواست‌ها انجام نشد.' : 'در حال دریافت درخواست‌ها…'}</p>}
    <button className={button} disabled={!entered || list.isFetching} onClick={refresh}>دریافت نسخهٔ تازهٔ درخواست‌ها</button>
  </div></main>
}
