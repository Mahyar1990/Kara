'use client'

import type { CompanyProject } from '@/service/company-projects'
import type { StarterTemplate } from '@/service/company-adoption'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import Link from '@/next/link'
import { adoptionApi } from '@/service/company-adoption'
import { button, input, panel, primary, ProjectPage, QueryNotice } from './project-page'

function Library({ project }: { project: CompanyProject }) {
  const catalog = useQuery({ queryKey: ['company-templates', project.workspace_id], queryFn: () => adoptionApi.templates(project.id) })
  const cache = useQueryClient()
  const [selected, setSelected] = useState<StarterTemplate | null>(null)
  const [name, setName] = useState('')
  const [dataset, setDataset] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [created, setCreated] = useState<{ id: string; name: string } | null>(null)
  const copy = async () => {
    if (!selected || busy) return
    setBusy(true); setError(''); setCreated(null)
    try {
      const result = await adoptionApi.copy(project.id, selected.id, { name: name.trim(), ...(selected.requires_knowledge ? { dataset_id: dataset } : {}) })
      setCreated(result); setSelected(null)
      await cache.invalidateQueries({ queryKey: ['company-projects'] })
      await cache.invalidateQueries({ queryKey: ['company-setup'] })
    }
    catch { setError('ساخت برنامه انجام نشد. مدل پیش‌فرض، آماده بودن دانش و دسترسی توسعهٔ خود را بررسی کنید. برای اطمینان از ساخته نشدن برنامه، فهرست برنامه‌های پروژه را هم بررسی کنید.') }
    finally { setBusy(false) }
  }
  if (!catalog.isSuccess) return <QueryNotice error={catalog.isError} retry={() => catalog.refetch()} />
  return <><p className="text-sm leading-7 text-text-secondary">از یک قالب شروع کنید. نسخهٔ مستقل در همین پروژه ساخته می‌شود و می‌توانید مراحل و دستورالعمل آن را ویرایش کنید. انتشار و اجرای برنامه با تصمیم تیم انجام می‌شود.</p>
    {!catalog.data.model_name && <section className={panel}><p className="mb-4 text-sm leading-7 text-text-secondary">برای استفاده از قالب‌ها، ابتدا مدل پیش‌فرض این پروژه را تنظیم کنید.</p><Link className={button} href="/integrations/model-provider">تنظیم مدل</Link><button className={`${button} mr-3`} onClick={() => catalog.refetch()}>به‌روزرسانی وضعیت</button></section>}
    {error && <p role="alert" className="text-sm leading-7 text-text-primary">{error}</p>}
    {created && <section className={panel} role="status"><p className="mb-4 text-text-primary">برنامهٔ «{created.name}» ساخته شد. ورودی نمونه را در ویرایشگر آزمایش و نتیجه را بررسی کنید.</p><Link className={primary} href={`/app/${created.id}/workflow`}>باز کردن برنامه</Link></section>}
    {!project.can_edit && <p className="text-sm text-text-secondary">برای ساخت نسخه از قالب به دسترسی توسعه نیاز دارید. از مالک پروژه بخواهید دسترسی شما را بررسی کند.</p>}
    <div className="grid gap-5 md:grid-cols-3">{catalog.data.data.map(template => <article key={template.id} className={`${panel} flex flex-col`}><p className="mb-3 text-xs text-text-accent">نسخهٔ {template.version.replace(/\d/g, value => Number(value).toLocaleString('fa-IR'))}</p><h2 className="text-lg font-semibold text-text-primary">{template.name}</h2><p className="mb-4 mt-3 text-sm leading-7 text-text-secondary">{template.description}</p><p className="mb-5 text-xs leading-6 text-text-tertiary">{template.requires_knowledge ? 'نیازمند انتخاب دانش آمادهٔ همین پروژه' : 'نیازمند مدل پیش‌فرض؛ دانش الزامی نیست'}</p><button className={`${button} mt-auto`} disabled={!project.can_edit || !catalog.data.model_name || busy} onClick={() => { setSelected(template); setName(template.name); setDataset(''); setError(''); setCreated(null) }}>استفاده از قالب</button></article>)}</div>
    {selected && <form aria-label="ساخت برنامه از قالب" className={`${panel} space-y-4`} onSubmit={event => { event.preventDefault(); void copy() }}><h2 className="text-lg font-semibold text-text-primary">ساخت نسخهٔ «{selected.name}»</h2><label className="block text-sm text-text-secondary">نام برنامه<input autoFocus required maxLength={120} className={input} value={name} disabled={busy} onChange={event => setName(event.target.value)} /></label>
      {selected.requires_knowledge && <label className="block text-sm text-text-secondary">دانش پروژه<select required className={input} value={dataset} disabled={busy} onChange={event => setDataset(event.target.value)}><option value="">دانش آماده را انتخاب کنید</option>{catalog.data.datasets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{!catalog.data.datasets.length && <span className="mt-2 block leading-7">دانش آماده‌ای در دسترس نیست. <Link href="/datasets" className="text-text-accent">اسناد را اضافه کنید</Link> و پس از پایان پردازش <button type="button" className="text-text-accent" onClick={() => catalog.refetch()}>وضعیت را به‌روزرسانی کنید</button>.</span>}</label>}
      <div><p className="text-sm text-text-tertiary">ورودی ساختگی برای آزمایش</p><p className="mt-2 whitespace-pre-wrap rounded-xl bg-background-default-subtle p-4 text-sm leading-7 text-text-secondary">{selected.example_input}</p></div><p className="text-xs leading-7 text-text-tertiary">مدل این نسخه: {catalog.data.model_name}. هیچ خروجی، کلید یا تنظیم خصوصی از پروژهٔ دیگری کپی نمی‌شود.</p><div className="flex gap-3"><button className={primary} disabled={busy || !name.trim() || (selected.requires_knowledge && !dataset)}>{busy ? 'در حال ساخت…' : 'ساخت برنامه در این پروژه'}</button><button type="button" className={button} disabled={busy} onClick={() => setSelected(null)}>انصراف</button></div></form>}
  </>
}
export default function ProjectTemplates({ projectId }: { projectId: string }) {
  return <ProjectPage projectId={projectId} title="کتابخانهٔ قالب‌ها">{project => <Library project={project} />}</ProjectPage>
}
