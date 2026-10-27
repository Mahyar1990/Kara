'use client'

import { useQuery, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect, useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import RosterPage from '@/features/agent-v2/roster/page'
import Link from '@/next/link'
import { useSearchParams } from '@/next/navigation'
import { agencyApi } from '@/service/company-agency'
import type { AgencyCatalog, AgencyCopy, AgencyTemplate } from '@/service/company-agency'
import { projectApi } from '@/service/company-projects'
import FormDialog, { FieldHelp } from './form-dialog'
import { DirectoryEmpty, DirectoryNotice, DirectoryPagination, DirectorySummary, DirectoryToolbar, directoryButton, directoryField, directoryPanel, matchesSearch, number, resultPage } from './team-directory'

function Templates({ project, copiedOnly = false }: { project: string; copiedOnly?: boolean }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  const cache = useQueryClient()
  const key = ['agency-catalog', profile.id, workspace, project]
  const catalog = useQuery({ queryKey: key, queryFn: () => agencyApi.list(project) })
  const value = catalog.data
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [kind, setKind] = useState('all')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<AgencyTemplate | null>(null)
  const [created, setCreated] = useState<AgencyCopy | null>(null)
  const templates = (value?.data || []).filter(item => !copiedOnly || item.copy)
  const categories = [...new Map(templates.map(item => [item.category, { label: item.category_label, original: item.category_original_label }])).entries()]
  const filtered = templates.filter(item => matchesSearch(query, item.name, item.original_name, item.description, item.category_label, item.category_original_label, item.category, item.copy?.name || '')
    && (category === 'all' || item.category === category) && (kind === 'all' || (kind === 'recommended' ? item.recommended : !!item.copy)))
    .sort((a, b) => Number(b.recommended) - Number(a.recommended) || a.name.localeCompare(b.name, 'fa'))
  const result = resultPage(filtered, page)
  const reset = () => { setQuery(''); setCategory('all'); setKind('all'); setPage(1) }
  return <section className="min-h-0 grow overflow-y-auto p-5 text-text-primary md:p-8"><div className="mx-auto max-w-6xl space-y-6" dir="rtl">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-bold">{copiedOnly ? 'Agencyهای پروژه' : 'قالب‌های پیش‌فرض Agency Agents'}</h1><p className="mt-3 max-w-3xl text-sm leading-7 text-text-secondary">{copiedOnly ? 'نسخه‌های افزوده‌شده به این پروژه را با دسته‌بندی اصلی پیدا کنید. نام و تنظیمات هر نسخه مستقل است؛ برای ویرایش، نسخهٔ پروژه را باز کنید.' : 'تخصص مورد نیاز را انتخاب و متن را بررسی کنید. افزودن به پروژه یک ایجنت و مهارت مستقل می‌سازد؛ مدل، دانش و مجوزهای پروژه را جدا تعیین می‌کنید. هیچ اجرا یا تغییر در فلوهای قبلی شروع نمی‌شود.'}</p></div><button className={directoryButton} disabled={catalog.isFetching} onClick={() => void catalog.refetch()}>تازه‌سازی</button></header>
    <DirectoryNotice loading={catalog.isPending} error={catalog.isError} entered project={project} retry={() => catalog.refetch()} />
    {value && <>
      <DirectorySummary items={copiedOnly ? [{ label: 'ایجنت‌های Agency پروژه', count: templates.length }, { label: 'دسته‌های استفاده‌شده', count: categories.length }] : [{ label: 'کل قالب‌ها', count: templates.length }, { label: 'پیشنهاد شروع برای تیم محصول و توسعه', count: templates.filter(t => t.recommended).length }, { label: 'دسته‌های تخصصی', count: categories.length }, { label: 'قالب‌های دارای نسخه در پروژه', count: templates.filter(t => t.copy).length }]} />
      {created && <section className={`${directoryPanel} space-y-3`} role="status"><p>ایجنت «{created.name}» {created.created ? 'به پروژه اضافه شد و مهارت مستقل آن آماده است.' : 'قبلاً به پروژه اضافه شده است؛ نسخهٔ دیگری ساخته نشد.'}</p><div className="flex flex-wrap gap-3"><Link className={directoryButton} href={`/agents/${created.agent_id}/configure`}>تنظیم ایجنت پروژه</Link><Link className={directoryButton} href={`/projects/${project}/team-agents`}>تعیین ایجنت تیمی و مجوزها</Link></div><p className="text-xs leading-6 text-text-tertiary">برای استفاده در فلو، در «ایجنت‌های تیم ← ایجاد ایجنت» منبع کتابخانه را انتخاب کنید؛ سپس اجراکننده، نهایی‌کننده و نگاشت ورودی و خروجی مرحله را مشخص کنید.</p></section>}
      <DirectoryToolbar query={query} change={value => { setQuery(value); setPage(1) }} placeholder="نام فارسی یا انگلیسی، تخصص یا کاربرد" filtered={filtered.length} total={templates.length} hasFilters={!!query || category !== 'all' || kind !== 'all'} reset={reset}>
        <label className="min-w-0 flex-1 basis-48 text-sm">دستهٔ اصلی Agency<select className={directoryField} value={category} onChange={e => { setCategory(e.target.value); setPage(1) }}><option value="all">همهٔ دسته‌ها · {number(templates.length)}</option>{categories.map(([id, label]) => <option key={id} value={id}>{label.label} · {label.original} ({number(templates.filter(item => item.category === id).length)})</option>)}</select></label>
        <label className="min-w-0 flex-1 basis-44 text-sm">نمایش<select className={directoryField} value={kind} onChange={e => { setKind(e.target.value); setPage(1) }}><option value="all">{copiedOnly ? 'همهٔ نسخه‌های پروژه' : 'همهٔ قالب‌ها'}</option><option value="recommended">پیشنهاد شروع تیم</option>{!copiedOnly && <option value="copied">دارای نسخه در پروژه</option>}</select></label>
      </DirectoryToolbar>
      {!result.items.length && <DirectoryEmpty filtered={!!query || category !== 'all' || kind !== 'all'} title={copiedOnly ? 'نسخه‌ای از Agency در این پروژه نیست' : 'قالبی در دسترس نیست'} reset={reset}>{copiedOnly ? 'در «قالب‌های پیش‌فرض Agency» قالب مورد نیاز را بررسی و به پروژه اضافه کنید.' : 'فهرست را تازه کنید.'}</DirectoryEmpty>}
      <ul className="m-0 grid list-none gap-4 p-0 md:grid-cols-2" aria-label="قالب‌های پیش‌فرض ایجنت">{result.items.map(item => {
        const current = item.copy?.source_commit === value.commit && item.copy?.policy_digest === value.policy_digest
        return <li key={item.id} className="min-w-0"><article className={`${directoryPanel} flex h-full min-w-0 flex-col gap-3 [overflow-wrap:anywhere]`}>
          <div className="flex flex-wrap items-center gap-2 text-xs"><button className="rounded-full bg-background-section px-3 py-1 text-text-accent ring-1 ring-divider-regular" aria-pressed={category === item.category} title="فیلتر این دسته" onClick={() => { setCategory(item.category); setPage(1) }}>{item.category_label} · <bdi>{item.category_original_label}</bdi></button>{item.recommended && <span className="text-text-tertiary">پیشنهاد شروع تیم</span>}</div><h2 className="text-lg font-semibold"><bdi>{copiedOnly ? item.copy?.name : item.name}</bdi></h2><p className="text-xs text-text-tertiary" dir="ltr">{item.original_name}</p><p className="line-clamp-3 text-sm leading-7 text-text-secondary" dir="auto">{item.description}</p>
          <footer className="mt-auto flex flex-wrap items-center gap-3 border-t border-divider-regular pt-4"><button className={directoryButton} onClick={() => setSelected(item)}>بررسی قالب{!current && value.can_adopt ? ' و افزودن' : ''}</button>{item.copy && <Link className="text-sm text-text-accent" href={`/agents/${item.copy.agent_id}/configure`}>{current ? 'نسخهٔ پروژه ←' : 'نسخهٔ قبلی پروژه ←'}</Link>}</footer>
        </article></li>
      })}</ul>
      <DirectoryPagination value={result} change={setPage} />
      <footer className="space-y-2 border-t border-divider-regular pt-5 text-xs leading-6 text-text-tertiary"><p>منبع: Agency Agents · مجوز MIT. متن اصلی، انتساب و مجوز در پنجرهٔ بررسی هر قالب در دسترس است. دسته‌بندی اصلی همراه نسخهٔ پروژه و مهارت آن حفظ می‌شود.</p><p>قالب، ابزار نصب نمی‌کند و دسترسی تازه‌ای نمی‌دهد. تغییر واقعی کد به هارنس مجاز روی Runner و سورس همان پروژه نیاز دارد. تأیید نهایی با انسان مسئول است.</p></footer>
      {selected && <AdoptDialog key={`${selected.id}:${value.commit}`} project={project} item={selected} catalog={value} close={() => setSelected(null)} saved={async value => { setCreated(value); setSelected(null); await cache.invalidateQueries({ queryKey: key }); await cache.invalidateQueries({ predicate: q => JSON.stringify(q.queryKey).includes('"agent"') }) }} />}
    </>}
  </div></section>
}

function AdoptDialog({ project, item, catalog, close, saved }: { project: string; item: AgencyTemplate; catalog: AgencyCatalog; close: () => void; saved: (value: AgencyCopy) => Promise<void> }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const preview = useQuery({ queryKey: ['agency-preview', workspace, project, item.id, catalog.commit, catalog.policy_digest], queryFn: () => agencyApi.preview(project, item.id) })
  const current = item.copy?.source_commit === catalog.commit && item.copy?.policy_digest === catalog.policy_digest
  const [name, setName] = useState(item.name + (item.copy && !current ? ' - نسخهٔ تازه' : ''))
  const [modelId, setModelId] = useState(catalog.models.find(m => m.is_default)?.id || catalog.models[0]?.id || '')
  const [dataset, setDataset] = useState('')
  const [source, setSource] = useState(false)
  const [reviewed, setReviewed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const operation = useRef<{ payload: string; key: string } | null>(null)
  useEffect(() => { setReviewed(false) }, [preview.data?.definition_digest, modelId, dataset])
  const model = catalog.models.find(m => m.id === modelId)
  const submit = async () => {
    if (busy || !reviewed || !model || !preview.data || !catalog.can_adopt || current) return
    const body = { name: name.trim(), model_connection_id: model.id, model_revision: model.revision, dataset_id: dataset || null, definition_digest: preview.data.definition_digest }
    const serialized = JSON.stringify(body)
    if (operation.current?.payload !== serialized) operation.current = { payload: serialized, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try { const result = await agencyApi.copy(project, item.id, body, operation.current.key); operation.current = null; await saved(result) }
    catch (cause) {
      let message = 'افزودن تأیید نشد؛ نام، نسخهٔ قالب، اتصال مدل و دسترسی را بررسی کنید. تکرار همین درخواست، کپی تکراری نمی‌سازد.'
      if (cause instanceof Response) { try { const data = await cause.clone().json(); if (typeof data.message === 'string') message = data.message } catch {} }
      setError(message)
    }
    finally { setBusy(false) }
  }
  return <FormDialog open title={`بررسی «${item.name}»`} description="متن اصلی و نسخهٔ سازگار با کارا را مقایسه کنید. نسخهٔ افزوده‌شده مستقل است و به‌روزرسانی کاتالوگ، آن یا فلوهای قبلی را تغییر نمی‌دهد." busy={busy} close={close} error={error}>
    {preview.isPending ? <p role="status">در حال دریافت متن قالب…</p> : preview.isError ? <p role="alert">دریافت متن انجام نشد. <button className={directoryButton} onClick={() => void preview.refetch()}>تلاش دوباره</button></p> : preview.data && <form className="space-y-4" onSubmit={e => { e.preventDefault(); void submit() }}>
      <div className="flex flex-wrap gap-2" aria-label="متن مورد بررسی"><button type="button" className={`${directoryButton} ${!source ? 'bg-background-section font-semibold text-text-accent' : ''}`} aria-pressed={!source} onClick={() => setSource(false)}>نسخهٔ کارا و قواعد اجرا</button><button type="button" className={`${directoryButton} ${source ? 'bg-background-section font-semibold text-text-accent' : ''}`} aria-pressed={source} onClick={() => setSource(true)}>متن اصلی</button></div>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-background-section p-4 font-sans text-xs leading-7 [overflow-wrap:anywhere]" dir="auto">{source ? preview.data.original : preview.data.adapted}</pre>
      <a href={preview.data.source_url} target="_blank" rel="noopener noreferrer" className="inline-block text-sm text-text-accent">فایل منبع در نسخهٔ ثابت مخزن ↗</a>
      <details className="text-xs"><summary className="cursor-pointer">مجوز و انتساب منبع</summary><pre className="mt-2 whitespace-pre-wrap leading-6" dir="ltr">{preview.data.license}</pre></details>
      {current ? <p className="text-sm leading-7">این نسخه قبلاً به پروژه اضافه شده است. <Link href={`/agents/${item.copy!.agent_id}/configure`} className="text-text-accent">نسخهٔ پروژه را باز کنید ←</Link></p> : <fieldset disabled={busy || !catalog.can_adopt} className="space-y-4">
        {!catalog.can_adopt && <p className="text-sm">افزودن قالب با مدیر مجاز پروژه است؛ مشاهدهٔ متن، دسترسی اجرایی ایجاد نمی‌کند.</p>}
        <label className="block text-sm">نام ایجنت پروژه<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} className={directoryField} /></label>
        <label className="block text-sm">مدل ایجنت<select required className={directoryField} value={modelId} onChange={e => setModelId(e.target.value)}><option value="">انتخاب کنید</option>{catalog.models.map(m => <option value={m.id} key={m.id}>{m.name} · {m.model_name}</option>)}</select><FieldHelp>فقط مشخصات مدل در ایجنت ثبت می‌شود؛ کلید شما منتقل نمی‌شود. اجراکننده در مسیر مدل به اتصال شخصی همین مدل نیاز دارد؛ مسیر هارنس هم با مجوز مستقل تیمی در دسترس است.</FieldHelp></label>
        {!catalog.models.length && <p className="text-sm">ابتدا <Link className="text-text-accent" href={`/projects/${project}/model-connections`}>اتصال شخصی مدل سازگار با Runner</Link> را ثبت کنید.</p>}
        <label className="block text-sm">دانش پروژه<select className={directoryField} value={dataset} onChange={e => setDataset(e.target.value)}><option value="">فعلاً متصل نشود</option>{catalog.datasets.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select><FieldHelp>برای تحلیل نیازمندی محصول، اسناد معتبر همان پروژه را متصل کنید. بدون سند، ایجنت باید کمبود شواهد را اعلام کند؛ متن قالب جای مستندات محصول نیست.</FieldHelp></label>
        <p className="text-xs leading-6 text-text-secondary">یک مهارت نسخه‌دار همراه ایجنت ساخته می‌شود. ابزارهای متن اصلی نصب یا فعال نمی‌شوند و هیچ اجرا، پیام یا تغییر کدی شروع نمی‌شود.</p>
        <label className="flex items-start gap-2 text-sm"><input className="mt-1" type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} /><span>متن و قواعد اجرا را بررسی کرده‌ام و افزودن نسخهٔ مستقل به این پروژه را تأیید می‌کنم.</span></label>
      </fieldset>}
      <div className="flex flex-wrap justify-end gap-3"><button type="button" className={directoryButton} disabled={busy} onClick={close}>بستن</button>{!current && <button className={`${directoryButton} bg-components-button-primary-bg text-components-button-primary-text`} disabled={busy || !catalog.can_adopt || !reviewed || !model || !name.trim()}>{busy ? 'در حال افزودن…' : 'افزودن به پروژه'}</button>}</div>
    </form>}
  </FormDialog>
}

export default function AgentLibrary() {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const params = useSearchParams()
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const [view, setView] = useState(['agency', 'agency-project'].includes(params.get('library') || '') ? params.get('library')! : 'project')
  const project = context.data?.current_project?.id
  if (workspace && context.isPending) return <p className="p-5" dir="rtl" role="status">در حال دریافت کتابخانهٔ پروژه…</p>
  if (context.isError) return <div className="p-5" dir="rtl"><p role="alert">دریافت فضای پروژه انجام نشد.</p><button className={`${directoryButton} mt-3`} onClick={() => void context.refetch()}>تلاش دوباره</button></div>
  return <div className="flex h-full min-h-0 min-w-0 flex-col bg-background-body" dir="rtl">
    {project && <nav aria-label="بخش‌های کتابخانهٔ ایجنت‌ها" className="flex shrink-0 flex-wrap gap-2 border-b border-divider-regular px-5 py-3">{[['project', 'ایجنت‌های پروژه'], ['agency', 'قالب‌های پیش‌فرض Agency'], ['agency-project', 'Agencyهای پروژه']].map(([id, title]) => <button key={id} className={`${directoryButton} ${view === id ? 'bg-background-section font-semibold text-text-accent ring-1 ring-text-accent' : ''}`} aria-pressed={view === id} onClick={() => setView(id)}>{title}</button>)}</nav>}
    {view !== 'project' && project ? <Templates key={`${workspace}:${project}:${view}`} project={project} copiedOnly={view === 'agency-project'} /> : <div className="flex min-h-0 grow flex-col"><RosterPage /></div>}
  </div>
}
