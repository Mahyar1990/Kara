'use client'

import type { Device, RunnerActivity } from '@/service/company-source'
import type { RunnerGuide } from './runner-setup-dialog'
import { DirectionProvider } from '@base-ui/react/direction-provider'
import { Button } from '@langgenius/dify-ui/button'
import { Tabs, TabsList, TabsPanel, TabsTab } from '@langgenius/dify-ui/tabs'
import { useQuery, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useAtomValue } from 'jotai'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { projectApi } from '@/service/company-projects'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import Link from '@/next/link'
import { sourceApi, sourceError } from '@/service/company-source'
import FormDialog from './form-dialog'
import ExecutionSettings from './execution-settings'
import { ConnectionBadge, dateLabel, StateBadge } from './runner-display'
import RunnerSetupDialog, { RunnerCommand } from './runner-setup-dialog'

const compact = 'rounded-xl border border-divider-regular bg-background-default p-3'
const field = 'mt-1 block w-full rounded-lg border border-divider-regular bg-background-default p-2 text-sm'
const number = (value: number) => value.toLocaleString('fa-IR')
const kindLabel = (job: RunnerActivity) => job.kind === 'harness' ? 'هارنس شخصی' : job.kind === 'source' ? 'آماده‌سازی سورس' : job.kind === 'rpc' ? 'مدل و اتصال‌ها' : 'اجرای برنامه'
type View = { kind: 'pair' | 'projects' | 'activity' | 'execution' | 'history' } | { kind: 'guide'; guide: RunnerGuide } | { kind: 'device'; id: string } | { kind: 'job'; job: RunnerActivity } | { kind: 'revoke'; device: Device } | { kind: 'enter'; id: string; section: string }

