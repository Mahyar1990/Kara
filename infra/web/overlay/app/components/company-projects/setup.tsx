'use client'

import type { CompanyProject } from '@/service/company-projects'
import { useQuery } from '@tanstack/react-query'
import Link from '@/next/link'
import { adoptionApi } from '@/service/company-adoption'
import { button, panel, ProjectPage, QueryNotice } from './project-page'

function Checklist({ project }: { project: CompanyProject }) {
  const status = useQuery({ queryKey: ['company-setup', project.workspace_id], queryFn: () => adoptionApi.setup(project.id) })
  if (!status.isSuccess) return <QueryNotice error={status.isError} retry={() => status.refetch()} />
  const data = status.data
  return <><section className={panel}><div className="flex flex-wrap items-center justify-between gap-4"><p className="text-lg font-semibold text-text-primary">{data.completed.toLocaleString('fa-IR')} از {data.required.toLocaleString('fa-IR')} گام اصلی انجام شده است</p><button className={button} disabled={status.isFetching} onClick={() => status.refetch()}>به‌روزرسانی وضعیت</button></div><p className="mt-3 text-sm leading-7 text-text-secondary">این وضعیت از اطلاعات واقعی پروژه خوانده می‌شود. اجرای موفق به معنی تأیید کیفیت پاسخ نیست؛ نتیجه را قبل از استفادهٔ تیم بررسی کنید.</p></section>
    <ol className="space-y-4">{data.steps.map((step, index) => <li key={step.id} className={`${panel} flex flex-wrap items-start justify-between gap-4`}><div className="min-w-0 flex-1"><p className="mb-2 text-xs text-text-accent">گام {(index + 1).toLocaleString('fa-IR')} · {step.complete ? 'انجام شده' : step.required ? 'نیازمند اقدام' : 'اختیاری'}</p><h2 className="text-lg font-semibold text-text-primary">{step.title}</h2><p className="mt-2 text-sm leading-7 text-text-secondary">{step.description}</p></div><Link href={step.href} className={button}>باز کردن بخش مربوط</Link></li>)}</ol>
    <section className={panel}><h2 className="text-lg font-semibold text-text-primary">برای فرایندهای مبتنی بر اسناد</h2><p className="mt-2 text-sm leading-7 text-text-secondary">در بخش دانش، اسناد مجاز تیم را اضافه کنید و منتظر پایان پردازش بمانید. سپس دانش را به برنامه متصل کنید. ساخت دانش برای سایر فرایندها الزامی نیست.</p><Link className={`${button} mt-4 inline-block`} href="/datasets">مدیریت دانش پروژه</Link></section>
  </>
}
export default function ProjectSetup({ projectId }: { projectId: string }) {
  return <ProjectPage projectId={projectId} title="راهنمای شروع پروژه">{project => <Checklist project={project} />}</ProjectPage>
}
