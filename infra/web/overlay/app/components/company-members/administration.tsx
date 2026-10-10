'use client'

import { useAtomValue } from 'jotai'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useCompanyNavigation } from '@/app/components/company-projects/navigation'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { consoleClient } from '@/service/console'
import CompanyMembers from '.'

export default function ProductMembers() {
  const { context } = useCompanyNavigation()
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const switching = useRef(false)
  const [error, setError] = useState(false)
  const switchToProduct = useCallback(async () => {
    const company = context.data
    if (!company?.is_product_owner || switching.current || workspace === company.root_workspace_id) return
    switching.current = true
    setError(false)
    try {
      await consoleClient.workspaces.switch.post({ body: { tenant_id: company.root_workspace_id } })
      window.location.reload()
    }
    catch { switching.current = false; setError(true) }
  }, [context.data, workspace])
  useEffect(() => { void switchToProduct() }, [switchToProduct])

  if (!context.data?.is_product_owner) return <main dir="rtl" className="p-8 text-text-primary">
    <h1 className="mb-4 text-2xl font-bold">دسترسی به مدیریت محصول ندارید</h1>
    <Link href="/projects" className="text-text-accent">مشاهدهٔ پروژه‌ها</Link>
  </main>
  if (workspace !== context.data.root_workspace_id) return <main dir="rtl" className="space-y-4 p-8 text-text-primary">
    <p role={error ? 'alert' : 'status'}>{error ? 'ورود به مدیریت محصول انجام نشد. اتصال خود را بررسی کنید.' : 'در حال باز کردن مدیریت محصول…'}</p>
    {error && <button onClick={switchToProduct} className="rounded-xl border border-divider-regular px-4 py-2">تلاش دوباره</button>}
  </main>
  return <CompanyMembers />
}
