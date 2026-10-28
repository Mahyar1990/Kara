'use client'

import type { AgentInput } from '@/service/company-agents'
import type { FlowInput, FlowOptions, FlowStage, StageParticipant } from '@/service/company-flows'
import { DirectionProvider } from '@base-ui/react/direction-provider'
import { Tabs, TabsList, TabsPanel, TabsTab } from '@langgenius/dify-ui/tabs'
import { useRef, useState } from 'react'
import FormDialog, { FieldHelp } from './form-dialog'
import { matchesSearch } from './team-directory'

const button = 'rounded-lg border border-divider-regular px-3 py-2 text-sm disabled:opacity-40'
const primary = `${button} bg-components-button-primary-bg text-components-button-primary-text`
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-sm text-text-primary'
const hint = 'text-xs leading-6 text-text-tertiary'
const number = (value: number) => value.toLocaleString('fa-IR')
export const defaultStageExecution = () => ({ program_enabled: true, enabled: false, instructions: '', requires_source: true })
const stageProgram = (options: FlowOptions, stage: FlowStage) => options.programs.find(value => value.workflow_id === stage.workflow_id && value.app_id === stage.app_id)

export function upgradeStage(stage: FlowStage, options: FlowOptions): FlowStage {
  if (stage.execution) return stage
  const legacy = options.agents.find(value => value.id === stage.agent_id)
  if (!legacy || !options.programs.some(value => value.app_id === legacy.app_id && value.workflow_id === legacy.workflow_id)) return stage
  return { ...stage, agent_id: null, app_id: legacy.app_id, workflow_id: legacy.workflow_id,
    execution: legacy.execution || defaultStageExecution(), participants: (legacy.participants || []).filter(person => ![stage.executor_id, stage.finalizer_id].includes(person.account_id)) }
}

function currentPerson(stage: FlowStage, options: FlowOptions, prefix: 'executor' | 'finalizer') {
  return options.members.find(member => member.account_id === stage[`${prefix}_id`] && member.membership_id === stage[`${prefix}_membership_id`])
}

