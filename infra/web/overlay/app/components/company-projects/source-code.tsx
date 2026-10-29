'use client'
import type { Job, Repository, Workspace } from '@/service/company-source'
import { DirectionProvider } from '@base-ui/react/direction-provider'
import { Tabs, TabsList, TabsPanel, TabsTab } from '@langgenius/dify-ui/tabs'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import Link from '@/next/link'
import { gitlabApi } from '@/service/company-gitlab'
import { sourceApi, sourceError } from '@/service/company-source'
import FormDialog, { FieldHelp } from './form-dialog'
import WorkspaceEditor from './source-workspace-editor'
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary'
const card = 'space-y-3 rounded-xl border border-divider-regular bg-background-default p-5'
const active = (job: Job) => ['pending', 'running'].includes(job.state)
const progress: Record<string, string> = { pending: 'درخواست ثبت شده و منتظر Runner است. Runner باید روشن و متصل باشد؛ اگر مشغول اجرای دیگری باشد، این درخواست در صف می‌ماند.', running: 'Runner در حال دریافت مخزن‌ها و آماده‌سازی فایل‌هاست. این کار بسته به حجم کد و سرعت شبکه ممکن است چند دقیقه طول بکشد. نتیجه به‌صورت خودکار نمایش داده می‌شود.' }
const status: Record<string, string> = { pending: 'در صف Runner', running: 'در حال آماده‌سازی', succeeded: 'آماده', failed: 'ناموفق', cancelled: 'لغوشده', interrupted: 'ارتباط Runner قطع شد' }
const errors: Record<string, string> = { workspace_busy: 'این پوشه هنوز در Runner دیگری در حال به‌روزرسانی است. صبر کنید اجرای قبلی متوقف شود و دوباره تلاش کنید.', merge_conflict: 'ادغام خودکار تعارض دارد. پوشه را در Git بررسی و تعارض‌ها را حل کنید؛ تغییرات ذخیره‌نشده در git stash و refs/kara/backups پشتیبان دارند. پس از حل تعارض، به‌روزرسانی را دوباره بزنید.', workspace_update_failed: 'به‌روزرسانی این پوشه ممکن نشد؛ مسیر ریشهٔ Runner، مالکیت پوشه و فایل manifest را بررسی کنید. پوشهٔ جدیدی ساخته نشده است.', runner_update_required: 'بستهٔ جدید Runner را دریافت و Runner را دوباره اجرا کنید.', git_failed: 'دریافت مخزن انجام نشد؛ نشانی، برنچ، مجوز read_repository و گواهی Git را روی کامپیوتر Runner بررسی کنید.', disk_error: 'پوشهٔ مقصد وجود دارد یا نوشتن روی دیسک ممکن نیست. یک آماده‌سازی تازه ایجاد کنید.', invalid_job: 'تعریف دریافت‌شده معتبر نیست.', runner_error: 'خطای Runner؛ نسخه و اتصال محلی را بررسی کنید.', runner_disconnected: 'ارتباط Runner قطع شد؛ پس از راه‌اندازی دوباره، آماده‌سازی تازه بزنید.', source_access_or_revision_changed: 'دسترسی یا نسخهٔ مخزن و اتصال تغییر کرده است؛ worktree را بازبینی و ذخیره کنید.' }

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

