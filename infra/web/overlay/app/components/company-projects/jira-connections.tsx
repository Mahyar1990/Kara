'use client'

import type { JiraConnection } from '@/service/company-jira'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import Link from '@/next/link'
import { jiraApi, jiraError } from '@/service/company-jira'
import FormDialog, { FieldHelp } from './form-dialog'

const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'

function ConnectionEditor({ value, saved, close }: { value: JiraConnection | null; saved: () => Promise<unknown>; close: () => void }) {
  const [name, setName] = useState(value?.name || '')
  const [address, setAddress] = useState(value?.base_url || '')
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async () => {
    if (busy) return
    setBusy(true); setError('')
    try {
      await jiraApi.save(value?.id || null, { name, base_url: address, token, expected_revision: value?.revision || 1 })
      setToken(''); await saved(); close()
    } catch (error) { setError(await jiraError(error, 'ذخیرهٔ اتصال انجام نشد. اطلاعات و دسترسی حساب را بررسی کنید.')) }
    finally { setBusy(false) }
  }
  return <FormDialog open title={value ? 'ویرایش اتصال به جیرا' : 'ایجاد اتصال به جیرا'} description="این اتصال فقط متعلق به حساب شماست و در پروژه‌های شما قابل انتخاب است. ذخیره‌کردن اتصال، به‌تنهایی سرویس جیرا را فراخوانی نمی‌کند." busy={busy} error={error} close={close}>
    <form className="space-y-4" onSubmit={event => { event.preventDefault(); void submit() }}>
      <fieldset disabled={busy} className="space-y-4">
        <label className="block text-sm">نام اتصال<input className={field} required maxLength={120} value={name} onChange={event => setName(event.target.value)} /><FieldHelp>نامی مانند «جیرای شرکت» انتخاب کنید تا هنگام ورود درخواست‌ها آن را پیدا کنید.</FieldHelp></label>
        <label className="block text-sm">آدرس پایهٔ جیرا<input className={field} dir="ltr" type="url" required maxLength={512} placeholder="https://jira.example.com" value={address} onChange={event => setAddress(event.target.value)} /><FieldHelp>نشانی HTTPS و مسیر نصب احتمالی را وارد کنید؛ مسیرهایی مانند /rest/api/2/search را اضافه نکنید.</FieldHelp></label>
        <label className="block text-sm">توکن شخصی جیرا<input className={field} dir="ltr" type="password" autoComplete="new-password" required={!value || address !== value.base_url} maxLength={8192} value={token} onChange={event => setToken(event.target.value)} /><FieldHelp>{value ? 'برای حفظ توکن فعلی، این کادر را خالی بگذارید. با تغییر آدرس، توکن را دوباره وارد کنید.' : 'فقط مقدار توکن خودتان را وارد کنید؛ عبارت Bearer و هدر Authorization لازم نیست.'} توکن رمزگذاری‌شده ذخیره می‌شود و دوباره نمایش داده نمی‌شود.</FieldHelp></label>
      </fieldset>
      <div className="flex justify-end gap-2"><Button type="button" variant="secondary" disabled={busy} onClick={close}>انصراف</Button><Button type="submit" variant="primary" disabled={busy}>{busy ? 'در حال ذخیره…' : 'ذخیرهٔ اتصال'}</Button></div>
    </form>
  </FormDialog>
}

