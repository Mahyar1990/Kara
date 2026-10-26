'use client'
import type { Component, Document, Repository, Workspace } from '@/service/company-source'
import type { GitLabConnection } from '@/service/company-gitlab'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import Link from '@/next/link'
import { gitlabApi } from '@/service/company-gitlab'
import { sourceApi, sourceError } from '@/service/company-source'
import FormDialog, { FieldHelp } from './form-dialog'
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const card = 'space-y-3 rounded-xl border border-divider-regular bg-background-default p-5'
const status: Record<string, string> = { pending: 'در صف Runner', running: 'در حال آماده‌سازی', succeeded: 'آماده', failed: 'ناموفق', cancelled: 'لغوشده', interrupted: 'ارتباط Runner قطع شد' }
const errors: Record<string, string> = { git_failed: 'دریافت مخزن انجام نشد؛ نشانی، برنچ، مجوز read_repository و گواهی Git را روی کامپیوتر Runner بررسی کنید.', disk_error: 'پوشهٔ مقصد وجود دارد یا نوشتن روی دیسک ممکن نیست. یک آماده‌سازی تازه ایجاد کنید.', invalid_job: 'تعریف دریافت‌شده معتبر نیست.', runner_error: 'خطای Runner؛ نسخه و اتصال محلی را بررسی کنید.', runner_disconnected: 'ارتباط Runner قطع شد؛ پس از راه‌اندازی دوباره، آماده‌سازی تازه بزنید.', source_access_or_revision_changed: 'دسترسی یا نسخهٔ مخزن و اتصال تغییر کرده است؛ worktree را بازبینی و ذخیره کنید.' }

function RepositoryEditor({ projectId, value, saved, close }: { projectId: string; value: Repository | null; saved: () => Promise<unknown>; close: () => void }) {
  const [name, setName] = useState(value?.name || '')
  const [url, setUrl] = useState(value?.url || '')
  const [branch, setBranch] = useState(value?.branch || '')
  const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const submit = async () => {
    setBusy(true); setError('')
    try { await sourceApi.saveRepo(projectId, value, { name, url, branch, expected_revision: value?.revision || 1 }); await saved(); close() }
    catch (e) { setError(await sourceError(e, 'ذخیرهٔ مخزن انجام نشد.')) } finally { setBusy(false) }
  }
  return <FormDialog open title={value ? 'ویرایش مخزن' : 'افزودن مخزن'} description="این تعریف در پروژه مشترک است؛ توکن و کد مخزن در این فرم قرار نمی‌گیرند." busy={busy} error={error} close={close}><form className="space-y-4" onSubmit={e => { e.preventDefault(); if (!busy) void submit() }}><fieldset disabled={busy} className="space-y-4">
    <label className="block">نام مخزن<input className={field} required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
    <label className="block">آدرس HTTPS مخزن گیت‌لب<input className={field} dir="ltr" type="url" required placeholder="https://gitlab.example.com/group/project.git" value={url} onChange={e => setUrl(e.target.value)} /><FieldHelp>نشانی Clone بدون توکن، پارامتر یا مسیر صفحهٔ برنچ؛ برای نصب دارای زیردایرکتوری همان مسیر را حفظ کنید.</FieldHelp></label>
    <label className="block">نام دقیق برنچ<input className={field} dir="ltr" required maxLength={200} placeholder="sandbox" value={branch} onChange={e => setBranch(e.target.value)} /><FieldHelp>برنچ هنگام آماده‌سازی خوانده می‌شود و commit دقیق آن در نتیجه ثبت می‌شود. تغییر این تعریف، فایل‌های قبلی را جابه‌جا نمی‌کند.</FieldHelp></label>
    </fieldset><div className="flex justify-end gap-2"><Button type="button" disabled={busy} onClick={close}>انصراف</Button><Button type="submit" variant="primary" disabled={busy}>ذخیرهٔ مخزن</Button></div></form></FormDialog>
}

