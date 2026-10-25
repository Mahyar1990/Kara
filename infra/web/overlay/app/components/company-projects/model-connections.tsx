'use client'

import type { PersonalModel, PersonalProvider } from '@/service/company-models'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useAtomValue } from 'jotai'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { FormTypeEnum } from '@/app/components/header/account-setting/model-provider-page/declarations'
import CredentialForm from '@/app/components/header/account-setting/model-provider-page/model-modal/Form'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import { jiraError } from '@/service/company-jira'
import { modelConnectionApi } from '@/service/company-models'
import FormDialog, { FieldHelp } from './form-dialog'

const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const kinds: Record<string, string> = { llm: 'مدل متنی (LLM)', 'text-embedding': 'بردارسازی متن', rerank: 'بازمرتب‌سازی', speech2text: 'گفتار به متن', tts: 'متن به گفتار', moderation: 'پالایش محتوا' }
const providerLabel = (provider: PersonalProvider) => provider.label.fa_IR || provider.label.en_US || provider.provider
const defaults = (provider?: PersonalProvider) => Object.fromEntries((provider?.fields || []).map(item => [item.variable, item.secret ? '' : item.default ?? '']))
const labels: Record<string, string> = { api_key: 'توکن شخصی مدل', endpoint_url: 'آدرس پایهٔ سرویس مدل', api_base: 'آدرس پایهٔ سرویس مدل', endpoint_model_name: 'نام مدل در سرویس', mode: 'حالت مدل' }

