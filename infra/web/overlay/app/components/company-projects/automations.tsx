'use client'

import type { Automation, AutomationSource, Schedule } from '@/service/company-automations'
import type { CompanyProject } from '@/service/company-projects'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import Link from '@/next/link'
import { automationApi } from '@/service/company-automations'
import { button, input, panel, primary, ProjectPage, QueryNotice } from './project-page'
import FormDialog, { FieldHelp } from './form-dialog'
import { DirectorySummary, DirectoryEmpty, directoryPanel } from './team-directory'

const defaultSchedule: Schedule = { frequency: 'weekly', time: '09:00', minute: 0, weekdays: ['sat'], day: 1 }
const days = [['sat', 'شنبه'], ['sun', 'یکشنبه'], ['mon', 'دوشنبه'], ['tue', 'سه‌شنبه'], ['wed', 'چهارشنبه'], ['thu', 'پنجشنبه'], ['fri', 'جمعه']] as const
const states: Record<string, string> = { enabled: 'فعال', disabled: 'متوقف', unauthorized: 'نیازمند اتصال', rate_limited: 'محدودیت مصرف' }
const results: Record<string, string> = { pending: 'در انتظار اجرا', queued: 'در صف', running: 'در حال اجرا', succeeded: 'موفق', failed: 'ناموفق', paused: 'در انتظار تصمیم', stopped: 'متوقف', 'partial-succeeded': 'بخشی موفق', rate_limited: 'محدودیت مصرف', retrying: 'تلاش دوباره' }
const types: Record<string, string> = { 'trigger-schedule': 'زمان‌بندی', 'trigger-webhook': 'رویداد بیرونی', 'trigger-plugin': 'اتصال به سامانه' }
const date = (value: string | null) => value ? new Date(value).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' }) : '—'
const number = (value: number) => value.toLocaleString('fa-IR')

