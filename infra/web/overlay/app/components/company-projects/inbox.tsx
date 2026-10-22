'use client'

import type { CompanyProject } from '@/service/company-projects'
import type { RunDetail, RunSummary } from '@/service/company-inbox'
import type { HumanInputFormData } from '@/types/workflow'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from '@/next/navigation'
import HumanInputForm from '@/app/components/base/chat/chat/answer/human-input-content/human-input-form'
import Link from '@/next/link'
import { inboxApi } from '@/service/company-inbox'
import TeamInbox from './team-inbox'
import { button, input, panel, ProjectPage, QueryNotice } from './project-page'

const states: Record<string, string> = { all: 'همهٔ اجراها', running: 'در حال اجرا', paused: 'در انتظار تصمیم', succeeded: 'موفق', failed: 'ناموفق', stopped: 'متوقف', 'partial-succeeded': 'بخشی موفق' }
const formStates: Record<string, string> = { waiting: 'در انتظار تصمیم', submitted: 'تصمیم ثبت شده', expired: 'مهلت تمام شده', timeout: 'مهلت مرحله تمام شده' }
const sources: Record<string, string> = { debugging: 'اجرای پیش‌نمایش', 'app-run': 'برنامهٔ منتشرشده', schedule: 'زمان‌بندی', webhook: 'درخواست بیرونی', plugin: 'افزونه' }
const date = (value: string | null) => value ? new Date(value).toLocaleString('fa-IR') : '—'
const number = (value: number) => value.toLocaleString('fa-IR', { maximumFractionDigits: 1 })

function Approval({ projectId, run, formId, done }: { projectId: string; run: RunDetail; formId: string; done: () => void }) {
  const form = useQuery({ queryKey: ['company-approval', projectId, run.id, formId], queryFn: () => inboxApi.form(projectId, run.id, formId), staleTime: 0 })
  const [message, setMessage] = useState('')
  const submit = async (_identifier: string, data: { inputs: Record<string, unknown>; action: string }) => {
    setMessage('')
    try { await inboxApi.submit(projectId, run.id, formId, data); done() }
    catch { setMessage('تصمیم ثبت نشد. وضعیت فرم را تازه کنید؛ ممکن است مهلت تمام شده، تصمیم قبلاً ثبت شده یا ورودی نامعتبر باشد.') }
  }
  if (!form.isSuccess) return <QueryNotice error={form.isError} retry={() => form.refetch()} />
  const value = form.data
  // The native renderer requires an identifier; the bearer token stays on the server.
  const data: HumanInputFormData = { form_id: value.id, node_id: value.node_id, node_title: value.title, form_content: value.content, inputs: value.inputs, actions: value.actions, form_token: value.id, resolved_default_values: value.default_values, display_in_ui: true, expiration_time: new Date(value.expiration_time).getTime() / 1000 }
  const expired = new Date(value.expiration_time).getTime() <= Date.now()
  return <section className={`${panel} space-y-4`}><h3 className="text-lg font-semibold text-text-primary">{value.title}</h3><p className="text-xs text-text-tertiary">مهلت تصمیم: {date(value.expiration_time)}</p>{message && <p role="alert" className="text-sm leading-7 text-text-primary">{message}</p>}{expired ? <p className="text-sm text-text-secondary">مهلت این فرم تمام شده است.</p> : <HumanInputForm key={value.id} formData={data} onSubmit={submit} />}<button className={button} onClick={() => form.refetch()}>به‌روزرسانی فرم</button></section>
}