function ModelForm({ value, copy = false, providers, close, saved }: { value: PersonalModel | null; copy?: boolean; providers: PersonalProvider[]; close: () => void; saved: () => Promise<unknown> }) {
  const [name, setName] = useState(copy && value ? `${value.name.slice(0, 110)} (کپی)` : value?.name || '')
  const [provider, setProvider] = useState(value?.provider || '')
  const [model, setModel] = useState(value?.model_name || '')
  const [kind, setKind] = useState(value?.model_type || 'llm')
  const selected = providers.find(item => item.provider === provider)
  const [credentials, setCredentials] = useState<Record<string, unknown>>({ ...defaults(selected), ...value?.values })
  const [isDefault, setIsDefault] = useState(!copy && (value?.is_default || false))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async () => {
    if (busy || !selected) return
    setBusy(true); setError('')
    try {
      const body = { name, provider, model_name: model, model_type: kind, credentials, is_default: isDefault, expected_revision: value?.revision || 1 }
      if (copy && value) await modelConnectionApi.copy(value.id, body)
      else await modelConnectionApi.save(value?.id || null, body)
      setCredentials({}); await saved(); close()
    } catch (error) { setError(await jiraError(error, 'ذخیرهٔ اتصال مدل انجام نشد؛ اطلاعات و نسخهٔ اتصال را بررسی کنید.')) }
    finally { setBusy(false) }
  }
  return <FormDialog open wide title={copy ? 'کپی اتصال شخصی مدل' : value ? 'ویرایش اتصال شخصی مدل' : 'ایجاد اتصال شخصی مدل'} description="آدرس، مدل و اعتبارنامهٔ متعلق به حساب خودتان را وارد کنید. این اتصال در پروژه‌هایی که افزونهٔ ارائه‌دهنده نصب است قابل استفاده خواهد بود. ذخیره‌کردن، فراخوانی مدل ایجاد نمی‌کند." busy={busy} error={error} close={close}>
    <form className="space-y-4" onSubmit={event => { event.preventDefault(); void submit() }}>
      <fieldset disabled={busy} className="space-y-4">
        {copy && <p className="text-sm leading-7">تنظیمات از اتصال خودتان کپی می‌شوند. نام اتصال و نام مدل جدید را وارد کنید. با ثابت‌ماندن ارائه‌دهنده و تنظیمات سرویس، توکن هم در سمت سرور کپی می‌شود؛ با تغییر مقصد، توکن را دوباره وارد کنید.</p>}
        <label className="block text-sm">نام اتصال<input required maxLength={120} className={field} value={name} onChange={event => setName(event.target.value)} /><FieldHelp>نامی برای شناسایی این اتصال در فهرست شخصی خود انتخاب کنید.</FieldHelp></label>
        <label className="block text-sm">ارائه‌دهنده<select required className={field} value={provider} onChange={event => { const next = providers.find(item => item.provider === event.target.value); setProvider(event.target.value); setCredentials(defaults(next)); if (next && !next.model_types.includes(kind)) setKind(next.model_types[0]) }}><option value="">انتخاب کنید</option>{providers.map(item => <option key={item.provider} value={item.provider}>{providerLabel(item)}</option>)}</select><FieldHelp>فقط ارائه‌دهنده‌هایی که افزونهٔ آن‌ها در پروژه نصب است نمایش داده می‌شوند.</FieldHelp></label>
        <label className="block text-sm">نوع مدل<select required className={field} value={kind} onChange={event => setKind(event.target.value)}>{(selected?.model_types || ['llm']).map(value => <option key={value} value={value}>{kinds[value] || value}</option>)}</select><FieldHelp>برای ایجنت‌ها و تولید پاسخ، مدل متنی (LLM) را انتخاب کنید.</FieldHelp></label>
        <label className="block text-sm">نام مدل<input required maxLength={255} className={field} dir="ltr" value={model} onChange={event => setModel(event.target.value)} /><FieldHelp>نامی را وارد کنید که در انتخاب مدل برنامه استفاده می‌کنید. برای اجرای برنامهٔ موجود، ارائه‌دهنده و نام مدل باید با مدل تعیین‌شده در آن برنامه سازگار باشد.</FieldHelp></label>
        {selected && <CredentialForm value={{ ...credentials, __model_type: kind, __model_name: model }} onChange={next => setCredentials(Object.fromEntries(Object.entries(next).filter(([key]) => selected.fields.some(item => item.variable === key))))} formSchemas={selected.fields.map(item => ({ ...item, type: item.secret ? FormTypeEnum.secretInput : item.type, required: item.required && !(value && item.secret), ...(labels[item.variable] ? { label: { ...item.label, en_US: labels[item.variable], fa_IR: labels[item.variable] } } : {}) }))} validating={busy} showOnVariableMap={{}} isEditMode={!!value} fieldMoreInfo={item => <FieldHelp>{selected.fields.find(field => field.variable === item.variable)?.secret ? (copy ? 'کادر خالی، توکن همین اتصال شخصی را در سمت سرور کپی می‌کند. با تغییر ارائه‌دهنده یا تنظیمات سرویس، توکن را دوباره وارد کنید.' : 'فقط اعتبارنامهٔ خودتان را وارد کنید. برای حفظ مقدار قبلی در ویرایش، کادر را خالی بگذارید؛ با تغییر آدرس یا مدل، آن را دوباره وارد کنید.') : 'این مقدار باید با سرویس و مدلی که در حساب خودتان مجاز به استفاده از آن هستید مطابقت داشته باشد.'}</FieldHelp>} />}
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={isDefault} onChange={event => setIsDefault(event.target.checked)} /><span>مدل پیش‌فرض شخصی من برای این نوع<FieldHelp>فقط پیش‌فرض حساب شما تغییر می‌کند. مدل تعیین‌شده در برنامه‌ها و نسخه‌های منتشرشده جابه‌جا نمی‌شود.</FieldHelp></span></label>
      </fieldset>
      <p className="text-xs leading-6 text-text-tertiary">اعتبارنامه رمزگذاری‌شده ذخیره می‌شود و دوباره نمایش داده نمی‌شود. پس از ذخیره، در صورت نیاز «آزمون اتصال» را بزنید.</p>
      <div className="flex justify-end gap-2"><Button type="button" variant="secondary" disabled={busy} onClick={close}>انصراف</Button><Button type="submit" variant="primary" disabled={busy || !selected}>{busy ? 'در حال ذخیره…' : copy ? 'ایجاد کپی' : 'ذخیرهٔ اتصال'}</Button></div>
    </form>
  </FormDialog>
}

