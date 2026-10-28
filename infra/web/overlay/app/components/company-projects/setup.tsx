'use client'

import type { CompanyProject } from '@/service/company-projects'
import Link from '@/next/link'
import { button, panel, ProjectPage } from './project-page'

function Guide({ project }: { project: CompanyProject }) {
  const sections = [
    { id: 'apps', title: 'برنامه‌ها و فرایندها', description: 'برنامه‌های تیم را در این پروژه پیدا کنید. با دسترسی ساخت برنامه، می‌توانید فرایند تازه بسازید و ورودی‌ها، مراحل و خروجی آن را تنظیم کنید.', href: `/projects/${project.id}`, action: 'مشاهدهٔ برنامه‌ها' },
    { id: 'templates', title: 'قالب‌های آماده', description: 'برای تحلیل درخواست، تهیهٔ گزارش یا پاسخ از روی اسناد از قالب‌های آماده استفاده کنید و برنامه را متناسب با نیاز تیم تغییر دهید.', href: `/projects/${project.id}/templates`, action: 'مشاهدهٔ قالب‌ها' },
    { id: 'knowledge', title: 'دانش پروژه', description: 'اسناد و منابع تیم را به دانش پروژه اضافه کنید و آن‌ها را در برنامه‌ها به کار بگیرید. منابع پس از پردازش قابل استفاده‌اند.', href: '/datasets', action: 'مدیریت دانش' },
    { id: 'skills', title: 'مهارت‌ها', description: 'دستورالعمل‌های قابل استفادهٔ مجدد را به‌صورت مهارت نگهداری کنید و در ایجنت‌ها و برنامه‌ها به کار ببرید.', href: '/skills', action: 'مشاهدهٔ مهارت‌ها' },
    { id: 'agents', title: 'ایجنت‌ها', description: 'برای کارهای تیم ایجنت بسازید و نقش، دستورالعمل و ابزارهای مورد نیاز آن را تنظیم کنید.', href: '/agents', action: 'مشاهدهٔ ایجنت‌ها' },
    { id: 'runs', title: 'اجراها و تأییدها', description: 'وضعیت اجرای فرایندها، نتیجه‌ها و خطاها را ببینید. اگر تصمیمی به شما ارجاع شده باشد، از کارتابل آن را بررسی و ثبت کنید.', href: `/projects/${project.id}/inbox`, action: 'باز کردن کارتابل' },
    { id: 'members', title: 'اعضای پروژه', description: 'مالک پروژه اعضای تیم را دعوت می‌کند و سطح دسترسی آن‌ها را مشخص می‌کند. دسترسی هر فرد به برنامه‌ها و امکانات پروژه براساس نقش اوست.', href: '/users', action: project.can_manage_members ? 'مدیریت اعضا' : 'مشاهدهٔ اعضا' },
    { id: 'model', title: 'مدل هوش مصنوعی', description: 'مدل و اعتبارنامهٔ شخصی خودتان را برای اجراهای این حساب تنظیم کنید.', href: `/projects/${project.id}/model-connections`, action: 'تنظیم مدل شخصی' },
  ]
  return <>
    <p className="text-sm leading-7 text-text-secondary">در هر پروژه، برنامه‌ها، دانش، مهارت‌ها و اعضای یک تیم را مدیریت می‌کنید. از بخش‌های زیر برای انجام کارهای تیم استفاده کنید.</p>
    <section aria-label="امکانات پروژه" className="grid gap-5 md:grid-cols-2">
      {sections.map(section => <article key={section.id} className={`${panel} flex flex-col`}>
        <h2 className="text-lg font-semibold text-text-primary">{section.title}</h2>
        <p className="mb-5 mt-3 text-sm leading-7 text-text-secondary">{section.description}</p>
        <Link href={section.href} className={`${button} mt-auto self-start`}>{section.action}</Link>
      </article>)}
    </section>
    <p className="text-sm leading-7 text-text-secondary">پیش از انتشار، نتیجهٔ برنامه را بررسی کنید. انتشار از داخل ویرایشگر هر برنامه انجام می‌شود.</p>
  </>
}

export default function ProjectSetup({ projectId }: { projectId: string }) {
  return <ProjectPage projectId={projectId} title="راهنمای استفاده از پروژه">{project => <Guide project={project} />}</ProjectPage>
}
