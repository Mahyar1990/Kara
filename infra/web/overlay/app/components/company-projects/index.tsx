'use client'

import type { FormEvent, ReactNode } from 'react'
import type { CompanyProject, ProjectApp, ResourceKind } from '@/service/company-projects'
import { useQuery, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useState } from 'react'
import { workspacePermissionKeysAtom } from '@/context/permission-state'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import { isAgentV2Enabled } from '@/features/agent-v2/feature-flag'
import { systemFeaturesQueryOptions } from '@/features/system-features/client'
import Link from '@/next/link'
import { useRouter } from '@/next/navigation'
import { projectApi } from '@/service/company-projects'
import { consoleClient } from '@/service/console'
import { getRedirectionPath } from '@/utils/app-redirection'
import { hasPermission } from '@/utils/permission'

const primary = 'rounded-xl bg-components-button-primary-bg px-4 py-2 text-sm font-semibold text-components-button-primary-text hover:opacity-90 disabled:opacity-50'
const secondary = 'rounded-xl border border-divider-regular bg-components-panel-bg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-background-default-hover disabled:opacity-50'
const input = 'mt-2 w-full rounded-xl border border-divider-regular bg-components-panel-bg px-3 py-2 text-sm text-text-primary'
const panel = 'rounded-2xl border border-divider-regular bg-components-panel-bg p-6'
const number = (value: number) => value.toLocaleString('fa-IR')
const modeLabels: Record<string, string> = { workflow: 'فرایند', 'advanced-chat': 'گفتگو با فرایند', 'agent-chat': 'ایجنت', agent: 'ایجنت', chat: 'گفتگو', completion: 'تولید متن' }
const modeLabel = (mode: string) => modeLabels[mode] || 'برنامه'

function useProjectTools() {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const permissions = useAtomValue(workspacePermissionKeysAtom)
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const key = ['company-projects', workspace]
  const run = async (operation: () => Promise<unknown>, done?: () => void) => {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await operation()
      await queryClient.invalidateQueries({ queryKey: key })
      done?.()
    }
    catch { setError('عملیات انجام نشد. نام تکراری، اتصال و دسترسی خود را بررسی کنید و دوباره تلاش کنید.') }
    finally { setBusy(false) }
  }
  return { key, enabled: !!workspace, canManage: hasPermission(permissions, 'app.create_and_management'), busy, error, run }
}

function Page({ children }: { children: ReactNode }) {
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-default-subtle p-6 lg:p-10"><div className="mx-auto max-w-6xl space-y-6">{children}</div></main>
}
function Notice({ error, retry }: { error: boolean; retry: () => void }) {
  return error
    ? <div role="alert" className={panel}><p className="mb-3 text-text-primary">دریافت اطلاعات انجام نشد. اتصال و دسترسی خود را بررسی کنید.</p><button type="button" className={secondary} onClick={retry}>تلاش دوباره</button></div>
    : <p role="status" className="p-6 text-text-tertiary">در حال دریافت اطلاعات…</p>
}
function ErrorText({ text }: { text: string }) {
  return text ? <p role="alert" className="rounded-xl bg-background-default-hover p-3 text-sm text-text-primary">{text}</p> : null
}
function ProjectForm({ project, busy, onSave, onCancel }: {
  project?: CompanyProject
  busy: boolean
  onSave: (values: { name: string; description: string }) => void
  onCancel: () => void
}) {
  const [name, setName] = useState(project?.name || '')
  const [description, setDescription] = useState(project?.description || '')
  const submit = (event: FormEvent) => { event.preventDefault(); if (name.trim()) onSave({ name: name.trim(), description }) }
  return <form onSubmit={submit} className={`${panel} space-y-4`} aria-label={project ? 'ویرایش پروژه' : 'ساخت پروژه'}>
    <h2 className="text-lg font-semibold text-text-primary">{project ? 'ویرایش پروژه' : 'پروژهٔ جدید'}</h2>
    <label className="block text-sm text-text-secondary">نام پروژه<input autoFocus required maxLength={120} value={name} onChange={event => setName(event.target.value)} className={input} placeholder="مثلاً توسعهٔ محصول" /></label>
    <label className="block text-sm text-text-secondary">توضیح پروژه<textarea rows={3} maxLength={2000} value={description} onChange={event => setDescription(event.target.value)} className={input} placeholder="هدف و محدودهٔ کار این پروژه" /></label>
    <div className="flex gap-3"><button disabled={busy || !name.trim()} className={primary}>{busy ? 'در حال ذخیره…' : 'ذخیرهٔ پروژه'}</button><button type="button" disabled={busy} onClick={onCancel} className={secondary}>انصراف</button></div>
  </form>
}