function WorkspaceEditor({ projectId, value, repositories, connections, saved, close }: { projectId: string; value: Workspace | null; repositories: Repository[]; connections: GitLabConnection[]; saved: () => Promise<unknown>; close: () => void }) {
  const fresh = (): Component => ({ key: '', path: '', repository_id: '', connection_id: '' })
  const [name, setName] = useState(value?.name || '')
  const [parts, setParts] = useState<Component[]>(value?.components.map(({ key, path, repository_id, connection_id }) => ({ key, path, repository_id, connection_id })) || [fresh()])
  const [docs, setDocs] = useState<Document[]>(value?.documents || [{ path: 'docs/architecture.md', content: '# ارتباط بخش‌ها\n\nدر اینجا مسئولیت هر بخش، ارتباط APIها و وابستگی‌ها را مستند کنید.\n' }])
  const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const change = (i: number, update: Partial<Component>) => setParts(parts.map((p, j) => j === i ? { ...p, ...update } : p))
  const changeDoc = (i: number, update: Partial<Document>) => setDocs(docs.map((p, j) => j === i ? { ...p, ...update } : p))
  const submit = async () => {
    setBusy(true); setError('')
    try { await sourceApi.saveWorkspace(projectId, value, { name, components: parts, documents: docs, expected_revision: value?.revision || 1 }); await saved(); close() }
    catch (e) { setError(await sourceError(e, 'ذخیرهٔ worktree انجام نشد.')) } finally { setBusy(false) }
  }
  return <FormDialog open title={value ? 'ویرایش worktree شخصی' : 'تعریف worktree شخصی'} description="یک فضای چندمخزنی روی کامپیوتر خودتان تعریف کنید. ذخیرهٔ این فرم فقط تعریف را ثبت می‌کند؛ دریافت کد با دکمهٔ آماده‌سازی انجام می‌شود." busy={busy} error={error} close={close}><form className="space-y-5" onSubmit={e => { e.preventDefault(); if (!busy) void submit() }}><fieldset disabled={busy} className="space-y-5">
    <label className="block">نام worktree<input className={field} required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
    <h2 className="font-semibold">بخش‌های سورس کد (حداکثر ۸)</h2>
    {parts.map((part, i) => <div key={i} className={card}><h3>بخش {i + 1}</h3><label className="block">شناسهٔ بخش<input className={field} dir="ltr" required pattern="[a-z][a-z0-9-]*" maxLength={48} placeholder="backend" value={part.key} onChange={e => change(i, { key: e.target.value })} /></label><label className="block">مسیر نسبی بخش<input className={field} dir="ltr" required placeholder="services/backend" value={part.path} onChange={e => change(i, { path: e.target.value })} /></label>
      <label className="block">مخزن و برنچ<select className={field} required value={part.repository_id} onChange={e => change(i, { repository_id: e.target.value })}><option value="">انتخاب مخزن</option>{!repositories.some(r => r.id === part.repository_id) && part.repository_id && <option value={part.repository_id}>مخزن حذف‌شده؛ جایگزین کنید</option>}{repositories.map(repo => <option key={repo.id} value={repo.id}>{repo.name} — {repo.branch}</option>)}</select></label>
      <label className="block">اتصال شخصی گیت‌لب<select className={field} required value={part.connection_id} onChange={e => change(i, { connection_id: e.target.value })}><option value="">انتخاب اتصال خودتان</option>{!connections.some(c => c.id === part.connection_id) && part.connection_id && <option value={part.connection_id}>اتصال حذف‌شده؛ جایگزین کنید</option>}{connections.map(c => <option key={c.id} value={c.id}>{c.name} — {c.base_url}</option>)}</select></label><Button type="button" disabled={parts.length === 1} onClick={() => setParts(parts.filter((_, j) => i !== j))}>حذف بخش</Button></div>)}
    <Button type="button" disabled={parts.length >= 8} onClick={() => setParts([...parts, fresh()])}>افزودن بخش</Button>
    <FieldHelp>مسیرها باید نسبی، بدون نقطهٔ آغازین و بدون هم‌پوشانی باشند. هر بخش یک Git worktree مستقل روی commit مشخص خواهد بود. ذخیرهٔ دوباره، نسخهٔ فعلی مخزن‌ها و اتصال‌ها را مبنا قرار می‌دهد.</FieldHelp>
    <h2 className="font-semibold">مستندات Markdown ارتباط بخش‌ها</h2>
    {docs.map((doc, i) => <div key={i} className={card}><label className="block">مسیر فایل md<input className={field} dir="ltr" required placeholder="docs/architecture.md" value={doc.path} onChange={e => changeDoc(i, { path: e.target.value })} /></label><label className="block">متن مستند<textarea className={field} rows={9} maxLength={65536} value={doc.content} onChange={e => changeDoc(i, { content: e.target.value })} /></label><Button type="button" onClick={() => setDocs(docs.filter((_, j) => i !== j))}>حذف مستند</Button></div>)}
    <Button type="button" disabled={docs.length >= 16} onClick={() => setDocs([...docs, { path: '', content: '' }])}>افزودن مستند</Button><FieldHelp>حداکثر ۱۶ فایل، هر فایل ۶۴ کیلوبایت و مجموع ۲۵۶ کیلوبایت. فایل‌های مستند بیرون از مسیر بخش‌ها قرار می‌گیرند و همراه snapshot روی Runner نوشته می‌شوند.</FieldHelp>
    </fieldset><div className="flex justify-end gap-2"><Button type="button" disabled={busy} onClick={close}>انصراف</Button><Button type="submit" variant="primary" disabled={busy || !connections.length || !repositories.length}>ذخیرهٔ worktree</Button></div></form></FormDialog>
}

