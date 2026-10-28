'use client'

import { useProgramDialogState } from './program-dialog-state'
import { useQuery, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect, useRef, useState } from 'react'
import Link from '@/next/link'
import { useSearchParams } from '@/next/navigation'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import { programAgentApi } from '@/service/company-program-agents'
import { ProjectPage } from './project-page'
import { directoryButton as button, directoryField as field, directoryPanel as panel } from './team-directory'

export function ProgramAgentComposer({ project, appId, onDefinitionChanged }: { project: string; appId?: string; onDefinitionChanged?: () => void }) {
  const { change } = useProgramDialogState()
  const params = useSearchParams()
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  const cache = useQueryClient()
  const key = ['program-roles', profile.id, workspace, project]
  const catalog = useQuery({ queryKey: key, queryFn: () => programAgentApi.catalog(project) })
  const [mode, setMode] = useState(appId || params.get('program') ? 'attach' : 'create')
  const [selectedProgram, setProgram] = useState(params.get('program') || '')
  const program = appId || selectedProgram
  const [source, setSource] = useState(params.get('agent') || '')
  const [target, setTarget] = useState('')
  const [name, setName] = useState('')
  const [bindings, setBindings] = useState<Record<string, string>>({})
  const [reviewed, setReviewed] = useState(false)
  const [detaching, setDetaching] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [created, setCreated] = useState<{ app_id: string; name: string } | null>(null)
  const [saved, setSaved] = useState(false)
  const operation = useRef<{ body: string; key: string } | null>(null)
  const selected = catalog.data?.sources.find(s => s.id === source)
  const preview = useQuery({ queryKey: [...key, source, selected?.snapshot_id], queryFn: () => programAgentApi.preview(project, source, selected!.snapshot_id!), enabled: !!selected?.snapshot_id && !selected.reason })
  const detail = useQuery({ queryKey: [...key, 'program', program], queryFn: () => programAgentApi.detail(project, program), enabled: mode === 'attach' && !!program })
  const node = detail.data?.nodes.find(n => n.id === target) || detail.data?.nodes[0]
  useEffect(() => {
    setReviewed(false); setSaved(false); setDetaching(false)
    setBindings(Object.fromEntries((preview.data?.inputs || []).map(v => [v.variable, v.variable === 'task' ? node?.task || node?.variables[0]?.value || '' : String(v.default ?? '')])))
  }, [mode, program, node?.id, preview.data?.source_digest])
  const act = async (payload: unknown, action: (key: string) => Promise<unknown>) => {
    if (busy) return
    const body = JSON.stringify(payload)
    if (operation.current?.body !== body) operation.current = { body, key: crypto.randomUUID() }
    setBusy(true); change(1); setError(''); setSaved(false)
    try { await action(operation.current.key); onDefinitionChanged?.(); operation.current = null; await cache.invalidateQueries({ queryKey: key }); setReviewed(false); setSaved(true) }
    catch (cause) {
      let message = 'ذخیره انجام نشد؛ دسترسی، نسخهٔ پیش‌نویس و نگاشت ورودی‌ها را بررسی کنید و اطلاعات را تازه کنید.'
      if (cause instanceof Response) { try { const value = await cause.clone().json(); if (typeof value.message === 'string') message = value.message } catch {} }
      setError(message)
    }
    finally { setBusy(false); change(-1) }
  }
  const ready = !!preview.data && !preview.isFetching && !preview.isError && !!selected?.snapshot_id && !selected.reason
  const submit = () => {
    if (!ready || !reviewed) return
    const common = { source_id: source, snapshot_id: selected!.snapshot_id!, source_digest: preview.data!.source_digest }
    if (mode === 'create') {
      const body = { ...common, name: name.trim() }
      void act({ mode, ...body }, async key => { const value = await programAgentApi.create(project, body, key); setCreated(value) })
    }
    else if (node && detail.data && !node.role && !detail.isFetching) {
      const body = { ...common, draft_hash: detail.data.hash, bindings }
      void act({ mode, program, node: node.id, ...body }, key => programAgentApi.attach(project, program, node.id, body, key))
    }
  }
  if (catalog.isPending) return <p role="status">در حال دریافت ایجنت‌ها و برنامه‌های پروژه…</p>
  if (catalog.isError) return <section role="alert" className={panel}><p>دریافت اطلاعات انجام نشد؛ مدیریت اتصال به مجوز ساخت/ویرایش برنامه و مدیریت پروژه نیاز دارد.</p><button className={`${button} mt-3`} onClick={() => void catalog.refetch()}>تلاش دوباره</button></section>
  return <div className="space-y-5">
    {!appId && <p className="text-sm leading-7 text-text-secondary">ایجنت کتابخانه را به یک برنامهٔ تازه یا مرحلهٔ LLM پیش‌نویس برنامه اضافه کنید. دستورالعمل، مهارت و دانشِ نسخهٔ انتخابی به برنامه متصل می‌شود. در هر اجرا، کاربر مدل شخصی خودش را انتخاب می‌کند.</p>}
    {!appId && <nav className="flex flex-wrap gap-3" aria-label="روش استفاده از ایجنت">{([['create', 'برنامهٔ تازه از ایجنت'], ['attach', 'استفاده در برنامهٔ موجود']] as const).map(([id, title]) => <button key={id} disabled={busy} className={`${button} ${mode === id ? 'bg-background-section font-semibold text-text-accent ring-1 ring-text-accent' : ''}`} aria-pressed={mode === id} onClick={() => setMode(id)}>{title}</button>)}</nav>}
    <form className={`${panel} space-y-5`} onSubmit={e => { e.preventDefault(); submit() }}>
      <fieldset disabled={busy} className="space-y-5">
        {mode === 'create' ? <label className="block text-sm">نام برنامه<input required maxLength={120} className={field} value={name} onChange={e => { setName(e.target.value); setReviewed(false) }} placeholder="برنامهٔ تحلیل درخواست" /></label> : <>
          {!appId && <label className="block text-sm">برنامه<select required className={field} value={program} onChange={e => { setProgram(e.target.value); setTarget(''); setReviewed(false) }}><option value="">انتخاب کنید</option>{catalog.data.programs.map(a => <option value={a.id} key={a.id}>{a.name}</option>)}</select></label>}
          <p className="text-xs leading-6 text-text-secondary">ابتدا تغییرات طراح را ذخیره کنید. این اقدام فقط پیش‌نویس را تغییر می‌دهد؛ نسخه‌های منتشرشده و فلوهای فعلی ثابت می‌مانند. مدل همهٔ مراحل LLM این برنامه از اجراکننده دریافت خواهد شد.</p>
          {program && (detail.isPending ? <p role="status">در حال دریافت مراحل…</p> : detail.isError ? <p role="alert">دریافت پیش‌نویس انجام نشد؛ برنامه را در طراح باز و ذخیره کنید، سپس <button type="button" className={button} onClick={() => void detail.refetch()}>تازه‌سازی</button></p> : <label className="block text-sm">مرحلهٔ LLM<select className={field} required value={node?.id || ''} onChange={e => { setTarget(e.target.value); setReviewed(false) }}><option value="">انتخاب کنید</option>{detail.data?.nodes.map(n => <option key={n.id} value={n.id}>{n.name}{n.role ? ` · ${n.role.name}` : ''}</option>)}</select>{!detail.data?.nodes.length && <span className="mt-2 block text-xs">ابتدا یک مرحلهٔ LLM مستقل در طراح برنامه اضافه کنید.</span>}</label>)}
          {node?.role && <section className="space-y-3 rounded-xl border border-divider-regular p-4 text-sm"><p>این مرحله به «{node.role.name}» نسخهٔ {node.role.snapshot_version} متصل است. برای تغییر نقش یا ویرایش آزاد دستورالعمل، ابتدا اتصال را جدا کنید.</p><button type="button" className={button} onClick={() => setDetaching(!detaching)}>جداکردن اتصال</button>{detaching && <><p>در مرحلهٔ موجود، تعریف پیش از اتصال برمی‌گردد؛ در برنامهٔ ساخته‌شده از ایجنت، متن و دانش باقی می‌مانند و مستقل می‌شوند. نسخهٔ منتشرشده تغییر نمی‌کند.</p><button type="button" className={button} onClick={() => { const hash = detail.data!.hash; void act({ detach: program, node: node.id, hash }, async key => { await programAgentApi.detach(project, program, node.id, hash, key); setDetaching(false) }) }}>تأیید جداکردن</button></>}</section>}
        </>}
        {(mode === 'create' || !node?.role) && <>
          <label className="block text-sm">ایجنت کتابخانه<select required className={field} value={source} onChange={e => { setSource(e.target.value); setReviewed(false) }}><option value="">انتخاب کنید</option>{catalog.data.sources.map(s => <option key={s.id} value={s.id}>{s.name}{s.reason ? ' · نیازمند بررسی' : ''}</option>)}</select></label>
          {!catalog.data.sources.length && <p className="text-sm">ابتدا در <Link className="text-text-accent" href="/agents?library=agency">کتابخانهٔ ایجنت‌ها</Link> ایجنت بسازید یا یک قالب Agency به پروژه اضافه کنید.</p>}
          {selected?.reason && <p role="alert" className="text-sm">{selected.reason}</p>}
          {selected?.snapshot_id && !selected.reason && (preview.isPending ? <p role="status">در حال بررسی نسخهٔ ایجنت…</p> : preview.isError ? <p role="alert">بررسی ایجنت انجام نشد. <button type="button" className={button} onClick={() => void preview.refetch()}>تلاش دوباره</button></p> : preview.data && <>
            <section className="space-y-3 rounded-xl bg-background-section p-4 text-sm"><p className="font-semibold">{preview.data.name} · نسخهٔ {preview.data.version}</p><p>مهارت‌ها: {preview.data.skills.map(s => s.name).join('، ') || 'مهارتی متصل نیست'}</p><p>دانش: {preview.data.knowledge.join('، ') || 'مجموعه‌ای متصل نیست'}</p><details><summary className="cursor-pointer">بررسی دستورالعمل و مهارت‌ها</summary><pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap font-sans text-xs leading-7 [overflow-wrap:anywhere]" dir="auto">{preview.data.prompt}</pre></details><p className="text-xs leading-6">مدل و کلید سازنده منتقل نمی‌شوند. اجراکننده باید اتصال شخصی سازگار و دسترسی به ایجنت، مهارت و دانش پروژه را داشته باشد. اجرای مدل و ابزار روی Runner انجام می‌شود.</p></section>
            {mode === 'attach' && node && <fieldset className="space-y-4"><legend className="mb-3 text-sm font-semibold">ورودی‌های ایجنت در این مرحله</legend>{preview.data.inputs.map(v => <label className="block text-sm" key={v.variable}>{v.label}{v.required && ' *'}<textarea required={v.required} maxLength={120000} className={field} value={bindings[v.variable] || ''} onChange={e => { setBindings({ ...bindings, [v.variable]: e.target.value }); setReviewed(false) }} /><select className={field} value="" onChange={e => { if (e.target.value) { setBindings({ ...bindings, [v.variable]: (bindings[v.variable] || '') + e.target.value }); setReviewed(false) } }}><option value="">افزودن متغیر از مراحل قبلی</option>{node.variables.map(x => <option key={x.value} value={x.value}>{x.label}</option>)}</select></label>)}<p className="text-xs leading-6 text-text-secondary">شناسه و خروجی متنی مرحله حفظ می‌شوند. پاسخ ایجنت در همان خروجی text در دسترس مراحل بعدی است.</p></fieldset>}
            <label className="flex items-start gap-2 text-sm"><input className="mt-1" type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} /><span>نسخهٔ ایجنت و ورودی‌ها را بررسی کردم؛ نتیجهٔ پیش‌نویس را پیش از انتشار در طراح بازبینی می‌کنم.</span></label>
          </>)}
          <button className={`${button} bg-components-button-primary-bg text-components-button-primary-text`} disabled={busy || !ready || !reviewed || (mode === 'create' ? !name.trim() : !node || !!node.role || detail.isFetching || detail.isError)}>{busy ? 'در حال ذخیره…' : mode === 'create' ? 'ساخت پیش‌نویس برنامه' : 'اتصال به مرحلهٔ برنامه'}</button>
        </>}
      </fieldset>
      {error && <p role="alert" className="text-sm leading-7">{error}</p>}{saved && <p role="status" className="text-sm">پیش‌نویس ذخیره شد. برنامه را در طراح بازبینی و سپس منتشر کنید.</p>}
    </form>
    {created && <section className={`${panel} space-y-3`} role="status"><p>پیش‌نویس «{created.name}» ساخته شد.</p><Link className={button} href={`/app/${created.app_id}/workflow`}>بازکردن طراح برنامه</Link><button className={`${button} ms-3`} onClick={() => { setProgram(created.app_id); setMode('attach'); setTarget('') }}>مدیریت ایجنت‌های همین برنامه</button></section>}
    {!appId && <div className="flex flex-wrap gap-3"><Link className={button} href={mode === 'attach' && program ? `/app/${program}/workflow` : '/apps'}>{mode === 'attach' && program ? 'بازکردن طراح برنامه' : 'فهرست برنامه‌ها'}</Link><Link className={button} href="/agents">کتابخانهٔ ایجنت‌ها</Link><button className={button} disabled={busy} onClick={() => { setReviewed(false); void cache.invalidateQueries({ queryKey: key }) }}>تازه‌سازی اطلاعات</button></div>}
  </div>
}

export default function ProgramAgents({ projectId }: { projectId: string }) {
  return <ProjectPage projectId={projectId} title="ایجنت‌های برنامه">{() => <ProgramAgentComposer project={projectId} />}</ProjectPage>
}
