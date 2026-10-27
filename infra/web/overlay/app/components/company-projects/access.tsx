'use client'

import type { ReactNode } from 'react'
import type { CompanyProject } from '@/service/company-projects'
import { useQuery, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useState } from 'react'
import { workspacePermissionKeysAtom } from '@/context/permission-state'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import { systemFeaturesQueryOptions } from '@/features/system-features/client'
import Link from '@/next/link'
import { useRouter } from '@/next/navigation'
import { projectApi } from '@/service/company-projects'
import { consoleClient } from '@/service/console'
import { getRedirectionPath } from '@/utils/app-redirection'
import { AppForm } from './forms'
import FormDialog, { FieldHelp } from './form-dialog'
import ProjectOverview from './overview'

const primary = 'rounded-xl bg-components-button-primary-bg px-4 py-2 text-sm font-semibold text-components-button-primary-text hover:opacity-90 disabled:opacity-50'
const secondary = 'rounded-xl border border-divider-regular bg-components-panel-bg px-4 py-2 text-sm text-text-secondary disabled:opacity-50'
const input = 'mt-2 w-full rounded-xl border border-divider-regular bg-components-panel-bg px-3 py-2 text-sm text-text-primary'
const panel = 'rounded-2xl border border-divider-regular bg-components-panel-bg p-6'

function useProjectTools() {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const key = ['company-projects', workspace]
  const run = async (operation: () => Promise<unknown>, done?: () => void) => {
    if (busy) return
    setBusy(true); setError('')
    try {
      await operation()
      await queryClient.invalidateQueries({ queryKey: ['company-projects'] })
      await queryClient.invalidateQueries({ queryKey: ['company-context'] })
      done?.()
    }
    catch { setError('عملیات انجام نشد. نام تکراری، اتصال و دسترسی خود را بررسی کنید و دوباره تلاش کنید.') }
    finally { setBusy(false) }
  }
  const enter = (id: string) => run(async () => { await projectApi.enter(id); window.location.assign(`/projects/${id}`) })
  return { key, workspace, enabled: !!workspace, busy, error, run, enter }
}
function Page({ children }: { children: ReactNode }) {
  return <main dir="rtl" className="h-full min-w-0 overflow-y-auto bg-background-default-subtle p-6 lg:p-10"><div className="mx-auto min-w-0 max-w-6xl space-y-6">{children}</div></main>
}
function Notice({ error, retry }: { error: boolean; retry: () => void }) {
  return error ? <section role="alert" className={panel}><p className="mb-3 text-text-primary">دریافت اطلاعات انجام نشد. اتصال و دسترسی خود را بررسی کنید.</p><button className={secondary} onClick={retry}>تلاش دوباره</button></section> : <p role="status" className="p-6 text-text-tertiary">در حال دریافت اطلاعات…</p>
}
function OwnerSelect({ value, onChange, disabled }: { value: string; onChange: (id: string) => void; disabled: boolean }) {
  const owners = useQuery({ queryKey: ['company-projects', 'owners'], queryFn: projectApi.owners })
  return <label className="block text-sm text-text-secondary">مالک پروژه<select required value={value} disabled={disabled || !owners.isSuccess} onChange={event => onChange(event.target.value)} className={input}><option value="">یک کاربر فعال انتخاب کنید</option>{owners.data?.data.map(owner => <option key={owner.id} value={owner.id}>{owner.name} — {owner.email}</option>)}</select><span className="mt-2 block text-xs leading-6 text-text-tertiary">مالک پروژه اعضای همان پروژه را مدیریت می‌کند. برای انتخاب همکار جدید، ابتدا او را دعوت کنید تا حسابش را فعال کند.</span>{owners.isError && <button type="button" className={`${secondary} mt-2`} onClick={() => owners.refetch()}>دریافت دوبارهٔ کاربران</button>}</label>
}
function ProjectForm({ project, busy, error, onSave, onCancel }: { project?: CompanyProject; busy: boolean; error?: string; onSave: (values: { name: string; description: string; owner_id?: string }) => void; onCancel: () => void }) {
  const [name, setName] = useState(project?.name || '')
  const [description, setDescription] = useState(project?.description || '')
  const [owner, setOwner] = useState('')
  return <FormDialog open title={project ? 'ویرایش پروژه' : 'ساخت پروژه'} description="پروژه فضای مشترک اعضا، برنامه‌ها و دانش یک تیم است. نام و هدف پروژه را بنویسید و برای پروژهٔ تازه، مالک آن را از کاربران فعال کارا انتخاب کنید." busy={busy} error={error} close={onCancel}>
    <form onSubmit={event => { event.preventDefault(); if (name.trim() && (project || owner)) onSave({ name: name.trim(), description, ...(project ? {} : { owner_id: owner }) }) }} className="space-y-4" aria-label={project ? 'ویرایش پروژه' : 'ساخت پروژه'}><fieldset disabled={busy} className="space-y-4"><label className="block text-sm text-text-secondary">نام پروژه<input autoFocus required maxLength={120} value={name} onChange={event => setName(event.target.value)} className={input} /><FieldHelp>نام تیم یا محصولی که برنامه‌ها، دانش و اعضای آن در این پروژه گرد هم می‌آیند.</FieldHelp></label><label className="block text-sm text-text-secondary">توضیح پروژه<textarea rows={3} maxLength={2000} value={description} onChange={event => setDescription(event.target.value)} className={input} /><FieldHelp>هدف، محدوده و کاربرد پروژه را برای اعضای تیم بنویسید؛ تکمیل این بخش اختیاری است.</FieldHelp></label>{!project && <OwnerSelect value={owner} onChange={setOwner} disabled={busy} />}<div className="flex gap-3"><button disabled={busy || !name.trim() || (!project && !owner)} className={primary}>{busy ? 'در حال ذخیره…' : 'ذخیرهٔ پروژه'}</button><button type="button" disabled={busy} onClick={onCancel} className={secondary}>انصراف</button></div></fieldset></form>
  </FormDialog>
}
function OwnerForm({ project, busy, error, onSave, onCancel }: { project: CompanyProject; busy: boolean; error?: string; onSave: (id: string) => void; onCancel: () => void }) {
  const [owner, setOwner] = useState(project.owner?.id || '')
  return <FormDialog open title="تعیین مالک پروژه" description="یک عضو فعال را برای مدیریت اعضا و دسترسی‌های همین پروژه انتخاب کنید." busy={busy} error={error} close={onCancel}>
    <form aria-label="تعیین مالک پروژه" className="space-y-4" onSubmit={event => { event.preventDefault(); if (owner) onSave(owner) }}><fieldset disabled={busy} className="space-y-4"><OwnerSelect value={owner} onChange={setOwner} disabled={busy} /><p className="text-xs leading-6 text-text-tertiary">با جایگزینی مالک، مالک قبلی به توسعه‌دهندهٔ همین پروژه تبدیل می‌شود. دسترسی مدیریتی ادمین کل Kara حفظ می‌شود.</p><div className="flex gap-3"><button className={primary} disabled={busy || !owner}>ثبت مالک پروژه</button><button type="button" className={secondary} disabled={busy} onClick={onCancel}>انصراف</button></div></fieldset></form>
  </FormDialog>
}

