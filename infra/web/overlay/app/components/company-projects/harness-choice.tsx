'use client'
import type { ExecutionChoice } from '@/service/company-harness'
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import Link from '@/next/link'
import { useSuspenseQuery } from '@tanstack/react-query'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import { harnessApi } from '@/service/company-harness'
import { sourceApi } from '@/service/company-source'
const field = 'mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-sm'
export default function HarnessChoice({ project, agent, value, change, valid }: { project: string; agent: string; value: ExecutionChoice | null; change: (v: ExecutionChoice | null) => void; valid: (v: boolean) => void }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  const policy = useQuery({ queryKey: ['harness-policy', profile.id, project, agent], queryFn: () => harnessApi.policy(project, agent) })
  const profiles = useQuery({ queryKey: ['harness-profiles', profile.id], queryFn: harnessApi.profiles, enabled: !!value, refetchInterval: value ? 15000 : false })
  const sources = useQuery({ queryKey: ['source-code', project, profile.id], queryFn: () => sourceApi.list(project), enabled: !!value })
  const device = profiles.data?.devices.find(d => d.id === value?.device_id)
  const enabled = policy.data?.compatible && policy.data.policy.enabled
  const sourceJobs = sources.data?.jobs.filter(j => j.device_id === value?.device_id && j.state === 'succeeded') || []
  const ready = !value || !!(enabled && !profiles.isError && !sources.isError && device && (value.mode === 'manual' || device.harnesses.some(p => p.key === value.profile_key)) && (!policy.data?.policy.requires_source || sourceJobs.some(j => j.id === value.source_job_id)))
  useEffect(() => { valid(ready) }, [ready, valid])
  return <section className="my-4 space-y-4 rounded-xl border border-divider-regular p-4" aria-label="انتخاب روش انجام کار"><h3 className="font-semibold">روش انجام کار</h3><label className="flex items-center gap-2 text-sm"><input type="radio" checked={!value} onChange={() => change(null)} />اجرای مراحل برنامه</label><label className="flex items-center gap-2 text-sm"><input type="radio" checked={!!value} disabled={!enabled} onChange={() => change({ method: 'harness', mode: 'manual', device_id: '', source_job_id: null, profile_key: null })} />انجام کار با ابزار شخصی</label>
    {policy.isError && <p role="alert" className="text-xs">دریافت تنظیم هارنس انجام نشد. <button type="button" onClick={() => void policy.refetch()}>تلاش دوباره</button></p>}
    {policy.isSuccess && !enabled && <p className="text-xs leading-6 text-text-tertiary">{policy.data.reason || 'مسئول دارای مجوز انتشار باید مأموریت هارنس این نسخه را فعال کند.'}</p>}
    {value && <div className="space-y-4"><label className="block text-sm">شیوهٔ کار<select className={field} value={value.mode} onChange={e => change({ ...value, mode: e.target.value as 'manual' | 'managed', profile_key: null })}><option value="manual">تعاملی در ابزار خودم؛ تحویل نتیجه در کارا</option><option value="managed">اجرای خودکار هارنس با Runner</option></select></label><label className="block text-sm">دستگاه انجام تسک<select className={field} value={value.device_id} onChange={e => change({ ...value, device_id: e.target.value, profile_key: null, source_job_id: null })}><option value="">انتخاب دستگاه</option>{profiles.data?.devices.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
      {value.mode === 'managed' && <label className="block text-sm">هارنس مجاز روی همین دستگاه<select className={field} value={value.profile_key || ''} onChange={e => change({ ...value, profile_key: e.target.value || null })}><option value="">انتخاب هارنس</option>{device?.harnesses.map(p => <option key={p.key} value={p.key}>{p.name}{p.version ? ` · ${p.version}` : ''}</option>)}</select></label>}
      <label className="block text-sm">سورس آماده‌شده{policy.data?.policy.requires_source ? ' (الزامی)' : ' (اختیاری)'}<select className={field} value={value.source_job_id || ''} onChange={e => change({ ...value, source_job_id: e.target.value || null })}><option value="">بدون سورس</option>{sourceJobs.map(j => <option key={j.id} value={j.id}>{sources.data?.workspaces.find(w => w.id === j.source_workspace_id)?.name || 'worktree'} · نسخهٔ {j.snapshot_revision} · {new Date(j.created_at).toLocaleString('fa-IR')}</option>)}</select></label>
      {(profiles.isError || sources.isError) && <p role="alert" className="text-xs">دریافت دستگاه یا سورس انجام نشد. <button type="button" onClick={() => { void profiles.refetch(); void sources.refetch() }}>تلاش دوباره</button></p>}
      {value.mode === 'managed' && device && !device.harnesses.length && <p className="text-xs leading-6">روی این دستگاه هارنس خودکار ثبت نشده است. بستهٔ تازه و راهنمای هارنس را از <Link className="text-text-accent" href={`/projects/${project}/source-runners`}>Runnerهای شخصی</Link> دریافت کنید.</p>}
      <p className="text-xs leading-7 text-text-secondary">Runner پوشهٔ مستقل تسک را از سورس انتخاب‌شده آماده می‌کند. هارنس از حساب و مدل خودش استفاده می‌کند. پس از انجام، نتیجه برای بررسی و نهایی‌سازی در همین تسک ثبت می‌شود.</p><details><summary className="cursor-pointer text-xs">مأموریت و معیارهای هارنس این نسخه</summary><p className="mt-2 whitespace-pre-wrap text-sm leading-7">{policy.data?.policy.instructions}</p></details>
    </div>}
  </section>
}
