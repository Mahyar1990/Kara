'use client'
import type { HarnessInfo } from '@/service/company-harness'
import type { TeamStage } from '@/service/company-stages'
import { useSuspenseQuery, useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import { harnessApi } from '@/service/company-harness'
import { sourceError } from '@/service/company-source'
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-sm'
const labels: Record<string, string> = { pending: 'در صف Runner', running: 'در حال اجرای هارنس', awaiting_user: 'در انتظار انجام و تحویل شما', succeeded: 'خروجی اولیه ثبت شد', failed: 'ناموفق', cancelled: 'لغوشده', interrupted: 'قطع‌شده', blocked: 'مجوز یا قرارداد تغییر کرده است' }
export default function HarnessDelivery({ project, agent, identity, outputs, stage, info, changed }: { project: string; agent: string; identity: string; outputs: string[]; stage?: TeamStage; info?: HarnessInfo; changed: () => Promise<unknown> }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  const query = useQuery({ queryKey: ['harness-attempt', profile.id, project, agent, identity], queryFn: () => harnessApi.detail(project, agent, identity), enabled: !info, refetchInterval: q => info || ['succeeded', 'failed', 'cancelled', 'interrupted', 'blocked'].includes(q.state.data?.state || '') ? false : 3000 })
  const value = info || query.data
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(outputs.map(k => [k, ''])))
  const [structured, setStructured] = useState<Record<string, boolean>>({})
  const [summary, setSummary] = useState(''); const [changes, setChanges] = useState(''); const [references, setReferences] = useState(''); const [diff, setDiff] = useState(''); const [session, setSession] = useState('')
  const [tests, setTests] = useState('not_run'); const [testSummary, setTestSummary] = useState(''); const [continueFlow, setContinueFlow] = useState(false); const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const operation = useRef<{ body: string; key: string } | null>(null)
  const refresh = async () => { await query.refetch(); await changed() }
  const download = async () => {
    if (busy) return
    setBusy(true); setError('')
    try { const bundle = await harnessApi.bundle(project, agent, identity); const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = `kara-task-${identity}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 30000) }
    catch (e) { setError(await sourceError(e, 'دریافت بستهٔ مأموریت انجام نشد.')) } finally { setBusy(false) }
  }
  const submit = async () => {
    if (!value || busy) return
    setBusy(true); setError('')
    try {
      const body = { snapshot_digest: value.snapshot_digest, outputs: Object.fromEntries(outputs.map(k => [k, structured[k] ? JSON.parse(values[k]) : values[k]])), evidence: { summary, changes: changes.split('\n').filter(Boolean), tests: { status: tests, summary: testSummary }, references: references.split('\n').filter(Boolean), diff }, session_id: session || null }
      const payload = stage ? { ...body, expected_revision: stage.revision, attempt_id: identity, continue_flow: continueFlow, reason } : body
      const encoded = JSON.stringify(payload)
      if (operation.current?.body !== encoded) operation.current = { body: encoded, key: crypto.randomUUID() }
      if (stage) await harnessApi.submitStage(project, stage.instance_id, stage.id, payload, operation.current.key)
      else await harnessApi.submit(project, agent, identity, payload)
      operation.current = null; await refresh()
    }
    catch (e) { setError(e instanceof SyntaxError ? 'ساختار JSON خروجی معتبر نیست.' : await sourceError(e, 'تحویل انجام نشد؛ نسخهٔ تسک، خروجی و دسترسی را بررسی کنید.')) } finally { setBusy(false) }
  }
  const importResult = async (file?: File) => {
    if (!file) return
    setError('')
    try {
      if (file.size > 524288) throw new Error('size')
      const data = JSON.parse(await file.text())
      if (!data.outputs || !data.evidence || outputs.some(k => !(k in data.outputs)) || Object.keys(data.outputs).length !== outputs.length) throw new Error('contract')
      setValues(Object.fromEntries(outputs.map(k => [k, typeof data.outputs[k] === 'string' ? data.outputs[k] : JSON.stringify(data.outputs[k], null, 2)])))
      setStructured(Object.fromEntries(outputs.map(k => [k, typeof data.outputs[k] !== 'string'])))
      setSummary(data.evidence.summary || ''); setChanges((data.evidence.changes || []).join('\n')); setReferences((data.evidence.references || []).join('\n')); setDiff(data.evidence.diff || ''); setTests(data.evidence.tests?.status || 'not_run'); setTestSummary(data.evidence.tests?.summary || ''); setSession(data.session_id || '')
    }
    catch { setError('فایل باید نتیجهٔ JSON مطابق قرارداد همین تسک و حداکثر ۵۱۲ کیلوبایت باشد.') }
  }
  const canSubmit = value?.mode === 'manual' && value.state === 'awaiting_user' && (!stage || value.actions?.includes('submit'))
  const canCancel = value && ['pending', 'running', 'awaiting_user'].includes(value.state) && (!stage || value.actions?.includes('cancel'))
  return <section className="space-y-4 rounded-xl border border-divider-regular p-4" aria-label="تحویل نتیجهٔ هارنس"><h3 className="font-semibold">کار با هارنس شخصی و تحویل نتیجه</h3>{!value ? <p role={query.isError ? 'alert' : 'status'}>{query.isError ? 'دریافت وضعیت هارنس انجام نشد.' : 'در حال دریافت…'}</p> : <><p role="status" className="text-sm">{labels[value.state] || value.state} · {value.mode === 'manual' ? 'تعاملی در ابزار شخصی' : 'اجرای مدیریت‌شده با Runner'}</p><p className="text-xs">دستگاه: {value.device_name || value.device_id} · هارنس: {value.profile_name || 'ابزار انتخابی خود کاربر'}</p><p className="text-xs leading-7 text-text-secondary">موفقیت اجرا، نتیجه را برای بررسی آماده می‌کند. نهایی‌سازی و تحویل به مرحلهٔ بعد با مسئول تعیین‌شدهٔ همان مرحله است.</p>
    {value.result?.error && <p role="alert" className="text-sm">{value.result.error}</p>}{value.result?.evidence != null && <details><summary className="cursor-pointer text-xs">شواهد و منشأ نتیجه</summary><p className="mt-2 text-xs">{value.result.origin === 'managed_harness' ? 'دریافت از هارنس روی Runner؛ گزارش تست خوداظهاری هارنس است.' : 'تحویل مستقیم کاربر از ابزار شخصی'}</p><pre className="mt-2 whitespace-pre-wrap break-words text-xs">{JSON.stringify(value.result.evidence, null, 2)}</pre></details>}
    {canSubmit && <><button type="button" disabled={busy} className="rounded-lg border border-divider-regular px-4 py-2 text-sm" onClick={() => void download()}>دریافت بستهٔ مأموریت</button><p className="text-xs leading-7">برای آماده‌سازی پوشهٔ مستقل، در پوشهٔ بستهٔ تازهٔ Runner و با تنظیم همان دستگاه اجرا کنید:</p><pre dir="ltr" className="overflow-x-auto rounded-lg bg-background-body p-3 text-left text-xs">{`python -m kara_source_runner harness-prepare --attempt ${identity}`}</pre><p className="text-xs leading-7">{value.prepared ? 'آماده‌سازی این تسک روی دستگاه ثبت شده است.' : 'اگر سورس برای این مأموریت لازم است، آماده‌سازی پوشه پیش از تحویل الزامی است.'} ابزار خود را در پوشهٔ اعلام‌شده باز کنید و فایل مأموریت و نمونهٔ نتیجه را بخوانید.</p>
      <p className="text-xs leading-7">خروجی‌های زیر به مراحل بعد تحویل می‌شوند؛ گزارش لازم برای ادامه را در آن‌ها کامل بنویسید. شواهد جداگانه برای بررسی و پیگیری نگهداری می‌شوند.</p><form className="space-y-4" onSubmit={e => { e.preventDefault(); void submit() }}><fieldset disabled={busy} className="space-y-4"><label className="block text-sm">خواندن نتیجهٔ ابزار از فایل (اختیاری)<input className="mt-2 block text-xs" type="file" accept=".json,application/json" onChange={e => void importResult(e.target.files?.[0])} /></label>{outputs.map(k => <div key={k}><label className="block text-sm">خروجی {k}<textarea required className={field} value={values[k]} onChange={e => setValues({ ...values, [k]: e.target.value })} /></label><label className="mt-2 flex items-center gap-2 text-xs"><input type="checkbox" checked={!!structured[k]} onChange={e => setStructured({ ...structured, [k]: e.target.checked })} />این خروجی دادهٔ ساختاریافتهٔ JSON است</label></div>)}<label className="block text-sm">خلاصهٔ انجام و پوشش معیار پذیرش<textarea required maxLength={8000} className={field} value={summary} onChange={e => setSummary(e.target.value)} /></label><label className="block text-sm">فایل‌ها یا بخش‌های تغییرکرده؛ هر مورد یک خط<textarea className={field} value={changes} onChange={e => setChanges(e.target.value)} /></label><label className="block text-sm">وضعیت واقعی تست‌ها<select className={field} value={tests} onChange={e => setTests(e.target.value)}><option value="not_run">اجرا نشده</option><option value="passed">گزارش موفق</option><option value="failed">گزارش ناموفق</option><option value="mixed">ترکیبی</option></select></label><label className="block text-sm">فرمان‌ها و توضیح تست<textarea maxLength={8000} className={field} value={testSummary} onChange={e => setTestSummary(e.target.value)} /></label><label className="block text-sm">مراجع تغییرات یا MR؛ هر مورد یک خط<textarea className={field} value={references} onChange={e => setReferences(e.target.value)} /></label><label className="block text-sm">diff یا توضیح تغییرات (اختیاری)<textarea dir="auto" maxLength={131072} className={field} value={diff} onChange={e => setDiff(e.target.value)} /></label><label className="block text-sm">شناسهٔ جلسهٔ ابزار (اختیاری)<input className={field} maxLength={200} value={session} onChange={e => setSession(e.target.value)} /></label>{stage && value.can_continue && <><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={continueFlow} onChange={e => setContinueFlow(e.target.checked)} />خروجی را به‌عنوان نهایی‌کنندهٔ این مرحله تأیید و فلو را ادامه می‌دهم</label>{continueFlow && <label className="block text-sm">علت نهایی‌سازی<textarea required maxLength={2000} className={field} value={reason} onChange={e => setReason(e.target.value)} /></label>}</>}<button type="submit" className="rounded-lg bg-components-button-primary-bg px-4 py-2 text-sm text-components-button-primary-text">{continueFlow ? 'تحویل و ادامهٔ فلو' : 'ثبت نتیجه برای بررسی'}</button></fieldset></form>
    </>}{canCancel && <button type="button" disabled={busy} className="text-sm text-text-destructive-secondary" onClick={async () => { setBusy(true); setError(''); try { await harnessApi.cancel(project, agent, identity); await refresh() } catch (e) { setError(await sourceError(e, 'لغو تلاش انجام نشد.')) } finally { setBusy(false) } }}>لغو این تلاش هارنس</button>}</>}{error && <p role="alert" className="text-sm text-text-destructive-secondary">{error}</p>}</section>
}