export default function Projects() {
  const tools = useProjectTools()
  const [creating, setCreating] = useState(false)
  const { push } = useRouter()
  const projects = useQuery({ queryKey: [...tools.key, 'list'], queryFn: projectApi.list, enabled: tools.enabled })
  return <Page>
    <header className="flex flex-wrap items-start justify-between gap-4"><div><p className="mb-2 text-sm text-text-tertiary">فضای کاری تیم</p><h1 className="text-3xl font-bold text-text-primary">پروژه‌ها</h1><p className="mt-3 text-sm leading-7 text-text-secondary">برای هر محصول یا تیم یک پروژه بسازید و فرایندها و ایجنت‌های آن را در همان پروژه مدیریت کنید.</p></div>{tools.canManage && !creating && <button className={primary} onClick={() => setCreating(true)}>ساخت پروژه</button>}</header>
    <p className="text-xs leading-6 text-text-tertiary">اعضا و اتصال مدل در سطح فضای کاری مشترک‌اند. هر برنامه به یک پروژه تعلق می‌گیرد.</p>
    <ErrorText text={tools.error} />
    {creating && <ProjectForm busy={tools.busy} onCancel={() => setCreating(false)} onSave={values => tools.run(async () => { const result = await projectApi.create(values); push(`/projects/${result.id}`) })} />}
    {projects.isPending || projects.isError ? <Notice error={projects.isError} retry={() => projects.refetch()} /> : projects.data.data.length ? <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{projects.data.data.map(project => <Link key={project.id} href={`/projects/${project.id}`} className={`${panel} flex min-h-48 flex-col transition-shadow hover:shadow-md`}>
      <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl bg-background-default-hover text-xl" aria-hidden="true">▦</div><h2 className="break-words text-lg font-semibold text-text-primary">{project.name}</h2><p className="mt-2 line-clamp-3 text-sm leading-6 text-text-secondary">{project.description || 'توضیحی ثبت نشده است.'}</p><span className="mt-5 text-sm font-medium text-text-accent">مشاهدهٔ پروژه ←</span>
    </Link>)}</div> : <div className={`${panel} py-14 text-center`}><h2 className="mb-3 text-xl font-semibold text-text-primary">اولین پروژهٔ تیم را بسازید</h2><p className="text-sm text-text-secondary">پس از ساخت پروژه می‌توانید فرایند و ایجنت جدید بسازید یا برنامه‌های موجود را به آن اضافه کنید.</p></div>}
  </Page>
}

