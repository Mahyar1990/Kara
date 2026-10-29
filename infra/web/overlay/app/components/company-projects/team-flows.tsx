'use client'

import type { FlowOptions, FlowStage, FlowVersion, TeamFlow } from '@/service/company-flows'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect, useId, useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { flowApi } from '@/service/company-flows'
import { projectApi } from '@/service/company-projects'
import { sourceError } from '@/service/company-source'
import DeleteTeamEntity from './delete-team-entity'
import FormDialog, { FieldHelp } from './form-dialog'
import FlowStageEditor, { defaultStageExecution, FlowStageRow, upgradeStage } from './flow-stage-editor'
import type { StageEditError } from './flow-stage-editor'
import { DirectoryPage, DirectoryNotice, DirectorySummary, DirectoryToolbar, DirectoryPagination, DirectoryEmpty, directoryButton, directoryField, matchesSearch, resultPage } from './team-directory'

const panel = 'min-w-0 space-y-4 [overflow-wrap:anywhere] rounded-2xl border border-divider-regular bg-background-default p-5'
const button = 'rounded-lg border border-divider-regular px-4 py-2 text-sm disabled:opacity-50'
const primary = `${button} bg-components-button-primary-bg text-components-button-primary-text`
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const number = (value: number) => value.toLocaleString('fa-IR')

