'use client'

import type { FormEvent } from 'react'
import { Button } from '@langgenius/dify-ui/button'
import { Combobox, ComboboxEmpty, ComboboxInput, ComboboxInputGroup, ComboboxInputTrigger, ComboboxItem, ComboboxItemIndicator, ComboboxItemText, ComboboxLabel, ComboboxList, ComboboxPopup, ComboboxPortal, ComboboxPositioner } from '@langgenius/dify-ui/combobox'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from '@langgenius/dify-ui/dialog'
import { IconButton } from '@langgenius/dify-ui/icon-button'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { RoleSelector } from '@/app/components/header/account-setting/members-page/invite-modal/role-selector'
import { projectApi } from '@/service/company-projects'
import { commonQueryKeys } from '@/service/use-common'

type KaraUser = { id: string; name: string; email: string }
const label = (user: KaraUser) => `${user.name} — ${user.email}`

export default function AddProjectMember({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [account, setAccount] = useState<KaraUser | null>(null)
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const queryClient = useQueryClient()
  const key = ['company-project-member-candidates', projectId]
  const candidates = useQuery({ queryKey: key, queryFn: () => projectApi.memberCandidates(projectId), enabled: open })
  const selected = !!account && query === label(account)
  const changeOpen = (value: boolean) => {
    if (busy) return
    setOpen(value); setError('')
    if (value) { setAccount(null); setQuery('') }
  }
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!account || !selected || busy) return
    const role = new FormData(event.currentTarget).get('role')
    if (typeof role !== 'string' || !role) { setError('نقش کاربر در پروژه را انتخاب کنید.'); return }
    setBusy(true); setError('')
    try {
      await projectApi.addMember(projectId, { account_id: account.id, role })
      await queryClient.invalidateQueries({ queryKey: commonQueryKeys.members })
      await queryClient.invalidateQueries({ queryKey: key })
      await queryClient.invalidateQueries({ queryKey: ['company-team-roles'] })
      setAccount(null); setQuery(''); setOpen(false)
    }
    catch { setError('افزودن انجام نشد. فعال‌بودن کاربر، دسترسی و فهرست کاربران را بررسی کنید.'); void candidates.refetch() }
    finally { setBusy(false) }
  }
  return <Dialog open={open} onOpenChange={changeOpen}>
    <DialogTrigger render={<Button variant="primary"><span aria-hidden="true" className="i-ri-user-add-line size-4" />افزودن عضو پروژه</Button>} />
    <DialogContent backdropProps={{ forceRender: true }}>
      <div className="grid gap-1 pr-8">
        <DialogTitle className="text-xl font-semibold text-text-primary">افزودن کاربر به پروژه</DialogTitle>
        <DialogDescription className="text-sm leading-7 text-text-tertiary">کاربر موجود کارا و نقش او را انتخاب کنید. عضویت بلافاصله فعال می‌شود و نیازی به لینک یا پذیرش دعوت پروژه نیست.</DialogDescription>
      </div>
      <form onSubmit={submit} className="mt-6 grid gap-5">
        {!candidates.isSuccess ? <p role={candidates.isError ? 'alert' : 'status'} className="text-sm text-text-secondary">{candidates.isError ? 'دریافت کاربران انجام نشد.' : 'در حال دریافت کاربران…'}{candidates.isError && <button type="button" onClick={() => candidates.refetch()}>تلاش دوباره</button>}</p> : <>
          <div>
            <Combobox<KaraUser> items={candidates.data.data} value={account} inputValue={query} onInputValueChange={setQuery} onValueChange={user => { setAccount(user); setQuery(user ? label(user) : '') }} itemToStringLabel={label} itemToStringValue={user => user.id} isItemEqualToValue={(a, b) => a.id === b.id} disabled={busy}>
              <ComboboxLabel>کاربر کارا</ComboboxLabel>
              <ComboboxInputGroup className="mt-2"><ComboboxInput placeholder="نام یا ایمیل کاربر را تایپ کنید…" /><ComboboxInputTrigger aria-label="نمایش کاربران کارا" /></ComboboxInputGroup>
              <ComboboxPortal><ComboboxPositioner><ComboboxPopup>
                <ComboboxList<KaraUser>>{user => <ComboboxItem key={user.id} value={user}><ComboboxItemText className="grid min-w-0 gap-0.5"><span className="truncate">{user.name}</span><bdi className="truncate text-xs text-text-tertiary">{user.email}</bdi></ComboboxItemText><ComboboxItemIndicator /></ComboboxItem>}</ComboboxList>
                <ComboboxEmpty>کاربر قابل افزودنی پیدا نشد.</ComboboxEmpty>
              </ComboboxPopup></ComboboxPositioner></ComboboxPortal>
            </Combobox>
            <p className="mt-2 text-xs leading-6 text-text-tertiary">با تایپ نام یا ایمیل، همین فهرست فیلتر می‌شود. فقط کاربران فعال کارا که هنوز عضو پروژه نیستند قابل انتخاب‌اند.</p>
          </div>
          <RoleSelector disabled={busy} />
          <p className="text-xs leading-6 text-text-tertiary">نقش انتخاب‌شده فقط در همین پروژه اعمال می‌شود و نقش کاربر در کارا یا پروژه‌های دیگر را تغییر نمی‌دهد.</p>
        </>}
        {error && <p role="alert" className="text-sm text-text-destructive-secondary">{error}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="secondary" disabled={busy} onClick={() => changeOpen(false)}>انصراف</Button><Button type="submit" variant="primary" disabled={busy || !selected || !candidates.isSuccess}>{busy ? 'در حال افزودن…' : 'افزودن به پروژه'}</Button></div>
      </form>
      <DialogClose render={<IconButton aria-label="بستن" size="lg" disabled={busy} className="absolute inset-e-6 top-6"><span aria-hidden className="i-ri-close-line size-4" /></IconButton>} />
    </DialogContent>
  </Dialog>
}