function EditModel({ value, copy, providers, close, saved }: { value: PersonalModel | null; copy: boolean; providers: PersonalProvider[]; close: () => void; saved: () => Promise<unknown> }) {
  const detail = useQuery({ queryKey: ['personal-model-detail', value?.id, value?.revision], queryFn: () => modelConnectionApi.detail(value!.id), enabled: !!value })
  if (!value) return <ModelForm value={null} providers={providers} close={close} saved={saved} />
  if (detail.isSuccess) return <ModelForm key={`${detail.data.id}:${detail.data.revision}`} value={detail.data} copy={copy} providers={providers} close={close} saved={saved} />
  return <FormDialog open title={copy ? 'کپی اتصال شخصی مدل' : 'ویرایش اتصال شخصی مدل'} description="اطلاعات غیرمحرمانهٔ اتصال دریافت می‌شود؛ مقدار توکن بازگردانده نمی‌شود." close={close}><p role={detail.isError ? 'alert' : 'status'}>{detail.isError ? 'دریافت اطلاعات اتصال انجام نشد. نصب افزونه و دسترسی خود را بررسی کنید.' : 'در حال دریافت اطلاعات اتصال…'}</p></FormDialog>
}

function Connections({ accountId }: { accountId: string }) {
  const workspaceId = useAtomValue(currentWorkspaceIdAtom)
  const list = useQuery({ queryKey: ['personal-model-connections', accountId], queryFn: modelConnectionApi.list })
  const providers = useQuery({ queryKey: ['personal-model-providers', accountId, workspaceId], queryFn: modelConnectionApi.providers })
  const [editing, setEditing] = useState<{ value: PersonalModel | null; copy: boolean } | null>(null)
  const [removing, setRemoving] = useState<PersonalModel | null>(null)
  const [testing, setTesting] = useState<PersonalModel | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { revision: number; status: 'pending' | 'success' | 'error'; message: string }>>({})
  const testResult = testing && testResults[testing.id]?.revision === testing.revision ? testResults[testing.id] : undefined
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const test = async () => {
    if (busy || !testing) return
    const target = testing
    const result = (status: 'pending' | 'success' | 'error', message: string) => setTestResults(previous => ({ ...previous, [target.id]: { revision: target.revision, status, message } }))
    setBusy(true); setError('')
    result('pending', 'در حال بررسی اتصال…')
    try { result('success', (await modelConnectionApi.test(target.id)).message) }
    catch (error) { result('error', await jiraError(error, 'آزمون اتصال مدل ناموفق بود؛ نشانی، توکن و دسترسی شبکه را بررسی کنید.')) }
    finally { setBusy(false) }
  }
  const remove = async () => {
    if (busy || !removing) return
    setBusy(true); setError('')
    try { await modelConnectionApi.remove(removing); await list.refetch(); setRemoving(null); setMessage('اتصال شخصی حذف شد. برنامه‌ها و سوابق قبلی حفظ شدند.') }
    catch (error) { setError(await jiraError(error, 'حذف اتصال انجام نشد؛ فهرست را تازه کنید.')) }
    finally { setBusy(false) }
  }
  return <section dir="rtl" className="mx-auto max-w-4xl space-y-5 p-5 text-text-primary md:p-8"><header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-bold">اتصال به مدل هوش مصنوعی</h1><p className="mt-3 text-sm leading-7 text-text-secondary">مدل‌ها و اعتبارنامه‌های شخصی حساب شما؛ برنامه‌ها و ایجنت‌ها هنگام اجرا فقط از اتصال خودِ اجراکننده استفاده می‌کنند.</p></div><Button variant="primary" disabled={busy || !providers.isSuccess} onClick={() => { setError(''); setEditing({ value: null, copy: false }) }}>ایجاد اتصال</Button></header>
    {error && !removing && !testing && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {providers.isError && <p role="alert">فهرست افزونه‌های مدل دریافت نشد. <button onClick={() => providers.refetch()}>تلاش دوباره</button></p>}
    {providers.isSuccess && !providers.data.data.length && <p>ابتدا مدیر پروژه باید افزونهٔ ارائه‌دهندهٔ مدل را نصب کند؛ سپس هر کاربر اتصال شخصی خودش را می‌سازد.</p>}
    {list.isPending ? <p role="status">در حال دریافت اتصال‌ها…</p> : list.isError ? <p role="alert">دریافت اتصال‌ها انجام نشد. <button onClick={() => list.refetch()}>تلاش دوباره</button></p> : !list.data.data.length ? <p>اتصال شخصی ندارید. آدرس، مدل و توکن خودتان را با «ایجاد اتصال» ثبت کنید. اتصال مشترک قبلی پروژه برای اجرای شما استفاده نمی‌شود.</p> : list.data.data.map(value => <article key={value.id} className="space-y-3 rounded-xl border border-divider-regular bg-background-default p-5"><h2 className="text-lg font-semibold">{value.name}{value.is_default && ' · پیش‌فرض شخصی'}</h2><p className="text-sm" dir="ltr">{value.provider} · {value.model_name}</p><p className="text-xs text-text-tertiary">{kinds[value.model_type] || value.model_type} · اعتبارنامه ذخیره شده است.</p><div className="flex flex-wrap gap-2"><Button variant="secondary" disabled={busy || !providers.isSuccess} onClick={() => { setError(''); setEditing({ value, copy: false }) }}>ویرایش</Button><Button variant="secondary" disabled={busy || !providers.isSuccess} onClick={() => { setError(''); setEditing({ value, copy: true }) }}>کپی کانفیگ</Button><Button variant="secondary" disabled={busy} onClick={() => { setError(''); setTesting(value) }}>آزمون اتصال</Button><Button variant="secondary" disabled={busy} onClick={() => { setError(''); setRemoving(value) }}>حذف اتصال</Button></div>{testResults[value.id]?.revision === value.revision && <p role={testResults[value.id].status === 'error' ? 'alert' : 'status'} className={`rounded-lg border border-divider-regular p-3 text-sm leading-7 ${testResults[value.id].status === 'error' ? 'text-text-destructive-secondary' : 'text-text-secondary'}`}>{testResults[value.id].message}</p>}</article>)}
    {editing && providers.isSuccess && <EditModel value={editing.value} copy={editing.copy} providers={providers.data.data} close={() => setEditing(null)} saved={list.refetch} />}
    {testing && <FormDialog open title="آزمون اتصال شخصی مدل" description={`اتصال «${testing.name}» با اعتبارنامهٔ خودتان بررسی می‌شود. این آزمون ممکن است یک فراخوانی کوتاه و مشمول هزینه به سرویس مدل ایجاد کند.`} busy={busy} close={() => setTesting(null)}>{testResult && <p role={testResult.status === 'error' ? 'alert' : 'status'} className={`mb-4 rounded-lg border border-divider-regular p-3 text-sm leading-7 ${testResult.status === 'error' ? 'text-text-destructive-secondary' : 'text-text-secondary'}`}>{testResult.message}</p>}<div className="flex justify-end gap-2"><Button variant="secondary" disabled={busy} onClick={() => setTesting(null)}>{testResult ? 'بستن' : 'انصراف'}</Button><Button variant="primary" disabled={busy} onClick={() => void test()}>{busy ? 'در حال بررسی…' : testResult ? 'آزمون دوباره' : 'آزمون اتصال'}</Button></div></FormDialog>}
    {removing && <FormDialog open title="حذف اتصال شخصی مدل" description={`اتصال «${removing.name}» و اعتبارنامهٔ ذخیره‌شده حذف می‌شوند. اجراهای بعدی به اتصال شخصی دیگری برای همان مدل نیاز خواهند داشت. برنامه‌ها و سوابق حذف نمی‌شوند.`} busy={busy} error={error} close={() => setRemoving(null)}><div className="flex justify-end gap-2"><Button variant="secondary" disabled={busy} onClick={() => setRemoving(null)}>انصراف</Button><Button variant="primary" disabled={busy} onClick={() => void remove()}>حذف اتصال</Button></div></FormDialog>}
  </section>
}

export default function PersonalModelConnections() {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  const workspaceId = useAtomValue(currentWorkspaceIdAtom)
  return <Connections key={`${profile.id}:${workspaceId}`} accountId={profile.id} />
}
