'use client'

import type { ReactNode } from 'react'
import type { CompanyProject } from '@/service/company-projects'
import { useQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { projectApi } from '@/service/company-projects'

export const panel = 'rounded-2xl border border-divider-regular bg-components-panel-bg p-6'
export const button = 'rounded-xl border border-divider-regular px-4 py-2 text-sm text-text-primary disabled:opacity-50'
export const primary = 'rounded-xl bg-components-button-primary-bg px-4 py-2 text-sm font-semibold text-components-button-primary-text disabled:opacity-50'
export const input = 'mt-2 w-full rounded-xl border border-divider-regular bg-components-panel-bg px-3 py-2 text-sm text-text-primary'

export function ProjectPage({ projectId, title, children }: { projectId: string; title: string; children: (project: CompanyProject) => ReactNode }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const project = useQuery({ queryKey: ['company-projects', workspace, projectId], queryFn: () => projectApi.detail(projectId), enabled: !!workspace })
  const enter = async () => {
    setBusy(true); setError('')
    try { await projectApi.enter(projectId); window.location.reload() }
    catch { setError('ورود به پروژه انجام نشد. اتصال و دسترسی خود را بررسی کنید.'); setBusy(false) }
  }
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-default-subtle p-6 lg:p-10"><div className="mx-auto max-w-6xl space-y-6">
    <Link href={`/projects/${projectId}`} className="text-sm text-text-accent">بازگشت به پروژه</Link>
    <header><p className="mb-2 text-sm text-text-tertiary">{project.data?.name}</p><h1 className="text-3xl font-bold text-text-primary">{title}</h1></header>
    {error && <p role="alert" className="text-text-primary">{error}</p>}
    {!project.isSuccess ? <QueryNotice error={project.isError} retry={() => project.refetch()} /> : project.data.workspace_id !== workspace ? <section className={panel}><p className="mb-4 text-sm leading-7 text-text-secondary">برای استفاده از این بخش وارد فضای همین پروژه شوید.</p><button disabled={busy} className={primary} onClick={enter}>ورود به پروژه</button></section> : children(project.data)}
  </div></main>
}

export function QueryNotice({ error, retry }: { error: boolean; retry: () => void }) {
  return <section className={panel} role={error ? 'alert' : 'status'}><p className="text-sm text-text-secondary">{error ? 'دریافت اطلاعات انجام نشد. اتصال و دسترسی خود را بررسی کنید.' : 'در حال دریافت اطلاعات…'}</p>{error && <button className={`${button} mt-4`} onClick={retry}>تلاش دوباره</button>}</section>
}