export function FlowStageRow({ stage, index, total, options, edit, move, remove }: {
  stage: FlowStage; index: number; total: number; options: FlowOptions; edit: () => void; move: (offset: number) => void; remove: () => void
}) {
  const source = stageProgram(options, stage)
  const legacy = options.agents.find(value => value.id === stage.agent_id)
  const executor = currentPerson(stage, options, 'executor')
  const finalizer = currentPerson(stage, options, 'finalizer')
  const needsReview = !source || !executor || !finalizer || (!!stage.decision_role && !finalizer.roles.includes(stage.decision_role)) || !stage.title.trim()
  return <article className="flex min-w-0 flex-wrap items-center gap-3 rounded-xl border border-divider-regular bg-background-default p-3 [overflow-wrap:anywhere]">
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-background-section text-sm font-semibold" aria-label={`مرحلهٔ ${number(index + 1)}`}>{number(index + 1)}</span>
    <div className="min-w-0 flex-1 basis-64 space-y-1">
      <div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{stage.title || 'مرحلهٔ بدون عنوان'}</h3>{needsReview && <span className="rounded-full bg-background-section px-2 py-0.5 text-xs text-text-secondary">نیازمند بازبینی</span>}</div>
      <p className={hint}>{source ? `${source.app_name} · ${source.version}` : legacy ? `${legacy.app_name} · تنظیم قبلی` : 'برنامه انتخاب نشده'}</p>
      <p className={hint}>اجرا: {executor?.name || 'انتخاب نشده'} · نهایی‌سازی: {finalizer?.name || 'انتخاب نشده'}</p>
    </div>
    <div className="flex flex-wrap items-center gap-2" aria-label={`اقدام‌های مرحلهٔ ${stage.title || number(index + 1)}`}>
      <button type="button" className={button} onClick={edit} aria-label={`ویرایش مرحلهٔ ${stage.title || number(index + 1)}`}>ویرایش مرحله</button>
      <button type="button" className={button} disabled={index === 0} onClick={() => move(-1)} aria-label={`انتقال ${stage.title} به بالا`}>بالا</button>
      <button type="button" className={button} disabled={index === total - 1} onClick={() => move(1)} aria-label={`انتقال ${stage.title} به پایین`}>پایین</button>
      <button type="button" className={`${button} text-text-destructive-secondary`} onClick={remove} aria-label={`حذف مرحلهٔ ${stage.title}`}>حذف مرحله</button>
    </div>
  </article>
}
function InputBinding({ item, value, previous, options, change }: { item: AgentInput; value?: FlowInput; previous: FlowStage[]; options: FlowOptions; change: (value?: FlowInput) => void }) {
  const selected = value?.source === 'stage' ? JSON.stringify({ source: 'stage', stage_key: value.stage_key, output: value.output }) : value?.source || ''
  const choose = (text: string) => {
    if (!text) change()
    else if (text === 'request') change({ source: 'request' })
    else if (text === 'constant') change({ source: 'constant', value: item.type === 'number' ? 0 : item.type === 'checkbox' ? false : '' })
    else change(JSON.parse(text) as FlowInput)
  }
  return <div className="space-y-2 rounded-lg border border-divider-regular p-3">
    <label className="block text-sm">منبع {item.label}{item.required && ' *'}<select className={field} value={selected} onChange={event => choose(event.target.value)}>
      <option value="">بدون اتصال</option>
      {['text-input', 'paragraph'].includes(item.type) && <option value="request">متن درخواست</option>}
      <option value="constant">مقدار ثابت</option>
      {previous.flatMap(stage => (stageProgram(options, stage)?.output_contract || options.agents.find(agent => agent.id === stage.agent_id)?.output_contract || []).map(output => <option key={`${stage.key}:${output}`} value={JSON.stringify({ source: 'stage', stage_key: stage.key, output })}>خروجی «{stage.title}»: {output}</option>))}
    </select><FieldHelp>متن درخواست: شرح همان درخواست. مقدار ثابت: دادهٔ مشترک همهٔ اجراهای این نسخهٔ فلو. خروجی مرحلهٔ قبل: نتیجهٔ منتخب و نهایی‌شدهٔ آن مرحله. ورودی الزامی را بدون اتصال نگذارید.</FieldHelp></label>
    {value?.source === 'constant' && <label className="block text-sm">مقدار {item.label}
      {item.type === 'checkbox' ? <input className="ms-3" type="checkbox" checked={Boolean(value.value)} onChange={event => change({ source: 'constant', value: event.target.checked })} />
        : item.type === 'select' ? <select className={field} value={String(value.value ?? '')} onChange={event => change({ source: 'constant', value: event.target.value })}><option value="">انتخاب کنید</option>{item.options.map(option => <option key={option}>{option}</option>)}</select>
          : <textarea className={field} maxLength={item.max_length || undefined} value={String(value.value ?? '')} onChange={event => change({ source: 'constant', value: item.type === 'number' && event.target.value !== '' ? Number(event.target.value) : event.target.value })} />}
    <FieldHelp>این مقدار در همهٔ اجراهای همین نسخه استفاده می‌شود؛ اطلاعات متغیر هر درخواست و رمز را اینجا وارد نکنید.</FieldHelp></label>}
  </div>
}

type StageTab = 'general' | 'inputs' | 'execution' | 'access'
const sections: { id: StageTab; label: string }[] = [
  { id: 'general', label: 'مشخصات مرحله' },
  { id: 'inputs', label: 'ورودی‌ها و خروجی‌ها' },
  { id: 'execution', label: 'روش اجرا' },
  { id: 'access', label: 'مسئولان و دسترسی' },
]

