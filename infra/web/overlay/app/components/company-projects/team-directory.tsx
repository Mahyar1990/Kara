'use client'

import type { ReactNode } from 'react'
import Link from '@/next/link'

export const directoryButton = 'rounded-xl border border-divider-regular px-4 py-2 text-sm text-text-primary hover:bg-background-default-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50'
export const directoryPanel = 'min-w-0 rounded-2xl border border-divider-regular bg-components-panel-bg p-5'
export const directoryField = 'mt-2 block w-full min-w-0 rounded-xl border border-divider-regular bg-components-panel-bg px-3 py-2 text-sm text-text-primary'
export const number = (value: number) => value.toLocaleString('fa-IR')

function normalize(value: string) {
  return value.toLocaleLowerCase('fa-IR').replace(/[يى]/g, 'ی').replace(/ك/g, 'ک')
    .replace(/[\u064B-\u065F\u0670]/g, '').replace(/[\u200c\u200d]/g, ' ')
    .replace(/[۰-۹]/g, digit => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(digit)))
    .replace(/[٠-٩]/g, digit => String('٠١٢٣٤٥٦٧٨٩'.indexOf(digit))).replace(/\s+/g, ' ').trim()
}

export function matchesSearch(query: string, ...values: (string | null | undefined)[]) {
  const text = normalize(values.filter(Boolean).join(' '))
  return normalize(query).split(' ').every(word => text.includes(word))
}

export function resultPage<T>(items: T[], requested: number, size = 8) {
  const pages = Math.max(1, Math.ceil(items.length / size))
  const page = Math.max(1, Math.min(requested, pages))
  const start = (page - 1) * size
  return { items: items.slice(start, start + size), page, pages, start: items.length ? start + 1 : 0, end: Math.min(start + size, items.length), total: items.length }
}

export function DirectoryPage({ project, title, description, actions, children }: { project: string; title: string; description: string; actions?: ReactNode; children: ReactNode }) {
  return <main dir="rtl" className="h-full min-w-0 overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto min-w-0 max-w-6xl space-y-6">
    <Link className="text-sm text-text-accent" href={`/projects/${project}`}>نمای کلی پروژه ←</Link>
    <header className="flex min-w-0 flex-wrap items-start justify-between gap-4"><div className="min-w-0 max-w-3xl"><h1 className="break-words text-3xl font-bold leading-normal">{title}</h1><p className="mt-3 text-sm leading-7 text-text-secondary">{description}</p></div><div className="flex flex-wrap items-center gap-2">{actions}</div></header>
    {children}
  </div></main>
}

export function DirectoryNotice({ loading, error, entered, retry, project }: { loading: boolean; error: boolean; entered: boolean; retry: () => unknown; project: string }) {
  if (error) return <section role="alert" className={directoryPanel}><p className="text-sm leading-7">دریافت اطلاعات انجام نشد. اتصال و دسترسی خود را بررسی کنید.</p><button className={`${directoryButton} mt-3`} onClick={() => void retry()}>تلاش دوباره</button></section>
  if (loading) return <p role="status" className={`${directoryPanel} text-sm text-text-secondary`}>در حال دریافت اطلاعات…</p>
  if (!entered) return <section className={directoryPanel}><p className="mb-3 text-sm leading-7">برای استفاده از این بخش، ابتدا وارد فضای همین پروژه شوید.</p><Link href={`/projects/${project}`} className={`${directoryButton} inline-block`}>باز کردن پروژه</Link></section>
  return null
}

export function DirectorySummary({ items }: { items: { label: string; count: number }[] }) {
  return <section aria-label="خلاصهٔ فهرست کامل" className="grid min-w-0 grid-cols-2 gap-3 lg:grid-cols-4">{items.map(item => <div key={item.label} className={directoryPanel}><p className="text-xs leading-6 text-text-secondary">{item.label}</p><p className="mt-2 text-2xl font-bold">{number(item.count)}</p></div>)}</section>
}

export function DirectoryToolbar({ query, change, placeholder, filtered, total, reset, hasFilters, children }: { query: string; change: (value: string) => void; placeholder: string; filtered?: number; total?: number; reset: () => void; hasFilters: boolean; children?: ReactNode }) {
  return <section aria-label="جستجو و فیلتر فهرست" className={`${directoryPanel} space-y-4`}>
    <div className="flex min-w-0 flex-wrap items-end gap-4"><label className="min-w-0 flex-[2] basis-56 text-sm">جستجو<input type="search" maxLength={200} className={directoryField} value={query} placeholder={placeholder} onChange={event => change(event.target.value)} /></label>{children}</div>
    <div className="flex flex-wrap items-center justify-between gap-3"><p role="status" className="text-xs leading-6 text-text-secondary">{filtered === undefined || total === undefined ? 'تعداد موارد هنوز دریافت نشده است.' : `${number(filtered)} مورد از ${number(total)} مورد در دسترس، مطابق فیلترها`}</p>{hasFilters && <button className={directoryButton} onClick={reset}>پاک‌کردن فیلترها</button>}</div>
  </section>
}

export function DirectoryPagination({ value, change }: { value: { page: number; pages: number; start: number; end: number; total: number }; change: (page: number) => void }) {
  if (!value.total) return null
  return <nav aria-label="صفحه‌بندی فهرست" className="flex flex-wrap items-center justify-between gap-3 border-t border-divider-regular pt-5"><p className="text-xs text-text-secondary">نمایش {number(value.start)} تا {number(value.end)} از {number(value.total)} مورد</p>{value.pages > 1 && <div className="flex flex-wrap items-center gap-3"><button className={directoryButton} disabled={value.page <= 1} onClick={() => change(value.page - 1)}>قبلی</button><span className="text-xs text-text-tertiary">صفحهٔ {number(value.page)} از {number(value.pages)}</span><button className={directoryButton} disabled={value.page >= value.pages} onClick={() => change(value.page + 1)}>بعدی</button></div>}</nav>
}

export function DirectoryEmpty({ filtered, title, children, reset }: { filtered: boolean; title: string; children: ReactNode; reset: () => void }) {
  return <section className={`${directoryPanel} py-10 text-center`}><h2 className="text-lg font-semibold">{filtered ? 'موردی با این فیلترها پیدا نشد' : title}</h2><p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-text-secondary">{filtered ? 'عبارت جستجو یا وضعیت انتخاب‌شده را تغییر دهید.' : children}</p>{filtered && <button className={`${directoryButton} mt-4`} onClick={reset}>نمایش همهٔ موارد</button>}</section>
}
