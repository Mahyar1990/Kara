'use client'

import type { CompanyProject } from '@/service/company-projects'
import type { StarterTemplate } from '@/service/company-adoption'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import Link from '@/next/link'
import { adoptionApi } from '@/service/company-adoption'
import { button, input, panel, primary, ProjectPage, QueryNotice } from './project-page'
import FormDialog, { FieldHelp } from './form-dialog'

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
    catch { setError('ساخت برنامه تأیید نشد. ابتدا فهرست برنامه‌های پروژه را بررسی کنید. سپس آماده بودن دانش و مجوز ساخت برنامه را بررسی کنید.') }
    finally { setBusy(false) }
  }
  if (!catalog.isSuccess) return <QueryNotice error={catalog.isError} retry={() => catalog.refetch()} />
  return <><p className="text-sm leading-7 text-text-secondary">یک قالب انتخاب کنید و برنامهٔ خود را بسازید. سپس متن‌ها، مراحل و منابع آن را متناسب با کار تیم تنظیم کنید.</p>

    {error && <p role="alert" className="text-sm leading-7 text-text-primary">{error}</p>}
    {created && <section className={panel} role="status"><p className="mb-4 text-text-primary">برنامهٔ «{created.name}» ساخته شد. برای تنظیم و اجرای آن، برنامه را باز کنید.</p><Link className={primary} href={`/app/${created.id}/workflow`}>باز کردن برنامه</Link></section>}
    {!project.can_edit && <p className="text-sm text-text-secondary">برای ساخت برنامه از قالب، به مجوز ساخت برنامه نیاز دارید. این دسترسی را از مالک پروژه درخواست کنید.</p>}
    <div className="grid gap-5 md:grid-cols-3">{catalog.data.data.map(template => <article key={template.id} className={`${panel} flex flex-col`}><h2 className="text-lg font-semibold text-text-primary">{template.name}</h2><p className="mb-4 mt-3 text-sm leading-7 text-text-secondary">{template.description}</p><p className="mb-5 text-xs leading-6 text-text-tertiary">{template.requires_knowledge ? 'نیازمند دانش پروژه' : 'نیازمند مدل شخصی'}</p><button className={`${button} mt-auto`} disabled={!project.can_edit || busy} onClick={() => { setSelected(template); setName(template.name); setDataset(''); setError(''); setCreated(null) }}>استفاده از قالب</button></article>)}</div>
    {selected && <FormDialog open title={`ساخت برنامه با قالب «${selected.name}»`} description="از این قالب یک برنامهٔ مستقل در پروژه ساخته می‌شود. نام برنامه و در صورت نیاز، دانش آمادهٔ پروژه را انتخاب کنید؛ سپس برنامه را برای تنظیم و بررسی باز کنید." busy={busy} error={error} close={() => setSelected(null)}><form aria-label="ساخت برنامه از قالب" className="space-y-4" onSubmit={event => { event.preventDefault(); void copy() }}><label className="block text-sm text-text-secondary">نام برنامه<input autoFocus required maxLength={120} className={input} value={name} disabled={busy} onChange={event => setName(event.target.value)} /><FieldHelp>نام نسخهٔ مستقل شما در پروژه است؛ می‌توانید نام قالب را متناسب با کاربرد تیم تغییر دهید.</FieldHelp></label>
      {selected.requires_knowledge && <label className="block text-sm text-text-secondary">دانش پروژه<select required className={input} value={dataset} disabled={busy} onChange={event => setDataset(event.target.value)}><option value="">دانش آماده را انتخاب کنید</option>{catalog.data.datasets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{!catalog.data.datasets.length && <span className="mt-2 block leading-7">دانش آماده‌ای در دسترس نیست. <Link href="/datasets" className="text-text-accent">اسناد را اضافه کنید</Link> و پس از پایان پردازش <button type="button" className="text-text-accent" onClick={() => catalog.refetch()}>وضعیت را به‌روزرسانی کنید</button>.</span>}<FieldHelp>دانش آماده‌ای را انتخاب کنید که اطلاعات معتبر لازم برای پاسخ‌های این برنامه را دارد.</FieldHelp></label>}
      <div><p className="text-sm text-text-tertiary">نمونهٔ ورودی</p><p className="mt-2 whitespace-pre-wrap rounded-xl bg-background-default-subtle p-4 text-sm leading-7 text-text-secondary">{selected.example_input}</p></div><p className="text-xs leading-7 text-text-tertiary">مدل برنامه هنگام اجرا از اتصال‌های شخصی اجراکننده انتخاب می‌شود.</p><div className="flex gap-3"><button className={primary} disabled={busy || !name.trim() || (selected.requires_knowledge && !dataset)}>{busy ? 'در حال ساخت…' : 'ساخت برنامه در این پروژه'}</button><button type="button" className={button} disabled={busy} onClick={() => setSelected(null)}>انصراف</button></div></form></FormDialog>}
  </>
}
export default function ProjectTemplates({ projectId }: { projectId: string }) {
  return <ProjectPage projectId={projectId} title="کتابخانهٔ قالب‌ها">{project => <Library project={project} />}</ProjectPage>
}