function SourceContent({ projectId, accountId }: { projectId: string; accountId: string }) {
  const list = useQuery({ queryKey: ['source-code', projectId, accountId], queryFn: () => sourceApi.list(projectId), refetchInterval: 8000 })
  const connections = useQuery({ queryKey: ['personal-gitlab-connections', accountId], queryFn: gitlabApi.list })
  const devices = useQuery({ queryKey: ['source-runners', accountId], queryFn: sourceApi.devices, refetchInterval: 15000 })
  const [repoEdit, setRepoEdit] = useState<Repository | 'new' | null>(null)
  const [treeEdit, setTreeEdit] = useState<Workspace | 'new' | null>(null)
  const [remove, setRemove] = useState<{ kind: 'repositories' | 'workspaces'; value: Repository | Workspace } | null>(null)
  const [selected, setSelected] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('')
  const [preparing, setPreparing] = useState<{ value: Workspace; key: string } | null>(null)
  const act = async (fn: () => Promise<unknown>, text: string) => {
    if (busy) return
    setBusy(true); setError(''); setMessage('')
    try { await fn(); await list.refetch(); setMessage(text); setRemove(null); setPreparing(null) }
    catch (e) { setError(await sourceError(e, 'عملیات انجام نشد. دسترسی، اتصال و نسخهٔ اطلاعات را بررسی کنید.')) } finally { setBusy(false) }
  }
  const data = list.data
  const activeDevices = devices.data?.data.filter(d => !d.revoked_at) || []
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto max-w-5xl space-y-7">
    <header><h1 className="text-3xl font-bold">سورس کد</h1><p className="mt-3 text-sm leading-7 text-text-secondary">مخزن‌های پروژه، worktreeهای شخصی و مستندات ارتباط بخش‌ها. دریافت کد روی کامپیوتر شما با Runner محلی انجام می‌شود. هر آماده‌سازی پوشهٔ تازه‌ای می‌سازد و commit دقیق بخش‌ها را ثبت می‌کند.</p><div className="mt-3 flex flex-wrap gap-5 text-sm text-text-accent"><Link href={`/projects/${projectId}/gitlab-connections`}>اتصال شخصی گیت‌لب</Link><Link href={`/projects/${projectId}/source-runners`}>راه‌اندازی و مدیریت Runner</Link></div></header>
    {message && <p role="status">{message}</p>}{error && <p role="alert" className="text-text-destructive-secondary">{error}</p>}
    {list.isPending ? <p role="status">در حال دریافت…</p> : list.isError ? <p role="alert">دریافت اطلاعات انجام نشد. <button onClick={() => list.refetch()}>تلاش دوباره</button></p> : data && <>
      <section className="space-y-4"><div className="flex justify-between gap-3"><h2 className="text-xl font-bold">مخزن‌های پروژه</h2><Button onClick={() => setRepoEdit('new')}>افزودن مخزن</Button></div>{!data.repositories.length && <p>هنوز مخزنی تعریف نشده است.</p>}{data.repositories.map(repo => <article key={repo.id} className={card}><h3 className="font-semibold">{repo.name}</h3><p dir="ltr" className="break-all text-sm">{repo.url}</p><p>برنچ: <bdi>{repo.branch}</bdi> · نسخهٔ تعریف: {repo.revision}</p>{repo.can_edit && <div className="flex gap-2"><Button disabled={busy} onClick={() => setRepoEdit(repo)}>ویرایش مخزن</Button><Button disabled={busy} onClick={() => setRemove({ kind: 'repositories', value: repo })}>حذف مخزن</Button></div>}</article>)}</section>
      <section className="space-y-4"><div className="flex justify-between gap-3"><h2 className="text-xl font-bold">worktreeهای من</h2><Button disabled={!data.repositories.length || !connections.data?.data.length} onClick={() => setTreeEdit('new')}>تعریف worktree</Button></div>{connections.isError && <p role="alert">دریافت اتصال‌های شخصی انجام نشد.</p>}{!connections.isPending && !connections.data?.data.length && <p>ابتدا در تنظیمات، اتصال شخصی گیت‌لب را تعریف کنید.</p>}{!data.workspaces.length && <p>هنوز worktree شخصی ندارید.</p>}
      <label className="block text-sm">Runner مقصد<select className={field} value={selected} onChange={e => setSelected(e.target.value)}><option value="">انتخاب Runner خودتان</option>{activeDevices.map(d => <option key={d.id} value={d.id}>{d.name} — {d.last_seen_at ? `آخرین ارتباط ${new Date(d.last_seen_at).toLocaleString('fa-IR')}` : 'هنوز متصل نشده'}</option>)}</select></label>{devices.isError && <p role="alert">دریافت Runnerها انجام نشد.</p>}
      {data.workspaces.map(tree => <article key={tree.id} className={card}><h3 className="font-semibold">{tree.name} · نسخهٔ {tree.revision}</h3>{tree.components.map(p => <p key={p.key} className="text-sm"><bdi>{p.path}</bdi> ← <bdi>{p.url} ({p.branch})</bdi></p>)}<details><summary className="cursor-pointer text-sm">مستندات ({tree.documents.length})</summary>{tree.documents.map(d => <div key={d.path} className="mt-3"><p dir="ltr">{d.path}</p><pre className="whitespace-pre-wrap text-sm">{d.content}</pre></div>)}</details><div className="flex flex-wrap gap-2"><Button disabled={busy || data.jobs.some(j => j.source_workspace_id === tree.id && ['pending', 'running'].includes(j.state))} onClick={() => setTreeEdit(tree)}>ویرایش worktree</Button><Button variant="primary" disabled={busy || !activeDevices.some(d => d.id === selected) || data.jobs.some(j => j.source_workspace_id === tree.id && ['pending', 'running'].includes(j.state))} onClick={() => setPreparing({ value: tree, key: crypto.randomUUID() })}>آماده‌سازی روی Runner</Button><Button disabled={busy} onClick={() => setRemove({ kind: 'workspaces', value: tree })}>حذف تعریف</Button></div></article>)}</section>
      <section className="space-y-4"><h2 className="text-xl font-bold">سابقهٔ آماده‌سازی من</h2>{!data.jobs.length && <p>هنوز آماده‌سازی انجام نشده است.</p>}{data.jobs.map(job => <article key={job.id} className={card}><h3>{data.workspaces.find(w => w.id === job.source_workspace_id)?.name || 'worktree حذف‌شده'} · {status[job.state] || job.state}</h3><p className="text-xs">نسخهٔ تعریف: {job.snapshot_revision} · {new Date(job.created_at).toLocaleString('fa-IR')} · Runner: {devices.data?.data.find(d => d.id === job.device_id)?.name || job.device_id}</p><p dir="ltr" className="break-all text-xs">{job.id}</p>{job.result?.error && <p>{errors[job.result.error] || 'آماده‌سازی ناموفق بود.'}</p>}{job.result?.components?.map(p => <p key={p.key} dir="ltr" className="break-all font-mono text-xs">{p.key}: {p.commit}</p>)}{job.result?.local_directory && <p className="text-sm">پوشهٔ محلی زیر مسیر ریشهٔ Runner: <bdi>{job.result.local_directory}</bdi></p>}{['pending', 'running'].includes(job.state) && <Button disabled={busy} onClick={() => void act(() => sourceApi.cancel(projectId, job.id), 'درخواست لغو ثبت شد؛ Runner در بررسی بعدی متوقف می‌شود.')}>لغو آماده‌سازی</Button>}</article>)}</section>
    </>}
    <p className="text-sm leading-7 text-text-tertiary">این بخش به برنامه‌ها، ایجنت‌ها یا فلوهای موجود متصل نشده است. دادهٔ کد روی Runner می‌ماند؛ این صفحه تعریف‌ها، مستندات نوشته‌شده و سابقهٔ commitها را نگه می‌دارد.</p>
    {repoEdit && <RepositoryEditor projectId={projectId} value={repoEdit === 'new' ? null : repoEdit} saved={list.refetch} close={() => setRepoEdit(null)} />}
    {treeEdit && <WorkspaceEditor projectId={projectId} value={treeEdit === 'new' ? null : treeEdit} repositories={data?.repositories || []} connections={connections.data?.data || []} saved={list.refetch} close={() => setTreeEdit(null)} />}
    {remove && <FormDialog open title="حذف تعریف سورس کد" description={`تعریف «${remove.value.name}» از فهرست فعال حذف می‌شود. فایل‌های محلی و سابقه حفظ می‌شوند. حذف مخزن، دریافت تازهٔ worktreeهای وابسته را تا بازبینی متوقف می‌کند.`} busy={busy} error={error} close={() => setRemove(null)}><Button disabled={busy} onClick={() => void act(() => sourceApi.remove(projectId, remove.kind, remove.value), 'تعریف حذف شد.')}>حذف تعریف</Button></FormDialog>}
    {preparing && <FormDialog open title="آماده‌سازی سورس کد" description={`«${preparing.value.name}» روی Runner انتخاب‌شده دریافت می‌شود. برنچ‌های تعریف‌شده به commit مشخص تبدیل می‌شوند؛ پوشهٔ تازه، بدون تغییر آماده‌سازی‌های قبلی ساخته می‌شود.`} busy={busy} error={error} close={() => setPreparing(null)}><Button variant="primary" disabled={busy} onClick={() => void act(() => sourceApi.prepare(projectId, preparing.value, selected, preparing.key), 'در صف Runner قرار گرفت؛ Runner باید در حال اجرا باشد.')}>ثبت آماده‌سازی</Button></FormDialog>}
  </div></main>
}
export default function SourceCode({ projectId }: { projectId: string }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  return <SourceContent key={`${projectId}:${profile.id}`} projectId={projectId} accountId={profile.id} />
}