function Connections({ projectId, accountId }: { projectId: string; accountId: string }) {
  const list = useQuery({ queryKey: ['personal-jira-connections', accountId], queryFn: jiraApi.list })
  const [editing, setEditing] = useState<JiraConnection | 'new' | null>(null)
  const [removing, setRemoving] = useState<JiraConnection | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const test = async (value: JiraConnection) => {
    if (busy) return
    setBusy(true); setError(''); setMessage('')
    try { setMessage(`${value.name}: ${(await jiraApi.test(value.id)).message}`) }
    catch (error) { setError(await jiraError(error, 'آزمون اتصال انجام نشد. شبکه و تنظیمات اتصال را بررسی کنید.')) }
    finally { setBusy(false) }
  }
  const remove = async () => {
    if (busy || !removing) return
    setBusy(true); setError('')
    try { await jiraApi.remove(removing); await list.refetch(); setRemoving(null); setMessage('اتصال حذف شد؛ درخواست‌های قبلاً واردشده حفظ شدند.') }
    catch (error) { setError(await jiraError(error, 'حذف اتصال انجام نشد. فهرست را تازه کنید.')) }
    finally { setBusy(false) }
  }
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto max-w-4xl space-y-6">
    <Link href={`/projects/${projectId}`} className="text-sm text-text-accent">نمای کلی پروژه ←</Link>
    <header className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-3xl font-bold">اتصال به جیرا</h1><p className="mt-3 text-sm leading-7 text-text-secondary">اتصال‌های شخصی حساب شما؛ فراخوانی با توکن خودتان و در محدودهٔ دسترسی شما در جیرا انجام می‌شود. اتصال کاربران دیگر در این فهرست نمایش داده نمی‌شود.</p></div><Button variant="primary" disabled={busy} onClick={() => { setError(''); setEditing('new') }}>ایجاد اتصال</Button></header>
    {message && <p role="status" className="text-sm leading-7">{message}</p>}{error && !removing && <p role="alert" className="text-sm text-text-destructive-secondary">{error}</p>}
    {list.isPending ? <p role="status">در حال دریافت اتصال‌ها…</p> : list.isError ? <p role="alert">دریافت اتصال‌ها انجام نشد. <button onClick={() => list.refetch()}>تلاش دوباره</button></p> : !list.data.data.length ? <p>هنوز اتصالی ذخیره نکرده‌اید. برای شروع، «ایجاد اتصال» را بزنید.</p> : list.data.data.map(value => <article key={value.id} className="space-y-3 rounded-xl border border-divider-regular bg-background-default p-5"><h2 className="text-lg font-semibold">{value.name}</h2><p dir="ltr" className="break-all text-sm">{value.base_url}</p><p className="text-xs text-text-tertiary">توکن ذخیره شده است؛ مقدار آن قابل نمایش نیست.</p><div className="flex flex-wrap gap-2"><Button variant="secondary" disabled={busy} onClick={() => setEditing(value)}>ویرایش</Button><Button variant="secondary" disabled={busy} onClick={() => void test(value)}>آزمون اتصال</Button><Button variant="secondary" disabled={busy} onClick={() => { setError(''); setRemoving(value) }}>حذف اتصال</Button></div></article>)}
    <p className="text-sm leading-7 text-text-tertiary">آزمون اتصال فقط احراز هویت را بررسی می‌کند. مجوز دسترسی به درخواست‌ها هنگام جست‌وجو بررسی می‌شود. سرور کارا باید به شبکهٔ جیرا دسترسی داشته باشد.</p>
    {editing && <ConnectionEditor value={editing === 'new' ? null : editing} saved={list.refetch} close={() => setEditing(null)} />}
    {removing && <FormDialog open title="حذف اتصال به جیرا" description={`اتصال «${removing.name}» و توکن ذخیره‌شدهٔ آن حذف می‌شوند. درخواست‌های واردشده و تاریخچهٔ آن‌ها حفظ می‌شوند.`} busy={busy} error={error} close={() => setRemoving(null)}><div className="flex justify-end gap-2"><Button variant="secondary" disabled={busy} onClick={() => setRemoving(null)}>انصراف</Button><Button variant="primary" disabled={busy} onClick={() => void remove()}>حذف اتصال</Button></div></FormDialog>}
  </div></main>
}

export default function JiraConnections({ projectId }: { projectId: string }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  return <Connections key={profile.id} projectId={projectId} accountId={profile.id} />
}
