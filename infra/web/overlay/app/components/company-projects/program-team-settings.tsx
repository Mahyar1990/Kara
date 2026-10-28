'use client'

import type { TeamProgram } from '@/service/company-program-team'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useEffect, useRef, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import Link from '@/next/link'
import { useSearchParams } from '@/next/navigation'
import { agentApi } from '@/service/company-agents'
import { programTeamApi } from '@/service/company-program-team'
import { projectApi } from '@/service/company-projects'
import FormDialog, { FieldHelp } from './form-dialog'
import { ProgramSettingsCard, useTeamAction } from './team-agents'
import { DirectoryPage, DirectoryNotice, DirectoryToolbar, DirectoryPagination, DirectoryEmpty, directoryButton, directoryField, matchesSearch, resultPage, number } from './team-directory'

function RegisterSettings({ project, program, refresh }: { project: string; program: TeamProgram; refresh: () => Promise<unknown> }) {
  const [open, setOpen] = useState(false)
  const sources = useQuery({ queryKey: ['team-agent-sources', project], queryFn: () => agentApi.sources(project), enabled: open })
  const versions = sources.data?.data.filter(value => value.app_id === program.id) || []
  const [workflowId, setWorkflowId] = useState('')
  const [name, setName] = useState(program.name.slice(0, 120))
  const [description, setDescription] = useState('')
  const [reviewed, setReviewed] = useState(false)
  const action = useTeamAction()
  const source = versions.find(value => value.workflow_id === workflowId)
  const ready = !!source && sources.isSuccess && !sources.isFetching
  const save = () => {
    if (!ready || !reviewed) return
    const body = { app_id: program.id, workflow_id: source.workflow_id, name, description, expected_revision: 1 }
    void action.run(body, async key => { await agentApi.register(project, body, key); await refresh(); setOpen(false); setWorkflowId(''); setReviewed(false) })
  }
  return <>
    <button className={directoryButton} onClick={() => setOpen(true)}>{program.profiles.length ? 'افزودن تنظیم مستقل' : 'فعال‌کردن استفادهٔ تیمی'}</button>
    <FormDialog open={open} title={`تنظیمات تیمی ${program.name}`} description="نسخهٔ برنامه را مشخص کنید؛ سپس دسترسی اعضا و روش‌های مجاز اجرا را در همین برنامه تنظیم کنید." busy={action.busy} close={() => setOpen(false)}>
      <form className="space-y-4" onSubmit={event => { event.preventDefault(); save() }}>
        <fieldset disabled={action.busy} className="space-y-4">
          {sources.isError && <p role="alert">دریافت نسخه‌ها انجام نشد. <button type="button" onClick={() => { setReviewed(false); void sources.refetch() }}>تلاش دوباره</button></p>}
          {sources.isPending && <p role="status">در حال دریافت نسخه‌ها…</p>}
          {sources.isSuccess && !versions.length && <p className="text-sm leading-7">ابتدا برنامه را با شروع دستی و خروجی مشخص منتشر کنید. فقط نسخه‌های سازگار با اجرای تیمی قابل انتخاب‌اند.</p>}
          <label className="block text-sm">نسخهٔ منتشرشده<select required className={directoryField} value={workflowId} onChange={event => { setWorkflowId(event.target.value); setReviewed(false) }}><option value="">انتخاب کنید</option>{versions.map(value => <option key={value.workflow_id} value={value.workflow_id}>{value.version}</option>)}</select><FieldHelp>انتشار بعدی برنامه، این انتخاب و فلوهای موجود را خودکار تغییر نمی‌دهد.</FieldHelp></label>
          {!!program.profiles.length && <label className="block text-sm">نام تنظیم<input required maxLength={120} className={directoryField} value={name} onChange={event => setName(event.target.value)} /><FieldHelp>برای استفادهٔ معمول، نام برنامه کافی است؛ تنظیم‌های مستقل را با نام قابل تشخیص مشخص کنید.</FieldHelp></label>}
          <label className="block text-sm">توضیح<textarea maxLength={2000} className={directoryField} value={description} onChange={event => setDescription(event.target.value)} /></label>
          {source && <p className="text-sm leading-7">ورودی‌ها: {source.input_contract.map(item => item.label).join('، ') || 'ندارد'} · خروجی‌ها: {source.output_contract.join('، ')}</p>}
          <label className="flex items-start gap-2 text-sm leading-7"><input type="checkbox" className="mt-2" checked={reviewed} disabled={!ready} onChange={event => setReviewed(event.target.checked)} /><span>نسخه و قرارداد اجرا را بررسی کردم و دسترسی اعضا را پس از ثبت مشخص می‌کنم.<FieldHelp>اجرای برنامه از مسیر کنترل‌شدهٔ تیمی انجام می‌شود. ویرایش و انتشار منبع مشترک به مجوز مربوط در همهٔ تنظیم‌های فعال نیاز دارد. موفقیت اجرا جای نهایی‌سازی انسانی را نمی‌گیرد.</FieldHelp></span></label>
        </fieldset>
        {action.error && <p role="alert">{action.error}</p>}
        <div className="flex gap-3"><button type="submit" className={directoryButton} disabled={action.busy || !ready || !reviewed || !name.trim()}>ذخیرهٔ تنظیم تیمی</button><button type="button" className={directoryButton} disabled={action.busy} onClick={() => setOpen(false)}>انصراف</button></div>
      </form>
    </FormDialog>
  </>
}

