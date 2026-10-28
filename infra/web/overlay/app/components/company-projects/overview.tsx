'use client'

import type { ReactNode } from 'react'
import type { CompanyProject } from '@/service/company-projects'
import { useQuery } from '@tanstack/react-query'
import Link from '@/next/link'
import { flowApi } from '@/service/company-flows'
import { projectApi } from '@/service/company-projects'
import { requestApi } from '@/service/company-requests'
import { stageApi } from '@/service/company-stages'
import { stageStates, taskLabels, teamStageHref } from '@/utils/company-team-work'

const panel = 'min-w-0 rounded-2xl border border-divider-regular bg-components-panel-bg p-5'
const link = 'rounded-lg text-sm font-medium text-text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4'
const button = 'rounded-xl border border-divider-regular px-4 py-2 text-sm text-text-primary disabled:opacity-50'
const number = (value: number) => value.toLocaleString('fa-IR')
const modes: Record<string, string> = { workflow: 'برنامهٔ فرایندی', 'advanced-chat': 'گفتگو با فرایند', 'agent-chat': 'برنامهٔ ایجنتی', agent: 'برنامهٔ ایجنتی', chat: 'گفتگو', completion: 'تولید متن' }
const requestStates: Record<string, string> = { pending: 'در انتظار تصمیم مالک محصول', approved: 'ورود تأیید شده', rejected: 'ورود رد شده', deferred: 'ورود به تعویق افتاده', revoked: 'تأیید ورود باطل شده', expired: 'تأیید ورود منقضی شده' }

function State({ pending, error, retry, empty, children }: { pending: boolean; error: boolean; retry: () => unknown; empty?: string; children: ReactNode }) {
  if (error) return <div role="alert" className="rounded-xl bg-background-default-subtle p-4 text-sm leading-7 text-text-secondary"><p>دریافت این بخش انجام نشد.</p><button className={`${link} mt-2`} onClick={() => void retry()}>تلاش دوباره</button></div>
  if (pending) return <p role="status" className="py-5 text-sm text-text-tertiary">در حال دریافت اطلاعات…</p>
  if (empty) return <p className="rounded-xl bg-background-default-subtle p-4 text-sm leading-7 text-text-secondary">{empty}</p>
  return children
}

function Metric({ title, value, description, href, failed }: { title: string; value?: number; description: string; href: string; failed: boolean }) {
  return <Link href={href} className={`${panel} block transition-colors hover:bg-background-default-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2`}>
    <p className="text-sm font-medium text-text-secondary">{title}</p>
    <p className="mt-3 text-3xl font-bold text-text-primary">{value === undefined ? '—' : number(value)}</p>
    <p className="mt-2 text-xs leading-6 text-text-tertiary">{failed ? 'اطلاعات دریافت نشد؛ دوباره تلاش کنید.' : value === undefined ? 'در حال دریافت…' : description}</p>
  </Link>
}

function Catalog({ id, title, description, count, href, children }: { id: string; title: string; description: string; count?: number; href: string; children: ReactNode }) {
  return <section aria-labelledby={id} className={`${panel} flex flex-col gap-4`}>
    <header><div className="flex items-start justify-between gap-3"><h3 id={id} className="text-lg font-semibold text-text-primary">{title}</h3>{count !== undefined && <span className="shrink-0 rounded-lg bg-background-default-subtle px-2 py-1 text-xs text-text-secondary">{number(count)}</span>}</div><p className="mt-2 text-xs leading-6 text-text-tertiary">{description}</p></header>
    <div className="min-w-0 flex-1">{children}</div>
    <Link className={`${link} self-start`} href={href}>مشاهدهٔ همهٔ {title} ←</Link>
  </section>
}

