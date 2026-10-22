'use client'

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import Link from '@/next/link'
import { stageApi } from '@/service/company-stages'
import { stageStates, taskLabels, teamStageHref } from '@/utils/company-team-work'
import { button, panel, QueryNotice } from './project-page'

const num = (value: number) => value.toLocaleString('fa-IR')

export default function TeamInbox({ projectId }: { projectId: string }) {
  const [page, setPage] = useState(1)
  const tasks = useQuery({ queryKey: ['team-actions', projectId, page], queryFn: () => stageApi.tasks(projectId, page), staleTime: 0 })
  const progress = useQuery({ queryKey: ['team-instances', projectId], queryFn: () => stageApi.list(projectId), staleTime: 0 })
  const refresh = () => { void tasks.refetch(); void progress.refetch() }
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold text-text-primary">اقدام‌های من</h2><p className="mt-2 text-sm leading-7 text-text-secondary">مرحله و تصمیمی که اکنون مجوز انجامش را دارید. باز کردن کارتابل یا مرحله، ایجنتی را اجرا نمی‌کند.</p></div><button className={button} disabled={tasks.isFetching || progress.isFetching} onClick={refresh}>تازه‌سازی کارتابل</button></div>
    {!tasks.isSuccess ? <QueryNotice error={tasks.isError} retry={() => tasks.refetch()} /> : <section aria-label="اقدام‌های من" className="space-y-4"><p className="text-sm text-text-secondary">{num(tasks.data.total)} اقدام در انتظار شما</p>{!tasks.data.data.length && <p className={panel}>در حال حاضر اقدام آماده‌ای با مجوز فعلی شما وجود ندارد.</p>}{tasks.data.data.map(task => <article className={`${panel} space-y-3`} key={`${task.instance_id}:${task.stage_id}`}><h3 className="text-lg font-semibold text-text-primary">{task.title}</h3><p className="text-sm text-text-secondary">{task.stage_title} · {stageStates[task.state]}</p><p className="font-medium text-text-primary">{taskLabels[task.kind]}</p><p className="text-sm text-text-secondary">خروجی مورد نیاز: {task.expected_outputs.join('، ')}</p><p className="text-sm text-text-secondary">اجراکننده: {task.executor.name} · نهایی‌کننده: {task.finalizer.name}</p><Link className={`${button} inline-block`} href={teamStageHref(projectId, task.instance_id, task.stage_id)}>بررسی مرحله و انجام اقدام</Link></article>)}{(page > 1 || tasks.data.has_more) && <nav aria-label="صفحه‌بندی اقدام‌ها" className="flex items-center gap-3"><button className={button} disabled={page === 1} onClick={() => setPage(page - 1)}>صفحهٔ قبل</button><span className="text-sm text-text-secondary">صفحهٔ {num(page)}</span><button className={button} disabled={!tasks.data.has_more} onClick={() => setPage(page + 1)}>صفحهٔ بعد</button></nav>}</section>}
    <section aria-label="وضعیت درخواست‌های تیم" className="space-y-4"><h2 className="text-xl font-semibold text-text-primary">وضعیت درخواست‌های تیم</h2>{!progress.isSuccess ? <QueryNotice error={progress.isError} retry={() => progress.refetch()} /> : <>{!progress.data.data.length && <p className={panel}>هنوز درخواست وارد اجرای تیمی نشده است.</p>}{progress.data.data.map(value => {
      const current = value.stages.find(stage => stage.id === value.current_stage_id)
      return <article key={value.id} className={`${panel} space-y-3`}><h3 className="font-semibold text-text-primary">{value.title}</h3><p className="text-sm text-text-secondary">{num(value.completed_stages)} از {num(value.total_stages)} مرحله نهایی شده{current && ` · مرحلهٔ فعلی: ${current.title} · ${stageStates[current.state]}`}</p><progress className="w-full" aria-label={`پیشرفت ${value.title}`} max={value.total_stages || 1} value={value.completed_stages} /><p className="text-sm text-text-primary">مسئول فعلی: {value.responsibility.kind === 'completed' ? 'فرایند تمام شده است' : value.responsibility.kind === 'po' ? 'مالک محصول' : value.responsibility.person?.name || 'نیاز به بررسی'}</p>{value.responsibility.reason && <p role="status" className="text-sm leading-7 text-text-secondary">{value.responsibility.reason}</p>}<div className="flex flex-wrap gap-3"><Link className={button} href={`/projects/${projectId}/team-runs?request=${value.request_id}`}>پیگیری کل فلو</Link><Link className={button} href={`/projects/${projectId}/requests?request=${value.request_id}`}>درخواست و تصمیم ورود</Link></div></article>
    })}</>}</section>
    <Link className={`${button} inline-block`} href={`/projects/${projectId}/team-runs`}>درخواست‌های آماده و اجراهای تیمی</Link>
  </div>
}