export default function FlowStageEditor({ value, index, stages, options, apply, close, refreshOptions, updatingOptions, optionsFailed }: {
  value: FlowStage; index: number; stages: FlowStage[]; options: FlowOptions; apply: (value: FlowStage) => void; close: () => void
  refreshOptions: () => unknown; updatingOptions: boolean; optionsFailed: boolean
}) {
  // The dialog edits its own draft. Switching tabs never drops values; cancel
  // leaves the enclosing flow draft unchanged, and applying does not publish it.
  const [stage, setStage] = useState(value)
  const [tab, setTab] = useState<StageTab>('general')
  const [error, setError] = useState('')
  const [memberQuery, setMemberQuery] = useState('')
  const titleInput = useRef<HTMLInputElement>(null)
  const source = stageProgram(options, stage)
  const legacy = options.agents.find(item => item.id === stage.agent_id)
  const cfg = stage.execution || legacy?.execution || defaultStageExecution()
  const participants = stage.participants || []
  const executor = currentPerson(stage, options, 'executor')
  const finalizer = currentPerson(stage, options, 'finalizer')
  const executorEligible = executor && (stage.execution || legacy?.runners.includes(executor.account_id)) ? executor : undefined
  const finalizerEligible = finalizer && (stage.execution || legacy?.finalizers.includes(finalizer.account_id)) && (!stage.decision_role || finalizer.roles.includes(stage.decision_role)) ? finalizer : undefined
  const staleParticipants = participants.filter(person => !options.members.some(member => member.account_id === person.account_id && member.membership_id === person.membership_id))
  const programs = [...new Map(options.programs.map(item => [item.app_id, item.app_name])).entries()]
  const versions = options.programs.filter(item => item.app_id === stage.app_id)
  const patch = (next: Partial<FlowStage>) => setStage(current => ({ ...current, ...next }))
  const configure = (next: Partial<typeof cfg>) => setStage(current => ({ ...current, execution: { ...current.execution!, ...next } }))
  const setPerson = (prefix: 'executor' | 'finalizer', id: string) => setStage(current => ({ ...current,
    [`${prefix}_id`]: id || null, [`${prefix}_membership_id`]: options.members.find(member => member.account_id === id)?.membership_id || null,
    participants: current.participants?.filter(person => person.account_id !== id) }))
  const setAccess = (member: FlowOptions['members'][number], permission: 'view' | 'feedback', checked: boolean) => {
    setStage(current => {
      const old = current.participants?.find(person => person.account_id === member.account_id && person.membership_id === member.membership_id)
      const actions: StageParticipant['actions'] = permission === 'view'
        ? checked ? old?.actions.includes('feedback') ? ['view', 'feedback'] : ['view'] : []
        : checked ? ['view', 'feedback'] : old ? ['view'] : []
      return { ...current, participants: [...(current.participants || []).filter(person => person.account_id !== member.account_id),
        ...(actions.length ? [{ account_id: member.account_id, membership_id: member.membership_id, actions }] : [])] }
    })
  }
  const confirm = () => {
    if (!stage.title.trim()) {
      setError('عنوان مرحله را وارد کنید.'); setTab('general')
      requestAnimationFrame(() => titleInput.current?.focus())
      return
    }
    apply(stage)
  }
  const sourceMissing = !!(stage.workflow_id || stage.agent_id) && !source
  const accessNeedsReview = !!stage.executor_id && !executorEligible || !!stage.finalizer_id && !finalizerEligible || staleParticipants.length > 0
  const panelClass = 'min-h-0 min-w-0 flex-1 space-y-5 overflow-y-auto overscroll-contain py-4 pe-2'
  return <FormDialog open wide fixedBody title={`تنظیم مرحلهٔ ${number(index + 1)} · ${stage.title || 'مرحلهٔ جدید'}`}
    description="تنظیمات این مرحله را در تب‌های زیر مشخص کنید. با اعمال تغییرات، به پیش‌نویس فلو برمی‌گردید."
    close={close} footer={<div className="flex flex-wrap items-center justify-between gap-3"><p className="max-w-xl text-xs leading-6 text-text-tertiary">پس از اعمال مرحله، برای ثبت تغییرات، پیش‌نویس فلو را ذخیره کنید.</p><div className="flex gap-2"><button type="button" className={button} onClick={close}>انصراف</button><button type="button" className={primary} onClick={confirm}>اعمال در پیش‌نویس</button></div></div>}>
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex shrink-0 flex-wrap items-center justify-between gap-2 text-xs text-text-secondary"><p>مرحلهٔ {number(index + 1)} · {source?.app_name || legacy?.app_name || 'برنامه انتخاب نشده'}</p><button type="button" className="rounded-lg px-2 py-1 text-text-accent disabled:opacity-40" disabled={updatingOptions} onClick={() => void refreshOptions()}>{updatingOptions ? 'در حال دریافت…' : 'تازه‌سازی اعضا و برنامه‌ها'}</button></div>
      {optionsFailed && <p role="alert" className="mb-2 shrink-0 text-xs leading-6">تازه‌سازی موفق نبود؛ اطلاعات قبلی و تغییرات شما حفظ شده‌اند. پیش از انتشار دوباره تازه‌سازی کنید.</p>}
      <DirectionProvider direction="rtl"><Tabs className="flex min-h-0 min-w-0 flex-1 flex-col" value={tab} onValueChange={next => setTab(next as StageTab)}>
        <TabsList aria-label="بخش‌های تنظیمات مرحله" className="shrink-0 gap-5 overflow-x-auto border-b border-divider-regular">
          {sections.map(section => <TabsTab key={section.id} value={section.id} type="button" className="shrink-0 whitespace-nowrap">{section.label}{(section.id === 'access' && accessNeedsReview || section.id === 'general' && sourceMissing) && <span className="ms-2 text-text-destructive-secondary" aria-label="نیازمند بازبینی">●</span>}</TabsTab>)}
        </TabsList>
        <TabsPanel value="general" className={panelClass}>
          <label className="block text-sm">عنوان مرحله<input ref={titleInput} className={field} maxLength={120} value={stage.title} aria-invalid={!!error} onChange={event => { patch({ title: event.target.value }); setError('') }} /><FieldHelp>کاری که باید در این گام انجام و بررسی شود.</FieldHelp></label>
          {error && <p role="alert" className="text-sm text-text-destructive-secondary">{error}</p>}
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm">برنامهٔ مرحله<select className={field} value={stage.app_id || ''} onChange={event => {
              const appId = event.target.value; const available = options.programs.filter(item => item.app_id === appId)
              patch({ agent_id: null, app_id: appId || null, workflow_id: available[0]?.workflow_id || null, inputs: {}, execution: cfg,
                participants: stage.participants || (legacy?.participants || []).filter(person => ![stage.executor_id, stage.finalizer_id].includes(person.account_id)) })
            }}><option value="">انتخاب برنامهٔ منتشرشده</option>{stage.app_id && !programs.some(([id]) => id === stage.app_id) && <option value={stage.app_id} disabled>برنامهٔ قبلی در دسترس نیست</option>}{programs.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
            <label className="block text-sm">نسخهٔ برنامه<select className={field} value={stage.workflow_id || ''} onChange={event => patch({ workflow_id: event.target.value || null, inputs: {} })}><option value="">انتخاب نسخه</option>{stage.workflow_id && !source && <option value={stage.workflow_id} disabled>نسخهٔ قبلی در دسترس نیست</option>}{versions.map(item => <option key={item.workflow_id} value={item.workflow_id}>{item.version}</option>)}</select><FieldHelp>انتشار نسخهٔ تازهٔ برنامه، این انتخاب را تغییر نمی‌دهد.</FieldHelp></label>
          </div>
          {sourceMissing && <p role="alert" className="rounded-lg bg-background-section p-3 text-sm leading-7">تنظیم قبلی حفظ شده است. برای پیکربندی تازه، برنامه و نسخهٔ منتشرشدهٔ قابل استفاده را انتخاب کنید. نسخه‌ها و اجراهای قبلی حفظ می‌شوند.</p>}
          {stage.execution && <label className="block text-sm">شرح کار و معیار پذیرش<textarea rows={5} className={field} maxLength={32000} value={cfg.instructions} onChange={event => configure({ instructions: event.target.value })} /><FieldHelp>خروجی مورد انتظار و معیار بررسی را بنویسید. مسئولان این متن را هنگام اجرا می‌بینند؛ در ابزار شخصی، همراه بستهٔ مأموریت تحویل می‌شود.</FieldHelp></label>}
        </TabsPanel>
        <TabsPanel value="inputs" className={panelClass}>
          {source ? <><div><h3 className="font-semibold">ورودی‌های مرحله</h3><p className={`mt-1 ${hint}`}>مشخص کنید هر ورودی از متن درخواست، مقدار ثابت یا خروجی نهایی‌شدهٔ مرحلهٔ قبل دریافت شود.</p></div>
            {source.input_contract.length ? source.input_contract.map(item => <InputBinding key={item.variable} item={item} value={stage.inputs[item.variable]} previous={stages.slice(0, index)} options={options} change={value => {
              const inputs = { ...stage.inputs }; if (value) inputs[item.variable] = value; else delete inputs[item.variable]; patch({ inputs })
            }} />) : <p className="text-sm text-text-secondary">این برنامه ورودی قابل تنظیم ندارد.</p>}
            <section className="rounded-xl border border-divider-regular p-4"><h3 className="text-sm font-semibold">خروجی‌های قابل تحویل</h3><div className="mt-3 flex flex-wrap gap-2">{source.output_contract.map(output => <span key={output} className="rounded-lg bg-background-section px-3 py-2 text-sm"><bdi>{output}</bdi></span>)}</div><p className={`mt-3 ${hint}`}>خروجی‌ها از نسخهٔ انتخاب‌شدهٔ برنامه می‌آیند و پس از نهایی‌سازی انسانی به مراحل بعد تحویل می‌شوند.</p></section>
          </> : <p className="rounded-lg bg-background-section p-4 text-sm leading-7">ابتدا برنامه و نسخه را در تب «مشخصات مرحله» انتخاب کنید.</p>}
        </TabsPanel>
        <TabsPanel value="execution" className={panelClass}>
          {stage.execution ? <><div><h3 className="font-semibold">روش‌های مجاز انجام کار</h3><p className={`mt-1 ${hint}`}>مجری هنگام شروع مرحله، از روش‌های مجاز زیر انتخاب می‌کند.</p></div>
            <label className="flex items-start gap-3 rounded-xl border border-divider-regular p-4 text-sm"><input className="mt-1" type="checkbox" checked={cfg.program_enabled} onChange={event => configure({ program_enabled: event.target.checked })} /><span><span className="block font-medium">اجرای مراحل برنامه</span><span className={`mt-1 block ${hint}`}>اجرای نسخهٔ انتخاب‌شده با تنظیمات شخصی مجری.</span></span></label>
            <label className="flex items-start gap-3 rounded-xl border border-divider-regular p-4 text-sm"><input className="mt-1" type="checkbox" checked={cfg.enabled} disabled={!!source && !source.harness_compatible && !cfg.enabled} onChange={event => configure({ enabled: event.target.checked })} /><span><span className="block font-medium">انجام کار با ابزار شخصی</span><span className={`mt-1 block ${hint}`}>مجری دستگاه، ابزار و سورس خود را هنگام اجرا انتخاب می‌کند.</span></span></label>
            {source && !source.harness_compatible && <p className="text-sm leading-7">{source.harness_reason}</p>}
            {cfg.enabled && <div className="space-y-3 rounded-xl bg-background-section p-4"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cfg.requires_source} onChange={event => configure({ requires_source: event.target.checked })} />سورس آماده‌شده الزامی است</label><p className={hint}>شرح کار و معیار پذیرش را در تب «مشخصات مرحله» کامل کنید.</p></div>}
            {cfg.program_enabled && source?.execution_plan && <section className="space-y-3 rounded-xl border border-divider-regular p-4"><h3 className="text-sm font-semibold">گام‌های اجرای این برنامه</h3><p className={hint}>مسئول اجرا هنگام شروع، مدل هر LLM و Runner هر گام اجرایی را از اتصال‌ها و دستگاه‌های شخصی خودش انتخاب می‌کند. این انتخاب‌ها همراه همان اجرا ثبت می‌شوند.</p><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-divider-regular text-start"><th className="p-2 text-start">گام</th><th className="p-2 text-start">مدل</th><th className="p-2 text-start">دستگاه اجرا (Runner)</th></tr></thead><tbody>{source.execution_plan.nodes.map(node => <tr key={node.id} className="border-b border-divider-regular"><td className="p-2">{node.title}</td><td className="p-2">{node.type === 'llm' ? 'انتخاب مستقل توسط مجری' : 'لازم ندارد'}</td><td className="p-2">{node.runner_required ? 'انتخاب دستگاه برای همین گام' : 'بدون Runner جدا؛ توسط هماهنگ‌کننده'}</td></tr>)}</tbody></table></div></section>}
            {!cfg.program_enabled && !cfg.enabled && <p role="alert" className="text-sm text-text-destructive-secondary">برای انتشار فلو، حداقل یک روش اجرا را فعال کنید.</p>}
          </> : <p className="rounded-lg bg-background-section p-4 text-sm leading-7">برای تنظیم روش اجرای مستقل این مرحله، ابتدا برنامه را در تب «مشخصات مرحله» انتخاب کنید. تنظیم قبلی تا آن زمان حفظ می‌شود.</p>}
        </TabsPanel>
        <TabsPanel value="access" className={panelClass}>
          <div className="grid gap-4 md:grid-cols-3">
            <label className="block text-sm">مسئول اجرا<select className={field} value={executorEligible ? stage.executor_id || '' : ''} onChange={event => setPerson('executor', event.target.value)}><option value="">انتخاب کنید</option>{options.members.filter(member => stage.execution || legacy?.runners.includes(member.account_id)).map(member => <option key={member.membership_id} value={member.account_id}>{member.name}</option>)}</select></label>
            <label className="block text-sm">نقش لازم برای تصمیم<select className={field} value={stage.decision_role || ''} onChange={event => patch({ decision_role: event.target.value as FlowStage['decision_role'] || null, finalizer_id: null, finalizer_membership_id: null })}><option value="">همان نهایی‌کنندهٔ منتخب</option><option value="po">مالک محصول (PO)</option><option value="tl">راهبر فنی (TL)</option></select></label>
            <label className="block text-sm">نهایی‌کننده<select className={field} value={finalizerEligible ? stage.finalizer_id || '' : ''} onChange={event => setPerson('finalizer', event.target.value)}><option value="">انتخاب کنید</option>{options.members.filter(member => (stage.execution || legacy?.finalizers.includes(member.account_id)) && (!stage.decision_role || member.roles.includes(stage.decision_role))).map(member => <option key={member.membership_id} value={member.account_id}>{member.name}</option>)}</select></label>
          </div>
          {stage.executor_id && !executorEligible && <p role="alert" className="text-sm">عضویت یا دسترسی مسئول اجرا تغییر کرده است؛ مسئول را دوباره انتخاب کنید.</p>}
          {stage.finalizer_id && !finalizerEligible && <p role="alert" className="text-sm">عضویت یا نقش نهایی‌کننده تغییر کرده است؛ فرد واجد شرایط را دوباره انتخاب کنید.</p>}
          <p className={hint}>دسترسی‌های مسئول اجرا و نهایی‌کننده از انتخاب‌های بالا می‌آیند. برای سایر همکاران، مشاهده و بازخورد همین مرحله را مشخص کنید. بازخورد، مشاهده را هم فعال می‌کند.</p>
          {!stage.execution && <p className="text-sm leading-7">دسترسی تنظیم قبلی نمایش داده می‌شود. برای تغییر دسترسی مستقل این مرحله، برنامه را در تب «مشخصات مرحله» انتخاب کنید.</p>}
          {staleParticipants.length > 0 && <div role="alert" className="space-y-3 rounded-lg bg-background-section p-3 text-sm leading-7"><p>عضویت این همکاران تغییر کرده یا دیگر فعال نیست. دسترسی قبلی را حذف یا برای عضویت فعلی دوباره انتخاب کنید.</p>{staleParticipants.map((person, i) => <div key={person.account_id} className="flex flex-wrap items-center justify-between gap-2"><span>{options.members.find(member => member.account_id === person.account_id)?.name || `همکار قبلی ${number(i + 1)}`}</span><button type="button" className={button} onClick={() => patch({ participants: participants.filter(item => item.account_id !== person.account_id) })}>حذف دسترسی قبلی</button></div>)}</div>}
          {(options.members.length > 8 || !!memberQuery) && <label className="block text-sm">جست‌وجوی عضو<input type="search" className={field} value={memberQuery} onChange={event => setMemberQuery(event.target.value)} /></label>}
          <div className="overflow-x-auto rounded-xl border border-divider-regular">
            <table className="w-full min-w-[36rem] text-sm"><caption className="sr-only">مجوزهای اعضا در همین مرحله</caption><thead className="bg-background-section text-text-secondary"><tr><th scope="col" className="p-3 text-start">عضو و مسئولیت</th>{['مشاهده', 'اجرا', 'بازخورد', 'نهایی‌سازی'].map(label => <th scope="col" className="px-3 py-3 text-center" key={label}>{label}</th>)}</tr></thead><tbody>
              {options.members.filter(member => matchesSearch(memberQuery, member.name)).map(member => {
                const roleAccount = [stage.executor_id, stage.finalizer_id].includes(member.account_id)
                const runs = executor?.account_id === member.account_id && (!!stage.execution || !!legacy?.runners.includes(member.account_id))
                const finalizes = finalizerEligible?.account_id === member.account_id && (!!stage.execution || !!legacy?.finalizers.includes(member.account_id))
                const assigned = executor?.account_id === member.account_id || finalizer?.account_id === member.account_id
                const person = (stage.execution ? participants : legacy?.participants)?.find(item => item.account_id === member.account_id && item.membership_id === member.membership_id)
                const feedback = !!(stage.execution && assigned || person?.actions.includes('feedback'))
                const views = !!(feedback || runs || finalizes || person?.actions.includes('view'))
                return <tr key={member.membership_id} className="border-t border-divider-regular"><th scope="row" className="p-3 text-start font-normal"><span className="block font-medium">{member.name}</span>{roleAccount && <span className={`mt-1 block ${hint}`}>{[member.account_id === stage.executor_id && 'مسئول اجرا', member.account_id === stage.finalizer_id && 'نهایی‌کننده'].filter(Boolean).join(' و ')}</span>}</th>
                  <td className="p-3 text-center"><input type="checkbox" className="h-4 w-4 accent-current text-text-accent" aria-label={`مشاهده برای ${member.name}`} checked={views} disabled={!stage.execution || roleAccount} onChange={event => setAccess(member, 'view', event.target.checked)} /></td>
                  <td className="p-3 text-center"><input type="checkbox" className="h-4 w-4 accent-current text-text-accent" aria-label={`اجرا برای ${member.name}؛ از انتخاب مسئول اجرا تعیین می‌شود`} checked={!!runs} disabled /></td>
                  <td className="p-3 text-center"><input type="checkbox" className="h-4 w-4 accent-current text-text-accent" aria-label={`بازخورد برای ${member.name}`} checked={feedback} disabled={!stage.execution || roleAccount} onChange={event => setAccess(member, 'feedback', event.target.checked)} /></td>
                  <td className="p-3 text-center"><input type="checkbox" className="h-4 w-4 accent-current text-text-accent" aria-label={`نهایی‌سازی برای ${member.name}؛ از انتخاب نهایی‌کننده تعیین می‌شود`} checked={!!finalizes} disabled /></td>
                </tr>
              })}
              {!options.members.some(member => matchesSearch(memberQuery, member.name)) && <tr><td colSpan={5} className="p-5 text-center text-text-tertiary">عضوی با این نام پیدا نشد.</td></tr>}
            </tbody></table>
          </div>
        </TabsPanel>
      </Tabs></DirectionProvider>
    </div>
  </FormDialog>
}