export default function ProjectOverview({ project, accountId, opening, openApp, createApp }: { project: CompanyProject; accountId: string; opening: boolean; openApp: (id: string) => void; createApp: () => void }) {
  const base = `/projects/${project.id}`
  const key = ['company-projects', project.workspace_id, project.id, 'overview', accountId]
  const options = { staleTime: 30000 }
  const apps = useQuery({ ...options, queryKey: [...key, 'apps'], queryFn: () => projectApi.apps(project.id, 'all', 1, 4) })
  const flows = useQuery({ ...options, queryKey: [...key, 'flows'], queryFn: () => flowApi.list(project.id) })
  const tasks = useQuery({ ...options, queryKey: [...key, 'tasks'], queryFn: () => stageApi.tasks(project.id, 1) })
  const runs = useQuery({ ...options, queryKey: [...key, 'runs'], queryFn: () => stageApi.list(project.id) })
  const requests = useQuery({ ...options, queryKey: [...key, 'requests'], queryFn: () => requestApi.list(project.id) })
  const visibleFlows = flows.data?.data.filter(value => !value.archived) || []
  const activeRuns = runs.data?.data.filter(value => value.state === 'active') || []
  const published = visibleFlows.filter(value => !!value.current_version_id)
  const readyRequests = runs.data?.available_requests || []
  const pendingRequests = requests.data?.data.filter(value => value.state === 'pending') || []
  const fetching = [apps, flows, tasks, runs, requests].some(query => query.isFetching)
  const refresh = () => { void Promise.all([apps.refetch(), flows.refetch(), tasks.refetch(), runs.refetch(), requests.refetch()]) }
  const sections = [
    { title: 'دانش پروژه', description: 'مستندات محصول و منابع تحلیل', href: '/datasets', icon: 'i-ri-book-open-line' },
    { title: 'سورس کد', description: 'مخزن‌ها و worktreeهای پروژه', href: `${base}/source-code`, icon: 'i-ri-code-box-line' },
    { title: 'مهارت‌ها', description: 'دستورالعمل‌های قابل استفادهٔ مجدد', href: '/skills', icon: 'i-ri-lightbulb-line' },
    { title: 'اعضای پروژه', description: 'همکاران، نقش‌ها و دسترسی‌ها', href: '/users', icon: 'i-ri-team-line' },
  ]
  return <div className="min-w-0 space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs leading-6 text-text-tertiary">اطلاعات زیر مربوط به همین پروژه و مطابق دسترسی شماست.</p><button className={button} disabled={fetching} onClick={refresh}>{fetching ? 'در حال تازه‌سازی…' : 'تازه‌سازی نمای کلی'}</button></div>
    <section aria-label="خلاصهٔ وضعیت پروژه" className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric title="اقدام‌های من" value={tasks.isSuccess ? tasks.data.total : undefined} failed={tasks.isError} description="مرحله‌هایی که اکنون نوبت اقدام شماست" href={`${base}/inbox`} />
      <Metric title="اجراهای تیمی باز" value={runs.isSuccess ? activeRuns.length : undefined} failed={runs.isError} description="در حال انجام یا منتظر اقدام و تصمیم" href={`${base}/team-runs`} />
      <Metric title="برنامه‌های مراحل فلو" value={flows.isSuccess ? new Set(visibleFlows.flatMap(flow => flow.published?.stage_bindings.map(stage => stage.app_id).filter(Boolean) || [])).size : undefined} failed={flows.isError} description="برنامه‌های متصل به نسخه‌های منتشرشدهٔ فلوها" href={`${base}/team-flows`} />
      <Metric title="فلوهای منتشرشده" value={flows.isSuccess ? published.length : undefined} failed={flows.isError} description="فلوهای غیربایگانی دارای نسخهٔ منتشرشده" href={`${base}/team-flows`} />
    </section>

    {runs.isSuccess && readyRequests.length > 0 && <section className={`${panel} flex flex-wrap items-center justify-between gap-4`} aria-label="درخواست‌های آمادهٔ شروع"><div className="min-w-0"><h2 className="font-semibold text-text-primary">{number(readyRequests.length)} درخواست پذیرفته‌شده آمادهٔ شروع است</h2><p className="mt-2 text-sm leading-7 text-text-secondary">در اجرای تیمی، درخواست و نسخهٔ فلو را بررسی کنید و در صورت آماده‌بودن کار را شروع کنید.</p></div><Link className={link} href={`${base}/team-runs`}>بررسی درخواست‌های آماده ←</Link></section>}

    <div className="grid min-w-0 grid-cols-1 items-start gap-5 xl:grid-cols-2">
      <section aria-labelledby="overview-actions" className={`${panel} space-y-4`}>
        <header><h2 id="overview-actions" className="text-xl font-semibold text-text-primary">اقدام بعدی من</h2><p className="mt-2 text-sm leading-7 text-text-secondary">حداکثر ۳ مورد از مرحله‌های آمادهٔ اجرا، بازخورد یا تصمیم شما.</p></header>
        <State pending={tasks.isPending} error={tasks.isError} retry={tasks.refetch} empty={tasks.isSuccess && !tasks.data.data.length ? 'اکنون مرحله‌ای در انتظار اقدام شما نیست. برای ثبت یا پیگیری نیازمندی‌ها، درخواست‌های پروژه را ببینید.' : undefined}>
          <ul className="m-0 list-none divide-y divide-divider-regular p-0">{tasks.data?.data.slice(0, 3).map(task => <li key={`${task.instance_id}:${task.stage_id}`} className="min-w-0 py-4 first:pt-0">
            <p className="text-xs font-medium text-text-accent">{taskLabels[task.kind] || 'بررسی مرحله'}</p><h3 className="mt-2 break-words text-sm font-semibold leading-7 text-text-primary [overflow-wrap:anywhere]">{task.title}</h3>
            <p className="mt-1 break-words text-xs leading-6 text-text-secondary">{task.stage_title} · {stageStates[task.state] || 'نیاز به بررسی'}</p>
            <Link className={`${link} mt-3 inline-block`} href={teamStageHref(project.id, task.instance_id, task.stage_id)}>باز کردن مرحله ←</Link>
          </li>)}</ul>
        </State>
        <div className="flex flex-wrap gap-4 border-t border-divider-regular pt-4"><Link className={link} href={`${base}/inbox`}>همهٔ اقدام‌های من{tasks.isSuccess ? ` (${number(tasks.data.total)})` : ''} ←</Link><Link className={link} href={`${base}/requests`}>درخواست‌های پروژه ←</Link></div>
      </section>

      <section aria-labelledby="overview-progress" className={`${panel} space-y-4`}>
        <header><h2 id="overview-progress" className="text-xl font-semibold text-text-primary">پیشرفت کار تیم</h2><p className="mt-2 text-sm leading-7 text-text-secondary">حداکثر ۳ اجرای باز؛ مرحلهٔ فعلی، مسئول ادامه و پیشرفت کار.</p></header>
        <State pending={runs.isPending} error={runs.isError} retry={runs.refetch} empty={runs.isSuccess && !activeRuns.length ? 'اجرای تیمی بازی وجود ندارد. درخواست‌های پذیرفته‌شده از بخش اجرای تیمی شروع می‌شوند.' : undefined}>
          <ul className="m-0 list-none divide-y divide-divider-regular p-0">{activeRuns.slice(0, 3).map(run => {
            const current = run.stages.find(stage => stage.id === run.current_stage_id)
            return <li key={run.id} className="min-w-0 py-4 first:pt-0">
              <h3 className="break-words text-sm font-semibold leading-7 text-text-primary [overflow-wrap:anywhere]">{run.title}</h3>
              <p className="mt-1 break-words text-xs leading-6 text-text-secondary">{current ? `${current.title} · ${stageStates[current.state] || 'نیاز به بررسی'}` : 'وضعیت مرحله را در اجرای تیمی بررسی کنید.'}</p>
              <progress className="mt-3 h-2 w-full accent-current text-text-accent" max={run.total_stages || 1} value={run.completed_stages} aria-label={`مراحل نهایی‌شدهٔ ${run.title}`} />
              <div className="mt-2 flex flex-wrap justify-between gap-x-4 gap-y-1 text-xs leading-6 text-text-tertiary"><span>{number(run.completed_stages)} از {number(run.total_stages)} مرحله نهایی‌شده</span><span className="break-words">مسئول ادامه: {run.responsibility.kind === 'po' ? 'مالک محصول' : run.responsibility.person?.name || 'نیاز به بررسی'}</span></div>
              {run.responsibility.reason && <p className="mt-2 break-words text-xs leading-6 text-text-secondary [overflow-wrap:anywhere]">{run.responsibility.reason}</p>}
              <Link className={`${link} mt-3 inline-block`} href={`${base}/team-runs?request=${encodeURIComponent(run.request_id)}`}>پیگیری فلو ←</Link>
            </li>
          })}</ul>
        </State>
        <Link className={`${link} inline-block border-t border-divider-regular pt-4`} href={`${base}/team-runs`}>همهٔ اجراها و درخواست‌های آماده ←</Link>
      </section>
    </div>

    <section aria-labelledby="overview-requests" className={`${panel} space-y-4`}>
      <header className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h2 id="overview-requests" className="text-xl font-semibold text-text-primary">درخواست‌های پروژه{requests.isSuccess ? ` (${number(requests.data.data.length)})` : ''}</h2><p className="mt-2 text-sm leading-7 text-text-secondary">نیازمندی‌های ثبت‌شده و تصمیم ورود آن‌ها؛ حداکثر ۴ درخواست اخیر نمایش داده می‌شود.</p></div><Link className={link} href={`${base}/requests`}>همهٔ درخواست‌ها و ثبت درخواست ←</Link></header>
      {requests.isSuccess && requests.data.can_decide && pendingRequests.length > 0 && <p className="rounded-xl bg-background-default-subtle p-3 text-sm leading-7 text-text-primary">{number(pendingRequests.length)} درخواست در انتظار تصمیم ورود شماست. آن‌ها را در فهرست درخواست‌ها بررسی کنید.</p>}
      <State pending={requests.isPending} error={requests.isError} retry={requests.refetch} empty={requests.isSuccess && !requests.data.data.length ? 'هنوز درخواستی در این پروژه ثبت نشده است. نیازمندی تازه را از فهرست درخواست‌ها ثبت کنید.' : undefined}>
        <ul className="m-0 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2">{requests.data?.data.slice(0, 4).map(request => <li key={request.id} className="min-w-0"><Link href={`${base}/requests?request=${encodeURIComponent(request.id)}`} className="block h-full rounded-xl border border-divider-regular p-4 hover:bg-background-default-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"><h3 className="break-words text-sm font-semibold leading-7 text-text-primary [overflow-wrap:anywhere]">{request.title}</h3><div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs leading-6 text-text-secondary"><span>{requestStates[request.state] || 'نیاز به بررسی'}</span><span>{request.jira ? `جیرا · ${request.jira.key}` : 'ثبت دستی'}</span>{request.jira?.needs_review && <span className="font-medium text-text-accent">تغییر جیرا نیاز به بررسی دارد</span>}</div></Link></li>)}</ul>
      </State>
    </section>

    <section aria-labelledby="overview-tools" className="min-w-0 space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3"><div className="min-w-0"><h2 id="overview-tools" className="text-xl font-semibold text-text-primary">ابزارهای انجام کار</h2><p className="mt-2 text-sm leading-7 text-text-secondary">ایجنت‌ها را داخل برنامه به کار بگیرید؛ در هر مرحلهٔ فلو، برنامه، مسئولان و روش مجاز اجرا را مشخص کنید.</p></div>{project.can_edit && <button className={button} disabled={opening} onClick={createApp}>ساخت برنامه</button>}</header>
      <div className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-2">
        <Catalog id="overview-apps" title="برنامه‌ها" description="برنامه‌های قابل مشاهده؛ حداکثر ۴ مورد اخیر" count={apps.isSuccess ? apps.data.total : undefined} href="/apps">
          <State pending={apps.isPending} error={apps.isError} retry={apps.refetch} empty={apps.isSuccess && !apps.data.data.length ? 'برنامه‌ای برای شما نمایش داده نمی‌شود. برای شروع می‌توانید قالب‌های آماده را ببینید یا از مدیر پروژه دسترسی بگیرید.' : undefined}>
            <ul className="m-0 list-none divide-y divide-divider-regular p-0">{apps.data?.data.slice(0, 4).map(app => <li key={app.id} className="min-w-0 py-3 first:pt-0"><button disabled={opening} className="block w-full rounded-lg text-start text-sm font-semibold leading-7 text-text-primary hover:text-text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50" onClick={() => openApp(app.id)}><span className="block break-words [overflow-wrap:anywhere]">{app.name}</span></button><p className="mt-1 text-xs text-text-tertiary">{modes[app.mode] || 'برنامه'}</p>{app.description && <p className="mt-1 line-clamp-2 break-words text-xs leading-6 text-text-secondary [overflow-wrap:anywhere]">{app.description}</p>}</li>)}</ul>
          </State>
        </Catalog>
        <Catalog id="overview-flows" title="فلوهای تیم" description="فلوهای قابل مشاهده و غیربایگانی؛ حداکثر ۴ مورد" count={flows.isSuccess ? visibleFlows.length : undefined} href={`${base}/team-flows`}>
          <State pending={flows.isPending} error={flows.isError} retry={flows.refetch} empty={flows.isSuccess && !visibleFlows.length ? 'فلوی غیربایگانی برای شما نمایش داده نمی‌شود. تعریف و انتشار فلو در فهرست فلوهای تیم انجام می‌شود.' : undefined}>
            <ul className="m-0 list-none divide-y divide-divider-regular p-0">{visibleFlows.slice(0, 4).map(flow => <li key={flow.id} className="min-w-0 py-3 first:pt-0"><h4 className="break-words text-sm font-semibold leading-7 text-text-primary [overflow-wrap:anywhere]">{flow.name}</h4><p className="mt-1 text-xs leading-6 text-text-tertiary">{flow.current_version_id ? 'نسخهٔ منتشرشده دارد' : 'پیش‌نویس؛ هنوز منتشر نشده'}</p>{flow.description && <p className="mt-1 line-clamp-2 break-words text-xs leading-6 text-text-secondary [overflow-wrap:anywhere]">{flow.description}</p>}</li>)}</ul>
          </State>
        </Catalog>
      </div>
      <Link className={`${link} inline-block`} href={`${base}/templates`}>شروع با قالب‌های آماده ←</Link>
    </section>

    <section aria-labelledby="overview-resources" className="space-y-4"><h2 id="overview-resources" className="text-xl font-semibold text-text-primary">منابع و اعضای پروژه</h2><div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">{sections.map(section => <Link key={section.href} href={section.href} className={`${panel} block hover:bg-background-default-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2`}><span aria-hidden="true" className={`${section.icon} mb-3 block h-5 w-5 text-text-accent`} /><h3 className="text-sm font-semibold text-text-primary">{section.title}</h3><p className="mt-2 text-xs leading-6 text-text-tertiary">{section.description}</p></Link>)}</div></section>
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-divider-regular pt-5"><p className="text-xs leading-6 text-text-tertiary">باز کردن بخش‌ها، برنامه یا هارنس را اجرا نمی‌کند. نهایی‌سازی مراحل با تصمیم مسئول همان مرحله است.</p><Link className={link} href={`${base}/setup`}>راهنمای پروژه ←</Link></div>
  </div>
}
