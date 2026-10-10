'use client'

import type { MemberStatusFilter } from '@/utils/company-members'
import { useAtomValue } from 'jotai'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Link from '@/next/link'
import { projectApi } from '@/service/company-projects'
import MembersPage from '@/app/components/header/account-setting/members-page'
import { useLocale } from '@/context/i18n'
import { workspacePermissionKeysAtom } from '@/context/permission-state'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { getAccessControlTemplateLanguage } from '@/i18n-config/language'
import { useMembers } from '@/service/use-common'
import { filterWorkspaceMembers } from '@/utils/company-members'
import { hasPermission } from '@/utils/permission'

const number = (value: number) => value.toLocaleString('fa-IR')

export default function CompanyMembers() {
  const workspaceId = useAtomValue(currentWorkspaceIdAtom)
  const permissions = useAtomValue(workspacePermissionKeysAtom)
  const canManage = hasPermission(permissions, 'workspace.member.manage')
  const locale = useLocale()
  const members = useMembers(getAccessControlTemplateLanguage(locale))
  const context = useQuery({ queryKey: ['company-context', workspaceId], queryFn: projectApi.context, enabled: !!workspaceId })
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<MemberStatusFilter>('all')
  const accounts = members.data?.accounts || []
  const visibleCount = filterWorkspaceMembers(accounts, search, status).length
  if (!context.isSuccess) return <main dir="rtl" className="p-8 text-text-primary"><p>{context.isError ? 'دریافت محدودهٔ دسترسی انجام نشد.' : 'در حال دریافت اطلاعات…'}</p>{context.isError && <button onClick={() => context.refetch()}>تلاش دوباره</button>}</main>
  const project = context.data.current_project
  if (!project && !context.data.is_product_owner) return <main dir="rtl" className="p-8 text-text-primary"><h1 className="mb-4 text-2xl font-bold">ابتدا پروژه را انتخاب کنید</h1><Link href="/projects" className="text-text-accent">مشاهدهٔ پروژه‌های من</Link></main>

  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 md:p-8">
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <p className="mb-2 text-sm text-text-tertiary">{project ? `اعضای پروژهٔ ${project.name}` : 'مرکز مدیریت محصول'}</p>
        <h1 className="text-3xl font-bold text-text-primary">{project ? 'اعضای پروژه' : 'مدیریت کاربران محصول'}</h1>
        <p className="mt-3 text-sm leading-7 text-text-secondary">کاربران تیم، دعوت‌نامه‌ها و نقش هر عضو را در این بخش مدیریت کنید.</p>
      </header>
      <p className="text-sm leading-7 text-text-tertiary">{project ? `دعوت و نقش کاربران فقط برای پروژهٔ «${project.name}» اعمال می‌شود. ${canManage ? 'برای افزودن همکار، ایمیل و نقش او را در فرم دعوت وارد کنید.' : 'مدیریت اعضا با مالک پروژه است.'}` : 'شما مالک محصول هستید. برای تعیین مالک جدید، ابتدا همکار را دعوت کنید تا حسابش فعال شود. دسترسی به پروژه‌ها از صفحهٔ هر پروژه تعیین می‌شود.'}</p>
      <Link href="/projects" className="inline-block text-sm text-text-accent">مشاهده و انتخاب پروژه‌ها ←</Link>
      {members.isPending ? <p role="status" className="text-sm text-text-secondary">در حال دریافت کاربران…</p> : members.isError ? <section role="alert" className="rounded-2xl border border-divider-regular bg-background-default p-6"><p className="mb-4 text-text-primary">دریافت فهرست کاربران انجام نشد.</p><button className="rounded-lg bg-components-button-primary-bg px-4 py-2 text-white" onClick={() => members.refetch()}>تلاش دوباره</button></section> : <>
        <section aria-label="آمار کاربران" className="grid grid-cols-3 gap-3">
          {([['کل اعضا', accounts.length], ['فعال', accounts.filter(member => member.status === 'active').length], ['در انتظار پذیرش دعوت', accounts.filter(member => member.status === 'pending').length]] as const).map(([label, count]) => <div key={label} className="rounded-xl border border-divider-regular bg-background-default p-4"><p className="text-xs leading-6 text-text-tertiary">{label}</p><p className="mt-2 text-2xl font-semibold text-text-primary">{number(count)}</p></div>)}
        </section>
        <div className="flex flex-wrap gap-4">
          <label className="min-w-52 flex-1 text-sm text-text-secondary">جستجوی کاربر<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="نام یا ایمیل" className="mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary" /></label>
          <label className="text-sm text-text-secondary">وضعیت کاربر<select value={status} onChange={event => setStatus(event.target.value as MemberStatusFilter)} className="mt-2 block rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary"><option value="all">همهٔ کاربران</option><option value="active">فعال</option><option value="pending">در انتظار پذیرش دعوت</option></select></label>
        </div>
        <section aria-label="فهرست کاربران" className="rounded-2xl border border-divider-regular bg-background-default p-5">
          <p role="status" className="mb-5 text-sm text-text-tertiary">{number(visibleCount)} کاربر در این فهرست{!visibleCount && '؛ کاربری با این جستجو و وضعیت پیدا نشد.'}</p>
          <div className="overflow-x-auto"><MembersPage key={workspaceId} search={search} status={status} /></div>
        </section>
      </>}
    </div>
  </main>
}
