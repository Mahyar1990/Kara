'use client'

import { keepPreviousData, useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import Link from '@/next/link'
import { stageApi } from '@/service/company-stages'
import { stageStates, taskLabels, teamStageHref } from '@/utils/company-team-work'
import { button, panel, QueryNotice } from './project-page'
import { DirectorySummary, DirectoryToolbar, DirectoryPagination, DirectoryEmpty, directoryField } from './team-directory'

export default function TeamInbox({ projectId }: { projectId: string }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState('all')
  useEffect(() => { const timer = setTimeout(() => { setSearch(query.trim()); setPage(1) }, 350); return () => clearTimeout(timer) }, [query])
  const tasks = useQuery({ queryKey: ['team-actions', projectId, profile.id, page, search, kind], queryFn: () => stageApi.tasks(projectId, page, search, kind), placeholderData: keepPreviousData, staleTime: 0 })
  const size = tasks.data?.page_size || 25
  const pages = Math.max(1, Math.ceil((tasks.data?.total || 0) / size))
  useEffect(() => { if (tasks.isSuccess && !tasks.isPlaceholderData && page > pages) setPage(pages) }, [tasks.isSuccess, tasks.isPlaceholderData, page, pages])
  const counts = tasks.data?.counts || {}
  const reset = () => { setQuery(''); setSearch(''); setKind('all'); setPage(1) }
  const hasFilters = !!query.trim() || kind !== 'all'
  return <div className="min-w-0 space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-semibold text-text-primary">اقدام بعدی من</h2><p className="mt-2 max-w-3xl text-sm leading-7 text-text-secondary">فقط مرحله‌هایی که اکنون مجوز اقدام در آن‌ها دارید. بررسی خروجی و تصمیم نهایی، اجرای تازه‌ای شروع نمی‌کند.</p></div><button className={button} disabled={tasks.isFetching} onClick={() => void tasks.refetch()}>{tasks.isFetching ? 'در حال تازه‌سازی…' : 'تازه‌سازی کارتابل'}</button></header>
    {tasks.data && <DirectorySummary items={[{ label: 'کل اقدام‌های مجاز من', count: tasks.data.unfiltered_total ?? tasks.data.total }, { label: 'تصمیم نهایی', count: counts.finalize || 0 }, { label: 'اجرا یا تلاش مجدد', count: (counts.run || 0) + (counts.retry || 0) }, { label: 'بررسی، بازخورد و اصلاح', count: (counts.feedback || 0) + (counts.request_decision || 0) + (counts.revalidate || 0) }]} />}
    <DirectoryToolbar query={query} change={setQuery} placeholder="عنوان درخواست یا مرحله" filtered={tasks.data?.total} total={tasks.data?.unfiltered_total ?? tasks.data?.total} hasFilters={hasFilters} reset={reset}><label className="min-w-0 flex-1 basis-48 text-sm">اقدام مورد نیاز<select className={directoryField} value={kind} onChange={event => { setKind(event.target.value); setPage(1) }}><option value="all">همهٔ اقدام‌ها</option>{Object.entries(taskLabels).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label></DirectoryToolbar>
    {(tasks.isFetching || tasks.isPlaceholderData) && <p role="status" className="text-xs text-text-tertiary">در حال دریافت نتیجهٔ جستجو…{tasks.isPlaceholderData && ' موارد قبلی تا دریافت پاسخ تازه نمایش داده می‌شوند.'}</p>}
    {tasks.isError && <QueryNotice error retry={() => tasks.refetch()} />}
    {tasks.isPending && <QueryNotice error={false} retry={() => tasks.refetch()} />}
    {tasks.data && <>{!tasks.data.data.length ? <DirectoryEmpty filtered={hasFilters} title="اکنون مرحله‌ای در انتظار اقدام شما نیست" reset={reset}>برای تصمیم ورود درخواست‌ها به بخش درخواست‌های پروژه و برای پیگیری کار تیم به اجرای تیمی بروید.</DirectoryEmpty> : <ul aria-label="اقدام‌های من" className="m-0 grid list-none grid-cols-1 gap-4 p-0 lg:grid-cols-2">{tasks.data.data.map(task => <li key={`${task.instance_id}:${task.stage_id}`} className="min-w-0"><article className={`${panel} flex h-full min-w-0 flex-col space-y-3 [overflow-wrap:anywhere]`}><p className="text-xs font-semibold text-text-accent">{taskLabels[task.kind] || 'بررسی مرحله'}</p><h3 className="break-words text-lg font-semibold leading-8 text-text-primary">{task.title}</h3><p className="text-sm leading-7 text-text-secondary">{task.stage_title} · {stageStates[task.state] || 'نیاز به بررسی'}</p><p className="text-xs leading-6 text-text-tertiary">اجراکننده: {task.executor.name} · نهایی‌کننده: {task.finalizer.name}</p><details className="text-xs text-text-secondary"><summary className="cursor-pointer">خروجی مورد انتظار</summary><p className="mt-2 leading-6">{task.expected_outputs.join('، ')}</p></details><footer className="mt-auto border-t border-divider-regular pt-4"><Link className={`${button} inline-block`} href={teamStageHref(projectId, task.instance_id, task.stage_id)}>بررسی مرحله و انجام اقدام ←</Link></footer></article></li>)}</ul>}<DirectoryPagination value={{ page, pages, total: tasks.data.total, start: tasks.data.data.length ? (page - 1) * size + 1 : 0, end: tasks.data.data.length ? (page - 1) * size + tasks.data.data.length : 0 }} change={setPage} /></>}
    <footer className="space-y-3 border-t border-divider-regular pt-5"><div className="flex flex-wrap gap-3"><Link className={`${button} inline-block`} href={`/projects/${projectId}/team-runs`}>پیگیری کار تیم و درخواست‌های آماده</Link><Link className={`${button} inline-block`} href={`/projects/${projectId}/requests`}>درخواست‌ها و تصمیم ورود</Link></div><p className="text-xs leading-6 text-text-tertiary">پیشرفت کلی پروژه در اجرای تیمی نمایش داده می‌شود؛ این بخش روی اقدام‌های مرحله‌ای خود شما تمرکز دارد.</p></footer>
  </div>
}
