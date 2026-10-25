'use client'

import type { TeamControls } from '@/service/company-stages'
import { useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { stageApi } from '@/service/company-stages'
import { stageStates } from '@/utils/company-team-work'
import { button, input, QueryNotice } from './project-page'
import FormDialog, { FieldHelp } from './form-dialog'

const labels: Record<string, string> = { reassign: 'تغییر مسئول', recover: 'بازیابی اجرای معلق یا سقف تلاش', reopen: 'بازگشایی مرحلهٔ نهایی‌شده', revalidate: 'بررسی مجدد ورودی', cancelled: 'لغو فرایند', request_invalidated: 'نامعتبرشدن نسخه یا تصمیم ورود' }

function Change({ value, perform }: { value: TeamControls; perform: (action: string, stage: string | null, data: Record<string, unknown>, key: string) => Promise<void> }) {
  const [stageId, setStageId] = useState(value.current_stage_id || value.stages[0]?.id || '')
  const stage = value.stages.find(item => item.id === stageId)!
  const allowed = value.controls[stageId] || []
  const [operation, setOperation] = useState('')
  const action = allowed.includes(operation) ? operation : allowed[0] || ''
  const [executor, setExecutor] = useState(stage.executor.account_id)
  const [finalizer, setFinalizer] = useState(stage.finalizer.account_id)
  const [reason, setReason] = useState('')
  const [ack, setAck] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const key = useRef<{ payload: string; id: string } | null>(null)
  const submit = async (cancel = false) => {
    if (busy) return
    const data: Record<string, unknown> = { expected_revision: cancel ? value.revision : stage.revision, reason }
    if (!cancel && action === 'reassign') {
      const run = value.members.find(item => item.account_id === executor), finish = value.members.find(item => item.account_id === finalizer)
      if (!run || !finish) return
      Object.assign(data, { executor_id: run.account_id, executor_membership_id: run.membership_id, finalizer_id: finish.account_id, finalizer_membership_id: finish.membership_id })
    }
    if (!cancel && action === 'recover') data.acknowledge_effects = ack
    const payload = JSON.stringify([cancel, stageId, action, data])
    if (key.current?.payload !== payload) key.current = { payload, id: crypto.randomUUID() }
    setBusy(true); setError('')
    try { await perform(cancel ? 'cancel' : action, cancel ? null : stageId, data, key.current.id); key.current = null }
    catch { setError('اقدام ثبت نشد. وضعیت را تازه کنید؛ نسخه، مهلت بازیابی، نقش و مجوز مسئول‌های منتخب باید معتبر باشند.') }
    finally { setBusy(false) }
  }
  return <form className="space-y-4" onSubmit={event => { event.preventDefault(); void submit() }}><fieldset disabled={busy} className="space-y-4">
    <p className="text-sm leading-7">مهلت بررسی اجرای معلق: {value.recovery_after_seconds.toLocaleString('fa-IR')} ثانیه · سقف تلاش مجدد فنی هر دور: {value.retry_limit.toLocaleString('fa-IR')}</p>
    <label className="block text-sm">مرحلهٔ مورد بررسی<select className={input} value={stageId} onChange={event => { const next = value.stages.find(item => item.id === event.target.value)!; setStageId(next.id); setOperation(''); setExecutor(next.executor.account_id); setFinalizer(next.finalizer.account_id) }}>{value.stages.map(item => <option key={item.id} value={item.id}>{item.title} · {stageStates[item.state]}</option>)}</select><FieldHelp>مرحله‌ای را انتخاب کنید که وضعیت یا مسئول آن نیاز به بررسی دارد؛ اقدام انتخاب‌شده فقط روی همان مرحله اعمال می‌شود.</FieldHelp></label>
    {allowed.length ? <><label className="block text-sm">اقدام مجاز<select className={input} value={action} onChange={event => setOperation(event.target.value)}>{allowed.map(item => <option key={item} value={item}>{labels[item]}</option>)}</select><FieldHelp>گزینه‌ها مطابق مجوز شما و وضعیت همین مرحله‌اند. توضیح اثر اقدام انتخاب‌شده را پیش از ثبت بخوانید.</FieldHelp></label>{action === 'reassign' && <><p className="text-sm leading-7">مسئول منتخب باید عضو فعال با مجوز اجرای یا نهایی‌سازی همین ایجنت باشد. تغییر مسئول، خروجی فعلی را برای بررسی مجدد کنار می‌گذارد و سابقه حفظ می‌شود.</p>{([['اجراکنندهٔ جدید', executor, setExecutor], ['نهایی‌کنندهٔ جدید', finalizer, setFinalizer]] as const).map(([title, selected, change]) => <label className="block text-sm" key={title}>{title}<select required className={input} value={selected} onChange={event => change(event.target.value)}>{value.members.map(person => <option key={person.account_id} value={person.account_id}>{person.name}</option>)}</select><FieldHelp>عضو فعال دارای مجوز متناسب با اجرای یا نهایی‌سازی همین ایجنت را انتخاب کنید.</FieldHelp></label>)}</>}{action === 'recover' && <><p className="text-sm leading-7">بازیابی، تلاش قبلی را از تغییر مرحله منع می‌کند و مرحله را برای بررسی خطا برمی‌گرداند. اجرای دوباره خودکار نیست. توقف محاسبهٔ قبلی و برگشت آثار بیرونی آن تضمین نمی‌شود.</p><label className="flex items-start gap-3 text-sm leading-7"><input type="checkbox" required checked={ack} onChange={event => setAck(event.target.checked)} className="mt-2" />آثار احتمالی اجرای قبلی را بررسی کرده‌ام و مسئولیت تصمیم دربارهٔ تلاش بعدی را می‌پذیرم.</label></>}{action === 'reopen' && <p className="text-sm leading-7">مرحله و مصرف‌کنندگان بعدی نیازمند بررسی مجدد می‌شوند؛ خروجی و تصمیم‌های پیشین در تاریخچه می‌مانند. تغییر خود نیازمندی باید از پرونده و تصمیم تازهٔ مالک محصول انجام شود.</p>}</> : <p className="text-sm leading-7">برای این مرحله اکنون اقدام مدیریتی یا بازگشایی مجازی ندارید. بازیابی اجرای معلق پس از مهلت مشخص و تازه‌سازی در دسترس مدیر قرار می‌گیرد.</p>}
    {(action || value.can_cancel) && <label className="block text-sm">علت اقدام<textarea className={input} required maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /><FieldHelp>دلیل تصمیم را برای پیگیری اعضای تیم بنویسید؛ این علت همراه نام اقدام در تاریخچه ثبت می‌شود.</FieldHelp></label>}
    <div className="flex flex-wrap gap-3">{action && <button className={button}>ثبت اقدام مرحله</button>}{value.can_cancel && <button type="button" className={button} disabled={!reason.trim()} onClick={() => submit(true)}>لغو این اجرای تیمی با علت ثبت‌شده</button>}</div>
    {value.can_cancel && <p className="text-sm leading-7">لغو، ادامهٔ این اجرا را می‌بندد و سابقه را نگه می‌دارد. اجرای محاسبهٔ در جریان ممکن است با تأخیر متوقف شود؛ آثار بیرونی قبلی برگردانده نمی‌شوند.</p>}
  </fieldset>{error && <p role="alert" className="text-sm">{error}</p>}</form>
}

export default function TeamRecovery({ projectId, instanceId, changed, close }: { projectId: string; instanceId: string; changed: () => Promise<unknown>; close: () => void }) {
  const [busy, setBusy] = useState(false)
  const query = useQuery({ queryKey: ['team-controls', projectId, instanceId], queryFn: () => stageApi.controls(projectId, instanceId), staleTime: 0 })
  const perform = async (action: string, stage: string | null, data: Record<string, unknown>, key: string) => {
    setBusy(true)
    try { await stageApi.control(projectId, instanceId, stage, action, data, key); await changed(); const result = await query.refetch(); if (result.isError) throw new Error('Refresh failed') }
    finally { setBusy(false) }
  }
  return <FormDialog open wide title="بازبینی و بازیابی فرایند" description="وضعیت همین اجرا و تاریخچهٔ آن را بررسی کنید. اقدامات قابل انجام بر اساس مجوز شما و وضعیت مرحله نمایش داده می‌شوند؛ پیش از ثبت، اثر اقدام و علت آن را مرور کنید." busy={busy} close={close}>
    <fieldset disabled={busy}>
      <section className="space-y-4 text-text-primary" aria-label="بازبینی و بازیابی فرایند">{!query.isSuccess ? <QueryNotice error={query.isError} retry={() => query.refetch()} /> : <><h3 className="font-semibold">{query.data.title}</h3>{query.data.cancellation ? <p role="status">فرایند لغو شده است: {query.data.cancellation.reason}</p> : <Change key={query.data.revision} value={query.data} perform={perform} />}<details className="space-y-3"><summary className="cursor-pointer">تاریخچهٔ تغییر مسئول، بازگشایی و لغو</summary>{!query.data.history.length && <p className="text-sm">هنوز اقدام بازیابی ثبت نشده است.</p>}{query.data.history.map((entry, index) => <article className="space-y-2 border-t border-divider-regular pt-3 text-sm" key={index}><p>{labels[entry.kind.replace('recovery.', '')]} · {new Date(entry.at).toLocaleString('fa-IR')}</p><p>{entry.change.reason}</p>{entry.change.after && <p>مسئول‌های جدید: {entry.change.after.executor.name} · {entry.change.after.finalizer.name}</p>}<p className="break-all text-xs">ثبت‌کننده: <bdi>{entry.actor_id}</bdi></p></article>)}</details></>}<button className={button} disabled={query.isFetching} onClick={() => query.refetch()}>تازه‌سازی وضعیت بازیابی</button></section>
    </fieldset>
    <div className="mt-4 flex justify-end"><button type="button" className={button} disabled={busy} onClick={close}>بستن</button></div>
  </FormDialog>
}
