'use client'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useState } from 'react'
import { projectApi } from '@/service/company-projects'
import { commonQueryKeys } from '@/service/use-common'

export default function AddProjectMember({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [account, setAccount] = useState('')
  const [role, setRole] = useState('normal')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const queryClient = useQueryClient()
  const key = ['company-project-member-candidates', projectId]
  const candidates = useQuery({ queryKey: key, queryFn: () => projectApi.memberCandidates(projectId), enabled: open })
  const users = (candidates.data?.data || []).filter(user => `${user.name} ${user.email}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!account || busy) return
    setBusy(true); setError('')
    try {
      await projectApi.addMember(projectId, { account_id: account, role })
      await queryClient.invalidateQueries({ queryKey: commonQueryKeys.members })
      await queryClient.invalidateQueries({ queryKey: key })
      await queryClient.invalidateQueries({ queryKey: ['company-team-roles'] })
      setAccount(''); setSearch(''); setOpen(false)
    }
    catch { setError('افزودن انجام نشد. فعال‌بودن کاربر، دسترسی و فهرست کاربران را بررسی کنید.'); void candidates.refetch() }
    finally { setBusy(false) }
  }
  const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
  return <section className="rounded-xl border border-divider-regular bg-background-default p-5">
    <button type="button" className="rounded-lg bg-components-button-primary-bg px-4 py-2 text-components-button-primary-text" onClick={() => { setOpen(!open); setError('') }}>افزودن عضو پروژه</button>
    {open && <form onSubmit={submit} className="mt-4 space-y-4">
      <p className="text-sm leading-7 text-text-secondary">کاربر فعال کارا را انتخاب کنید. عضویت بلافاصله ثبت می‌شود و نیازی به لینک یا پذیرش دعوت پروژه نیست.</p>
      {!candidates.isSuccess ? <p role={candidates.isError ? 'alert' : 'status'}>{candidates.isError ? 'دریافت کاربران انجام نشد.' : 'در حال دریافت کاربران…'}{candidates.isError && <button type="button" onClick={() => candidates.refetch()}>تلاش دوباره</button>}</p> : <>
        <label className="block text-sm text-text-secondary">جستجوی کاربر<input className={field} value={search} onChange={event => { setSearch(event.target.value); setAccount('') }} placeholder="نام یا ایمیل کاربر موجود کارا" /></label>
        <label className="block text-sm text-text-secondary">کاربر کارا<select required className={field} value={account} disabled={busy} onChange={event => setAccount(event.target.value)}><option value="">یک کاربر انتخاب کنید</option>{users.map(user => <option key={user.id} value={user.id}>{user.name} — {user.email}</option>)}</select></label>
        {!users.length && <p className="text-sm text-text-tertiary">کاربر قابل افزودنی پیدا نشد. کاربر باید در مدیریت کاربران کارا فعال باشد و قبلاً عضو این پروژه نشده باشد.</p>}
        <label className="block text-sm text-text-secondary">نقش در پروژه<select className={field} value={role} disabled={busy} onChange={event => setRole(event.target.value)}>{candidates.data.roles.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <button disabled={busy || !account} className="rounded-lg bg-components-button-primary-bg px-4 py-2 text-components-button-primary-text">{busy ? 'در حال افزودن…' : 'افزودن به پروژه'}</button>
      </>}
      {error && <p role="alert" className="text-sm text-text-destructive">{error}</p>}
    </form>}
  </section>
}
