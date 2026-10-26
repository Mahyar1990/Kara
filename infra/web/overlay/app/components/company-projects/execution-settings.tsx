'use client'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { executionApi } from '@/service/company-execution'
import { sourceApi, sourceError } from '@/service/company-source'
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3'
const labels: Record<string, string> = { pending: 'در انتظار Runner', running: 'در حال اجرا روی دستگاه', succeeded: 'موفق', failed: 'ناموفق', cancelled: 'لغوشده', interrupted: 'ارتباط قطع شد', blocked: 'دسترسی یا نسخه تغییر کرده است' }
export default function ExecutionSettings({ projectId, accountId }: { projectId: string; accountId: string }) {
  const state = useQuery({ queryKey: ['local-execution', projectId, accountId], queryFn: () => executionApi.settings(projectId), refetchInterval: 10000 })
  const devices = useQuery({ queryKey: ['source-runners', accountId], queryFn: sourceApi.devices, refetchInterval: 15000 })
  const sources = useQuery({ queryKey: ['source-code', projectId, accountId], queryFn: () => sourceApi.list(projectId) })
  const [selected, setSelected] = useState(''); const [source, setSource] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('')
  const binding = state.data?.binding
  useEffect(() => { setSelected(binding?.device_id || ''); setSource(binding?.source_job_id || '') }, [binding?.device_id, binding?.source_job_id, binding?.revision])
  const save = async () => {
    setBusy(true); setError(''); setMessage('')
    try { await executionApi.save(projectId, { device_id: selected, source_job_id: source || null, expected_revision: binding?.revision || 1 }); await state.refetch(); setMessage('دستگاه اجرای این پروژه برای حساب شما ذخیره شد.') }
    catch (e) { setError(await sourceError(e, 'تنظیم دستگاه انجام نشد.')) } finally { setBusy(false) }
  }
  const cancel = async (id: string) => {
    setBusy(true); setError('')
    try { await executionApi.cancel(projectId, id); await state.refetch() } catch (e) { setError(await sourceError(e, 'لغو اجرا انجام نشد.')) } finally { setBusy(false) }
  }
  return <section className="space-y-4 rounded-xl border border-divider-regular bg-background-default p-5"><h2 className="text-xl font-bold">دستگاه اجرای این پروژه</h2><p className="text-sm leading-7">اجرای برنامه‌ها، ایجنت‌ها، فراخوانی مدل و ابزارها به دستگاه انتخاب‌شدهٔ خودتان واگذار می‌شود. هر پروژه تنظیم مستقل دارد. نبود دستگاه یا محیط اجرای مجاز، باعث اجرای روی سرور نمی‌شود.</p>
    {state.isError && <p role="alert">دریافت تنظیم اجرا انجام نشد.</p>}{error && <p role="alert" className="text-text-destructive-secondary">{error}</p>}{message && <p role="status">{message}</p>}
    <label className="block text-sm">Runner مقصد<select className={field} value={selected} disabled={busy} onChange={e => { setSelected(e.target.value); setSource('') }}><option value="">انتخاب دستگاه</option>{devices.data?.data.filter(d => !d.revoked_at).map(d => <option key={d.id} value={d.id}>{d.name} — {d.protocol === 2 ? 'نسخهٔ اجرای محلی' : 'نیازمند دریافت و اجرای نسخهٔ جدید Runner'}</option>)}</select></label>
    <label className="block text-sm">سورس آماده‌شده روی همین دستگاه (اختیاری)<select className={field} value={source} disabled={busy} onChange={e => setSource(e.target.value)}><option value="">بدون اتصال فایل‌های سورس</option>{sources.data?.jobs.filter(j => j.device_id === selected && j.state === 'succeeded').map(j => <option key={j.id} value={j.id}>{sources.data?.workspaces.find(w => w.id === j.source_workspace_id)?.name || 'worktree'} — {new Date(j.created_at).toLocaleString('fa-IR')}</option>)}</select></label>
    <Button variant="primary" disabled={busy || state.isPending || !selected} onClick={() => void save()}>ذخیرهٔ دستگاه اجرای پروژه</Button>
    <p className="text-xs leading-7 text-text-tertiary">تغییر دستگاه روی اجراهای تازه اعمال می‌شود؛ کار واگذارشده به دستگاه قبلی، خودکار منتقل یا تکرار نمی‌شود. اتصال سورس، پوشهٔ همان آماده‌سازی را در اختیار اجرای محلی قرار می‌دهد. در Docker، دسترسی نوشتن باید روی خود Runner فعال شود؛ حالت بدون Docker محدودیت فایل در سطح سیستم‌عامل ندارد.</p>
    <details><summary className="cursor-pointer font-semibold">آخرین اجراهای محلی من</summary><div className="mt-3 space-y-3">{!state.data?.executions.length && <p className="text-sm">هنوز اجرایی ثبت نشده است.</p>}{state.data?.executions.map(job => <article key={job.id} className="rounded-lg border border-divider-regular p-3 text-sm"><p>{job.kind === 'rpc' ? 'فراخوانی اتصال یا مدل' : 'اجرای برنامه'} · {labels[job.state] || job.state} · {devices.data?.data.find(d => d.id === job.device_id)?.name || 'دستگاه تعیین نشده'}</p><p dir="ltr" className="mt-1 break-all text-xs">{job.id}</p>{job.result?.error && <p className="mt-2">{job.result.error}</p>}{['pending', 'running'].includes(job.state) && <Button disabled={busy} onClick={() => void cancel(job.id)}>لغو اجرا</Button>}</article>)}</div></details>
  </section>
}