function ProgramCard({ project, program, canManage, focused, refresh }: { project: string; program: TeamProgram; canManage: boolean; focused: boolean; refresh: () => Promise<unknown> }) {
  const [open, setOpen] = useState(focused)
  useEffect(() => { if (focused) setOpen(true) }, [focused])
  return <details open={open} onToggle={event => setOpen(event.currentTarget.open)} className="min-w-0 rounded-2xl border border-divider-regular bg-components-panel-bg p-5 [overflow-wrap:anywhere]">
    <summary className="cursor-pointer leading-8"><span className="text-xl font-semibold">{program.name}</span><span className="mt-1 block text-xs leading-6 text-text-tertiary">{number(program.profiles.filter(value => !value.archived).length)} تنظیم فعال · {program.library_adapter ? 'اتصال کتابخانه با طراحی ثابت' : 'برنامهٔ فرایندی'}</span></summary>
    <div className="mt-5 space-y-4">
      {program.description && <p className="whitespace-pre-wrap text-sm leading-7">{program.description}</p>}
      {!program.available && <p role="status" className="text-sm">منبع برنامه اکنون در دسترس اجرا نیست؛ تنظیم‌ها برای بررسی سابقه نمایش داده می‌شوند.</p>}
      <div className="flex flex-wrap gap-3">{canManage && program.available && !program.library_adapter && !program.profiles.length && <RegisterSettings project={project} program={program} refresh={refresh} />}<Link className={directoryButton} href={`/projects/${project}/team-flows`}>استفاده در فلو</Link></div>
      {program.library_adapter && <p className="text-sm leading-7 text-text-secondary">دسترسی‌ها و روش اجرای این اتصال حفظ شده‌اند. برای طراحی قابل ویرایش، از کتابخانهٔ ایجنت‌ها یک برنامهٔ تازه بسازید.</p>}
      {!program.profiles.length && <p className="text-sm leading-7 text-text-secondary">هنوز تنظیم تیمی ندارد. پس از انتشار برنامه، استفادهٔ تیمی را فعال و مجوز اعضا را مشخص کنید.</p>}
      {program.profiles.length > 1 && <p className="text-xs leading-6 text-text-secondary">هر تنظیم، نسخه و دسترسی مستقل دارد. در فلو، تنظیم موردنظر را صریح انتخاب کنید.</p>}
      {canManage && program.available && !program.library_adapter && !!program.profiles.length && <details className="text-sm"><summary className="cursor-pointer text-text-secondary">تنظیم پیشرفته: استفادهٔ مستقل از نسخه یا دسترسی دیگر</summary><div className="mt-3"><RegisterSettings project={project} program={program} refresh={refresh} /></div></details>}
      {program.profiles.map(profile => <ProgramSettingsCard key={profile.id} project={project} agent={profile} canManage={canManage} refresh={refresh} />)}
    </div>
  </details>
}