export default function Projects() {
  const tools = useProjectTools()
  const [creating, setCreating] = useState(false)
  const { push } = useRouter()
  const projects = useQuery({ queryKey: [...tools.key, 'list'], queryFn: projectApi.list, enabled: tools.enabled })
  return <Page><header className="flex flex-wrap items-start justify-between gap-4"><div><p className="mb-2 text-sm text-text-tertiary">پروژه‌های در دسترس شما</p><h1 className="text-3xl font-bold text-text-primary">پروژه‌ها</h1><p className="mt-3 text-sm leading-7 text-text-secondary">برای شروع، یک پروژه انتخاب کنید. برنامه‌ها، ایجنت‌ها، دانش و اعضای هر پروژه در فضای همان تیم قرار دارند.</p></div>{projects.data?.can_create_projects && <button className={primary} onClick={() => setCreating(true)}>ساخت پروژه</button>}</header><p className="text-sm leading-7 text-text-tertiary">{projects.data?.can_create_projects ? 'شما مدیر کارا هستید. پروژه بسازید و مالک پروژهٔ جدید را انتخاب کنید.' : 'ساخت پروژه با مدیر کارا است. برای شروع، وارد یکی از پروژه‌های خود شوید.'}</p>{tools.error && <p role="alert" className="text-text-primary">{tools.error}</p>}{creating && projects.data?.can_create_projects && <ProjectForm busy={tools.busy} error={tools.error} onCancel={() => setCreating(false)} onSave={values => tools.run(async () => { const result = await projectApi.create(values); push(`/projects/${result.id}`) })} />}
    {projects.isPending || projects.isError ? <Notice error={projects.isError} retry={() => projects.refetch()} /> : projects.data.data.length ? <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{projects.data.data.map(project => <article key={project.id} className={`${panel} flex min-h-56 flex-col`}><h2 className="break-words text-lg font-semibold text-text-primary">{project.name}</h2><p className="mt-2 line-clamp-3 text-sm leading-6 text-text-secondary">{project.description || 'توضیحی ثبت نشده است.'}</p><p className="mb-5 mt-3 text-xs text-text-tertiary">مالک پروژه: {project.owner?.name || 'تعیین نشده'}</p><div className="mt-auto flex flex-wrap gap-3"><Link href={`/projects/${project.id}`} className={secondary}>جزئیات پروژه</Link>{project.workspace_id && <button className={primary} disabled={tools.busy} onClick={() => tools.enter(project.id)}>ورود به پروژه</button>}</div></article>)}</div> : <section className={`${panel} py-14 text-center`}><h2 className="mb-3 text-xl font-semibold text-text-primary">پروژه‌ای برای شما ثبت نشده است</h2><p className="text-sm text-text-secondary">{projects.data.can_create_projects ? 'اولین پروژه را بسازید و مالک آن را انتخاب کنید.' : 'از مالک پروژه بخواهید شما را به تیم دعوت کند.'}</p></section>}
  </Page>
}

