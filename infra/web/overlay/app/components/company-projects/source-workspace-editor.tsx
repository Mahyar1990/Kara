'use client'

import type { Component, Document, Repository, Workspace } from '@/service/company-source'
import type { GitLabConnection } from '@/service/company-gitlab'
import { DirectionProvider } from '@base-ui/react/direction-provider'
import { Button } from '@langgenius/dify-ui/button'
import { Tabs, TabsList, TabsPanel, TabsTab } from '@langgenius/dify-ui/tabs'
import { useState } from 'react'
import { sourceApi, sourceError } from '@/service/company-source'
import FormDialog, { FieldHelp } from './form-dialog'

const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-sm text-text-primary'
const row = 'flex flex-wrap items-center justify-between gap-3 rounded-lg border border-divider-regular p-3'
const emptyPart = (): Component => ({ key: '', path: '', repository_id: '', connection_id: '' })
const emptyDoc = (): Document => ({ path: '', content: '' })
const pathValid = (path: string) => !!path && path.length <= 240 && /^[\p{L}\p{N}_./-]+$/u.test(path) && path.split('/').length <= 8 && path.split('/').every(segment => !!segment && !segment.startsWith('.'))
const overlaps = (a: string, b: string) => a === b || a.startsWith(`${b}/`) || b.startsWith(`${a}/`)

function DocumentFields({ value, change }: { value: Document; change: (value: Document) => void }) {
  return <><label className="block">مسیر فایل Markdown<input className={field} dir="ltr" required maxLength={240} placeholder="docs/architecture.md" value={value.path} onChange={e => change({ ...value, path: e.target.value })} /></label><label className="block">متن مستند<textarea className={field} rows={7} maxLength={65536} value={value.content} onChange={e => change({ ...value, content: e.target.value })} /></label></>
}

function PartEditor({ value, repositories, connections, confirm, close }: { value: Component; repositories: Repository[]; connections: GitLabConnection[]; confirm: (part: Component, doc?: Document) => string | undefined; close: () => void }) {
  const [part, setPart] = useState(value)
  const [withDoc, setWithDoc] = useState(false)
  const [doc, setDoc] = useState(emptyDoc)
  const [error, setError] = useState('')
  const change = (update: Partial<Component>) => setPart(current => ({ ...current, ...update }))
  return <FormDialog open title={value.key ? 'ویرایش بخش' : 'بخش جدید'} description="اطلاعات بخش را تکمیل و تأیید کنید تا به فهرست بخش‌ها برگردید." error={error} close={close}><form className="space-y-4" onSubmit={e => {
    e.preventDefault(); e.stopPropagation()
    const problem = confirm(part, withDoc ? doc : undefined)
    if (problem) setError(problem)
    else close()
  }}>
    <div className="grid gap-4 sm:grid-cols-2"><label className="block">شناسهٔ بخش<input className={field} dir="ltr" required pattern="[a-z][a-z0-9-]*" maxLength={48} placeholder="backend" value={part.key} onChange={e => change({ key: e.target.value })} /></label><label className="block">مسیر نسبی بخش<input className={field} dir="ltr" required maxLength={240} placeholder="services/backend" value={part.path} onChange={e => change({ path: e.target.value })} /></label></div>
    <label className="block">مخزن و برنچ<select className={field} required value={part.repository_id} onChange={e => change({ repository_id: e.target.value })}><option value="">انتخاب مخزن</option>{!repositories.some(r => r.id === part.repository_id) && part.repository_id && <option value={part.repository_id}>مخزن حذف‌شده؛ جایگزین کنید</option>}{repositories.map(repo => <option key={repo.id} value={repo.id}>{repo.name} — {repo.branch}</option>)}</select></label>
    <label className="block">اتصال شخصی گیت‌لب<select className={field} required value={part.connection_id} onChange={e => change({ connection_id: e.target.value })}><option value="">انتخاب اتصال خودتان</option>{!connections.some(c => c.id === part.connection_id) && part.connection_id && <option value={part.connection_id}>اتصال حذف‌شده؛ جایگزین کنید</option>}{connections.map(c => <option key={c.id} value={c.id}>{c.name} — {c.base_url}</option>)}</select></label>
    <FieldHelp>مسیر بخش باید نسبی، بدون نقطهٔ آغازین و بدون هم‌پوشانی با بخش‌های دیگر باشد.</FieldHelp>
    <label className="flex items-center gap-2"><input type="checkbox" checked={withDoc} onChange={e => setWithDoc(e.target.checked)} />افزودن مستند همراه این بخش</label>
    {withDoc && <div className="space-y-4 rounded-lg border border-divider-regular p-3"><DocumentFields value={doc} change={setDoc} /><FieldHelp>مستند خارج از مسیر مخزن ذخیره می‌شود و از تب «مستندات» قابل ویرایش است.</FieldHelp></div>}
    <div className="flex justify-end gap-2"><Button type="button" onClick={close}>انصراف</Button><Button type="submit" variant="primary">تأیید بخش</Button></div>
  </form></FormDialog>
}