export default function ProgramTeamSettings({ projectId }: { projectId: string }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const cache = useQueryClient()
  const params = useSearchParams()
  const selected = params.get('program')
  const linkedAgent = params.get('agent')
  const linkedAttempt = params.get('harness_attempt')
  const focused = useRef('')
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const entered = context.data?.current_project?.id === projectId
  const list = useQuery({ queryKey: ['program-team', workspace, projectId], queryFn: () => programTeamApi.list(projectId), enabled: entered })
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  const programs = list.data?.programs || []
  const target = linkedAgent ? programs.find(program => program.profiles.some(profile => profile.id === linkedAgent))?.id : selected
  useEffect(() => { setQuery(''); setStatus('all'); setPage(1); focused.current = '' }, [workspace, projectId])
  useEffect(() => {
    const marker = `${workspace}:${projectId}:${selected}:${linkedAgent}:${linkedAttempt}`
    if (!target || !list.data || focused.current === marker) return
    focused.current = marker; setQuery(''); setStatus('all'); setPage(1)
  }, [target, list.data, selected, linkedAgent, linkedAttempt, workspace, projectId])
  const refresh = async () => {
    const result = await list.refetch()
    await Promise.all([
      cache.invalidateQueries({ queryKey: ['team-flow-options'] }),
      cache.invalidateQueries({ queryKey: ['company-projects', workspace, projectId, 'overview'] }),
    ])
    return result
  }
  const scoped = target ? programs.filter(program => program.id === target) : selected || linkedAgent ? [] : programs
  const filtered = scoped.filter(program => matchesSearch(query, program.name, program.description, ...program.profiles.map(profile => profile.name)) && (status === 'all' || (status === 'active' ? program.profiles.some(profile => !profile.archived) : !program.profiles.length)))
  const results = resultPage(filtered, page)
  const visible = new Set(results.items.map(program => program.id))
  const reset = () => { setQuery(''); setStatus('all'); setPage(1) }
  return <DirectoryPage project={projectId} title={target ? `تنظیمات تیمی ${scoped[0]?.name || 'برنامه'}` : 'تنظیمات تیمی برنامه‌ها'} description="نسخهٔ قابل اجرا، مجوز اعضا، روش‌های مجاز اجرا و قرارداد ورودی و خروجی را در برنامه مدیریت کنید. مسئولان و تحویل خروجی هر مرحله در فلو تعیین می‌شوند." actions={<><Link href="/apps" className={directoryButton}>برنامه‌ها و فرایندها</Link><button className={directoryButton} disabled={!entered || list.isFetching} onClick={() => void refresh()}>تازه‌سازی</button></>}>
    <DirectoryNotice project={projectId} entered={!!entered} loading={context.isPending || (!!entered && list.isPending)} error={context.isError || (!!entered && list.isError)} retry={() => context.isError ? context.refetch() : refresh()} />
    {entered && list.data && <>
      {(selected || linkedAgent) && <Link className="text-sm text-text-accent" href={`/projects/${projectId}/program-settings`}>تنظیمات همهٔ برنامه‌ها ←</Link>}
      {(selected || linkedAgent) && !scoped.length && <p role="alert">برنامه یا تنظیم در دسترس شما نیست؛ عضویت، مجوز و وضعیت آن را بررسی کنید.</p>}
      <DirectoryToolbar query={query} change={value => { setQuery(value); setPage(1) }} placeholder="نام برنامه یا تنظیم تیمی" filtered={filtered.length} total={scoped.length} hasFilters={!!query.trim() || status !== 'all'} reset={reset}>
        <label className="text-sm">وضعیت<select className={directoryField} value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="all">همه</option><option value="active">دارای تنظیم فعال</option><option value="unconfigured">بدون تنظیم تیمی</option></select></label>
      </DirectoryToolbar>
      {!filtered.length && !selected && !linkedAgent && <DirectoryEmpty filtered={!!query.trim() || status !== 'all'} title="برنامه‌ای برای استفادهٔ تیمی در دسترس نیست" reset={reset}>مدیر پروژه می‌تواند برنامه را منتشر و دسترسی اعضا را در تنظیمات تیمی آن مشخص کند.</DirectoryEmpty>}
      {scoped.map(program => <div key={`${workspace}:${projectId}:${program.id}`} hidden={!visible.has(program.id)}><ProgramCard project={projectId} program={program} canManage={list.data.can_manage} focused={target === program.id} refresh={refresh} /></div>)}
      <DirectoryPagination value={results} change={setPage} />
      <p className="text-xs leading-7 text-text-tertiary">بستن پنل یا تغییر فیلتر، اجرای جاری را لغو نمی‌کند. برای انجام مرحلهٔ یک فلو، از کارتابل همان مرحله استفاده کنید. اجرای موفق به معنی تأیید انسانی نیست.</p>
    </>}
  </DirectoryPage>
}