export function ProjectDetail({ projectId }: { projectId: string }) {
  const tools = useProjectTools()
  const [editing, setEditing] = useState(false)
  const [owning, setOwning] = useState(false)
  const [creating, setCreating] = useState(false)
  const { push } = useRouter()
  const permissions = useAtomValue(workspacePermissionKeysAtom)
  const { data: features } = useSuspenseQuery(systemFeaturesQueryOptions())
  const { data: profile } = useSuspenseQuery(userProfileQueryOptions())
  const project = useQuery({ queryKey: [...tools.key, projectId], queryFn: () => projectApi.detail(projectId), enabled: tools.enabled })
  const entered = !!project.data?.workspace_id && project.data.workspace_id === tools.workspace
  const openApp = (id: string) => tools.run(async () => {
    const app = await consoleClient.apps.byAppId.get({ params: { app_id: id } })
    push(getRedirectionPath(app, { currentUserId: profile.profile.id, resourceMaintainer: app.maintainer, workspacePermissionKeys: permissions, isRbacEnabled: features.rbac_enabled }))
  })
  if (!project.isSuccess) return <Page><Link href="/projects" className="text-sm text-text-accent">همهٔ پروژه‌ها</Link><Notice error={project.isError} retry={() => project.refetch()} /></Page>
  const value = project.data
  return <Page>
    <nav aria-label="مسیر صفحه" className="flex flex-wrap items-center gap-2 text-sm"><Link href="/projects" className="text-text-accent">پروژه‌ها</Link><span aria-hidden="true" className="text-text-tertiary">/</span><span className="text-text-tertiary">نمای کلی پروژه</span></nav>
    <header className="flex min-w-0 flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 max-w-3xl flex-1"><h1 className="break-words text-3xl font-bold leading-normal text-text-primary [overflow-wrap:anywhere]">{value.name}</h1>
        {value.description && (value.description.length > 180 ? <details className="mt-3 text-sm leading-7 text-text-secondary"><summary className="cursor-pointer">هدف و توضیحات پروژه</summary><p className="mt-2 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{value.description}</p></details> : <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-text-secondary">{value.description}</p>)}
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs leading-6 text-text-tertiary"><span className="break-words">مالک پروژه: {value.owner?.name || 'تعیین نشده'}</span>{entered && <span>در فضای همین پروژه هستید</span>}</div>
      </div>
      {value.is_product_owner && <details className="shrink-0"><summary className={`${secondary} cursor-pointer`}>تنظیمات پروژه</summary><div className="mt-2 flex flex-wrap gap-2"><button disabled={tools.busy} className={secondary} onClick={() => { setEditing(true); setOwning(false) }}>ویرایش پروژه</button><button disabled={tools.busy || !value.workspace_id} className={secondary} onClick={() => { setOwning(true); setEditing(false) }}>تعیین مالک پروژه</button></div></details>}
    </header>
    {tools.error && <p role="alert" className="text-sm leading-7 text-text-primary">{tools.error}</p>}
    {editing && value.is_product_owner && <ProjectForm key={value.updated_at} project={value} busy={tools.busy} error={tools.error} onCancel={() => setEditing(false)} onSave={values => tools.run(() => projectApi.update(projectId, values), () => setEditing(false))} />}
    {owning && value.is_product_owner && <OwnerForm project={value} busy={tools.busy} error={tools.error} onCancel={() => setOwning(false)} onSave={id => tools.run(() => projectApi.setOwner(projectId, id), () => setOwning(false))} />}
    {!entered ? <section className={panel}><h2 className="mb-3 text-lg font-semibold text-text-primary">ورود به فضای پروژه</h2><p className="mb-5 text-sm leading-7 text-text-secondary">برای دیدن وضعیت کارها، برنامه‌ها و اعضای این پروژه، ابتدا وارد فضای همین پروژه شوید.</p>{value.workspace_id ? <button className={primary} disabled={tools.busy} onClick={() => tools.enter(projectId)}>ورود به پروژه</button> : <p className="text-sm text-text-tertiary">فضای مستقل این پروژه هنوز آماده نشده است.</p>}</section> : <>
      {creating && value.can_edit && <AppForm busy={tools.busy} error={tools.error} onCancel={() => setCreating(false)} onSave={values => tools.run(() => projectApi.createApp(projectId, values), () => setCreating(false))} />}
      <ProjectOverview key={`${value.workspace_id}:${value.id}:${profile.profile.id}`} project={value} accountId={profile.profile.id} opening={tools.busy} openApp={openApp} createApp={() => setCreating(true)} />
    </>}
  </Page>
}
