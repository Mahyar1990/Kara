'use client'

import { useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { userProfileQueryOptions } from '@/features/account-profile/client'
import { modelConnectionApi } from '@/service/company-models'

export default function RuntimeModelPicker({ value, onChange, capabilities = [], disabled = false }: {
  value?: string; onChange: (value: string) => void; capabilities?: string[]; disabled?: boolean
}) {
  const { data: { profile } } = useSuspenseQuery(userProfileQueryOptions())
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const required = [...new Set(capabilities)].sort()
  const models = useQuery({ queryKey: ['personal-runtime-models', profile.id, workspace, required], queryFn: () => modelConnectionApi.runtimeOptions(required) })
  return <div dir="rtl" className="space-y-2">
    <select aria-label="مدل اجرای برنامه" className="block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-sm text-text-primary" disabled={disabled || !models.isSuccess} value={value || ''} onChange={event => onChange(event.target.value)}>
      <option value="">مدل پیش‌فرض شخصی من{models.data?.data.find(model => model.is_default) ? ` · ${models.data.data.find(model => model.is_default)!.model_name}` : ''}</option>
      {models.data?.data.map(model => <option key={model.id} value={model.id}>{model.name} · {model.model_name}{model.is_default ? ' · پیش‌فرض' : ''}</option>)}
    </select>
    <p className="text-xs leading-6 text-text-tertiary">فقط اتصال‌های شخصی سازگار شما نمایش داده می‌شوند. خالی‌گذاشتن انتخاب، مدل پیش‌فرض شخصی را استفاده می‌کند. توکن در سمت سرور خوانده می‌شود.</p>
    {models.isPending && <p role="status" className="text-xs">در حال دریافت مدل‌های شخصی…</p>}
    {models.isError && <p role="alert" className="text-xs">دریافت مدل‌ها انجام نشد. <button type="button" onClick={() => models.refetch()}>تلاش دوباره</button></p>}
    {models.isSuccess && !models.data.data.length && <p role="alert" className="text-xs leading-6">مدل شخصی سازگاری در این پروژه ندارید. از «تنظیمات و اتصال‌ها ← اتصال به مدل هوش مصنوعی» اتصال خودتان را ثبت کنید.</p>}
    {models.isSuccess && value && !models.data.data.some(model => model.id === value) && <p role="alert" className="text-xs">مدل قبلی در فهرست اتصال‌های سازگار شما نیست؛ انتخاب را تازه کنید.</p>}
  </div>
}