function SourceContent({ projectId, accountId }: { projectId: string; accountId: string }) {
  const queryClient = useQueryClient()
  const queryKey = ['source-code', projectId, accountId]
  const list = useQuery({ queryKey, queryFn: () => sourceApi.list(projectId), refetchInterval: query => query.state.data?.jobs.some(active) ? 2000 : 8000 })
  const connections = useQuery({ queryKey: ['personal-gitlab-connections', accountId], queryFn: gitlabApi.list })
  const devices = useQuery({ queryKey: ['source-runners', accountId], queryFn: sourceApi.devices, refetchInterval: 15000 })
  const [tab, setTab] = useState('repositories')
  const [repoEdit, setRepoEdit] = useState<Repository | 'new' | null>(null)
  const [treeEdit, setTreeEdit] = useState<Workspace | 'new' | null>(null)
  const [remove, setRemove] = useState<{ kind: 'repositories' | 'workspaces'; value: Repository | Workspace } | null>(null)
  const [selected, setSelected] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('')
  const [preparing, setPreparing] = useState<{ value: Workspace; key: string; deviceId: string; base?: Job; job?: Job } | null>(null)
  const act = async (fn: () => Promise<unknown>, text: string) => {
    if (busy) return
    setBusy(true); setError(''); setMessage('')
    try { await fn(); await list.refetch(); setMessage(text); setRemove(null); setPreparing(null) }
    catch (e) { setError(await sourceError(e, 'عملیات انجام نشد. دسترسی، اتصال و نسخهٔ اطلاعات را بررسی کنید.')) } finally { setBusy(false) }
  }
  const startPreparation = async () => {
    if (!preparing || busy || preparing.job) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = preparing.base ? await sourceApi.update(projectId, preparing.value, preparing.deviceId, preparing.key, preparing.base.id) : await sourceApi.prepare(projectId, preparing.value, preparing.deviceId, preparing.key)
      const job = { ...result, snapshot_revision: preparing.value.revision, update_of: preparing.base?.id, local_directory: preparing.base?.local_directory }
      queryClient.setQueryData<Awaited<ReturnType<typeof sourceApi.list>>>(queryKey, current => current ? { ...current, jobs: [job, ...current.jobs.filter(old => old.id !== job.id)] } : current)
      setPreparing(current => current ? { ...current, job } : current)
      void list.refetch()
    }
    catch (e) { setError(await sourceError(e, 'ثبت آماده‌سازی انجام نشد.')) }
    finally { setBusy(false) }
  }
  const data = list.data
  const updateBase = (tree: Workspace) => data?.jobs.find(job => job.source_workspace_id === tree.id && job.device_id === selected && !active(job) && (job.state === 'succeeded' || job.update_of))
  const preparation = preparing?.job && (data?.jobs.find(job => job.id === preparing.job?.id) || preparing.job)
  const activeDevices = devices.data?.data.filter(d => !d.revoked_at) || []
  return <main dir="rtl" className="h-full overflow-y-auto bg-background-body p-5 text-text-primary md:p-8"><div className="mx-auto max-w-5xl space-y-7">
    <header><h1 className="text-3xl font-bold">سورس کد</h1><p className="mt-3 text-sm leading-7 text-text-secondary">مخزن‌های پروژه، worktreeهای شخصی و مستندات ارتباط بخش‌ها. دریافت کد روی کامپیوتر شما با Runner محلی انجام می‌شود. آماده‌سازی اولیه پوشه می‌سازد؛ دفعات بعد سورس در همان پوشه به‌روز و تغییرات محلی با Git ادغام می‌شوند.</p><div className="mt-3 flex flex-wrap gap-5 text-sm text-text-accent"><Link href={`/projects/${projectId}/gitlab-connections`}>اتصال شخصی گیت‌لب</Link><Link href={`/projects/${projectId}/source-runners`}>راه‌اندازی و مدیریت Runner</Link></div></header>
    {message && <p role="status">{message}</p>}{error && <p role="alert" className="text-text-destructive-secondary">{error}</p>}
    {list.isPending ? <p role="status">در حال دریافت…</p> : list.isError && !data ? <p role="alert">دریافت اطلاعات انجام نشد. <button onClick={() => list.refetch()}>تلاش دوباره</button></p> : data && <>
      <DirectionProvider direction="rtl"><Tabs value={tab} onValueChange={next => setTab(String(next))}>
      <TabsList aria-label="بخش‌های سورس کد" className="mb-5 gap-5 overflow-x-auto border-b border-divider-regular"><TabsTab type="button" value="repositories">مخزن‌ها ({data.repositories.length})</TabsTab><TabsTab type="button" value="worktrees">worktreeهای من ({data.workspaces.length})</TabsTab></TabsList>
      <TabsPanel value="repositories"><section className="space-y-3"><div className="flex items-center justify-between gap-3"><h2 className="text-xl font-bold">مخزن‌های پروژه</h2><Button onClick={() => setRepoEdit('new')}>افزودن مخزن</Button></div>{!data.repositories.length && <p>هنوز مخزنی تعریف نشده است.</p>}{data.repositories.map(repo => <article key={repo.id} className="flex flex-wrap items-start gap-x-4 gap-y-2 rounded-xl border border-divider-regular bg-background-default px-4 py-3"><div className="min-w-0 flex-1 space-y-1"><h3 className="break-words font-semibold">{repo.name}</h3><p dir="ltr" className="break-all text-sm text-text-secondary">{repo.url}</p><p className="break-all text-xs text-text-tertiary">برنچ: <bdi>{repo.branch}</bdi> · نسخهٔ تعریف: {repo.revision}</p></div>{repo.can_edit && <div className="flex shrink-0 gap-2"><Button disabled={busy} aria-label={`ویرایش مخزن ${repo.name}`} onClick={() => setRepoEdit(repo)}>ویرایش</Button><Button disabled={busy} aria-label={`حذف مخزن ${repo.name}`} onClick={() => setRemove({ kind: 'repositories', value: repo })}><span className="text-text-destructive-secondary">حذف</span></Button></div>}</article>)}</section></TabsPanel>
      <TabsPanel value="worktrees" className="space-y-6">
      {data.jobs.some(active) && <section aria-label="آماده‌سازی‌های در حال انجام" className="space-y-3">{data.jobs.filter(active).map(job => <article key={job.id} className="rounded-xl border border-divider-regular bg-background-default p-4"><div role="status" className="flex items-start gap-3"><span aria-hidden className="i-ri-loader-2-line mt-1 size-5 shrink-0 animate-spin motion-reduce:animate-none" /><div><h3 className="font-semibold">{data.workspaces.find(tree => tree.id === job.source_workspace_id)?.name || 'worktree'} · {status[job.state]}</h3><p className="mt-2 text-sm leading-7 text-text-secondary">{progress[job.state]}</p></div></div><Button className="mt-3" disabled={busy} onClick={() => void act(() => sourceApi.cancel(projectId, job.id), 'درخواست لغو ثبت شد.')}>لغو آماده‌سازی</Button></article>)}</section>}
      {list.isError && <p role="alert" className="text-sm">اتصال برای دریافت وضعیت قطع شده است؛ آخرین وضعیت نمایش داده می‌شود. <button onClick={() => void list.refetch()}>تلاش دوباره</button></p>}
      <section className="space-y-4"><div className="flex justify-between gap-3"><h2 className="text-xl font-bold">worktreeهای من</h2><Button disabled={!data.repositories.length || !connections.data?.data.length} onClick={() => setTreeEdit('new')}>تعریف worktree</Button></div>{connections.isError && <p role="alert">دریافت اتصال‌های شخصی انجام نشد.</p>}{!connections.isPending && !connections.data?.data.length && <p>ابتدا در تنظیمات، اتصال شخصی گیت‌لب را تعریف کنید.</p>}{!data.workspaces.length && <p>هنوز worktree شخصی ندارید.</p>}
      <label className="block text-sm">Runner مقصد<select className={field} value={selected} onChange={e => setSelected(e.target.value)}><option value="">انتخاب Runner خودتان</option>{activeDevices.map(d => <option key={d.id} value={d.id}>{d.name} — {d.last_seen_at ? `آخرین ارتباط ${new Date(d.last_seen_at).toLocaleString('fa-IR')}` : 'هنوز متصل نشده'}</option>)}</select></label>{devices.isError && <p role="alert">دریافت Runnerها انجام نشد.</p>}
      {data.workspaces.map(tree => <article key={tree.id} className={card}><h3 className="font-semibold">{tree.name} · نسخهٔ {tree.revision}</h3>{tree.components.map(p => <p key={p.key} className="text-sm"><bdi>{p.path}</bdi> ← <bdi>{p.url} ({p.branch})</bdi></p>)}<details><summary className="cursor-pointer text-sm">مستندات ({tree.documents.length})</summary>{tree.documents.map(d => <div key={d.path} className="mt-3"><p dir="ltr">{d.path}</p><pre className="whitespace-pre-wrap text-sm">{d.content}</pre></div>)}</details><div className="flex flex-wrap gap-2"><Button disabled={busy || data.jobs.some(j => j.source_workspace_id === tree.id && ['pending', 'running'].includes(j.state))} onClick={() => setTreeEdit(tree)}>ویرایش worktree</Button><Button variant="primary" disabled={busy || !activeDevices.some(d => d.id === selected) || data.jobs.some(j => j.source_workspace_id === tree.id && ['pending', 'running'].includes(j.state))} onClick={() => { setError(''); setPreparing({ value: tree, key: crypto.randomUUID(), deviceId: selected, base: updateBase(tree) }) }}>{updateBase(tree) ? 'به‌روزرسانی در همین پوشه' : 'آماده‌سازی روی Runner'}</Button><Button disabled={busy} onClick={() => setRemove({ kind: 'workspaces', value: tree })}>حذف تعریف</Button></div></article>)}</section>
      <section className="space-y-4"><h2 className="text-xl font-bold">سابقهٔ آماده‌سازی من</h2>{!data.jobs.length && <p>هنوز آماده‌سازی انجام نشده است.</p>}{data.jobs.map(job => <article key={job.id} className={card}><h3>{data.workspaces.find(w => w.id === job.source_workspace_id)?.name || 'worktree حذف‌شده'} · {status[job.state] || job.state}{job.result?.superseded_by && ' · نسخهٔ جایگزین‌شده'}{job.update_of && ' · به‌روزرسانی درجا'}</h3><p className="text-xs">نسخهٔ تعریف: {job.snapshot_revision} · {new Date(job.created_at).toLocaleString('fa-IR')} · اجراکنندهٔ محلی: {devices.data?.data.find(d => d.id === job.device_id)?.name || job.device_id}</p><p dir="ltr" className="break-all text-xs">{job.id}</p>{job.result?.error && <p>{errors[job.result.error] || 'آماده‌سازی ناموفق بود.'}</p>}{job.result?.components?.map(p => <p key={p.key} dir="ltr" className="break-all font-mono text-xs">{p.key}: {p.commit}</p>)}{job.result?.local_directory && <p className="text-sm">پوشهٔ محلی زیر مسیر ریشهٔ Runner: <bdi>{job.result.local_directory}</bdi></p>}{['pending', 'running'].includes(job.state) && <Button disabled={busy} onClick={() => void act(() => sourceApi.cancel(projectId, job.id), 'درخواست لغو ثبت شد؛ Runner در بررسی بعدی متوقف می‌شود.')}>لغو آماده‌سازی</Button>}</article>)}</section>
      </TabsPanel></Tabs></DirectionProvider>
    </>}
    <p className="text-sm leading-7 text-text-tertiary">این بخش به برنامه‌ها، ایجنت‌ها یا فلوهای موجود متصل نشده است. دادهٔ کد روی Runner می‌ماند؛ این صفحه تعریف‌ها، مستندات نوشته‌شده و سابقهٔ commitها را نگه می‌دارد.</p>
    {repoEdit && <RepositoryEditor projectId={projectId} value={repoEdit === 'new' ? null : repoEdit} saved={list.refetch} close={() => setRepoEdit(null)} />}
    {treeEdit && <WorkspaceEditor projectId={projectId} value={treeEdit === 'new' ? null : treeEdit} repositories={data?.repositories || []} connections={connections.data?.data || []} saved={list.refetch} close={() => setTreeEdit(null)} />}
    {remove && <FormDialog open title="حذف تعریف سورس کد" description={`تعریف «${remove.value.name}» از فهرست فعال حذف می‌شود. فایل‌های محلی و سابقه حفظ می‌شوند. حذف مخزن، دریافت تازهٔ worktreeهای وابسته را تا بازبینی متوقف می‌کند.`} busy={busy} error={error} close={() => setRemove(null)}><Button disabled={busy} onClick={() => void act(() => sourceApi.remove(projectId, remove.kind, remove.value), 'تعریف حذف شد.')}>حذف تعریف</Button></FormDialog>}
    {preparing && <FormDialog open title={preparation ? 'وضعیت دریافت سورس کد' : preparing.base ? 'به‌روزرسانی در همین پوشه' : 'آماده‌سازی سورس کد'} description={preparing.base ? `«${preparing.value.name}» در پوشهٔ قبلی به‌روز می‌شود. commitها و تغییرات محلی با نسخهٔ جدید Git ادغام می‌شوند. هنگام تعارض، عملیات متوقف و پشتیبان تغییرات حفظ می‌شود. پوشهٔ تازه ساخته نمی‌شود.` : `«${preparing.value.name}» روی Runner انتخاب‌شده در پوشهٔ تازه آماده می‌شود.`} busy={busy} error={error} close={() => setPreparing(null)}>
      {preparation ? <div className="space-y-4"><div role="status" className="flex items-start gap-3">{active(preparation) && <span aria-hidden className="i-ri-loader-2-line mt-1 size-5 shrink-0 animate-spin motion-reduce:animate-none" />}<div><p className="font-semibold">{status[preparation.state] || preparation.state}</p><p className="mt-2 text-sm leading-7 text-text-secondary">{progress[preparation.state] || (preparation.state === 'succeeded' ? 'سورس کد آماده است. مسیر پوشه و commit بخش‌ها در سابقهٔ آماده‌سازی نمایش داده می‌شود.' : errors[preparation.result?.error || ''] || 'آماده‌سازی متوقف شد؛ وضعیت را در سابقه بررسی کنید.')}</p></div></div>{list.isError && <p role="alert">دریافت وضعیت فعلی انجام نشد؛ آخرین وضعیت نمایش داده می‌شود.</p>}<Button onClick={() => setPreparing(null)}>{active(preparation) ? 'بستن و ادامه در پس‌زمینه' : 'بستن'}</Button></div> : <Button variant="primary" loading={busy} disabled={busy} onClick={() => void startPreparation()}>{busy ? 'در حال ثبت درخواست…' : preparing.base ? 'ثبت به‌روزرسانی و ادغام' : 'ثبت آماده‌سازی'}</Button>}
    </FormDialog>}

  </div></main>
}
export default function SourceCode({ projectId }: { projectId: string }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  return <SourceContent key={`${projectId}:${profile.id}`} projectId={projectId} accountId={profile.id} />
}
