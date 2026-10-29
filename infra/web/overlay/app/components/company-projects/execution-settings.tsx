'use client'
import type { ExecutionBinding } from '@/service/company-execution'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import Link from '@/next/link'
import { executionApi } from '@/service/company-execution'
import { sourceApi, sourceError } from '@/service/company-source'
import FormDialog from './form-dialog'
import { connectionState, dateLabel, StateBadge } from './runner-display'

const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-body p-3'
export default function ExecutionSettings({ projectId, accountId, projectName, mode = 'settings', close }: { projectId: string; accountId: string; projectName?: string; mode?: 'settings' | 'history'; close: () => void }) {
  const cache = useQueryClient()
  const settingsKey = ['local-execution', projectId, accountId]
  const state = useQuery({ queryKey: settingsKey, queryFn: () => executionApi.settings(projectId), refetchInterval: 10000 })
  const devices = useQuery({ queryKey: ['source-runners', accountId], queryFn: sourceApi.devices, refetchInterval: 15000 })
  const sources = useQuery({ queryKey: ['source-code', projectId, accountId], queryFn: () => sourceApi.list(projectId), enabled: mode === 'settings' })
  const [draft, setDraft] = useState<{ device: string; source: string; base: ExecutionBinding | null } | null>(null)
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('')
  const binding = state.data?.binding
  const selected = draft?.device ?? binding?.device_id ?? ''
  const source = draft?.source ?? binding?.source_job_id ?? ''
  const changedElsewhere = !!draft && ((draft.base?.revision ?? null) !== (binding?.revision ?? null) || draft.base?.device_id !== binding?.device_id || draft.base?.source_job_id !== binding?.source_job_id)
  const edit = (device: string, sourceId: string) => {
    setDraft(current => ({ device, source: sourceId, base: current ? current.base : binding || null }))
    setMessage(''); setError('')
  }
  const target = devices.data?.data.find(d => d.id === selected)
  const savedDevice = devices.data?.data.find(d => d.id === binding?.device_id)
  const prepared = sources.data?.jobs.filter(j => j.device_id === selected && j.state === 'succeeded' && !j.result?.superseded_by) || []
  const sourceUnavailable = !!source && !prepared.some(job => job.id === source)
  const dirty = changedElsewhere || selected !== (binding?.device_id || '') || source !== (binding?.source_job_id || '')
  const loading = state.isPending || devices.isPending || (mode === 'settings' && sources.isPending)
  const unavailable = state.isError || devices.isError || (mode === 'settings' && sources.isError)
  const save = async () => {
    if (busy || !dirty || loading || unavailable || changedElsewhere || sourceUnavailable || !target || target.revoked_at || target.protocol !== 2) return
    setBusy(true); setError(''); setMessage('')
    try {
      const saved = await executionApi.save(projectId, { device_id: selected, source_job_id: source || null, expected_revision: draft?.base?.revision || 1, expected_binding: draft?.base ?? null })
      cache.setQueryData<Awaited<ReturnType<typeof executionApi.settings>>>(settingsKey, current => current ? { ...current, binding: saved } : current)
      setDraft(null)
      void state.refetch(); void cache.invalidateQueries({ queryKey: ['runner-overview', accountId] })
      setMessage('مقصد اجرا ذخیره شد. کارهای تازهٔ این پروژه به دستگاه انتخاب‌شده فرستاده می‌شوند.')
    }
    catch (e) { setError(await sourceError(e, 'تنظیم دستگاه انجام نشد.')); void state.refetch() } finally { setBusy(false) }
  }
  const cancel = async (id: string) => {
    setBusy(true); setError('')
    try { await executionApi.cancel(projectId, id); await state.refetch(); await cache.invalidateQueries({ queryKey: ['runner-overview', accountId] }) }
    catch (e) { setError(await sourceError(e, 'لغو اجرا انجام نشد.')) } finally { setBusy(false) }
  }
  const history = <div className="space-y-3">{state.isSuccess && !state.data.executions.length && <p className="text-sm">هنوز اجرایی ثبت نشده است.</p>}{state.data?.executions.map(job => <article key={job.id} className="rounded-lg border border-divider-regular p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><strong>{job.kind === 'rpc' ? 'فراخوانی اتصال یا مدل' : 'اجرای برنامه'}</strong><StateBadge state={job.state} /></div><p className="mt-2 text-xs text-text-secondary">روی {devices.data?.data.find(d => d.id === job.device_id)?.name || 'دستگاه تعیین‌نشده'} · {dateLabel(job.created_at)}</p>{job.result?.error && <p className="mt-2 break-words">{job.result.error}</p>}<p dir="ltr" className="mt-2 break-all text-xs text-text-tertiary">{job.id}</p>{['pending', 'running'].includes(job.state) && <Button className="mt-3" size="small" disabled={busy} onClick={() => void cancel(job.id)}>لغو این کار</Button>}</article>)}</div>
  return <FormDialog open wide title={mode === 'history' ? `اجراهای ${projectName || 'پروژهٔ فعلی'}` : `مقصد اجرای ${projectName || 'پروژهٔ فعلی'}`} description={mode === 'history' ? 'وضعیت و خطاهای اجراهای شخصی این پروژه را بررسی کنید؛ کارهای در صف یا در حال اجرا قابل لغو هستند.' : 'دستگاه و سورس مورد استفادهٔ برنامه‌ها، ایجنت‌ها، فلوها و درخواست‌های مدل را برای حساب خودتان انتخاب کنید.'} busy={busy} close={close}>
    <div className="space-y-4">
    {loading && <p role="status" className="text-sm">{mode === 'history' ? 'در حال دریافت اجراهای پروژه…' : 'در حال دریافت مقصد اجرا و سورس‌های آماده‌شده…'}</p>}
    {unavailable && <p role="alert" className="text-sm">{mode === 'history' ? 'دریافت وضعیت تازهٔ اجراها انجام نشد؛ اطلاعات موجود آخرین وضعیت دریافت‌شده است.' : 'اطلاعات کامل دریافت نشد؛ برای جلوگیری از تغییر ناخواسته، ذخیره غیرفعال است.'} <button className="text-text-accent" onClick={() => { void state.refetch(); void devices.refetch(); if (mode === 'settings') void sources.refetch() }}>تلاش دوباره</button></p>}
    {mode === 'settings' && <>{!state.isPending && !state.isError && <div className="rounded-xl bg-background-body p-4 text-sm leading-7"><span className="text-text-tertiary">مقصد ذخیره‌شده: </span><strong>{binding ? savedDevice?.name || 'در حال دریافت نام دستگاه…' : 'هنوز انتخاب نشده'}</strong>{savedDevice && <span> · {connectionState(savedDevice)}</span>}<p className="mt-1 text-text-secondary">{binding ? 'تغییر مقصد، کار واگذارشده به دستگاه قبلی را جابه‌جا یا تکرار نمی‌کند.' : 'یک Runner انتخاب و ذخیره کنید تا درخواست‌های این پروژه مقصد داشته باشند.'}</p></div>}
    <div className="grid gap-5 md:grid-cols-2">
      <label className="block text-sm font-medium">۱. دستگاه اجرای برنامه و مدل<select className={field} value={selected} disabled={busy || loading || unavailable} onChange={e => { edit(e.target.value, '') }}><option value="">انتخاب دستگاه</option>{devices.data?.data.map(d => <option key={d.id} value={d.id} disabled={!!d.revoked_at || d.protocol !== 2}>{d.name} — {d.revoked_at ? 'دسترسی لغوشده' : d.protocol !== 2 ? 'نیازمند به‌روزرسانی Runner' : connectionState(d)}</option>)}</select><span className="mt-2 block text-xs font-normal leading-6 text-text-tertiary">همان کامپیوتر یا VDI که می‌خواهید کار را انجام دهد.</span></label>
      <label className="block text-sm font-medium">۲. فایل‌های سورس در دسترس اجرا (اختیاری)<select className={field} value={source} disabled={busy || loading || unavailable || !selected} onChange={e => { edit(selected, e.target.value) }}><option value="">بدون اتصال فایل‌های سورس</option>{sourceUnavailable && <option value={source} disabled>سورس انتخاب‌شده در فهرست فعلی در دسترس نیست</option>}{prepared.map(j => <option key={j.id} value={j.id}>{sources.data?.workspaces.find(w => w.id === j.source_workspace_id)?.name || 'worktree'} · نسخهٔ {j.snapshot_revision} · {dateLabel(j.created_at)}</option>)}</select><span className="mt-2 block text-xs font-normal leading-6 text-text-tertiary">فقط آماده‌سازی موفق روی همین دستگاه قابل انتخاب است. انتخاب سورس، به‌تنهایی فایل‌ها را اجرا نمی‌کند.</span></label>
    </div>
    {selected && target && <p className="text-sm leading-7 text-text-secondary">با ذخیره، <strong>{target.name}</strong> اجرای برنامه و درخواست مدل را بر عهده می‌گیرد؛ {source ? 'فایل‌های سورس انتخاب‌شده نیز در اختیار اجرا قرار می‌گیرند.' : 'فایل‌های مخزن به اجرای برنامه متصل نمی‌شوند.'}</p>}
    {selected && prepared.length === 0 && !loading && !unavailable && <p className="text-xs leading-6 text-text-secondary">روی این دستگاه سورس آماده‌ای ندارید. اگر برنامه به فایل‌ها نیاز دارد، از <Link className="text-text-accent" href={`/projects/${projectId}/source-code`}>سورس کد</Link> ابتدا worktree را روی همین دستگاه آماده کنید.</p>}
    {target && !target.revoked_at && target.protocol === 2 && !target.capabilities?.includes('python3') && <p className="text-xs leading-6 text-text-secondary">این Runner قابلیت اجرای Python را اعلام نکرده است؛ برنامه‌های نیازمند آن در صف می‌مانند. راهنمای «محیط اجرای کد» را در صفحهٔ Runnerهای شخصی باز کنید.</p>}
    {changedElsewhere && <p role="alert" className="text-sm leading-7 text-text-destructive-secondary">مقصد ذخیره‌شده در جای دیگری تغییر کرده است. انتخاب‌های شما حفظ شده‌اند؛ برای بارگیری مقصد جدید، «بازگرداندن انتخاب‌ها» را بزنید و دوباره انتخاب کنید.</p>}
    {sourceUnavailable && !loading && <p role="alert" className="text-sm leading-7">سورس انتخاب‌شده در فهرست فعلی موجود نیست؛ سورس دیگری انتخاب کنید یا <button type="button" disabled={sources.isFetching} className="text-text-accent" onClick={() => void sources.refetch()}>فهرست سورس‌ها را تازه کنید</button>.</p>}
    <div className="flex flex-wrap items-center gap-3"><Button variant="primary" disabled={busy || loading || unavailable || changedElsewhere || sourceUnavailable || !selected || !!target?.revoked_at || target?.protocol !== 2 || !dirty} onClick={() => void save()}>ذخیرهٔ مقصد اجرا</Button>{dirty && <><span className="text-xs text-text-secondary">تغییرات هنوز ذخیره نشده‌اند.</span><Button disabled={busy} onClick={() => { setDraft(null); setMessage(''); setError('') }}>بازگرداندن انتخاب‌ها</Button></>}</div>
    <p className="text-xs leading-7 text-text-tertiary">Runner را روی دستگاه مقصد روشن نگه دارید. نبود دستگاه یا محیط لازم، اجرای سروری را فعال نمی‌کند. در Docker، نوشتن در سورس باید روی Runner مجاز شود؛ حالت بدون Docker محدودیت فایل در سطح سیستم‌عامل ندارد.</p>
    </>}
    {mode === 'history' && history}
    {error && <p role="alert" className="text-sm text-text-destructive-secondary">{error}</p>}{message && <p role="status" className="text-sm text-text-accent">{message}</p>}
    </div>
  </FormDialog>
}
