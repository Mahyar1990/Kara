'use client'

import type { BusinessRole, MemberBusinessRoles } from '@/service/company-projects'
import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { teamApi } from '@/service/company-projects'

const labels: Record<BusinessRole, string> = { po: 'مالک محصول (PO)', tl: 'راهبر فنی (TL)', designer: 'طراح UI/UX', developer: 'توسعه‌دهنده', qc: 'کنترل کیفیت (QC)' }
type Member = { id: string; name: string; status: string }

function MemberRoles({ projectId, member, value, canManage, refresh }: { projectId: string; member: Member; value: MemberBusinessRoles; canManage: boolean; refresh: () => Promise<unknown> }) {
  const [roles, setRoles] = useState<BusinessRole[]>(value.roles)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const operation = useRef<{ payload: string; key: string } | null>(null)
  const changed = [...roles].sort().join() !== [...value.roles].sort().join()
  const editable = canManage && member.status === 'active'
  const save = async () => {
    setBusy(true)
    setMessage('')
    const body = { roles: [...roles].sort(), expected_revision: value.revision, expected_membership_id: value.membership_id }
    const payload = JSON.stringify(body)
    if (operation.current?.payload !== payload) operation.current = { payload, key: crypto.randomUUID() }
    try {
      await teamApi.replace(projectId, member.id, body, operation.current.key)
      await refresh()
    }
    catch { setMessage('ذخیره انجام نشد. اتصال و دسترسی را بررسی کنید؛ اگر نقش‌ها تغییر کرده‌اند، فهرست تازه را دریافت کنید.') }
    finally { setBusy(false) }
  }
  return <form aria-label={`نقش‌های کاری ${member.name}`} className="space-y-3 rounded-xl border border-divider-regular p-4" onSubmit={event => { event.preventDefault(); if (changed && editable && !busy) void save() }}>
    <fieldset disabled={!editable || busy}>
      <legend className="mb-3 font-medium text-text-primary">{member.name}</legend>
      <div className="flex flex-wrap gap-x-5 gap-y-3">{(Object.entries(labels) as [BusinessRole, string][]).map(([role, label]) => <label key={role} className="flex items-center gap-2 text-sm text-text-secondary"><input type="checkbox" checked={roles.includes(role)} onChange={event => setRoles(event.target.checked ? [...roles, role] : roles.filter(item => item !== role))} />{label}</label>)}</div>
    </fieldset>
    {canManage && member.status !== 'active' && <p className="text-xs text-text-tertiary">پس از فعال‌شدن حساب، نقش کاری تعیین کنید.</p>}
    {editable && <button disabled={!changed || busy} className="rounded-lg bg-components-button-primary-bg px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? 'در حال ذخیره…' : 'ذخیرهٔ نقش‌های کاری'}</button>}
    {message && <p role="alert" className="text-sm text-text-primary">{message}</p>}
  </form>
}

export default function BusinessRoles({ projectId, workspaceId, members, canManage }: { projectId: string; workspaceId: string; members: Member[]; canManage: boolean }) {
  const membershipVersion = members.map(member => `${member.id}:${member.status}`).sort().join(',')
  const roles = useQuery({ queryKey: ['company-team-roles', workspaceId, projectId, membershipVersion], queryFn: () => teamApi.list(projectId) })
  return <section aria-label="نقش‌های کاری اعضا" className="space-y-4 rounded-2xl border border-divider-regular bg-background-default p-5">
    <h2 className="text-lg font-semibold text-text-primary">نقش‌های کاری اعضا</h2>
    <p className="text-sm leading-7 text-text-secondary">هر عضو می‌تواند چند نقش کاری داشته باشد. این نقش‌ها سطح دسترسی فنی یا مجوز اجرای ایجنت را تغییر نمی‌دهند. تعیین نقش‌ها با ادمین کل Kara و مدیر پروژه است.</p>
    {roles.isPending ? <p role="status">در حال دریافت نقش‌ها…</p> : roles.isError ? <p role="alert">دریافت نقش‌ها انجام نشد.</p> : members.map(member => {
      const value = roles.data.data.find(item => item.account_id === member.id)
      return value && <MemberRoles key={`${value.membership_id}:${value.revision}`} projectId={projectId} member={member} value={value} canManage={canManage} refresh={roles.refetch} />
    })}
    <button type="button" disabled={roles.isFetching} onClick={() => roles.refetch()} className="text-sm text-text-accent">دریافت فهرست تازهٔ نقش‌ها</button>
  </section>
}
