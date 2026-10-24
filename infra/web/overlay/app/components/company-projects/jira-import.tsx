'use client'

import type { FormEvent } from 'react'
import type { JiraImportResult } from '@/service/company-requests'
import { Button } from '@langgenius/dify-ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from '@langgenius/dify-ui/dialog'
import { IconButton } from '@langgenius/dify-ui/icon-button'
import { useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { requestApi } from '@/service/company-requests'

const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const outcomes: Record<JiraImportResult['data'][number]['outcome'], string> = {
  created: 'ثبت شد', updated: 'نسخهٔ تازه ثبت شد', metadata_updated: 'مشخصات جیرا به‌روز شد',
  unchanged: 'بدون تغییر', older_ignored: 'نسخهٔ قدیمی نادیده گرفته شد', needs_review: 'نیازمند بررسی؛ متن کارا حفظ شد',
}

export default function JiraImport({ projectId, saved }: { projectId: string; saved: () => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('run')
  const [address, setAddress] = useState('')
  const [runId, setRunId] = useState('')
  const [json, setJson] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<JiraImportResult | null>(null)
  const operation = useRef<{ payload: string; key: string } | null>(null)
  const runs = useQuery({ queryKey: ['jira-import-runs', projectId], queryFn: () => requestApi.jiraRuns(projectId), enabled: open && mode === 'run' })
  const changeOpen = (next: boolean) => { if (!busy) { setOpen(next); setError(''); setResult(null) } }
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (busy) return
    setError(''); setResult(null)
    let body: { base_url: string; run_id: string } | { base_url: string; response: unknown }
    try {
      body = mode === 'run' ? { base_url: address, run_id: runId } : { base_url: address, response: JSON.parse(json) }
    } catch { setError('JSON معتبر وارد کنید؛ متن نمایشی تب نتیجه یا دستور cURL قابل ورود نیست.'); return }
    const payload = JSON.stringify(body)
    if (operation.current?.payload !== payload) operation.current = { payload, key: crypto.randomUUID() }
    setBusy(true)
    try {
      const imported = await requestApi.importJira(projectId, body, operation.current.key)
      setResult(imported); operation.current = null
      try { await saved() } catch { setError('ورود انجام شد؛ برای مشاهدهٔ فهرست تازه، صفحه را به‌روزرسانی کنید.') }
    } catch { setError('ورود انجام نشد. نشانی پایه، ساختار پاسخ، مجوز و نتیجهٔ اجرای انتخاب‌شده را بررسی کنید.') }
    finally { setBusy(false) }
  }
  return <Dialog open={open} onOpenChange={changeOpen}>
    <DialogTrigger render={<Button variant="secondary">ورود از جیرا</Button>} />
    <DialogContent className="max-w-2xl" dir="rtl">
      <DialogTitle>ورود درخواست‌های جیرا</DialogTitle>
      <DialogDescription>نتیجهٔ اجرای خودتان یا پاسخ ذخیره‌شده را وارد کنید. درخواست تکراری دوباره ساخته نمی‌شود. این اقدام به سرور جیرا متصل نمی‌شود و تصمیم PO ثبت نمی‌کند.</DialogDescription>
      <form onSubmit={submit} className="mt-5 space-y-4">
        <fieldset disabled={busy} className="space-y-4">
          <label className="block text-sm">نشانی پایهٔ جیرا<input type="url" required maxLength={512} className={field} dir="ltr" placeholder="https://jira.example.com" value={address} onChange={event => setAddress(event.target.value)} /></label>
          <label className="block text-sm">منبع ورود<select className={field} value={mode} onChange={event => { setMode(event.target.value); setResult(null); setError('') }}><option value="run">نتیجهٔ اجرای Workflow</option><option value="json">پاسخ JSON ذخیره‌شده</option></select></label>
          {mode === 'run' ? <>
            <label className="block text-sm">اجرای موفق<select required className={field} value={runId} onChange={event => setRunId(event.target.value)}><option value="">یک اجرا انتخاب کنید</option>{runs.data?.data.map(run => <option key={run.id} value={run.id}>{run.app_name} · {new Date(run.created_at).toLocaleString('fa-IR')} · {run.received_count.toLocaleString('fa-IR')} درخواست</option>)}</select></label>
            <p className="text-xs leading-6 text-text-tertiary">اجراهای موفق اخیرِ خودتان در همین پروژه، از جمله اجرای آزمایشی، نمایش داده می‌شوند. اجرای دارای خروجی issues، total و start_at یا startAt را انتخاب کنید.</p>
            {runs.isFetching && <p role="status">در حال دریافت اجراها…</p>}
            {runs.isError && <p role="alert">دریافت اجراها انجام نشد. <button type="button" onClick={() => runs.refetch()}>تلاش دوباره</button></p>}
            {runs.isSuccess && !runs.data.data.length && <p role="status">اجرای سازگاری پیدا نشد؛ می‌توانید پاسخ JSON ذخیره‌شده را وارد کنید.</p>}
          </> : <label className="block text-sm">پاسخ JSON<textarea required maxLength={2000000} className={`${field} min-h-48 font-mono`} dir="ltr" value={json} onChange={event => setJson(event.target.value)} /><span className="mt-2 block text-xs leading-6 text-text-tertiary">بدنهٔ پاسخ جست‌وجوی جیرا یا خروجی JSON فرایند؛ حداکثر ۱۰۰ درخواست و دو مگابایت. توکن و هدر Authorization وارد نکنید.</span></label>}
          <p className="text-xs leading-6 text-text-tertiary">تغییر متن یا عنوان جیرا، نسخهٔ تازه و نیاز به تصمیم مجدد PO ایجاد می‌کند. اگر متن در کارا جداگانه ویرایش شده باشد، متن فعلی حفظ و تغییر جیرا برای بررسی نمایش داده می‌شود. نوع فیچر، باگ یا ساپورت از روی متن حدس زده نمی‌شود.</p>
        </fieldset>
        {error && <p role="alert" className="text-sm text-text-destructive-secondary">{error}</p>}
        {result && <section aria-label="نتیجهٔ ورود از جیرا" className="space-y-2 text-sm" role="status">
          <p>تعداد این صفحه: {result.received_count.toLocaleString('fa-IR')} از مجموع {result.total.toLocaleString('fa-IR')} · شروع صفحه: {result.start_at.toLocaleString('fa-IR')}</p>
          {result.has_more && <p>صفحه‌های دیگری باقی مانده‌اند؛ این نتیجه به معنی دریافت همهٔ درخواست‌ها نیست.</p>}
          {!result.data.length && <p>این صفحه درخواستی ندارد.</p>}
          <ul>{result.data.map(item => <li key={item.request_id}><span dir="ltr">{item.key}</span> — {outcomes[item.outcome]}</li>)}</ul>
        </section>}
        <div className="flex justify-end gap-2"><Button type="button" variant="secondary" disabled={busy} onClick={() => changeOpen(false)}>بستن</Button><Button type="submit" variant="primary" disabled={busy || (mode === 'run' && (!runId || !runs.isSuccess))}>{busy ? 'در حال ورود…' : 'ثبت و به‌روزرسانی درخواست‌ها'}</Button></div>
      </form>
      <DialogClose render={<IconButton aria-label="بستن" size="lg" disabled={busy} className="absolute inset-e-6 top-6"><span aria-hidden className="i-ri-close-line size-4" /></IconButton>} />
    </DialogContent>
  </Dialog>
}
