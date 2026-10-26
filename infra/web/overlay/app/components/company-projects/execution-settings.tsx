'use client'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import Link from '@/next/link'
import { executionApi } from '@/service/company-execution'
import { sourceApi, sourceError } from '@/service/company-source'
import { connectionState, dateLabel, panel, StateBadge } from './runner-display'

const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-body p-3'
export default function ExecutionSettings({ projectId, accountId, projectName }: { projectId: string; accountId: string; projectName?: string }) {
  const cache = useQueryClient()
  const state = useQuery({ queryKey: ['local-execution', projectId, accountId], queryFn: () => executionApi.settings(projectId), refetchInterval: 10000 })
  const devices = useQuery({ queryKey: ['source-runners', accountId], queryFn: sourceApi.devices, refetchInterval: 15000 })
  const sources = useQuery({ queryKey: ['source-code', projectId, accountId], queryFn: () => sourceApi.list(projectId) })
  const [selected, setSelected] = useState(''); const [source, setSource] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('')
  const binding = state.data?.binding
  useEffect(() => { setSelected(binding?.device_id || ''); setSource(binding?.source_job_id || ''); setMessage('') }, [binding?.device_id, binding?.source_job_id, binding?.revision])
  const target = devices.data?.data.find(d => d.id === selected)
  const savedDevice = devices.data?.data.find(d => d.id === binding?.device_id)
  const prepared = sources.data?.jobs.filter(j => j.device_id === selected && j.state === 'succeeded') || []
  const dirty = selected !== (binding?.device_id || '') || source !== (binding?.source_job_id || '')
  const loading = state.isPending || devices.isPending || sources.isPending
  const unavailable = state.isError || devices.isError || sources.isError
  const save = async () => {
    if (busy || !dirty || loading || unavailable) return
    setBusy(true); setError(''); setMessage('')
    try {
      await executionApi.save(projectId, { device_id: selected, source_job_id: source || null, expected_revision: binding?.revision || 1 })
      await state.refetch(); await cache.invalidateQueries({ queryKey: ['runner-overview', accountId] })
      setMessage('مقصد اجرا ذخیره شد. کارهای تازهٔ این پروژه به دستگاه انتخاب‌شده فرستاده می‌شوند.')
    }
    catch (e) { setError(await sourceError(e, 'تنظیم دستگاه انجام نشد.')) } finally { setBusy(false) }
  }
  const cancel = async (id: string) => {
    setBusy(true); setError('')
    try { await executionApi.cancel(projectId, id); await state.refetch(); await cache.invalidateQueries({ queryKey: ['runner-overview', accountId] }) }
    catch (e) { setError(await sourceError(e, 'لغو اجرا انجام نشد.')) } finally { setBusy(false) }
  }
  return <section id="project-execution" className={`${panel} scroll-mt-5 space-y-5`}>
    <header><p className="mb-1 text-xs text-text-tertiary">تنظیم شخصی شما در این پروژه</p><h2 className="text-xl font-bold">مقصد اجرای {projectName || 'پروژهٔ فعلی'}</h2><p className="mt-2 text-sm leading-7 text-text-secondary">برنامه‌ها، ایجنت‌ها، فلوها و درخواست‌های مدل این پروژه روی دستگاه زیر اجرا می‌شوند. تنظیم پروژه‌های دیگر مستقل است.</p></header>
    {loading && <p role="status" className="text-sm">در حال دریافت مقصد اجرا و سورس‌های آماده‌شده…</p>}
    {unavailable && <p role="alert" className="text-sm">اطلاعات کامل دریافت نشد؛ برای جلوگیری از تغییر ناخواسته، ذخیره غیرفعال است. <button className="text-text-accent" onClick={() => { void state.refetch(); void devices.refetch(); void sources.refetch() }}>تلاش دوباره</button></p>}
    {!state.isPending && !state.isError && <div className="rounded-xl bg-background-body p-4 text-sm leading-7"><span className="text-text-tertiary">مقصد ذخیره‌شده: </span><strong>{binding ? savedDevice?.name || 'در حال دریافت نام دستگاه…' : 'هنوز انتخاب نشده'}</strong>{savedDevice && <span> · {connectionState(savedDevice)}</span>}<p className="mt-1 text-text-secondary">{binding ? 'تغییر مقصد، کار واگذارشده به دستگاه قبلی را جابه‌جا یا تکرار نمی‌کند.' : 'یک Runner انتخاب و ذخیره کنید تا درخواست‌های این پروژه مقصد داشته باشند.'}</p></div>}
    {error && <p role="alert" className="text-sm text-text-destructive-secondary">{error}</p>}{message && <p role="status" className="text-sm text-text-accent">{message}</p>}
    <div className="grid gap-5 md:grid-cols-2">
      <label className="block text-sm font-medium">۱. دستگاه اجرای برنامه و مدل<select className={field} value={selected} disabled={busy || loading || unavailable} onChange={e => { setSelected(e.target.value); setSource(''); setMessage('') }}><option value="">انتخاب دستگاه</option>{devices.data?.data.map(d => <option key={d.id} value={d.id} disabled={!!d.revoked_at || d.protocol !== 2}>{d.name} — {d.revoked_at ? 'دسترسی لغوشده' : d.protocol !== 2 ? 'نیازمند به‌روزرسانی Runner' : connectionState(d)}</option>)}</select><span className="mt-2 block text-xs font-normal leading-6 text-text-tertiary">همان کامپیوتر یا VDI که می‌خواهید کار را انجام دهد.</span></label>
      <label className="block text-sm font-medium">۲. فایل‌های سورس در دسترس اجرا (اختیاری)<select className={field} value={source} disabled={busy || loading || unavailable || !selected} onChange={e => { setSource(e.target.value); setMessage('') }}><option value="">بدون اتصال فایل‌های سورس</option>{prepared.map(j => <option key={j.id} value={j.id}>{sources.data?.workspaces.find(w => w.id === j.source_workspace_id)?.name || 'worktree'} · نسخهٔ {j.snapshot_revision} · {dateLabel(j.created_at)}</option>)}</select><span className="mt-2 block text-xs font-normal leading-6 text-text-tertiary">فقط آماده‌سازی موفق روی همین دستگاه قابل انتخاب است. انتخاب سورس، به‌تنهایی فایل‌ها را اجرا نمی‌کند.</span></label>
    </div>
    {selected && target && <p className="text-sm leading-7 text-text-secondary">با ذخیره، <strong>{target.name}</strong> اجرای برنامه و درخواست مدل را بر عهده می‌گیرد؛ {source ? 'فایل‌های سورس انتخاب‌شده نیز در اختیار اجرا قرار می‌گیرند.' : 'فایل‌های مخزن به اجرای برنامه متصل نمی‌شوند.'}</p>}
    {selected && prepared.length === 0 && !loading && !unavailable && <p className="text-xs leading-6 text-text-secondary">روی این دستگاه سورس آماده‌ای ندارید. اگر برنامه به فایل‌ها نیاز دارد، از <Link className="text-text-accent" href={`/projects/${projectId}/source-code`}>سورس کد</Link> ابتدا worktree را روی همین دستگاه آماده کنید.</p>}
    {target && !target.revoked_at && target.protocol === 2 && !target.capabilities?.includes('python3') && <p className="text-xs leading-6 text-text-secondary">این Runner قابلیت اجرای Python را اعلام نکرده است؛ برنامه‌های نیازمند آن در صف می‌مانند. راه‌اندازی محیط کد را در راهنمای پایین صفحه ببینید.</p>}
    <div className="flex flex-wrap items-center gap-3"><Button variant="primary" disabled={busy || loading || unavailable || !selected || !!target?.revoked_at || target?.protocol !== 2 || !dirty} onClick={() => void save()}>ذخیرهٔ مقصد اجرا</Button>{dirty && <><span className="text-xs text-text-secondary">تغییرات هنوز ذخیره نشده‌اند.</span><Button disabled={busy} onClick={() => { setSelected(binding?.device_id || ''); setSource(binding?.source_job_id || ''); setMessage(''); setError('') }}>بازگرداندن انتخاب‌ها</Button></>}</div>
    <p className="text-xs leading-7 text-text-tertiary">Runner را روی دستگاه مقصد روشن نگه دارید. نبود دستگاه یا محیط لازم، اجرای سروری را فعال نمی‌کند. در Docker، نوشتن در سورس باید روی Runner مجاز شود؛ حالت بدون Docker محدودیت فایل در سطح سیستم‌عامل ندارد.</p>
    <details><summary className="cursor-pointer text-sm font-semibold">پیگیری و لغو اجراهای این پروژه</summary><div className="mt-3 space-y-3">{state.isSuccess && !state.data.executions.length && <p className="text-sm">هنوز اجرایی ثبت نشده است.</p>}{state.data?.executions.map(job => <article key={job.id} className="rounded-xl border border-divider-regular p-4 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><strong>{job.kind === 'rpc' ? 'فراخوانی اتصال یا مدل' : 'اجرای برنامه'}</strong><StateBadge state={job.state} /></div><p className="mt-2 text-text-secondary">روی {devices.data?.data.find(d => d.id === job.device_id)?.name || 'دستگاه تعیین‌نشده'} · {dateLabel(job.created_at)}</p>{job.result?.error && <p className="mt-2">{job.result.error}</p>}{['pending', 'running'].includes(job.state) && <div className="mt-3"><Button disabled={busy} onClick={() => void cancel(job.id)}>لغو این کار</Button></div>}<details className="mt-2"><summary className="cursor-pointer text-xs text-text-tertiary">شناسهٔ پیگیری</summary><p dir="ltr" className="mt-1 break-all text-xs">{job.id}</p></details></article>)}</div></details>
  </section>
}