export default function WorkspaceEditor({ projectId, value, repositories, connections, saved, close }: { projectId: string; value: Workspace | null; repositories: Repository[]; connections: GitLabConnection[]; saved: () => Promise<unknown>; close: () => void }) {
  const [tab, setTab] = useState('info')
  const [name, setName] = useState(value?.name || '')
  const [parts, setParts] = useState<Component[]>(value?.components.map(({ key, path, repository_id, connection_id }) => ({ key, path, repository_id, connection_id })) || [])
  const [docs, setDocs] = useState<Document[]>(value?.documents || [])
  const [partEdit, setPartEdit] = useState<{ index: number; value: Component } | null>(null)
  const [docEdit, setDocEdit] = useState<{ index: number; value: Document } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [docError, setDocError] = useState('')
  const validateDoc = (doc: Document, index = -1, components = parts): string | undefined => {
    if (!pathValid(doc.path) || !doc.path.toLowerCase().endsWith('.md')) return 'مسیر نسبی معتبر با پسوند .md وارد کنید.'
    if (docs.some((other, i) => i !== index && overlaps(other.path, doc.path)) || components.some(part => overlaps(part.path, doc.path))) return 'مسیر مستند با یک بخش یا مستند دیگر هم‌پوشانی دارد.'
    const bytes = new TextEncoder()
    if (bytes.encode(doc.content).length > 65536 || docs.reduce((sum, d, i) => sum + (i === index ? 0 : bytes.encode(d.content).length), bytes.encode(doc.content).length) > 262144) return 'حجم مستندها از حد مجاز بیشتر است.'
    if (index === -1 && docs.length >= 16) return 'حداکثر ۱۶ مستند می‌توانید اضافه کنید.'
  }
  const submit = async () => {
    if (!name.trim()) { setTab('info'); setError('نام worktree را وارد کنید.'); return }
    if (!parts.length) { setTab('parts'); setError('حداقل یک بخش اضافه کنید.'); return }
    setBusy(true); setError('')
    try { await sourceApi.saveWorkspace(projectId, value, { name, components: parts, documents: docs, expected_revision: value?.revision || 1 }); await saved(); close() }
    catch (e) { setError(await sourceError(e, 'ذخیرهٔ worktree انجام نشد.')) } finally { setBusy(false) }
  }
  return <FormDialog open wide fixedBody title={value ? 'ویرایش worktree شخصی' : 'تعریف worktree شخصی'} description="بخش‌ها و مستندات را تعریف کنید؛ پس از ذخیره، دریافت کد با «آماده‌سازی روی Runner» انجام می‌شود." busy={busy} error={error} close={close} footer={<div className="flex justify-end gap-2"><Button type="button" disabled={busy} onClick={close}>انصراف</Button><Button type="submit" form="source-workspace-form" variant="primary" disabled={busy || !!partEdit || !!docEdit || !connections.length || !repositories.length}>ذخیرهٔ worktree</Button></div>}>
    <form id="source-workspace-form" className="h-full" onSubmit={e => { e.preventDefault(); if (!busy && !partEdit && !docEdit) void submit() }}><fieldset disabled={busy} className="h-full min-w-0"><DirectionProvider direction="rtl"><Tabs className="flex h-full min-w-0 flex-col" value={tab} onValueChange={next => setTab(String(next))}>
      <TabsList aria-label="تنظیمات worktree" className="shrink-0 gap-5 overflow-x-auto border-b border-divider-regular"><TabsTab type="button" value="info">اطلاعات</TabsTab><TabsTab type="button" value="parts">بخش‌ها ({parts.length})</TabsTab><TabsTab type="button" value="docs">مستندات ({docs.length})</TabsTab></TabsList>
      <TabsPanel value="info" className="min-h-0 flex-1 space-y-4 overflow-y-auto py-4"><label className="block">نام worktree<input className={field} maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label><FieldHelp>این worktree شخصی است. هر بخش از مخزن و اتصال گیت‌لب انتخاب‌شدهٔ شما دریافت می‌شود.</FieldHelp></TabsPanel>
      <TabsPanel value="parts" className="min-h-0 flex-1 space-y-3 overflow-y-auto py-4"><div className="flex items-center justify-between gap-3"><h2 className="font-semibold">بخش‌های سورس کد</h2><Button type="button" disabled={parts.length >= 8} onClick={() => setPartEdit({ index: -1, value: emptyPart() })}>بخش جدید</Button></div>{!parts.length && <p className="text-sm text-text-secondary">برای شروع، یک بخش اضافه کنید.</p>}{parts.map((part, i) => <article key={i} className={row}><div className="min-w-0 flex-1 space-y-1"><h3 className="break-all font-semibold"><bdi>{part.key}</bdi></h3><p dir="ltr" className="break-all text-sm">{part.path}</p><p className="break-all text-xs text-text-secondary">{repositories.find(repo => repo.id === part.repository_id)?.name || 'مخزن حذف‌شده'} · <bdi>{repositories.find(repo => repo.id === part.repository_id)?.branch}</bdi></p></div><div className="flex shrink-0 gap-2"><Button type="button" aria-label={`ویرایش بخش ${part.key}`} onClick={() => setPartEdit({ index: i, value: part })}>ویرایش</Button><Button type="button" aria-label={`حذف بخش ${part.key}`} onClick={() => setParts(parts.filter((_, j) => i !== j))}>حذف</Button></div></article>)}<FieldHelp>حداکثر ۸ بخش. تأیید دیالوگ داخلی، بخش را به این فهرست اضافه می‌کند؛ برای ثبت نهایی «ذخیرهٔ worktree» را بزنید.</FieldHelp></TabsPanel>
      <TabsPanel value="docs" className="min-h-0 flex-1 space-y-3 overflow-y-auto py-4"><div className="flex items-center justify-between gap-3"><h2 className="font-semibold">مستندات ارتباط بخش‌ها</h2><Button type="button" disabled={docs.length >= 16} onClick={() => { setDocError(''); setDocEdit({ index: -1, value: emptyDoc() }) }}>مستند جدید</Button></div>{!docs.length && <p className="text-sm text-text-secondary">هنوز مستندی اضافه نشده است.</p>}{docs.map((doc, i) => <article key={i} className={row}><p dir="ltr" className="min-w-0 flex-1 break-all text-sm">{doc.path}</p><div className="flex shrink-0 gap-2"><Button type="button" aria-label={`ویرایش مستند ${doc.path}`} onClick={() => { setDocError(''); setDocEdit({ index: i, value: { ...doc } }) }}>ویرایش</Button><Button type="button" aria-label={`حذف مستند ${doc.path}`} onClick={() => setDocs(docs.filter((_, j) => i !== j))}>حذف</Button></div></article>)}<FieldHelp>حداکثر ۱۶ فایل، هر فایل ۶۴ کیلوبایت و مجموع ۲۵۶ کیلوبایت. مستندات خارج از مسیر بخش‌ها همراه سورس روی Runner نوشته می‌شوند.</FieldHelp></TabsPanel>
    </Tabs></DirectionProvider></fieldset></form>
    {partEdit && <PartEditor value={partEdit.value} repositories={repositories} connections={connections} close={() => setPartEdit(null)} confirm={(part, doc) => {
      const others = parts.filter((_, i) => i !== partEdit.index)
      if (!pathValid(part.path) || others.some(other => other.key === part.key || overlaps(other.path, part.path)) || docs.some(d => overlaps(d.path, part.path))) return 'شناسه باید یکتا و مسیر نسبی و بدون هم‌پوشانی باشد.'
      if (!repositories.some(repo => repo.id === part.repository_id) || !connections.some(connection => connection.id === part.connection_id)) return 'مخزن و اتصال معتبر انتخاب کنید.'
      const next = partEdit.index === -1 ? [...parts, part] : parts.map((old, i) => i === partEdit.index ? part : old)
      if (doc) { const problem = validateDoc(doc, -1, next); if (problem) return problem }
      setParts(next); if (doc) setDocs([...docs, doc]); setError('')
    }} />}
    {docEdit && <FormDialog open title={docEdit.index === -1 ? 'مستند جدید' : 'ویرایش مستند'} description="مسیر و متن Markdown مستند را وارد کنید." error={docError} close={() => setDocEdit(null)}><form className="space-y-4" onSubmit={e => {
      e.preventDefault(); e.stopPropagation()
      const problem = validateDoc(docEdit.value, docEdit.index)
      if (problem) { setDocError(problem); return }
      setDocs(docEdit.index === -1 ? [...docs, docEdit.value] : docs.map((old, i) => i === docEdit.index ? docEdit.value : old)); setDocEdit(null); setError('')
    }}><DocumentFields value={docEdit.value} change={doc => setDocEdit({ ...docEdit, value: doc })} /><div className="flex justify-end gap-2"><Button type="button" onClick={() => setDocEdit(null)}>انصراف</Button><Button type="submit" variant="primary">تأیید مستند</Button></div></form></FormDialog>}
  </FormDialog>
}
