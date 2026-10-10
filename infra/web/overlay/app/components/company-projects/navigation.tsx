'use client'

import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { usePathname, useRouter } from '@/next/navigation'
import { projectApi } from '@/service/company-projects'
import { companyNavigationScope, isCompanyStartPath } from '@/utils/company-navigation'

export function useCompanyNavigation() {
  const workspaceId = useAtomValue(currentWorkspaceIdAtom)
  const pathname = usePathname()
  const context = useQuery({ queryKey: ['company-context', workspaceId], queryFn: projectApi.context, enabled: !!workspaceId })
  const currentProject = context.data?.current_project || null
  const scope = companyNavigationScope(pathname, currentProject)
  return { context, scope, project: scope === 'project' ? currentProject : null }
}

export { productNavigation, projectNavigation } from '@/utils/company-navigation'

export function CompanyNavigationHeader() {
  const { project } = useCompanyNavigation()
  return project ? <section aria-label="پروژهٔ فعال" className="rounded-xl border border-divider-regular bg-components-panel-bg p-3">
    <p className="text-xs text-text-tertiary">پروژهٔ فعال</p>
    <p className="my-2 break-words text-sm font-semibold text-text-primary">{project.name}</p>
    <Link href="/projects" className="text-xs font-medium text-text-accent">تغییر پروژه</Link>
  </section> : <p className="px-2 py-3 text-sm font-semibold text-text-secondary">مدیریت محصول</p>
}

// Do not mount native project pages until their workspace context is known.
// This is a navigation boundary; server permissions remain authoritative.
export function CompanyNavigationBoundary({ children, selection }: { children: ReactNode; selection: ReactNode }) {
  const { context, scope } = useCompanyNavigation()
  const pathname = usePathname()
  const router = useRouter()
  useEffect(() => {
    if (isCompanyStartPath(pathname)) router.replace('/projects')
  }, [pathname, router])

  if (isCompanyStartPath(pathname) || !context.isSuccess) return <main dir="rtl" className="flex h-full flex-1 items-center justify-center p-8">
    <div role={context.isError ? 'alert' : 'status'} className="space-y-4 text-text-secondary">
      <p>{context.isError ? 'دریافت اطلاعات پروژه‌ها انجام نشد.' : 'در حال دریافت اطلاعات…'}</p>
      {context.isError && <button onClick={() => context.refetch()} className="rounded-xl border border-divider-regular px-4 py-2">تلاش دوباره</button>}
    </div>
  </main>
  return scope === 'choose' ? selection : children
}