function Runners({ projectId, accountId }: { projectId: string; accountId: string }) {
  const cache = useQueryClient()
  const currentWorkspace = useAtomValue(currentWorkspaceIdAtom)
  const overview = useQuery({ queryKey: ['runner-overview', accountId], queryFn: sourceApi.overview, refetchInterval: 15000 })
  const [view, setView] = useState<View | null>(null)
  const [name, setName] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const [code, setCode] = useState<{ code: string; expires_at: string } | null>(null)
  const [showRevoked, setShowRevoked] = useState(false)
  const [deviceFilter, setDeviceFilter] = useState(''); const [projectFilter, setProjectFilter] = useState('')
  const [activityTab, setActivityTab] = useState('active')
  const [origin, setOrigin] = useState(''); const [now, setNow] = useState(Date.now())
  useEffect(() => {
    setOrigin(window.location.origin)
    const url = new URL(window.location.href)
    const requested = url.searchParams.get('dialog')
    if (requested === 'execution' || requested === 'history') {
      setView({ kind: requested })
      // Consume the handoff once; closing and refreshing must keep the dialog closed.
      url.searchParams.delete('dialog')
      window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash)
    }
    const timer = setInterval(() => setNow(Date.now()), 15000)
    return () => clearInterval(timer)
  }, [])
  const data = overview.data
  const devices = data?.devices || []; const projects = data?.projects || []
  const current = projects.find(p => p.id === projectId)
  const inCurrentProject = !!current && current.workspace_id === currentWorkspace
  const activeDevices = devices.filter(d => !d.revoked_at)
  const visibleDevices = showRevoked ? devices : activeDevices
  const selectedDevice = view?.kind === 'device' ? devices.find(d => d.id === view.id) : undefined
  const selectedJob = view?.kind === 'job' ? [...(data?.active || []), ...(data?.recent || [])].find(job => job.id === view.job.id) || view.job : undefined
  const staleNotice = overview.isError && <p role="alert" className="text-xs leading-6 text-text-destructive-secondary">تازه‌سازی انجام نشد؛ آخرین وضعیت دریافت‌شده نمایش داده می‌شود. <button className="text-text-accent" onClick={() => void overview.refetch()}>تلاش دوباره</button></p>
  const expired = !!code && new Date(code.expires_at).getTime() <= now
  const show = (next: View) => { if (!busy) { setError(''); setCode(null); if (next.kind === 'pair') setName(''); setView(next) } }
  const close = () => { if (!busy) { setView(null); setCode(null); setError('') } }
  const showActivity = (device = '') => { setDeviceFilter(device); setProjectFilter(''); setActivityTab('active'); show({ kind: 'activity' }) }
  const projectSettings = (id: string, mode: 'execution' | 'history' = 'execution') => {
    if (id === projectId && inCurrentProject) show({ kind: mode })
    else show({ kind: 'enter', id, section: `source-runners?dialog=${mode}` })
  }
  const create = async () => {
    if (busy) return
    setBusy(true); setError(''); setCode(null)
    try { setCode(await sourceApi.pairing(name.trim())); setNow(Date.now()) }
    catch (e) { setError(await sourceError(e, 'ساخت کد اتصال انجام نشد.')) } finally { setBusy(false) }
  }
  const download = async () => {
    if (busy) return false
    setBusy(true); setError('')
    try { const value = await sourceApi.download(); const bytes = Uint8Array.from(atob(value.content), c => c.charCodeAt(0)); const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' })); const a = document.createElement('a'); a.href = url; a.download = value.filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 30000); return true }
    catch (e) { setError(await sourceError(e, 'دریافت Runner انجام نشد.')); return false } finally { setBusy(false) }
  }
  const revoke = async (device: Device) => {
    if (busy) return
    setBusy(true); setError('')
    try { await sourceApi.revoke(device.id); await Promise.all([overview.refetch(), cache.invalidateQueries({ queryKey: ['source-runners', accountId] }), cache.invalidateQueries({ queryKey: ['local-execution', projectId, accountId] })]); setView(null) }
    catch (e) { setError(await sourceError(e, 'لغو دسترسی انجام نشد.')) } finally { setBusy(false) }
  }
  const openProject = async (id: string, section: string) => {
    if (busy) return
    setBusy(true); setError('')
    try { await projectApi.enter(id); window.location.assign(`/projects/${id}/${section}`) }
    catch (e) { setError(await sourceError(e, 'ورود به پروژه انجام نشد.')); setBusy(false) }
  }
  const filtered = (jobs: RunnerActivity[]) => jobs.filter(j => (!deviceFilter || j.device_id === deviceFilter) && (!projectFilter || j.project_id === projectFilter))
  const activity = (job: RunnerActivity) => <article key={job.id} className={compact}><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="min-w-0 break-words text-sm font-semibold">{job.title}</h3><StateBadge state={job.state} /></div><p className="mt-1 text-xs leading-6 text-text-secondary">{kindLabel(job)} · {projects.find(p => p.id === job.project_id)?.name || 'پروژه'} · {devices.find(d => d.id === job.device_id)?.name || 'دستگاه تعیین‌نشده'}</p><div className="mt-2 flex items-center justify-between gap-2 text-xs"><span className="text-text-tertiary">{dateLabel(job.created_at)}</span><Button size="small" onClick={() => show({ kind: 'job', job })}>جزئیات و پیگیری</Button></div></article>
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto max-w-6xl space-y-5">
    <Link href={`/projects/${projectId}/source-code`} className="text-sm text-text-accent">بازگشت به سورس کد پروژه</Link>
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-bold">Runnerهای شخصی</h1><p className="mt-2 text-sm text-text-secondary">دستگاه‌ها و کارهای حساب خود را مدیریت کنید.</p></div><div className="flex flex-wrap gap-2"><Button variant="primary" disabled={busy} onClick={() => show({ kind: 'pair' })}>اتصال دستگاه تازه</Button><Button disabled={busy} onClick={() => show({ kind: 'guide', guide: 'download' })}>دریافت بسته</Button><Button disabled={busy} onClick={() => show({ kind: 'guide', guide: 'run' })}>اجرای Runner</Button></div></header>
    <nav aria-label="عملیات و راهنمای Runner" className="flex flex-wrap gap-2">{current && <Button size="small" disabled={busy} onClick={() => projectSettings(projectId)}>مقصد اجرای پروژه</Button>}<Button size="small" disabled={busy || !data} onClick={() => showActivity()}>فعالیت‌ها و سابقه</Button>{([['code', 'محیط اجرای کد'], ['harness', 'هارنس شخصی'], ['storage', 'فایل‌ها و دسترسی‌ها']] as const).map(([guide, label]) => <Button key={guide} size="small" disabled={busy} onClick={() => show({ kind: 'guide', guide })}>{label}</Button>)}</nav>
    {overview.isPending && <p role="status" className={compact}>در حال دریافت دستگاه‌ها…</p>}
    {overview.isError && <div role="alert" className={`${compact} text-sm`}>{data ? 'تازه‌سازی انجام نشد؛ آخرین اطلاعات دریافت‌شده نمایش داده می‌شود.' : 'دریافت فهرست دستگاه‌ها انجام نشد.'}<button className="ms-3 text-text-accent" onClick={() => void overview.refetch()}>تلاش دوباره</button></div>}
    {data && <>
      <section className="grid grid-cols-2 gap-2 lg:grid-cols-4" aria-label="خلاصهٔ Runnerهای من">
        <div className={compact}><p className="text-xs text-text-tertiary">دستگاه‌های دارای دسترسی</p><p className="mt-1 text-xl font-bold">{number(activeDevices.length)}</p><p className="mt-1 text-xs text-text-secondary">{number(activeDevices.filter(d => !!d.last_seen_at && now - new Date(d.last_seen_at).getTime() <= 90000).length)} ارتباط تازه</p></div>
        <div className={compact}><p className="text-xs text-text-tertiary">مقصد پروژهٔ فعلی</p><p className="mt-1 break-words text-sm font-semibold">{devices.find(d => d.id === current?.binding?.device_id)?.name || 'انتخاب نشده'}</p>{current && <button className="mt-2 text-xs text-text-accent" onClick={() => projectSettings(projectId)}>تنظیم مقصد</button>}</div>
        <div className={compact}><p className="text-xs text-text-tertiary">پروژه‌های دارای مقصد اجرا</p><p className="mt-1 text-xl font-bold">{number(projects.filter(p => p.binding).length)}</p><button className="mt-1 text-xs text-text-accent" onClick={() => show({ kind: 'projects' })}>مشاهدهٔ پروژه‌ها</button></div>
        <div className={compact}><p className="text-xs text-text-tertiary">کارهای جاری</p><p className="mt-1 text-xl font-bold">{number(data.active.length)}</p><button className="mt-1 text-xs text-text-accent" onClick={() => showActivity()}>مشاهده و پیگیری</button></div>
      </section>
      <section aria-labelledby="my-devices" className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-2"><h2 id="my-devices" className="text-lg font-bold">دستگاه‌های من</h2><div className="flex items-center gap-3">{devices.some(d => d.revoked_at) && <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={showRevoked} onChange={e => setShowRevoked(e.target.checked)} />نمایش لغوشده‌ها</label>}<button className="text-xs text-text-accent" disabled={overview.isFetching} onClick={() => void overview.refetch()}>{overview.isFetching ? 'در حال تازه‌سازی…' : 'تازه‌سازی'}</button></div></div>
        {!visibleDevices.length ? <div className={`${compact} space-y-3`}><p className="text-sm">{devices.length ? 'دستگاه دارای دسترسی ندارید.' : 'هنوز دستگاهی متصل نکرده‌اید.'}</p><Button onClick={() => show({ kind: 'pair' })}>اتصال دستگاه تازه</Button></div> : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{visibleDevices.map(device => {
          const assigned = projects.filter(p => p.binding?.device_id === device.id)
          const working = data.active.filter(job => job.device_id === device.id)
          return <article key={device.id} className={`${compact} flex min-w-0 flex-col gap-2`}><header className="flex flex-wrap items-center justify-between gap-2"><h3 className="min-w-0 break-words font-semibold">{device.name}</h3><ConnectionBadge device={device} /></header><p className="text-xs text-text-tertiary">آخرین تماس: {device.last_seen_at ? dateLabel(device.last_seen_at) : 'هنوز ثبت نشده'}</p><p className="text-xs leading-6 text-text-secondary">{number(assigned.length)} پروژه · {number(working.filter(job => job.state === 'running').length)} در حال اجرا · {number(working.filter(job => job.state === 'pending').length)} در صف{working.some(job => job.state === 'awaiting_user') && ` · ${number(working.filter(job => job.state === 'awaiting_user').length)} در اختیار کاربر`}</p><div className="mt-auto flex flex-wrap gap-2 pt-1"><Button size="small" onClick={() => show({ kind: 'device', id: device.id })} aria-label={`جزئیات دستگاه ${device.name}`}>جزئیات</Button><Button size="small" onClick={() => showActivity(device.id)} aria-label={`کارهای دستگاه ${device.name}`}>کارها</Button>{!device.revoked_at && <Button size="small" tone="destructive" onClick={() => show({ kind: 'revoke', device })} aria-label={`لغو دسترسی ${device.name}`}>لغو دسترسی</Button>}</div></article>
        })}</div>}
        <p className="text-xs leading-6 text-text-tertiary">ارتباط تازه یعنی تماس در ۹۰ ثانیهٔ اخیر؛ موفقیت اجرا به محیط و شبکهٔ همان دستگاه هم وابسته است. تازه‌سازی خودکار هر ۱۵ ثانیه.</p>
      </section>
    </>}
    {view?.kind === 'pair' && <FormDialog open title="اتصال دستگاه تازه" description="ابتدا بستهٔ Runner را روی دستگاه مقصد آماده کنید؛ سپس نام دستگاه را وارد و کد یک‌بارمصرف بسازید." busy={busy} error={error} close={close}><form className="space-y-4" onSubmit={e => { e.preventDefault(); void create() }}><label className="block text-sm">نام دستگاه<input className={field} required maxLength={120} placeholder="مثلاً لپ‌تاپ کاری" value={name} disabled={busy} onChange={e => setName(e.target.value)} /></label><Button type="submit" variant="primary" loading={busy} disabled={busy || !name.trim()}>{code ? 'ساخت کد تازه' : 'ساخت کد اتصال'}</Button><p className="text-xs leading-6 text-text-secondary">کد ۱۰ دقیقه معتبر است. ساخت کد تازه، کد مصرف‌نشدهٔ قبلی را باطل می‌کند و دستگاه‌های متصل را تغییر نمی‌دهد.</p>{code && <div role="status" className="space-y-3 rounded-lg bg-background-body p-3">{expired ? <p className="text-sm">کد منقضی شد؛ کد تازه بسازید.</p> : <><p className="text-sm">کد خصوصی اتصال · معتبر تا {new Date(code.expires_at).toLocaleTimeString('fa-IR')}</p><code dir="ltr" className="block select-all break-all text-left text-sm">{code.code}</code><p className="text-xs leading-6 text-text-secondary">کد را در پرسش مخفی ترمینال وارد کنید؛ آن را در چت یا متن دستور ننویسید.</p></>}<Button type="button" size="small" onClick={() => setCode(null)}>پنهان‌کردن کد</Button></div>}{origin && <RunnerCommand value={`python -m kara_source_runner pair --server ${origin}`} />}<p className="text-xs leading-6 text-text-secondary">پس از اتصال، دیالوگ «اجرای Runner» را باز کنید. برای دستگاهی که قبلاً متصل شده، بسته را به‌روز و تنظیمات خصوصی قبلی را حفظ کنید؛ کد تازه لازم نیست. با بستن این دیالوگ، کد از صفحه پاک می‌شود.</p></form></FormDialog>}
    {view?.kind === 'guide' && <RunnerSetupDialog key={view.guide} guide={view.guide} busy={busy} error={error} download={download} close={close} />}
    {(view?.kind === 'execution' || view?.kind === 'history') && (current && inCurrentProject ? <ExecutionSettings key={view.kind} mode={view.kind === 'history' ? 'history' : 'settings'} projectId={projectId} accountId={accountId} projectName={current.name} close={close} /> : <FormDialog open title="اجرای پروژه" description="برای تنظیم یا پیگیری اجراها باید در فضای همین پروژه باشید." busy={busy} error={error} close={close}>{overview.isPending ? <p role="status">در حال دریافت اطلاعات پروژه…</p> : current ? <Button loading={busy} onClick={() => void openProject(projectId, `source-runners?dialog=${view.kind}`)}>ورود به {current.name}</Button> : <div className="space-y-3"><p>اطلاعات یا دسترسی این پروژه در دسترس نیست.</p><Button disabled={overview.isFetching} onClick={() => void overview.refetch()}>تازه‌سازی اطلاعات پروژه</Button></div>}</FormDialog>)}
    {view?.kind === 'projects' && <FormDialog open wide title="پروژه‌های من و مقصد اجرا" description="مقصد اجرای هر پروژه و حساب شما مستقل است." close={close}><div className="space-y-2">{staleNotice}{!projects.length && <p className="text-sm">پروژه‌ای در دسترس نیست.</p>}{projects.map(project => <article key={project.id} className={compact}><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="break-words text-sm font-semibold">{project.name}{project.id === projectId && ' · پروژهٔ فعلی'}</h3><Button size="small" onClick={() => projectSettings(project.id)}>تنظیم مقصد</Button></div><p className="mt-1 text-xs leading-6 text-text-secondary">دستگاه: {devices.find(device => device.id === project.binding?.device_id)?.name || 'انتخاب نشده'} · سورس: {project.binding?.source_name || 'متصل نشده'}</p></article>)}</div></FormDialog>}
    {view?.kind === 'device' && <FormDialog open title={selectedDevice?.name || 'جزئیات دستگاه'} description="قابلیت‌ها، پروژه‌ها و وضعیت این دستگاه." close={close}>{selectedDevice ? <div className="space-y-4 text-sm">{staleNotice}<ConnectionBadge device={selectedDevice} /><p className="text-xs">آخرین تماس: {selectedDevice.last_seen_at ? dateLabel(selectedDevice.last_seen_at) : 'هنوز ثبت نشده'}</p><p dir="ltr" className="break-all text-xs text-text-tertiary">{selectedDevice.id}</p><div className="flex flex-wrap gap-2">{[['سورس Git', selectedDevice.capabilities?.includes('source-v1')], ['به‌روزرسانی سورس', selectedDevice.capabilities?.includes('source-update-v1')], ['برنامه و مدل', selectedDevice.protocol === 2 && selectedDevice.capabilities?.includes('workflow-v2')], ['Python', selectedDevice.capabilities?.includes('python3')], ['JavaScript', selectedDevice.capabilities?.includes('javascript')]].map(([label, available]) => <span key={String(label)} className="rounded-lg border border-divider-regular px-2 py-1 text-xs">{label} · {available ? 'اعلام شده' : 'اعلام نشده'}</span>)}</div><p className="text-xs leading-6">هارنس‌های خودکار: {selectedDevice.harnesses?.map(h => h.name).join('، ') || 'ثبت نشده'}</p>{selectedDevice.revoked_at ? <p className="text-xs leading-6">دسترسی این دستگاه لغو شده است؛ برای اتصال دوباره کد و تنظیمات تازه لازم است.</p> : selectedDevice.protocol !== 2 && <p className="text-xs leading-6">برای اجرای برنامه و مدل، بستهٔ تازه را دریافت و Runner را روی همین دستگاه اجرا کنید.</p>}<section className="space-y-2"><h3 className="font-semibold">پروژه‌های دارای این مقصد اجرا</h3>{!projects.some(p => p.binding?.device_id === selectedDevice.id) && <p className="text-xs leading-6 text-text-secondary">برای اجرای برنامهٔ پروژه‌ای انتخاب نشده است. مقصد دریافت سورس را در صفحهٔ سورس کد انتخاب می‌کنید.</p>}{projects.filter(p => p.binding?.device_id === selectedDevice.id).map(project => <div key={project.id} className={compact}><div className="flex flex-wrap items-center justify-between gap-2"><strong className="break-words text-sm">{project.name}</strong><Button size="small" onClick={() => projectSettings(project.id)}>تنظیم مقصد</Button></div><p className="mt-1 text-xs leading-6 text-text-secondary">سورس: {project.binding?.source_name || 'متصل نشده'}{project.binding?.source_revision != null && ` · نسخهٔ ${number(project.binding.source_revision)}`}</p></div>)}</section><div className="flex flex-wrap gap-2"><Button onClick={() => showActivity(selectedDevice.id)}>کارهای این دستگاه</Button>{!selectedDevice.revoked_at && <Button tone="destructive" onClick={() => show({ kind: 'revoke', device: selectedDevice })}>لغو دسترسی</Button>}</div></div> : <p>اطلاعات دستگاه در فهرست فعلی موجود نیست.</p>}</FormDialog>}
    {view?.kind === 'activity' && data && <FormDialog open wide title="فعالیت‌ها و سابقهٔ Runnerها" description="کارهای شخصی شما در پروژه‌های در دسترس؛ تا ۱۰۰ کار جاری از هر نوع و ۲۰ کار اخیر." close={close}><div className="space-y-4">{staleNotice}<div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">دستگاه<select className={field} value={deviceFilter} onChange={e => setDeviceFilter(e.target.value)}><option value="">همهٔ دستگاه‌ها</option>{devices.map(device => <option key={device.id} value={device.id}>{device.name}</option>)}</select></label><label className="text-sm">پروژه<select className={field} value={projectFilter} onChange={e => setProjectFilter(e.target.value)}><option value="">همهٔ پروژه‌ها</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label></div><DirectionProvider direction="rtl"><Tabs value={activityTab} onValueChange={next => setActivityTab(String(next))}><TabsList aria-label="نوع فعالیت" className="mb-3 border-b border-divider-regular"><TabsTab type="button" value="active">کارهای جاری ({number(filtered(data.active).length)})</TabsTab><TabsTab type="button" value="recent">کارهای اخیر ({number(filtered(data.recent).length)})</TabsTab></TabsList><TabsPanel value="active"><div className="grid gap-2 md:grid-cols-2">{filtered(data.active).length ? filtered(data.active).map(activity) : <p className="text-sm text-text-secondary">کار جاری با این انتخاب وجود ندارد.</p>}</div></TabsPanel><TabsPanel value="recent"><div className="grid gap-2 md:grid-cols-2">{filtered(data.recent).length ? filtered(data.recent).map(activity) : <p className="text-sm text-text-secondary">کار اخیری با این انتخاب وجود ندارد.</p>}</div></TabsPanel></Tabs></DirectionProvider><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-text-tertiary">آخرین دریافت: {overview.dataUpdatedAt ? dateLabel(new Date(overview.dataUpdatedAt).toISOString()) : '—'}</p>{current && <Button size="small" onClick={() => projectSettings(projectId, 'history')}>پیگیری و لغو اجراهای این پروژه</Button>}</div></div></FormDialog>}
    {view?.kind === 'job' && selectedJob && <FormDialog open title={selectedJob.title} description={kindLabel(selectedJob)} busy={busy} error={error} close={close}><div className="space-y-3 text-sm">{staleNotice}<StateBadge state={selectedJob.state} /><p>پروژه: {projects.find(project => project.id === selectedJob.project_id)?.name || 'پروژه'}</p><p>دستگاه: {devices.find(device => device.id === selectedJob.device_id)?.name || 'هنوز تعیین نشده'}</p><p className="text-xs text-text-secondary">{dateLabel(selectedJob.created_at)}</p><p dir="ltr" className="break-all text-xs">{selectedJob.id}</p><div className="flex flex-wrap gap-2">{selectedJob.kind === 'workflow' || selectedJob.kind === 'rpc' ? <Button onClick={() => projectSettings(selectedJob.project_id, 'history')}>پیگیری و لغو در پروژه</Button> : <Button loading={busy} onClick={() => void openProject(selectedJob.project_id, selectedJob.kind === 'source' ? 'source-code' : selectedJob.instance_id && selectedJob.stage_id ? `team-runs?instance=${encodeURIComponent(selectedJob.instance_id)}&stage=${encodeURIComponent(selectedJob.stage_id)}` : `program-settings?agent=${encodeURIComponent(selectedJob.agent_id || '')}&harness_attempt=${encodeURIComponent(selectedJob.id)}`)}>ورود به پروژه و پیگیری</Button>}<Button disabled={busy} onClick={() => show({ kind: 'activity' })}>بازگشت به فعالیت‌ها</Button></div></div></FormDialog>}
    {view?.kind === 'enter' && <FormDialog open title="ورود به فضای پروژه" description={`برای تنظیم یا پیگیری «${projects.find(project => project.id === view.id)?.name || 'پروژه'}» وارد فضای آن می‌شوید.`} busy={busy} error={error} close={close}><Button variant="primary" loading={busy} onClick={() => void openProject(view.id, view.section)}>ورود و ادامه</Button></FormDialog>}
    {view?.kind === 'revoke' && <FormDialog open title={`لغو دسترسی ${view.device.name}`} description={`این دستگاه دیگر کار دریافت نمی‌کند و کارهای فعال آن متوقف می‌شوند. ${projects.filter(project => project.binding?.device_id === view.device.id).length ? `برای ${projects.filter(project => project.binding?.device_id === view.device.id).map(project => project.name).join('، ')} باید مقصد دیگری انتخاب کنید. ` : ''}فایل‌های محلی حفظ می‌شوند. اتصال دوباره به کد تازه نیاز دارد.`} busy={busy} error={error} close={close}><Button tone="destructive" loading={busy} onClick={() => void revoke(view.device)}>لغو دسترسی این دستگاه</Button></FormDialog>}
  </div></main>
}

export default function SourceRunners({ projectId }: { projectId: string }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  return <Runners key={`${profile.id}:${projectId}`} projectId={projectId} accountId={profile.id} />
}