function Execution({ projectId, id, close }: { projectId: string; id: string; close: () => void }) {
  const cache = useQueryClient()
  const [formId, setFormId] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const detail = useQuery({ queryKey: ['company-run', projectId, id], queryFn: () => inboxApi.run(projectId, id), refetchInterval: 10000 })
  const done = () => {
    setFormId(null); setMessage('تصمیم شما ثبت شد. فرایند ادامه می‌یابد.')
    void cache.invalidateQueries({ queryKey: ['company-run'] })
    void cache.invalidateQueries({ queryKey: ['company-runs'] })
    void cache.invalidateQueries({ queryKey: ['company-setup'] })
  }
  if (!detail.isSuccess) return <section><button className={`${button} mb-4`} onClick={close}>بستن جزئیات</button><QueryNotice error={detail.isError} retry={() => detail.refetch()} /></section>
  const run = detail.data
  return <section aria-label="جزئیات اجرا" className={`${panel} space-y-5`}><div className="flex flex-wrap justify-between gap-4"><div><h2 className="text-xl font-semibold text-text-primary">{run.app_name}</h2><p className="mt-2 text-sm text-text-secondary">{states[run.status] || 'وضعیت نامشخص'} · {date(run.created_at)}</p></div><button className={button} onClick={close}>بستن جزئیات</button></div><p className="break-all text-xs text-text-tertiary">شناسهٔ اجرا: <bdi>{run.id}</bdi></p>{message && <p role="status" className="text-sm leading-7 text-text-accent">{message}</p>}
    {run.forms.length > 0 && <div className="space-y-3"><h3 className="font-semibold text-text-primary">تصمیم‌های این اجرا</h3>{run.forms.map(form => <div key={form.id} className="rounded-xl border border-divider-regular p-4"><p className="text-sm text-text-primary">{formStates[form.status] || 'وضعیت نامشخص'}</p><p className="mt-2 text-xs text-text-tertiary">مهلت: {date(form.expiration_time)}{form.submitted_at && ` · ثبت تصمیم: ${date(form.submitted_at)}`}</p>{form.can_submit ? <button className={`${button} mt-3`} onClick={() => { setFormId(form.id); setMessage('') }}>بررسی و ثبت تصمیم</button> : form.status === 'waiting' && <p className="mt-2 text-xs leading-6 text-text-secondary">ثبت تصمیم برای گیرندهٔ تعیین‌شده و در مهلت فرم امکان‌پذیر است.</p>}</div>)}</div>}
    {formId && run.forms.some(form => form.id === formId && form.can_submit) && <Approval projectId={projectId} run={run} formId={formId} done={done} />}
    {run.can_read_payload ? <>{run.truncated && <p className="text-xs text-text-secondary">متن بسیار طولانی است؛ بخشی از آن در این صفحه نمایش داده می‌شود.</p>}{([['inputs', 'ورودی اجرا'], ['outputs', 'خروجی اجرا'], ['error', 'جزئیات خطا']] as const).map(([key, title]) => run[key] && <details key={key} className="rounded-xl border border-divider-regular p-4" open={key === 'error'}><summary className="cursor-pointer text-sm font-semibold text-text-primary">{title}</summary><pre dir="auto" className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap break-words text-sm leading-7 text-text-secondary">{run[key]}</pre></details>)}</> : <p className="text-sm text-text-secondary">محتوای این اجرا فقط در فرم تصمیم تعیین‌شده برای شما نمایش داده می‌شود.</p>}
    <Link className={`${button} inline-block`} href={`/app/${run.app_id}/workflow`}>باز کردن فرایند</Link>
  </section>
}

function Runs({ project }: { project: CompanyProject }) {
  const params = useSearchParams()
  const [status, setStatus] = useState('all')
  const [name, setName] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<string | null>(params.get('run'))
  const runs = useQuery({ queryKey: ['company-runs', project.workspace_id, status, search, page], queryFn: () => inboxApi.runs(project.id, status, search, page), refetchInterval: 10000 })
  return <><p className="text-sm leading-7 text-text-secondary">وضعیت اجراها، نتیجه‌ها و درخواست‌های تصمیم را پیگیری کنید. تصمیم‌های ارجاع‌شده به شما در همین کارتابل قابل بررسی‌اند.</p>
    <div className="grid gap-4 sm:grid-cols-3">{(['running', 'paused', 'failed'] as const).map(state => <button key={state} className={`${panel} text-right`} onClick={() => { setStatus(state); setPage(1); setSelected(null) }}><p className="text-sm text-text-secondary">{states[state]}</p><p className="mt-3 text-3xl font-bold text-text-primary">{number(runs.data?.counts[state] || 0)}</p></button>)}</div>
    <form className={`${panel} flex flex-wrap items-end gap-4`} onSubmit={event => { event.preventDefault(); setSearch(name.trim()); setPage(1); setSelected(null) }}><label className="min-w-48 flex-1 text-sm text-text-secondary">نام فرایند<input className={input} maxLength={120} value={name} onChange={event => setName(event.target.value)} placeholder="جستجو در نام برنامه‌ها" /></label><label className="min-w-48 text-sm text-text-secondary">وضعیت<select className={input} value={status} onChange={event => { setStatus(event.target.value); setPage(1); setSelected(null) }}>{Object.entries(states).map(([value, title]) => <option value={value} key={value}>{title}</option>)}</select></label><button className={button}>جستجو</button><button type="button" className={button} disabled={runs.isFetching} onClick={() => runs.refetch()}>به‌روزرسانی</button></form>
    {selected && <Execution key={selected} projectId={project.id} id={selected} close={() => setSelected(null)} />}
    {!runs.isSuccess ? <QueryNotice error={runs.isError} retry={() => runs.refetch()} /> : <><p className="text-sm text-text-tertiary">{number(runs.data.total)} اجرا در این فهرست</p>{runs.data.data.length ? <div className={`${panel} overflow-x-auto`}><table className="w-full min-w-[650px] text-right text-sm"><thead className="text-text-tertiary"><tr>{['فرایند', 'وضعیت', 'زمان شروع', 'نوع اجرا', 'مصرف توکن', 'جزئیات'].map(title => <th className="pb-4 font-medium" key={title}>{title}</th>)}</tr></thead><tbody className="text-text-primary">{runs.data.data.map((run: RunSummary) => <tr key={run.id} className="border-t border-divider-regular"><td className="max-w-60 py-4 pl-4">{run.app_name}</td><td className="pl-4">{states[run.status] || 'وضعیت نامشخص'}</td><td className="pl-4">{date(run.created_at)}</td><td className="pl-4">{sources[run.triggered_from] || 'سایر'}</td><td className="pl-4">{number(run.total_tokens)}</td><td><button aria-label={`جزئیات اجرای ${run.app_name}`} className={button} onClick={() => { setSelected(run.id) }}>مشاهده</button></td></tr>)}</tbody></table></div> : <section className={panel}><p className="text-sm leading-7 text-text-secondary">اجرایی با این شرایط پیدا نشد. فیلترها را تغییر دهید یا یک فرایند را از صفحهٔ برنامه اجرا کنید.</p></section>}{(page > 1 || runs.data.has_more) && <nav aria-label="صفحه‌بندی اجراها" className="flex justify-center gap-4"><button className={button} disabled={page === 1} onClick={() => setPage(page - 1)}>صفحهٔ قبل</button><p className="py-2 text-sm text-text-secondary">صفحهٔ {number(page)}</p><button className={button} disabled={!runs.data.has_more} onClick={() => setPage(page + 1)}>صفحهٔ بعد</button></nav>}</>}
  </>
}
function InboxSections({ project }: { project: CompanyProject }) {
  const params = useSearchParams()
  const [section, setSection] = useState(params.get('run') ? 'technical' : 'team')
  return <><nav aria-label="بخش‌های کارتابل" className="flex flex-wrap gap-3"><button className={button} aria-pressed={section === 'team'} onClick={() => setSection('team')}>اقدام‌های من و وضعیت تیم</button><button className={button} aria-pressed={section === 'technical'} onClick={() => setSection('technical')}>اجراها و تأییدهای فنی</button></nav>{section === 'team' ? <TeamInbox key={project.workspace_id} projectId={project.id} /> : <Runs key={project.workspace_id} project={project} />}</>
}
export default function ProjectInbox({ projectId }: { projectId: string }) {
  return <ProjectPage projectId={projectId} title="کارتابل پروژه">{project => <InboxSections project={project} />}</ProjectPage>
}