function useAction() {
  const operation = useRef<{ payload: string; key: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async (payload: unknown, action: (key: string) => Promise<unknown>) => {
    if (busy) return
    const serialized = JSON.stringify(payload)
    if (operation.current?.payload !== serialized) operation.current = { payload: serialized, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try { await action(operation.current.key); operation.current = null }
    catch (error) { setError(await sourceError(error, 'اقدام انجام نشد. مجوزها و کامل‌بودن مراحل را بررسی کنید؛ اگر فلو تغییر کرده است، نسخهٔ تازه را دریافت کنید.')) }
    finally { setBusy(false) }
  }
  return { busy, error, run }
}


function FlowEditor({ project, value, options, saved, cancel, refreshOptions, updatingOptions, optionsFailed, remoteChanged }: { project: string; value: TeamFlow | null; options: FlowOptions; saved: (value: TeamFlow) => Promise<unknown>; cancel: () => void; refreshOptions: () => unknown; updatingOptions: boolean; optionsFailed: boolean; remoteChanged: boolean }) {
  const [name, setName] = useState(value?.name || '')
  const [description, setDescription] = useState(value?.description || '')
  const [stages, setStages] = useState<FlowStage[]>(() => (value?.draft_stages || []).map(stage => upgradeStage(stage, options)))
  const [editingStage, setEditingStage] = useState<FlowStage | null>(null)
  const [stageOrigin, setStageOrigin] = useState<FlowStage | null>(null)
  const [stageError, setStageError] = useState<StageEditError | null>(null)
  const [exitPrompt, setExitPrompt] = useState<'stage' | 'flow' | null>(null)
  const continueButton = useRef<HTMLButtonElement>(null)
  const exitLauncher = useRef<HTMLElement | null>(null)
  const stagePane = useRef<HTMLDivElement>(null)
  const flowForm = useRef<HTMLFormElement>(null)
  const stageLauncher = useRef<HTMLButtonElement | null>(null)
  const [archiving, setArchiving] = useState(false)
  const formId = useId()
  const action = useAction()
  const locked = action.busy || !!editingStage || !!exitPrompt
  const changed = !value || name !== value.name || description !== value.description || JSON.stringify(stages) !== JSON.stringify(value.draft_stages)
  const dirtyFlow = value ? changed : !!name || !!description || stages.length > 0
  useEffect(() => {
    if (!exitPrompt) return
    const frame = requestAnimationFrame(() => continueButton.current?.focus())
    return () => cancelAnimationFrame(frame)
  }, [exitPrompt])
  const save = (closeAfter = false) => { const body = { name, description, stages, expected_revision: value?.revision || 1 }; void action.run({ id: value?.id, body }, async key => { await saved(await flowApi.save(project, value?.id || null, body, key)); if (closeAfter) cancel() }) }
  const publish = () => { if (value) void action.run({ publish: value.id, revision: value.revision }, async key => saved(await flowApi.publish(project, value.id, value.revision, key))) }
  const editStage = (stage: FlowStage) => {
    stageLauncher.current = document.activeElement instanceof HTMLButtonElement ? document.activeElement : null
    setStageOrigin(stage); setEditingStage(stage); setStageError(null); setExitPrompt(null)
  }
  const add = () => editStage({ key: `step_${crypto.randomUUID().slice(0, 8)}`, title: `مرحلهٔ ${number(stages.length + 1)}`, agent_id: null, app_id: null, workflow_id: null, execution: defaultStageExecution(), participants: [], executor_id: null, executor_membership_id: null, finalizer_id: null, finalizer_membership_id: null, decision_role: null, inputs: {} })
  const stageChanged = JSON.stringify(editingStage) !== JSON.stringify(stageOrigin)
  const returnToFlow = () => {
    const launcher = stageLauncher.current
    setEditingStage(null); setStageOrigin(null); setStageError(null); setExitPrompt(null)
    requestAnimationFrame(() => launcher?.focus())
  }
  const showExit = (target: 'stage' | 'flow') => {
    exitLauncher.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setExitPrompt(target)
  }
  const continueEditing = () => {
    const launcher = exitLauncher.current
    setExitPrompt(null)
    requestAnimationFrame(() => {
      if (launcher?.isConnected) launcher.focus()
      else (editingStage ? stagePane.current : flowForm.current)?.focus()
    })
  }
  const requestReturn = () => { if (stageChanged) showExit('stage'); else returnToFlow() }
  const requestCloseFlow = () => { if (dirtyFlow) showExit('flow'); else cancel() }
  const requestClose = () => { if (exitPrompt) continueEditing(); else if (editingStage) requestReturn(); else requestCloseFlow() }
  const applyStage = () => {
    if (!editingStage) return
    if (!editingStage.title.trim()) {
      setStageError(previous => ({ message: 'عنوان مرحله را وارد کنید.', attempt: (previous?.attempt || 0) + 1 }))
      setExitPrompt(null)
      return
    }
    const next = editingStage
    setStages(current => current.some(stage => stage.key === next.key) ? current.map(stage => stage.key === next.key ? next : stage) : [...current, next])
    returnToFlow()
  }
  const move = (index: number, offset: number) => { const current = stages[index]; const other = stages[index + offset]; if (!current || !other) return; const result = [...stages]; result[index] = other; result[index + offset] = current; setStages(result) }
  const editingIndex = editingStage ? stages.findIndex(stage => stage.key === editingStage.key) : -1
  return <FormDialog open wide fixedBody title={exitPrompt ? 'پیش از برگشت، دربارهٔ تغییرات تصمیم بگیرید' : editingStage ? `تنظیم مرحلهٔ ${number((editingIndex < 0 ? stages.length : editingIndex) + 1)} · ${editingStage.title || 'مرحلهٔ جدید'}` : value ? `ویرایش فلو: ${value.name}` : 'ساخت فلو'}
    description={exitPrompt ? 'تغییرات شما هنوز ثبت نشده‌اند. می‌توانید آن‌ها را نگه دارید، کنار بگذارید یا ویرایش را ادامه دهید.' : editingStage ? 'تنظیمات این مرحله را در تب‌های زیر مشخص کنید. اعمال مرحله، پیش‌نویس فلو را تغییر می‌دهد؛ ذخیرهٔ نهایی را در صفحهٔ مراحل انجام دهید.' : 'نام و ترتیب مراحل را مشخص کنید. تنظیمات هر مرحله از دکمهٔ «ویرایش مرحله» باز می‌شود.'}
    header={editingStage ? <button type="button" className={exitPrompt ? 'hidden' : 'flex items-center gap-2 rounded-lg py-1 text-sm text-text-accent'} onClick={requestReturn}><span aria-hidden className="i-ri-arrow-right-line size-4" />بازگشت به مراحل فلو</button> : undefined}
    closeLabel={exitPrompt ? 'ادامهٔ ویرایش' : editingStage ? 'بازگشت به مراحل فلو' : 'بستن'}
    busy={action.busy} close={requestClose} footer={exitPrompt ? undefined : editingStage ? <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="max-w-xl text-xs leading-6 text-text-tertiary">پس از اعمال مرحله، برای ثبت تغییرات، پیش‌نویس فلو را ذخیره کنید.</p><div className="flex flex-wrap gap-2">
        <button type="button" className={primary} onClick={applyStage}>اعمال و بازگشت</button>
        <button type="button" className={button} onClick={requestReturn}>بازگشت</button>
      </div></div>
    </div> : <div className="space-y-3">
      {action.error && <p role="alert" className="text-sm leading-7 text-text-destructive-secondary">{action.error}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3"><p role="status" className="text-xs leading-6 text-text-secondary">{changed ? 'تغییرات ذخیره‌نشده دارید.' : 'پیش‌نویس ذخیره شده است.'}</p><div className="flex flex-wrap gap-2">
        <button type="submit" form={formId} className={primary} disabled={locked || !!value?.archived || !changed || !name.trim()}>{action.busy ? 'در حال ثبت…' : 'ذخیرهٔ پیش‌نویس'}</button>
        {value && <button type="button" className={button} disabled={locked || value.archived || changed || !stages.length || optionsFailed} onClick={publish}>انتشار نسخهٔ تازه</button>}
        <button type="button" className={button} disabled={locked} onClick={requestCloseFlow}>بستن</button>
      </div></div><p className="text-xs leading-6 text-text-tertiary">انتشار نسخهٔ تازه، اجرا را شروع نمی‌کند و نسخه‌ها و اجراهای قبلی را تغییر نمی‌دهد.</p>
    </div>}>
    {exitPrompt && <section className="h-full overflow-y-auto rounded-xl bg-background-section p-5 text-center" aria-label="تصمیم دربارهٔ تغییرات ذخیره‌نشده"><div className="flex min-h-full flex-col items-center justify-center gap-5">
      <p role="alert" className="max-w-2xl text-base leading-8">{exitPrompt === 'stage' ? 'تنظیمات این مرحله تغییر کرده‌اند. آیا تغییرات را به پیش‌نویس فلو اعمال کنیم و به فهرست مراحل برگردیم؟' : 'پیش‌نویس این فلو تغییر کرده است. آیا آن را ذخیره کنیم و ویرایشگر را ببندیم؟'}</p>
      <p className="max-w-2xl text-sm leading-7 text-text-tertiary">{exitPrompt === 'stage' ? 'اعمال تغییرات، فقط پیش‌نویس محلی فلو را تغییر می‌دهد. پس از برگشت، برای ثبت نهایی «ذخیرهٔ پیش‌نویس» را بزنید.' : 'ذخیرهٔ پیش‌نویس، نسخهٔ تازه منتشر نمی‌کند و اجرا را شروع نمی‌کند.'}</p>
      <div className="flex flex-wrap justify-center gap-3">
        <button type="button" className={primary} disabled={action.busy || (exitPrompt === 'flow' && (!name.trim() || !!value?.archived))} onClick={() => exitPrompt === 'stage' ? applyStage() : save(true)}>{action.busy ? 'در حال ذخیره…' : exitPrompt === 'stage' ? 'اعمال تغییرات و بازگشت' : 'ذخیرهٔ پیش‌نویس و بستن'}</button>
        <button type="button" className={button} disabled={action.busy} onClick={exitPrompt === 'stage' ? returnToFlow : cancel}>{exitPrompt === 'stage' ? 'بازگشت بدون اعمال' : 'بستن بدون ذخیره'}</button>
        <button ref={continueButton} type="button" className={button} disabled={action.busy} onClick={continueEditing}>ادامهٔ ویرایش</button>
      </div>
      {exitPrompt === 'flow' && !name.trim() && <p className="text-sm leading-7">برای ذخیره، به ویرایش برگردید و نام فلو را وارد کنید.</p>}
      {exitPrompt === 'flow' && action.error && <p role="alert" className="text-sm leading-7 text-text-destructive-secondary">{action.error}</p>}
    </div></section>}
    <form ref={flowForm} tabIndex={-1} id={formId} aria-label="ویرایش پیش‌نویس فلو" hidden={!!editingStage || !!exitPrompt} className={editingStage || exitPrompt ? 'hidden' : 'flex h-full min-h-0 min-w-0 flex-col gap-4'} onSubmit={event => { event.preventDefault(); if (!locked) save() }}>
      {remoteChanged && <p role="alert" className="shrink-0 rounded-lg border border-divider-regular p-3 text-sm leading-7">این فلو پس از بازشدن ویرایشگر تغییر کرده یا از فهرست خارج شده است. تغییرات شما حفظ شده‌اند؛ پیش از بستن آن‌ها را کپی کنید و سپس نسخهٔ تازه را باز کنید.</p>}
      <fieldset disabled={locked || value?.archived} className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
        <div className="grid shrink-0 gap-4 md:grid-cols-2">
          <label className="block text-sm">نام فلو<input required maxLength={120} className={field} value={name} onChange={event => setName(event.target.value)} /><FieldHelp>نامی یکتا برای مسیر همکاری تیم انتخاب کنید.</FieldHelp></label>
          <label className="block text-sm">توضیح فلو<textarea rows={2} maxLength={2000} className={field} value={description} onChange={event => setDescription(event.target.value)} /><FieldHelp>کاربرد این مسیر و نتیجهٔ مورد انتظار را بنویسید.</FieldHelp></label>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-divider-regular pt-3"><h3 className="font-semibold">مراحل فلو <span className="ms-2 text-xs font-normal text-text-tertiary">{number(stages.length)} از ۳۰ مرحله</span></h3><div className="flex flex-wrap gap-2"><button type="button" className={button} disabled={updatingOptions} onClick={() => void refreshOptions()}>{updatingOptions ? 'در حال دریافت…' : 'تازه‌سازی اعضا و برنامه‌ها'}</button><button type="button" className={button} disabled={stages.length >= 30} onClick={add}>افزودن مرحله</button></div></div>
        {optionsFailed && <p role="alert" className="shrink-0 text-xs leading-6">تازه‌سازی موفق نبود؛ اطلاعات قبلی و تغییرات شما حفظ شده‌اند. پیش از انتشار دوباره تازه‌سازی کنید.</p>}
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain pe-2">
          {stages.length ? <ol aria-label="مراحل پیش‌نویس فلو" className="m-0 list-none space-y-3 p-0">{stages.map((stage, index) => <li key={stage.key}><FlowStageRow stage={stage} index={index} total={stages.length} options={options} edit={() => editStage(stage)} move={offset => move(index, offset)} remove={() => setStages(current => current.filter(item => item.key !== stage.key))} /></li>)}</ol> : <div className="rounded-xl border border-dashed border-divider-regular p-6 text-center"><p className="text-sm font-medium">اولین مرحلهٔ همکاری را اضافه کنید</p><p className="mt-2 text-xs leading-6 text-text-tertiary">برنامه، ورودی‌ها، روش اجرا و دسترسی‌ها را در تنظیمات همان مرحله مشخص می‌کنید.</p><button type="button" className={`${button} mt-4`} onClick={add}>افزودن مرحله</button></div>}
        </div>
      </fieldset>
      {value && !value.archived && <details open={archiving} onToggle={event => setArchiving(event.currentTarget.open)} className="shrink-0 border-t border-divider-regular pt-3"><summary className="cursor-pointer text-xs text-text-tertiary">بایگانی فلو</summary><div className="mt-3 flex flex-wrap items-center justify-between gap-3"><p className="text-xs leading-6">ویرایش و انتشار تازه متوقف می‌شود. تغییرات ذخیره‌نشده اعمال نمی‌شوند و نسخه‌های قبلی حفظ می‌شوند.</p><button type="button" className={`${button} text-text-destructive-secondary`} disabled={locked} onClick={() => action.run({ archive: value.id, revision: value.revision }, async key => saved(await flowApi.archive(project, value.id, value.revision, key)))}>تأیید بایگانی فلو</button></div></details>}
    </form>
    {editingStage && <div ref={stagePane} tabIndex={-1} role="group" aria-label="تنظیمات مرحله" hidden={!!exitPrompt} className={exitPrompt ? 'hidden' : 'h-full min-h-0'}><FlowStageEditor key={editingStage.key} value={editingStage} change={update => setEditingStage(current => current ? update(current) : current)} error={stageError} clearError={() => setStageError(null)} index={editingIndex < 0 ? stages.length : editingIndex} stages={stages} options={options} refreshOptions={refreshOptions} updatingOptions={updatingOptions} optionsFailed={optionsFailed} /></div>}
  </FormDialog>
}

function Published({ value }: { value: FlowVersion }) {
  return <section aria-label={`نسخهٔ منتشرشده ${value.version}`} className="space-y-4 rounded-lg bg-background-section p-4"><h3 className="font-semibold">نسخهٔ منتشرشدهٔ {number(value.version)} · {value.name}</h3><p className="text-sm text-text-secondary">{value.description}</p><ol className="m-0 list-none space-y-3 p-0">{value.stage_bindings.map((stage, index) => <li key={stage.key} className="space-y-2 rounded-lg border border-divider-regular p-3"><p className="font-medium">{number(index + 1)}. {stage.title} · {stage.app_name || stage.agent_name}{stage.workflow_version && ` · ${stage.workflow_version}`}</p><p className="text-sm text-text-secondary">اجراکننده: {stage.executor.name} · نهایی‌کننده: {stage.finalizer.name}{stage.decision_role && ` · نقش تصمیم: ${stage.decision_role.toUpperCase()}`}</p>{stage.execution && <div className="space-y-2 text-xs leading-6"><p>روش اجرا: {[stage.execution.program_enabled && 'اجرای برنامه', stage.execution.enabled && 'ابزار شخصی'].filter(Boolean).join('، ')}{stage.execution.enabled && (stage.execution.requires_source ? ' · سورس الزامی' : ' · سورس اختیاری')}</p>{stage.execution.instructions && <p className="whitespace-pre-wrap">{stage.execution.instructions}</p>}{!!stage.participants?.length && <p>همکاران: {stage.participants.map(person => `${person.name} (${person.actions.includes('feedback') ? 'بازخورد' : 'مشاهده'})`).join('، ')}</p>}</div>}<details className="text-xs leading-6 text-text-tertiary"><summary className="cursor-pointer">اتصال ورودی‌ها</summary>{Object.entries(stage.inputs).map(([name, source]) => <p key={name}>{name}: {source.source === 'request' ? 'متن درخواست' : source.source === 'constant' ? `مقدار ثابت: ${JSON.stringify(source.value)}` : `خروجی ${source.output} از ${value.stage_bindings.find(value => value.key === source.stage_key)?.title || source.stage_key}`}</p>)}</details></li>)}</ol><details className="text-xs text-text-tertiary"><summary className="cursor-pointer">شناسهٔ نسخه</summary><p className="mt-2 break-all" dir="ltr">{value.id}</p></details></section>
}

function History({ project, flow }: { project: string; flow: TeamFlow }) {
  const versions = useQuery({ queryKey: ['team-flow-versions', project, flow.id, flow.current_version_id], queryFn: () => flowApi.versions(project, flow.id) })
  const [selected, setSelected] = useState(flow.current_version_id)
  const value = versions.data?.data.find(value => value.id === selected) || flow.published
  return <div className="min-w-0 space-y-4 [overflow-wrap:anywhere]">
    {versions.isPending && <p role="status" className="text-sm">در حال دریافت نسخه‌ها…</p>}
    {versions.isError && <div role="alert" className="space-y-2"><p>دریافت تاریخچه انجام نشد؛ نسخهٔ فعلی در ادامه نمایش داده می‌شود.</p><button className={button} onClick={() => void versions.refetch()}>تلاش دوباره</button></div>}
    {versions.isSuccess && <label className="block max-w-md text-sm">نسخهٔ مورد بررسی<select className={field} value={value?.id || ''} onChange={event => setSelected(event.target.value)}>{versions.data.data.map(version => <option value={version.id} key={version.id}>نسخهٔ {number(version.version)} · {version.id === flow.current_version_id ? 'انتشار فعلی' : 'نسخهٔ تاریخی'}</option>)}</select></label>}
    {value && <><p className="text-xs leading-6 text-text-secondary">منتشرشده در {new Date(value.published_at).toLocaleString('fa-IR')} · تغییر پیش‌نویس، محتوای این نسخه را تغییر نمی‌دهد.</p><Published value={value} /></>}
  </div>
}

function FlowCard({ project, flow, canEdit, edit, remove }: { project: string; flow: TeamFlow; canEdit: boolean; edit: () => void; remove: () => void }) {
  const [inspecting, setInspecting] = useState(false)
  const published = flow.published
  const newerDraft = !flow.archived && !!published && flow.revision > published.source_revision + 1
  return <article className={panel}>
    <header><p className="mb-2 text-xs font-medium text-text-accent">{flow.archived ? 'بایگانی‌شده' : published ? `نسخهٔ منتشرشدهٔ ${number(published.version)}` : 'فقط پیش‌نویس؛ قابل شروع برای درخواست نیست'}</p><h2 className="break-words text-xl font-semibold leading-8">{flow.name}</h2></header>
    {flow.description && <p className="line-clamp-2 whitespace-pre-wrap text-sm leading-7 text-text-secondary">{flow.description}</p>}
    <p className="text-xs leading-6 text-text-tertiary">{published ? `${number(published.stage_bindings.length)} مرحله در نسخهٔ منتشرشده` : 'برای استفاده در درخواست‌ها، فلو باید منتشر شود.'}{flow.draft_stages && ` · ${number(flow.draft_stages.length)} مرحله در پیش‌نویس`}</p>
    {newerDraft && <p className="rounded-lg bg-background-section p-3 text-xs leading-6">پس از انتشار فعلی، پیش‌نویس دوباره ذخیره شده است. درخواست‌ها همچنان نسخهٔ منتخب در تصمیم ورود را استفاده می‌کنند.</p>}
    {published && <ol aria-label="پیش‌نمایش مسیر فلو" className="m-0 flex list-none flex-wrap gap-2 p-0">{published.stage_bindings.slice(0, 3).map((stage, index) => <li key={stage.key} className="max-w-full break-words rounded-lg bg-background-section px-3 py-2 text-xs leading-6">{number(index + 1)}. {stage.title}</li>)}{published.stage_bindings.length > 3 && <li className="px-2 py-2 text-xs leading-6 text-text-tertiary">و {number(published.stage_bindings.length - 3)} مرحلهٔ دیگر</li>}</ol>}
    <footer className="border-t border-divider-regular pt-5"><div className="flex flex-wrap items-center gap-2">{published && <button className={primary} onClick={() => setInspecting(true)}>مراحل و نسخه‌ها</button>}{canEdit && <>{!flow.archived && <button className={button} onClick={edit}>ویرایش فلو</button>}<button className={`${button} text-text-destructive-secondary`} onClick={remove}>حذف فلو</button></>}</div></footer>
    {published && inspecting && <FormDialog open wide title={`مراحل و نسخه‌های ${flow.name}`} description="نسخهٔ منتشرشده، ایجنت‌ها، اجراکننده و نهایی‌کنندهٔ مراحل را بررسی کنید. این صفحه فقط برای مشاهده است و اجرا را شروع نمی‌کند." close={() => setInspecting(false)}><History project={project} flow={flow} /><button className={`${button} mt-5`} onClick={() => setInspecting(false)}>بستن</button></FormDialog>}
  </article>
}

export default function TeamFlows({ projectId }: { projectId: string }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const cache = useQueryClient()
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const entered = context.data?.current_project?.id === projectId
  const list = useQuery({ queryKey: ['team-flows', workspace, projectId], queryFn: () => flowApi.list(projectId), enabled: entered })
  const [editingValue, setEditingValue] = useState<TeamFlow | null>(null)
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState<TeamFlow | null>(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('active')
  const [sort, setSort] = useState('registered')
  const [page, setPage] = useState(1)
  const options = useQuery({ queryKey: ['team-flow-options', workspace, projectId], queryFn: () => flowApi.options(projectId), enabled: entered && !!list.data?.can_edit && editing })
  useEffect(() => { setEditingValue(null); setEditing(false); setDeleting(null); setQuery(''); setStatus('active'); setSort('registered'); setPage(1) }, [workspace, projectId])
  // Keep the form and its CAS revision independent from background catalog refreshes.
  const value = editingValue
  const selected = value?.id || null
  const remoteChanged = !!value && list.isSuccess && list.data.data.find(flow => flow.id === value.id)?.revision !== value.revision
  const refresh = async () => { const result = await list.refetch(); void cache.invalidateQueries({ queryKey: ['company-projects', workspace, projectId, 'overview'] }); return result }
  const saved = async (flow: TeamFlow) => { const fresh = await refresh(); if (!fresh.isSuccess) throw new Error('Refresh failed'); setEditingValue(flow); setEditing(!flow.archived); setQuery(''); setStatus(flow.archived ? 'all' : 'active'); setSort('registered'); const index = fresh.data.data.filter(item => flow.archived || !item.archived).findIndex(item => item.id === flow.id); setPage(Math.floor(Math.max(0, index) / 8) + 1) }
  const values = list.data?.data || []
  const ordered = sort === 'name' ? [...values].sort((a, b) => a.name.localeCompare(b.name, 'fa')) : values
  const filtered = ordered.filter(flow => matchesSearch(query, flow.name, flow.description) && (status === 'all' || (status === 'archived' ? flow.archived : !flow.archived && (status === 'active' || (status === 'published' ? !!flow.current_version_id : !flow.current_version_id)))))
  const results = resultPage(filtered, page)
  const hasFilters = !!query.trim() || status !== 'all' || sort !== 'registered'
  const reset = () => { setQuery(''); setStatus('all'); setSort('registered'); setPage(1) }
  return <DirectoryPage project={projectId} title="فلوهای تیم" description="مسیر همکاری تیم را پیدا کنید؛ مراحل و مسئولان نسخهٔ منتشرشده را ببینید یا پیش‌نویس را برای انتشار بعدی ویرایش کنید." actions={<><button className={directoryButton} disabled={!entered || list.isFetching} onClick={() => void refresh()}>{list.isFetching ? 'در حال تازه‌سازی…' : 'تازه‌سازی'}</button>{entered && list.data?.can_edit && <button className={primary} onClick={() => { setEditingValue(null); setEditing(true) }}>ساخت فلو</button>}</>}>
    <DirectoryNotice project={projectId} entered={!!entered} loading={context.isPending || (!!entered && list.isPending)} error={context.isError || (!!entered && list.isError)} retry={() => context.isError ? context.refetch() : refresh()} />
    {entered && list.data && <>
      {list.isError && <p role="status" className="text-sm leading-7 text-text-secondary">آخرین فهرست دریافت‌شده نمایش داده می‌شود؛ تازه‌سازی موفق نبوده است.</p>}
      <DirectorySummary items={[{ label: 'کل فلوهای در دسترس', count: values.length }, { label: 'منتشرشده و غیربایگانی', count: values.filter(flow => !flow.archived && !!flow.current_version_id).length }, { label: 'فقط پیش‌نویس', count: values.filter(flow => !flow.archived && !flow.current_version_id).length }, { label: 'بایگانی‌شده', count: values.filter(flow => flow.archived).length }]} />
      <DirectoryToolbar query={query} change={value => { setQuery(value); setPage(1) }} placeholder="نام یا توضیح فلو" filtered={filtered.length} total={values.length} hasFilters={hasFilters} reset={reset}>
        <label className="min-w-0 flex-1 basis-48 text-sm">وضعیت فلو<select className={directoryField} value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="active">همهٔ غیربایگانی‌ها</option><option value="published">منتشرشده</option><option value="draft">فقط پیش‌نویس</option><option value="archived">بایگانی‌شده</option><option value="all">همهٔ فلوها</option></select></label>
        <label className="min-w-0 flex-1 basis-36 text-sm">ترتیب نمایش<select className={directoryField} value={sort} onChange={event => { setSort(event.target.value); setPage(1) }}><option value="registered">ترتیب ثبت</option><option value="name">نام فلو</option></select></label>
      </DirectoryToolbar>
      {editing && list.data.can_edit && (options.data ? <FlowEditor key={`${workspace}:${value?.id || 'new'}:${value?.revision || 1}`} project={projectId} value={value} options={options.data} saved={saved} cancel={() => setEditing(false)} refreshOptions={() => options.refetch()} updatingOptions={options.isFetching} optionsFailed={options.isError} remoteChanged={remoteChanged} /> : <FormDialog open title={selected ? 'ویرایش فلو' : 'ساخت فلو'} description="برنامه‌های منتشرشده و اعضای پروژه برای تنظیم مراحل دریافت می‌شوند." close={() => setEditing(false)}><p role={options.isError ? 'alert' : 'status'}>{options.isError ? 'دریافت برنامه‌ها و اعضا انجام نشد.' : 'در حال دریافت مسئولان…'}</p>{options.isError && <button className={button} onClick={() => options.refetch()}>تلاش دوباره</button>}</FormDialog>)}
      {!results.items.length ? <DirectoryEmpty filtered={hasFilters && !!values.length} title="فلویی برای نمایش وجود ندارد" reset={reset}>فلو بسازید و در هر مرحله برنامه، مسئولان و روش اجرا را مشخص کنید.</DirectoryEmpty> : <ul aria-label="فهرست فلوهای تیم" className="m-0 list-none space-y-4 p-0">{results.items.map(flow => <li key={`${workspace}:${flow.id}:${flow.revision}`} className="min-w-0"><FlowCard project={projectId} flow={flow} canEdit={list.data.can_edit} edit={() => { setEditingValue(flow); setEditing(true) }} remove={() => setDeleting(flow)} /></li>)}</ul>}
      <DirectoryPagination value={results} change={setPage} />
      <div className="flex flex-wrap gap-4 border-t border-divider-regular pt-5 text-sm text-text-accent"><Link href="/apps">برنامه‌ها و فرایندها ←</Link><Link href={`/projects/${projectId}/team-runs`}>اجرای تیمی و پیشرفت درخواست‌ها ←</Link></div>
      <p className="text-xs leading-6 text-text-tertiary">ساخت یا انتشار فلو، اجرا را شروع نمی‌کند. شروع رسیدگی از درخواست پذیرفته‌شده و ادامهٔ مراحل با تصمیم مسئول تعیین‌شده انجام می‌شود.</p>
    </>}
    {deleting && list.data?.can_edit && <DeleteTeamEntity project={projectId} kind="flow" value={deleting} close={() => setDeleting(null)} deleted={async () => { await refresh(); setEditing(false); setEditingValue(null) }} />}
  </DirectoryPage>
}
