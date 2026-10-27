'use client'
import { useSuspenseQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import { harnessApi } from '@/service/company-harness'
import { sourceError } from '@/service/company-source'
export default function HarnessPolicyEditor({ project, agent }: { project: string; agent: string }) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  const cache = useQueryClient()
  const query = useQuery({ queryKey: ['harness-policy', profile.id, project, agent], queryFn: () => harnessApi.policy(project, agent) })
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('')
  const save = async (form: HTMLFormElement) => {
    if (!query.data || busy) return
    const fields = new FormData(form)
    setBusy(true); setError(''); setMessage('')
    try { await harnessApi.savePolicy(project, agent, { expected_revision: query.data.policy.revision, enabled: fields.get('enabled') === 'on', instructions: String(fields.get('instructions') || ''), requires_source: fields.get('source') === 'on' }); await cache.invalidateQueries({ queryKey: ['harness-policy', profile.id, project, agent] }); setMessage('روش مجاز اجرا ذخیره شد.') }
    catch (e) { setError(await sourceError(e, 'ذخیرهٔ تنظیم هارنس انجام نشد.')) } finally { setBusy(false) }
  }
  return <details className="space-y-4 border-t border-divider-regular pt-4"><summary className="cursor-pointer font-semibold">تنظیم اجازهٔ استفاده از هارنس</summary>{query.isPending ? <p>در حال دریافت…</p> : query.isError ? <p role="alert">دریافت تنظیم انجام نشد. <button onClick={() => void query.refetch()}>تلاش دوباره</button></p> : query.data.can_manage && <form key={query.data.policy.revision} className="space-y-4" onSubmit={e => { e.preventDefault(); void save(e.currentTarget) }}><p className="text-xs leading-7 text-text-secondary">این اجازه مخصوص همین نسخهٔ برنامه است. مأموریت باید معیار پذیرش و نحوهٔ تحویل خروجی‌های {query.data.output_contract.join('، ')} را مشخص کند.</p>{!query.data.compatible && <p role="status" className="text-sm">{query.data.reason}</p>}<fieldset disabled={busy} className="space-y-4"><label className="flex items-center gap-2 text-sm"><input name="enabled" type="checkbox" defaultChecked={query.data.policy.enabled} disabled={!query.data.compatible} />مجری بتواند هارنس شخصی را انتخاب کند</label><label className="block text-sm">مأموریت و معیار پذیرش<textarea name="instructions" maxLength={32000} defaultValue={query.data.policy.instructions} className="mt-2 min-h-40 w-full rounded-lg border border-divider-regular bg-background-default p-3" /></label><label className="flex items-center gap-2 text-sm"><input name="source" type="checkbox" defaultChecked={query.data.policy.requires_source} />سورس آماده‌شده و پوشهٔ مستقل تسک الزامی باشد</label><button type="submit" className="rounded-lg border border-divider-regular px-4 py-2 text-sm">ذخیرهٔ روش مجاز اجرا</button></fieldset></form>}{error && <p role="alert" className="text-sm">{error}</p>}{message && <p role="status" className="text-sm">{message}</p>}</details>
}
