'use client'

import type { FormEvent } from 'react'
import type { JiraImportResult } from '@/service/company-requests'
import { Button } from '@langgenius/dify-ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from '@langgenius/dify-ui/dialog'
import { IconButton } from '@langgenius/dify-ui/icon-button'
import { useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import Link from '@/next/link'
import { jiraApi, jiraError } from '@/service/company-jira'
import { requestApi } from '@/service/company-requests'

const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const outcomes: Record<JiraImportResult['data'][number]['outcome'], string> = {
  created: 'ثبت شد', updated: 'نسخهٔ تازه ثبت شد', metadata_updated: 'مشخصات جیرا به‌روز شد',
  unchanged: 'بدون تغییر', older_ignored: 'نسخهٔ قدیمی نادیده گرفته شد', needs_review: 'نیازمند بررسی؛ متن کارا حفظ شد',
}

function JiraImportForm({ projectId, accountId, saved }: { projectId: string; accountId: string; saved: () => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('fetch')
  const [connectionId, setConnectionId] = useState('')
  const [jql, setJql] = useState('')
  const [startAt, setStartAt] = useState(0)
  const [maxResults, setMaxResults] = useState(50)
  const [runId, setRunId] = useState('')
  const [json, setJson] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<JiraImportResult | null>(null)
  const operation = useRef<{ payload: string; key: string } | null>(null)
  const runs = useQuery({ queryKey: ['jira-import-runs', projectId, accountId], queryFn: () => requestApi.jiraRuns(projectId), enabled: open && mode === 'run' })
  const connections = useQuery({ queryKey: ['personal-jira-connections', accountId], queryFn: jiraApi.list, enabled: open })
  const selected = connections.data?.data.find(value => value.id === connectionId)
  const reset = () => { setError(''); setResult(null); operation.current = null }
  const changeOpen = (next: boolean) => { if (!busy) { setOpen(next); reset() } }
  const perform = async (start = startAt) => {
    if (busy) return
    setError(''); setResult(null)
    if (!selected) { setError('یکی از اتصال‌های شخصی جیرا را انتخاب کنید.'); return }
    let body: { connection_id: string; run_id: string } | { connection_id: string; response: unknown }
    try {
      body = mode === 'json' ? { connection_id: connectionId, response: JSON.parse(json) } : { connection_id: connectionId, run_id: runId }
    } catch { setError('JSON معتبر وارد کنید؛ متن نمایشی تب نتیجه یا دستور cURL قابل ورود نیست.'); return }
    const fetchBody = { connection_id: connectionId, jql, start_at: start, max_results: maxResults }
    const payload = JSON.stringify({ mode, body: mode === 'fetch' ? fetchBody : body })
    if (operation.current?.payload !== payload) operation.current = { payload, key: crypto.randomUUID() }
    setBusy(true)
    try {
      const imported = mode === 'fetch' ? await requestApi.fetchJira(projectId, fetchBody, operation.current.key) : await requestApi.importJira(projectId, body, operation.current.key)
      setResult(imported); operation.current = null
      if (mode === 'fetch') setStartAt(imported.start_at)
      try { await saved() } catch { setError('ورود انجام شد؛ برای مشاهدهٔ فهرست تازه، صفحه را به‌روزرسانی کنید.') }
    } catch (error) { setError(await jiraError(error, 'ورود انجام نشد. اتصال، ساختار پاسخ و مجوزهای خود را بررسی کنید.')) }
    finally { setBusy(false) }
  }
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void perform() }
  return <Dialog open={open} onOpenChange={changeOpen}>
    <DialogTrigger render={<Button variant="secondary">ورود از جیرا</Button>} />
    <DialogContent className="max-w-2xl" dir="rtl">
      <DialogTitle>ورود درخواست‌های جیرا</DialogTitle>
      <DialogDescription>اتصال شخصی خودتان را انتخاب کنید و درخواست‌ها را مستقیم از جیرا یا از پاسخ ذخیره‌شده وارد کنید. دریافت تکراری، درخواست تازه نمی‌سازد. تصمیم PO همچنان جداگانه ثبت می‌شود.</DialogDescription>
      <form onSubmit={submit} className="mt-5 space-y-4">
        <fieldset disabled={busy} className="space-y-4">
          <label className="block text-sm">اتصال جیرا<select required className={field} value={connectionId} onChange={event => { setConnectionId(event.target.value); reset() }}><option value="">اتصال شخصی خودتان را انتخاب کنید</option>{connections.data?.data.map(value => <option key={value.id} value={value.id}>{value.name} · {value.base_url}</option>)}</select></label>
          {selected && <p className="text-xs leading-6 text-text-tertiary">نشانی از اتصال انتخاب‌شده گرفته می‌شود. در دریافت مستقیم، فقط توکن ذخیره‌شدهٔ همین اتصال در حساب شما استفاده می‌شود.</p>}
          {connections.isPending && <p role="status">در حال دریافت اتصال‌ها…</p>}
          {connections.isError && <p role="alert">دریافت اتصال‌ها انجام نشد. <button type="button" onClick={() => connections.refetch()}>تلاش دوباره</button></p>}
          {connections.isSuccess && !connections.data.data.length && <p>ابتدا از «اتصال به جیرا» یک اتصال شخصی بسازید.</p>}
          <Link className="inline-block text-sm text-text-accent" href={`/projects/${projectId}/jira-connections`}>تنظیمات و اتصال‌ها ← اتصال به جیرا</Link>
          <label className="block text-sm">منبع ورود<select className={field} value={mode} onChange={event => { setMode(event.target.value); reset() }}><option value="fetch">دریافت مستقیم از جیرا</option><option value="run">نتیجهٔ اجرای Workflow</option><option value="json">پاسخ JSON ذخیره‌شده</option></select></label>
          {mode === 'fetch' ? <>
            <label className="block text-sm">عبارت جست‌وجوی JQL<textarea required maxLength={4000} className={`${field} font-mono`} dir="ltr" placeholder={'project = "Your Project" ORDER BY key DESC'} value={jql} onChange={event => { setJql(event.target.value); reset() }} /><span className="mt-2 block text-xs leading-6 text-text-tertiary">فیلتر پروژه و محصول را مطابق جیرای خودتان وارد کنید. نتایج به دسترسی همان توکن در جیرا محدودند.</span></label>
            <div className="grid grid-cols-2 gap-4"><label className="block text-sm">شروع صفحه<input type="number" min={0} max={2147483647} required className={field} value={startAt} onChange={event => { setStartAt(Number(event.target.value)); reset() }} /></label><label className="block text-sm">تعداد هر صفحه<input type="number" min={1} max={100} required className={field} value={maxResults} onChange={event => { setMaxResults(Number(event.target.value)); reset() }} /></label></div>
            <p className="text-xs leading-6 text-text-tertiary">هر بار یک صفحه دریافت و ثبت می‌شود. شروع اولین صفحه صفر است. سرور کارا باید به جیرا دسترسی شبکه داشته باشد.</p>
          </> : mode === 'run' ? <>
            <label className="block text-sm">اجرای موفق<select required className={field} value={runId} onChange={event => { setRunId(event.target.value); reset() }}><option value="">یک اجرا انتخاب کنید</option>{runs.data?.data.map(run => <option key={run.id} value={run.id}>{run.app_name} · {new Date(run.created_at).toLocaleString('fa-IR')} · {run.received_count.toLocaleString('fa-IR')} درخواست</option>)}</select></label>
            <p className="text-xs leading-6 text-text-tertiary">اجراهای موفق اخیرِ خودتان در همین پروژه، از جمله اجرای آزمایشی، نمایش داده می‌شوند. اجرای دارای خروجی issues، total و start_at یا startAt را انتخاب کنید.</p>
            {runs.isFetching && <p role="status">در حال دریافت اجراها…</p>}
            {runs.isError && <p role="alert">دریافت اجراها انجام نشد. <button type="button" onClick={() => runs.refetch()}>تلاش دوباره</button></p>}
            {runs.isSuccess && !runs.data.data.length && <p role="status">اجرای سازگاری پیدا نشد؛ می‌توانید پاسخ JSON ذخیره‌شده را وارد کنید.</p>}
          </> : <label className="block text-sm">پاسخ JSON<textarea required maxLength={2000000} className={`${field} min-h-48 font-mono`} dir="ltr" value={json} onChange={event => { setJson(event.target.value); reset() }} /><span className="mt-2 block text-xs leading-6 text-text-tertiary">بدنهٔ پاسخ جست‌وجوی جیرا یا خروجی JSON فرایند؛ حداکثر ۱۰۰ درخواست و دو مگابایت. توکن و هدر Authorization وارد نکنید.</span></label>}
          <p className="text-xs leading-6 text-text-tertiary">تغییر متن یا عنوان جیرا، نسخهٔ تازه و نیاز به تصمیم مجدد PO ایجاد می‌کند. اگر متن در کارا جداگانه ویرایش شده باشد، متن فعلی حفظ و تغییر جیرا برای بررسی نمایش داده می‌شود. نوع فیچر، باگ یا ساپورت از روی متن حدس زده نمی‌شود.</p>
        </fieldset>
        {error && <p role="alert" className="text-sm text-text-destructive-secondary">{error}</p>}
        {result && <section aria-label="نتیجهٔ ورود از جیرا" className="space-y-2 text-sm" role="status">
          <p>تعداد این صفحه: {result.received_count.toLocaleString('fa-IR')} از مجموع {result.total.toLocaleString('fa-IR')} · شروع صفحه: {result.start_at.toLocaleString('fa-IR')}</p>
          {result.has_more && <p>صفحه‌های دیگری باقی مانده‌اند؛ این نتیجه به معنی دریافت همهٔ درخواست‌ها نیست.</p>}
          {mode === 'fetch' && result.has_more && result.received_count > 0 && <Button type="button" variant="secondary" disabled={busy} onClick={() => void perform(result.start_at + result.received_count)}>دریافت و ثبت صفحهٔ بعد</Button>}
          {!result.data.length && <p>این صفحه درخواستی ندارد.</p>}
          <ul>{result.data.map(item => <li key={item.request_id}><span dir="ltr">{item.key}</span> — {outcomes[item.outcome]}</li>)}</ul>
        </section>}
        <div className="flex justify-end gap-2"><Button type="button" variant="secondary" disabled={busy} onClick={() => changeOpen(false)}>بستن</Button><Button type="submit" variant="primary" disabled={busy || !selected || (mode === 'run' && (!runId || !runs.isSuccess))}>{busy ? 'در حال ورود…' : mode === 'fetch' ? 'دریافت و ثبت درخواست‌ها' : 'ثبت و به‌روزرسانی درخواست‌ها'}</Button></div>
      </form>
      <DialogClose render={<IconButton aria-label="بستن" size="lg" disabled={busy} className="absolute inset-e-6 top-6"><span aria-hidden className="i-ri-close-line size-4" /></IconButton>} />
    </DialogContent>
  </Dialog>
}

export default function JiraImport({ projectId, saved }: { projectId: string; saved: () => Promise<void> }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  return <JiraImportForm key={`${profile.id}:${projectId}`} projectId={projectId} accountId={profile.id} saved={saved} />
}