function ScheduleFields({ projectId, value, change, disabled }: { projectId: string; value: Schedule; change: (value: Schedule) => void; disabled: boolean }) {
  const preview = useQuery({ queryKey: ['company-schedule-preview', projectId, value], queryFn: () => automationApi.preview(projectId, value), retry: false, staleTime: 30000 })
  return <fieldset disabled={disabled} className="space-y-4"><legend className="mb-3 font-semibold text-text-primary">زمان اجرا</legend>
    <div className="flex flex-wrap gap-4"><label className="min-w-48 flex-1 text-sm text-text-secondary">تکرار<select className={input} value={value.frequency} onChange={event => change({ ...value, frequency: event.target.value as Schedule['frequency'] })}>{([['hourly', 'هر ساعت'], ['daily', 'هر روز'], ['weekly', 'هر هفته'], ['monthly', 'هر ماه']] as const).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select><FieldHelp>مشخص کنید فرایند هر ساعت، هر روز، روزهای انتخاب‌شدهٔ هفته یا یک روز مشخص از ماه اجرا شود.</FieldHelp></label>
      {value.frequency === 'hourly' ? <label className="min-w-40 text-sm text-text-secondary">دقیقهٔ هر ساعت<input type="number" min={0} max={59} required className={input} value={value.minute} onChange={event => change({ ...value, minute: Number(event.target.value) })} /><FieldHelp>عددی از صفر تا ۵۹؛ مثلاً ۱۵ یعنی اجرا در دقیقهٔ پانزدهم هر ساعت.</FieldHelp></label> : <label className="min-w-40 text-sm text-text-secondary">ساعت به وقت تهران<input type="time" required dir="ltr" className={input} value={value.time} onChange={event => change({ ...value, time: event.target.value })} /><FieldHelp>ساعت اجرای روزهای انتخاب‌شده بر اساس منطقهٔ زمانی تهران است.</FieldHelp></label>}
    </div>
    {value.frequency === 'weekly' && <div><p className="mb-3 text-sm text-text-secondary">روزهای هفته</p><p className="mb-3 text-xs leading-6 text-text-tertiary">حداقل یک روز را انتخاب کنید؛ فرایند در همین روزها و ساعت تعیین‌شده اجرا می‌شود.</p><div className="flex flex-wrap gap-4">{days.map(([key, label]) => <label className="flex items-center gap-2 text-sm text-text-primary" key={key}><input type="checkbox" checked={value.weekdays.includes(key)} onChange={event => change({ ...value, weekdays: event.target.checked ? [...value.weekdays, key] : value.weekdays.filter(day => day !== key) })} />{label}</label>)}</div></div>}
    {value.frequency === 'monthly' && <label className="block text-sm text-text-secondary">روز ماه<input type="number" required min={1} max={31} className={`${input} max-w-40`} value={value.day} onChange={event => change({ ...value, day: Number(event.target.value) })} /><FieldHelp>شمارهٔ روز ماه میلادی از ۱ تا ۳۱؛ در ماه فاقد این روز، اجرا انجام نمی‌شود.</FieldHelp></label>}
    <p className="text-sm leading-7 text-text-tertiary" role="status">{preview.data ? `اولین زمان پیش رو: ${date(preview.data.next_run_at)} · به وقت تهران` : preview.isError ? 'برای نمایش زمان بعدی، ساعت و روزهای معتبر انتخاب کنید.' : 'در حال محاسبهٔ زمان بعدی…'}</p>
  </fieldset>
}

function SourceInputs({ source, values, change }: { source: AutomationSource; values: Record<string, string | boolean>; change: (values: Record<string, string | boolean>) => void }) {
  if (!source.fields.length) return <p className="text-sm text-text-tertiary">این فرایند ورودی ثابت نیاز ندارد.</p>
  return <fieldset className="space-y-4"><legend className="mb-3 font-semibold text-text-primary">ورودی‌های ثابت</legend><p className="text-sm leading-7 text-text-secondary">این مقادیر در هر اجرای زمان‌بندی‌شده به فرایند داده می‌شوند. دریافت اطلاعات تازه را داخل خود فرایند تعریف کنید.</p>{source.fields.map(field => {
    const text = typeof values[field.variable] === 'string' ? values[field.variable] as string : ''
    return <label className="block text-sm text-text-secondary" key={field.variable}>{field.label || field.variable}{field.required && ' (الزامی)'}
      {field.type === 'checkbox' ? <input className="mr-3" type="checkbox" checked={values[field.variable] === true} onChange={event => change({ ...values, [field.variable]: event.target.checked })} />
        : field.type === 'select' ? <select required={field.required} className={input} value={text} onChange={event => change({ ...values, [field.variable]: event.target.value })}><option value="">انتخاب کنید</option>{field.options?.map(option => <option key={option} value={option}>{option}</option>)}</select>
          : field.type === 'paragraph' ? <textarea rows={3} required={field.required} maxLength={field.max_length || 48000} className={input} value={text} onChange={event => change({ ...values, [field.variable]: event.target.value })} />
            : <input type={field.type === 'number' ? 'number' : 'text'} step={field.type === 'number' ? 'any' : undefined} required={field.required || field.type === 'number'} maxLength={field.max_length || 48000} className={input} value={text} onChange={event => change({ ...values, [field.variable]: event.target.value })} />}
      <FieldHelp>این مقدار ثابت در هر اجرای زمان‌بندی‌شده برای همین ورودی استفاده می‌شود؛ دریافت دادهٔ تازه را داخل فرایند تعریف کنید.</FieldHelp>
    </label>
  })}</fieldset>
}

function CreateAutomation({ project, busy, error, save, cancel }: { project: CompanyProject; busy: boolean; error?: string; save: (operation: () => Promise<unknown>, done: () => void) => Promise<void>; cancel: () => void }) {
  const sources = useQuery({ queryKey: ['company-automation-sources', project.workspace_id], queryFn: () => automationApi.sources(project.id) })
  const [sourceId, setSourceId] = useState('')
  const [name, setName] = useState('')
  const [values, setValues] = useState<Record<string, string | boolean>>({})
  const [schedule, setSchedule] = useState(defaultSchedule)
  const source = sources.data?.data.find(value => value.id === sourceId)
  return <FormDialog open title="ساخت اتوماسیون" description="نسخه‌ای مستقل از یک فرایند منتشرشده بسازید و ورودی‌ها و زمان اجرای آن را مشخص کنید. اتوماسیون پس از ساخت متوقف می‌ماند تا آن را بررسی و فعال کنید." busy={busy} error={error} close={cancel}>
    <form aria-label="ساخت اتوماسیون" className="space-y-6" onSubmit={event => {
    event.preventDefault()
    if (!source || !source.available || !name.trim()) return
    const inputs = Object.fromEntries(source.fields.map(field => [field.variable, field.type === 'number' ? Number(values[field.variable]) : field.type === 'checkbox' ? values[field.variable] === true : values[field.variable] || '']))
    void save(() => automationApi.create(project.id, { name: name.trim(), source_app_id: source.id, source_workflow_id: source.workflow_id, inputs, schedule }), cancel)
  }}>
    <fieldset disabled={busy} className="space-y-6">
    <label className="block text-sm text-text-secondary">نام اتوماسیون<input required maxLength={120} className={input} value={name} disabled={busy} onChange={event => setName(event.target.value)} /><FieldHelp>نامی روشن برای هدف این اجرای دوره‌ای انتخاب کنید تا در فهرست و تاریخچه قابل تشخیص باشد.</FieldHelp></label>
    {!sources.isSuccess ? <QueryNotice error={sources.isError} retry={() => sources.refetch()} /> : <><label className="block text-sm text-text-secondary">فرایند مبنا<select required disabled={busy} className={input} value={sourceId} onChange={event => { setSourceId(event.target.value); setValues({}) }}><option value="">یک فرایند منتشرشده انتخاب کنید</option>{sources.data.data.map(value => <option key={value.id} value={value.id} disabled={!value.available}>{value.name}{!value.available && ' · نیازمند تنظیم در فرایند'}</option>)}</select><FieldHelp>از نسخهٔ منتشرشدهٔ این فرایند یک کپی مستقل ساخته می‌شود؛ تغییرات بعدی برنامهٔ مبنا به آن منتقل نمی‌شوند.</FieldHelp></label>
      {!sources.data.data.some(value => value.available) && <p className="text-sm leading-7 text-text-secondary">فرایند مناسبی برای زمان‌بندی پیدا نشد. یک فرایند با شروع «ورودی کاربر» بسازید و منتشر کنید. فرایند دارای ورودی فایل به مرحلهٔ دریافت داده در داخل فرایند نیاز دارد.</p>}
      {source && <><Link className="inline-block text-sm text-text-accent" href={`/app/${source.id}/workflow`}>مشاهدهٔ فرایند مبنا</Link><SourceInputs source={source} values={values} change={setValues} /></>}
    </>}
    <ScheduleFields projectId={project.id} value={schedule} change={setSchedule} disabled={busy} />
    <div className="flex flex-wrap gap-3"><button className={primary} disabled={busy || !source?.available || (schedule.frequency === 'weekly' && !schedule.weekdays.length)}>ساخت اتوماسیون</button><button type="button" className={button} disabled={busy} onClick={cancel}>انصراف</button></div>
    </fieldset>
    </form>
  </FormDialog>
}

function ActivateAutomation({ projectId, value, busy, save, close }: { projectId: string; value: Automation; busy: boolean; save: (operation: () => Promise<unknown>, done: () => void) => Promise<void>; close: () => void }) {
  const [reviewed, setReviewed] = useState(false)
  return <section aria-label="فعال‌سازی اتوماسیون" className={`${panel} space-y-4`}><h2 className="text-xl font-semibold text-text-primary">فعال‌سازی «{value.name}»</h2>
    <p className="text-sm leading-7 text-text-secondary">{value.managed ? 'با فعال‌سازی، نسخهٔ فعلی این فرایند منتشر می‌شود و اجراهای بعدی از همین نسخه استفاده می‌کنند. ورودی‌ها، اتصال‌ها و گیرندهٔ مراحل تأیید را بررسی کنید.' : 'شروع خودکار این فرایند فعال می‌شود. فرایند منتشرشده، اتصال‌ها و گیرندهٔ مراحل تأیید را بررسی کنید.'}</p>
    {value.type === 'trigger-schedule' && <p className="text-sm leading-7 text-text-tertiary">اجراهای زمان‌بندی‌شده با حساب مالک پروژه انجام می‌شوند.</p>}
    <Link className="inline-block text-sm text-text-accent" href={`/app/${value.app_id}/workflow`}>بررسی فرایند و ورودی‌ها</Link>
    <label className="flex items-start gap-3 text-sm leading-7 text-text-primary"><input className="mt-2" type="checkbox" checked={reviewed} disabled={busy} onChange={event => setReviewed(event.target.checked)} />فرایند را بررسی کرده‌ام و برای اجرای خودکار آماده است.</label>
    <div className="flex flex-wrap gap-3"><button className={primary} disabled={busy || !reviewed} onClick={() => save(() => automationApi.state(projectId, value.id, true, reviewed), close)}>فعال‌سازی</button><button className={button} disabled={busy} onClick={close}>انصراف</button></div>
  </section>
}

function EditSchedule({ projectId, value, busy, save, close }: { projectId: string; value: Automation; busy: boolean; save: (operation: () => Promise<unknown>, done: () => void) => Promise<void>; close: () => void }) {
  const current = useQuery({ queryKey: ['company-automation-schedule', projectId, value.id], queryFn: () => automationApi.schedule(projectId, value.id), retry: false })
  const [changed, setChanged] = useState<Schedule | null>(null)
  if (!current.isSuccess) return <section className={`${panel} space-y-4`}><p className="text-sm text-text-secondary">{current.isError ? 'این زمان‌بندی تنظیمات پیشرفته دارد یا دریافت آن انجام نشد. آن را از صفحهٔ فرایند بررسی کنید.' : 'در حال دریافت زمان‌بندی…'}</p><Link className="inline-block text-sm text-text-accent" href={`/app/${value.app_id}/workflow`}>باز کردن فرایند</Link><button className={button} onClick={close}>بستن</button></section>
  const schedule = changed || current.data
  return <form aria-label="ویرایش زمان‌بندی" className={`${panel} space-y-5`} onSubmit={event => { event.preventDefault(); void save(() => automationApi.updateSchedule(projectId, value.id, schedule), close) }}><h2 className="text-xl font-semibold text-text-primary">زمان‌بندی «{value.name}»</h2><ScheduleFields projectId={projectId} value={schedule} change={setChanged} disabled={busy} /><p className="text-sm leading-7 text-text-tertiary">پس از ذخیره، اتوماسیون متوقف می‌ماند. برای اجرای برنامهٔ جدید آن را دوباره فعال کنید.</p><div className="flex gap-3"><button className={primary} disabled={busy || (schedule.frequency === 'weekly' && !schedule.weekdays.length)}>ذخیرهٔ زمان‌بندی</button><button type="button" className={button} disabled={busy} onClick={close}>انصراف</button></div></form>
}

function Automations({ project }: { project: CompanyProject }) {
  const cache = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [activating, setActivating] = useState<Automation | null>(null)
  const [editing, setEditing] = useState<Automation | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [status, setStatus] = useState('all')
  const [name, setName] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const list = useQuery({ queryKey: ['company-automations', project.workspace_id, status, search, page], queryFn: () => automationApi.list(project.id, status, search, page), refetchInterval: 10000 })
  const save = async (operation: () => Promise<unknown>, done: () => void) => {
    if (busy) return
    setBusy(true); setMessage('')
    try { await operation(); await cache.invalidateQueries({ queryKey: ['company-automations'] }); await cache.invalidateQueries({ queryKey: ['company-automation-sources'] }); await cache.invalidateQueries({ queryKey: ['company-automation-schedule'] }); done() }
    catch { setMessage('عملیات انجام نشد. وضعیت فرایند، ورودی‌ها، اتصال‌ها و دسترسی خود را بررسی کنید و دوباره تلاش کنید.') }
    finally { setBusy(false) }
  }
  return <><div className="flex flex-wrap items-start justify-between gap-4"><p className="max-w-3xl text-sm leading-7 text-text-secondary">فرایندهای خودکار این پروژه را زمان‌بندی کنید و وضعیت اجراهای آن‌ها را ببینید. توقف اتوماسیون، شروع‌های بعدی را غیرفعال می‌کند؛ اجراهای در حال انجام ادامه می‌یابند.</p>{project.can_edit && <button className={primary} onClick={() => { setCreating(true); setActivating(null); setEditing(null); setMessage('') }}>اتوماسیون جدید</button>}</div>
    {message && <p role="alert" className="text-sm leading-7 text-text-primary">{message}</p>}
    {creating && <CreateAutomation project={project} busy={busy} error={message} save={save} cancel={() => setCreating(false)} />}
    {activating && <FormDialog open title="فعال‌سازی اتوماسیون" description="تنظیمات و ورودی‌های فرایند را بررسی کنید؛ با تأیید شما، شروع‌های بعدی اتوماسیون فعال می‌شوند." busy={busy} error={message} close={() => setActivating(null)}><ActivateAutomation key={activating.id} projectId={project.id} value={activating} busy={busy} save={save} close={() => setActivating(null)} /></FormDialog>}
    {editing && <FormDialog open title="ویرایش زمان‌بندی" description="زمان‌های اجرای بعدی را تنظیم کنید. پس از ذخیره، اتوماسیون متوقف می‌ماند تا دوباره آن را فعال کنید." busy={busy} error={message} close={() => setEditing(null)}><EditSchedule key={editing.id} projectId={project.id} value={editing} busy={busy} save={save} close={() => setEditing(null)} /></FormDialog>}
    <form aria-label="جستجو و فیلتر اتوماسیون‌ها" className={`${directoryPanel} flex min-w-0 flex-wrap items-end gap-4`} onSubmit={event => { event.preventDefault(); setSearch(name.trim()); setPage(1) }}><label className="min-w-0 flex-1 basis-48 text-sm text-text-secondary">نام اتوماسیون<input maxLength={120} className={input} value={name} onChange={event => setName(event.target.value)} /></label><label className="min-w-0 flex-1 basis-40 text-sm text-text-secondary">وضعیت<select className={input} value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="all">همه</option>{Object.entries(states).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label><button className={primary}>اعمال جستجو</button>{(search || status !== 'all' || name) && <button type="button" className={button} onClick={() => { setName(''); setSearch(''); setStatus('all'); setPage(1) }}>پاک‌کردن فیلترها</button>}<button type="button" disabled={list.isFetching} className={button} onClick={() => list.refetch()}>به‌روزرسانی</button></form>
    {list.isError && <QueryNotice error retry={() => list.refetch()} />}{list.isPending && <QueryNotice error={false} retry={() => list.refetch()} />}{list.data && <>{list.isError && <p role="status" className="text-sm">آخرین اطلاعات دریافت‌شده نمایش داده می‌شود؛ تازه‌سازی موفق نبود.</p>}<DirectorySummary items={[{ label: 'نتیجه مطابق فیلترها', count: list.data.total }, { label: 'فعال در این صفحه', count: list.data.data.filter(value => value.status === 'enabled').length }, { label: 'متوقف در این صفحه', count: list.data.data.filter(value => value.status === 'disabled').length }, { label: 'نیازمند رسیدگی در این صفحه', count: list.data.data.filter(value => ['unauthorized', 'rate_limited'].includes(value.status) || value.last_run?.status === 'failed').length }]} />{list.data.data.length ? <div className="grid gap-5 lg:grid-cols-2">{list.data.data.map(value => <article className={`${panel} min-w-0 space-y-4 [overflow-wrap:anywhere]`} key={value.id}><div className="flex flex-wrap items-start justify-between gap-3"><h2 className="break-words text-lg font-semibold text-text-primary">{value.name}</h2><span className="rounded-lg bg-background-default-subtle px-3 py-1 text-xs text-text-secondary">{states[value.status] || 'وضعیت نامشخص'}</span></div><p className="text-sm text-text-secondary">{types[value.type] || 'شروع خودکار'}{value.title && ` · ${value.title}`}</p><dl className="space-y-3 text-sm"><div><dt className="text-text-tertiary">اجرای بعدی</dt><dd className="mt-1 text-text-primary">{value.type !== 'trigger-schedule' ? 'پس از دریافت رویداد' : value.status === 'enabled' ? `${date(value.next_run_at)} · به وقت تهران` : 'پس از فعال‌سازی زمان‌بندی می‌شود'}</dd></div><div><dt className="text-text-tertiary">آخرین اجرا</dt><dd className="mt-1 text-text-primary">{value.last_run ? `${results[value.last_run.status] || 'وضعیت نامشخص'} · ${date(value.last_run.created_at)}` : 'هنوز اجرا نشده است'}</dd></div></dl>
      {value.last_run?.status === 'failed' && <p className="rounded-xl bg-background-default-subtle p-3 text-sm leading-7 text-text-primary">آخرین اجرا ناموفق بوده است؛ جزئیات آن را در کارتابل بررسی کنید. فعال‌بودن زمان‌بندی به معنی موفقیت اجرا نیست.</p>}
      {!value.published && <p className="text-xs leading-6 text-text-tertiary">فرایند هنوز منتشر نشده است؛ هنگام فعال‌سازی بررسی و منتشر می‌شود.</p>}
      <footer className="flex flex-wrap gap-2 border-t border-divider-regular pt-5"><Link className={button} href={`/app/${value.app_id}/workflow`}>مشاهدهٔ فرایند</Link><Link className={button} href={`/projects/${project.id}/inbox${value.last_run?.run_id ? `?run=${value.last_run.run_id}` : ''}`}>کارتابل اجراها</Link>
        {value.can_manage && (value.status === 'enabled' ? <button className={button} disabled={busy} onClick={() => save(() => automationApi.state(project.id, value.id, false), () => { setActivating(null); setEditing(null) })}>توقف</button> : value.can_publish && <button className={primary} disabled={busy} onClick={() => { setActivating(value); setEditing(null); setCreating(false); setMessage('') }}>فعال‌سازی</button>)}
        {value.can_manage && value.managed && value.status !== 'enabled' && <button className={button} disabled={busy} onClick={() => { setEditing(value); setActivating(null); setCreating(false); setMessage('') }}>ویرایش زمان‌بندی</button>}
      </footer>
    </article>)}</div> : <DirectoryEmpty filtered={!!search || status !== 'all'} title="هنوز اتوماسیونی در دسترس شما نیست" reset={() => { setName(''); setSearch(''); setStatus('all'); setPage(1) }}>از یک فرایند منتشرشده اتوماسیون بسازید؛ اتوماسیون تازه تا بررسی و فعال‌سازی شما متوقف می‌ماند.</DirectoryEmpty>}
      {(page > 1 || list.data.has_more) && <nav aria-label="صفحه‌بندی اتوماسیون‌ها" className="flex justify-center gap-4"><button className={button} disabled={page === 1} onClick={() => setPage(page - 1)}>صفحهٔ قبل</button><p className="py-2 text-sm text-text-secondary">صفحهٔ {number(page)}</p><button className={button} disabled={!list.data.has_more} onClick={() => setPage(page + 1)}>صفحهٔ بعد</button></nav>}
    </>}
  </>
}

export default function ProjectAutomations({ projectId }: { projectId: string }) {
  return <ProjectPage projectId={projectId} title="اتوماسیون‌ها">{project => <Automations project={project} />}</ProjectPage>
}