function AppForm({ busy, onSave, onCancel }: { busy: boolean; onSave: (values: { name: string; description: string; mode: string }) => void; onCancel: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [mode, setMode] = useState('workflow')
  return <form className={`${panel} space-y-4`} aria-label="ساخت برنامه در پروژه" onSubmit={event => { event.preventDefault(); if (name.trim()) onSave({ name: name.trim(), description, mode }) }}>
    <h2 className="text-lg font-semibold text-text-primary">برنامهٔ جدید در این پروژه</h2>
    <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm text-text-secondary">نام برنامه<input autoFocus required maxLength={120} value={name} onChange={event => setName(event.target.value)} className={input} /></label><label className="text-sm text-text-secondary">نوع برنامه<select className={input} value={mode} onChange={event => setMode(event.target.value)}><option value="workflow">فرایند</option><option value="advanced-chat">گفتگو با فرایند</option><option value="agent-chat">ایجنت</option>{isAgentV2Enabled() && <option value="agent">ایجنت با ویرایشگر جدید</option>}</select></label></div>
    <label className="block text-sm text-text-secondary">توضیح برنامه<textarea maxLength={400} rows={2} value={description} onChange={event => setDescription(event.target.value)} className={input} /></label>
    <p className="text-xs text-text-tertiary">پس از ساخت، برنامه را باز کنید و مراحل، دستورالعمل و مدل آن را تنظیم کنید.</p>
    <div className="flex gap-3"><button disabled={busy || !name.trim()} className={primary}>{busy ? 'در حال ساخت…' : 'ساخت برنامه'}</button><button type="button" disabled={busy} onClick={onCancel} className={secondary}>انصراف</button></div>
  </form>
}

function ResourcePicker({ projectId, busy, onAssign, onClose }: { projectId: string; busy: boolean; onAssign: (app: ProjectApp) => void; onClose: () => void }) {
  const tools = useProjectTools()
  const [search, setSearch] = useState('')
  const [name, setName] = useState('')
  const [page, setPage] = useState(1)
  const [moving, setMoving] = useState<ProjectApp | null>(null)
  const resources = useQuery({ queryKey: [...tools.key, 'resources', name, page], queryFn: () => projectApi.resources(name, page), enabled: tools.enabled })
  const select = (app: ProjectApp) => { if (app.project) setMoving(app); else onAssign(app) }
  return <section className={`${panel} space-y-4`} aria-label="انتخاب برنامهٔ موجود">
    <div className="flex items-center justify-between"><h2 className="text-lg font-semibold text-text-primary">افزودن برنامهٔ موجود</h2><button className={secondary} onClick={onClose} disabled={busy}>بستن</button></div>
    <form className="flex gap-3" onSubmit={event => { event.preventDefault(); setName(search); setPage(1) }}><label className="flex-1 text-sm text-text-secondary">جستجوی برنامه<input value={search} maxLength={30} onChange={event => setSearch(event.target.value)} className={input} /></label><button className={`${secondary} self-end`}>جستجو</button></form>
    {moving && <div role="alert" className="rounded-xl bg-background-default-hover p-4 text-sm text-text-primary"><p className="mb-3">«{moving.name}» اکنون در پروژهٔ «{moving.project?.name}» است. با انتقال، از پروژهٔ قبلی خارج می‌شود.</p><div className="flex gap-3"><button disabled={busy} className={primary} onClick={() => { onAssign(moving); setMoving(null) }}>تأیید انتقال به این پروژه</button><button disabled={busy} className={secondary} onClick={() => setMoving(null)}>انصراف از انتقال</button></div></div>}
    {resources.isPending || resources.isError ? <Notice error={resources.isError} retry={() => resources.refetch()} /> : <>
      {!resources.data.data.length && <p className="text-sm text-text-tertiary">برنامه‌ای پیدا نشد.</p>}
      <ul className="divide-y divide-divider-regular">{resources.data.data.map(app => <li key={app.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><p className="font-medium text-text-primary">{app.name}</p><p className="mt-1 text-xs text-text-tertiary">{modeLabel(app.mode)} · {app.project ? `پروژهٔ ${app.project.name}` : 'بدون پروژه'}</p></div><button disabled={busy || app.project?.id === projectId} className={secondary} onClick={() => select(app)}>{app.project?.id === projectId ? 'در همین پروژه' : app.project ? 'انتقال به این پروژه' : 'افزودن به پروژه'}</button></li>)}</ul>
      <Pagination page={page} hasMore={resources.data.has_more} onPage={setPage} />
    </>}
  </section>
}

function Pagination({ page, hasMore, onPage }: { page: number; hasMore: boolean; onPage: (page: number) => void }) {
  if (page === 1 && !hasMore) return null
  return <nav aria-label="صفحه‌بندی برنامه‌ها" className="flex items-center justify-center gap-4"><button className={secondary} disabled={page === 1} onClick={() => onPage(page - 1)}>صفحهٔ قبل</button><span className="text-sm text-text-secondary">صفحهٔ {number(page)}</span><button className={secondary} disabled={!hasMore} onClick={() => onPage(page + 1)}>صفحهٔ بعد</button></nav>
}

export function ProjectDetail({ projectId }: { projectId: string }) {
  const tools = useProjectTools()
  const [editing, setEditing] = useState(false)
  const [creating, setCreating] = useState(false)
  const [picking, setPicking] = useState(false)
  const [kind, setKind] = useState<ResourceKind>('all')
  const [page, setPage] = useState(1)
  const [removing, setRemoving] = useState<ProjectApp | null>(null)
  const { push } = useRouter()
  const permissions = useAtomValue(workspacePermissionKeysAtom)
  const { data: features } = useSuspenseQuery(systemFeaturesQueryOptions())
  const { data: profile } = useSuspenseQuery(userProfileQueryOptions())
  const project = useQuery({ queryKey: [...tools.key, projectId], queryFn: () => projectApi.detail(projectId), enabled: tools.enabled })
  const apps = useQuery({ queryKey: [...tools.key, projectId, 'apps', kind, page], queryFn: () => projectApi.apps(projectId, kind, page), enabled: tools.enabled && project.isSuccess })
  const openApp = (id: string) => tools.run(async () => {
    const app = await consoleClient.apps.byAppId.get({ params: { app_id: id } })
    push(getRedirectionPath(app, { currentUserId: profile.profile.id, resourceMaintainer: app.maintainer, workspacePermissionKeys: permissions, isRbacEnabled: features.rbac_enabled }))
  })
  if (!project.isSuccess) return <Page><Link href="/projects" className="text-sm text-text-accent">← همهٔ پروژه‌ها</Link><Notice error={project.isError} retry={() => project.refetch()} /></Page>
  return <Page>
    <Link href="/projects" className="text-sm font-medium text-text-accent">← همهٔ پروژه‌ها</Link>
    <header className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="break-words text-3xl font-bold text-text-primary">{project.data.name}</h1><p className="mt-3 max-w-3xl whitespace-pre-wrap text-sm leading-7 text-text-secondary">{project.data.description || 'فرایندها و ایجنت‌های این پروژه را اینجا بسازید و مدیریت کنید.'}</p></div>{tools.canManage && <button disabled={tools.busy} className={secondary} onClick={() => setEditing(!editing)}>ویرایش پروژه</button>}</header>
    <ErrorText text={tools.error} />
    {editing && <ProjectForm key={project.data.updated_at} project={project.data} busy={tools.busy} onCancel={() => setEditing(false)} onSave={values => tools.run(() => projectApi.update(projectId, values), () => setEditing(false))} />}
    <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap gap-2" aria-label="نوع برنامه">{([['all', 'همهٔ برنامه‌ها'], ['workflow', 'فرایندها'], ['agent', 'ایجنت‌ها'], ['other', 'سایر برنامه‌ها']] as const).map(([value, label]) => <button aria-pressed={kind === value} className={kind === value ? primary : secondary} key={value} onClick={() => { setKind(value); setPage(1) }}>{label}</button>)}</div>{tools.canManage && <div className="flex gap-2"><button className={secondary} disabled={tools.busy} onClick={() => { setPicking(!picking); setCreating(false) }}>افزودن برنامهٔ موجود</button><button className={primary} disabled={tools.busy} onClick={() => { setCreating(!creating); setPicking(false) }}>ساخت برنامه</button></div>}</div>
    {creating && <AppForm busy={tools.busy} onCancel={() => setCreating(false)} onSave={values => tools.run(() => projectApi.createApp(projectId, values), () => { setCreating(false); setKind('all'); setPage(1) })} />}
    {picking && <ResourcePicker projectId={projectId} busy={tools.busy} onClose={() => setPicking(false)} onAssign={app => tools.run(() => projectApi.assign(projectId, app.id))} />}
    {removing && <section role="alert" className={panel}><p className="mb-4 text-sm text-text-primary">«{removing.name}» از این پروژه خارج شود؟ برنامه در استودیو باقی می‌ماند.</p><div className="flex gap-3"><button className={primary} disabled={tools.busy} onClick={() => tools.run(() => projectApi.remove(projectId, removing.id), () => setRemoving(null))}>تأیید خروج از پروژه</button><button className={secondary} disabled={tools.busy} onClick={() => setRemoving(null)}>انصراف</button></div></section>}
    {apps.isPending || apps.isError ? <Notice error={apps.isError} retry={() => apps.refetch()} /> : <>
      <p className="text-sm text-text-tertiary">{number(apps.data.total)} برنامه در این بخش</p>
      {apps.data.data.length ? <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{apps.data.data.map(app => <article key={app.id} className={`${panel} flex min-h-52 flex-col`}><span className="mb-4 text-xs font-medium text-text-accent">{modeLabel(app.mode)}</span><h2 className="break-words text-lg font-semibold text-text-primary">{app.name}</h2><p className="mb-6 mt-2 line-clamp-3 text-sm leading-6 text-text-secondary">{app.description || 'برای تنظیم برنامه، آن را باز کنید.'}</p><div className="mt-auto flex flex-wrap gap-2"><button className={secondary} disabled={tools.busy} onClick={() => openApp(app.id)}>باز کردن برنامه</button>{tools.canManage && <button className="text-xs text-text-tertiary hover:text-text-primary" disabled={tools.busy} onClick={() => setRemoving(app)}>خروج از پروژه</button>}</div></article>)}</div> : <div className={`${panel} py-14 text-center`}><h2 className="mb-3 text-lg font-semibold text-text-primary">هنوز برنامه‌ای در این بخش وجود ندارد</h2><p className="text-sm text-text-secondary">یک برنامه بسازید یا از برنامه‌های موجود به این پروژه اضافه کنید.</p></div>}
      <Pagination page={page} hasMore={apps.data.has_more} onPage={setPage} />
    </>}
  </Page>
}
