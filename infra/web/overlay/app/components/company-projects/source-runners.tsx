'use client'
import type { Device } from '@/service/company-source'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import Link from '@/next/link'
import { sourceApi, sourceError } from '@/service/company-source'
import FormDialog from './form-dialog'

function Runners({ projectId, accountId }: { projectId: string; accountId: string }) {
  const list = useQuery({ queryKey: ['source-runners', accountId], queryFn: sourceApi.devices, refetchInterval: 15000 })
  const [name, setName] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const [code, setCode] = useState<{ code: string; expires_at: string } | null>(null)
  const [remove, setRemove] = useState<Device | null>(null)
  const [origin] = useState(() => typeof window === 'undefined' ? 'https://kara.example.com' : window.location.origin)
  const create = async () => {
    if (busy) return
    setBusy(true); setError(''); setCode(null)
    try { setCode(await sourceApi.pairing(name)) } catch (e) { setError(await sourceError(e, 'ساخت کد اتصال انجام نشد.')) } finally { setBusy(false) }
  }
  const download = async () => {
    setBusy(true); setError('')
    try { const value = await sourceApi.download(); const bytes = Uint8Array.from(atob(value.content), c => c.charCodeAt(0)); const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' })); const a = document.createElement('a'); a.href = url; a.download = value.filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 30000) }
    catch (e) { setError(await sourceError(e, 'دریافت Runner انجام نشد.')) } finally { setBusy(false) }
  }
  const revoke = async () => {
    if (!remove || busy) return
    setBusy(true); setError('')
    try { await sourceApi.revoke(remove.id); await list.refetch(); setRemove(null) } catch (e) { setError(await sourceError(e, 'لغو دسترسی انجام نشد.')) } finally { setBusy(false) }
  }
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto max-w-4xl space-y-6"><Link href={`/projects/${projectId}/source-code`} className="text-text-accent">سورس کد ←</Link><header><h1 className="text-3xl font-bold">Runnerهای شخصی</h1><p className="mt-3 text-sm leading-7">Runner روی کامپیوتر شما اجرا می‌شود و فقط کارهای آماده‌سازی سورس کد خودتان را دریافت می‌کند. اتصال به بیرون است؛ نیازی به بازکردن پورت محلی نیست.</p></header>
    {error && <p role="alert" className="text-text-destructive-secondary">{error}</p>}
    <section className="space-y-4 rounded-xl border border-divider-regular bg-background-default p-5"><h2 className="text-xl font-bold">راه‌اندازی روی macOS یا Linux</h2><ol className="list-inside list-decimal space-y-3 text-sm leading-7"><li>Python نسخهٔ ۳.۱۰ یا بالاتر و Git را نصب کنید. در Windows از WSL استفاده کنید.</li><li><button disabled={busy} className="text-text-accent" onClick={() => void download()}>بستهٔ Runner را دریافت کنید</button> و در یک پوشهٔ خصوصی باز کنید.</li><li>در همین صفحه یک کد اتصال بسازید، سپس از پوشهٔ بازشده دستور زیر را اجرا کنید. کد را در پرسش مخفی ترمینال وارد کنید؛ آن را در آرگومان دستور یا چت قرار ندهید.</li></ol><pre dir="ltr" className="overflow-auto rounded-lg bg-background-body p-3 text-sm">{`python3 -m kara_source_runner pair --server ${origin}`}</pre><p className="text-sm">سپس Runner را اجرا کنید و در صفحهٔ سورس کد آن را به‌عنوان مقصد انتخاب کنید:</p><pre dir="ltr" className="overflow-auto rounded-lg bg-background-body p-3 text-sm">python3 -m kara_source_runner run</pre><p className="text-sm leading-7">ریشهٔ پیش‌فرض فایل‌ها <bdi>~/KaraSourceWorkspaces</bdi> است. برای تغییر آن از <bdi>--root /your/private/path</bdi> استفاده کنید. هر آماده‌سازی شناسه و پوشهٔ مستقل دارد؛ فایل <bdi>.kara/manifest.json</bdi> نسخه‌ها و commitها را ثبت می‌کند. بستن ترمینال یا خاموش‌شدن کامپیوتر اجرای Runner را متوقف می‌کند.</p></section>
    <form className="space-y-3 rounded-xl border border-divider-regular bg-background-default p-5" onSubmit={e => { e.preventDefault(); void create() }}><h2 className="text-xl font-bold">اتصال Runner تازه</h2><label className="block text-sm">نام کامپیوتر<input className="mt-2 block w-full rounded-lg border border-divider-regular bg-background-body p-3" required maxLength={120} placeholder="کامپیوتر من" value={name} disabled={busy} onChange={e => setName(e.target.value)} /></label><Button type="submit" variant="primary" disabled={busy}>ساخت کد یک‌بارمصرف</Button><p className="text-xs leading-6">کد تا ۱۰ دقیقه معتبر است. ساخت کد تازه، کد مصرف‌نشدهٔ قبلی را باطل می‌کند. Runner فقط پس از واردکردن این کد به حساب شما وصل می‌شود.</p>{code && <div role="status" className="space-y-2"><p>کد خصوصی اتصال — تا {new Date(code.expires_at).toLocaleTimeString('fa-IR')}</p><code dir="ltr" className="block break-all select-all rounded-lg bg-background-body p-3">{code.code}</code><Button type="button" onClick={() => setCode(null)}>پنهان‌کردن کد</Button></div>}</form>
    <section className="space-y-3"><h2 className="text-xl font-bold">دستگاه‌های حساب من</h2>{list.isPending ? <p>در حال دریافت…</p> : list.isError ? <p role="alert">دریافت دستگاه‌ها انجام نشد. <button onClick={() => list.refetch()}>تلاش دوباره</button></p> : !list.data?.data.length ? <p>هنوز Runner متصل ندارید.</p> : list.data.data.map(device => <article key={device.id} className="space-y-3 rounded-xl border border-divider-regular bg-background-default p-5"><h3 className="font-semibold">{device.name} · {device.revoked_at ? 'دسترسی لغوشده' : 'مجاز'}</h3><p className="text-sm">آخرین ارتباط: {device.last_seen_at ? new Date(device.last_seen_at).toLocaleString('fa-IR') : 'هنوز متصل نشده'}</p>{!device.revoked_at && <Button disabled={busy} onClick={() => setRemove(device)}>لغو دسترسی Runner</Button>}</article>)}</section>
    <p className="text-xs leading-7 text-text-tertiary">توکن دستگاه در فایل خصوصی <bdi>~/.config/kara-source-runner/device.json</bdi> نگهداری می‌شود. Runner توکن گیت‌لب را فقط برای کار واگذارشده دریافت می‌کند؛ توکن وارد URL، تنظیمات Git یا نتیجهٔ کار نمی‌شود. کد و مستندات دریافتی اجرا نمی‌شوند و به سرور ارسال نمی‌شوند.</p>
    {remove && <FormDialog open title="لغو دسترسی Runner" description={`دسترسی «${remove.name}» و کارهای فعال آن متوقف می‌شوند. فایل‌های محلی حفظ می‌شوند. اتصال دوباره به کد یک‌بارمصرف تازه نیاز دارد.`} busy={busy} error={error} close={() => setRemove(null)}><Button disabled={busy} onClick={() => void revoke()}>لغو دسترسی</Button></FormDialog>}
  </div></main>
}
export default function SourceRunners({ projectId }: { projectId: string }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  return <Runners key={profile.id} projectId={projectId} accountId={profile.id} />
}
