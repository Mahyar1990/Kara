'use client'

import { useProgramDialogState } from './program-dialog-state'

import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { agentApi } from '@/service/company-agents'
import { flowApi } from '@/service/company-flows'
import { jiraError } from '@/service/company-jira'
import FormDialog, { FieldHelp } from './form-dialog'

export default function DeleteTeamEntity({ project, kind, value, close, deleted, label: customLabel }: {
  project: string; kind: 'agent' | 'flow'; label?: string; value: { id: string; name: string; revision: number }
  close: () => void; deleted: () => Promise<unknown>
}) {
  const label = customLabel || (kind === 'agent' ? 'تنظیم تیمی' : 'فلو')
  const { change } = useProgramDialogState()
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const key = useRef<string | null>(null)
  const queryClient = useQueryClient()
  const remove = async () => {
    if (busy || confirmation !== value.name) return
    setBusy(true); change(1); setError('')
    key.current ||= crypto.randomUUID()
    try {
      const api = kind === 'agent' ? agentApi : flowApi
      await api.remove(project, value.id, value.revision, confirmation, key.current)
      await queryClient.invalidateQueries({ queryKey: ['team-flow-options'] })
      await deleted()
      close()
    } catch (error) { setError(await jiraError(error, `حذف ${label} انجام نشد؛ اطلاعات تازه را دریافت و دوباره تلاش کنید.`)) }
    finally { setBusy(false); change(-1) }
  }
  return <FormDialog open title={`حذف ${label}`} description={`${label} از فهرست و انتخاب‌های جدید حذف می‌شود. برنامهٔ اصلی، نسخه‌های منتشرشده و سوابق اجرا و تصمیم‌ها حفظ می‌شوند.`} busy={busy} error={error} close={close}>
    <form className="space-y-4" onSubmit={event => { event.preventDefault(); void remove() }}>
      <p className="whitespace-pre-wrap break-words rounded-lg bg-background-section p-3 font-medium" dir="auto">{value.name}</p>
      <label className="block text-sm">نام کامل {label}<input autoComplete="off" spellCheck={false} required disabled={busy} className="mt-2 block w-full rounded-lg border border-divider-regular bg-background-default p-3 text-text-primary" value={confirmation} onChange={event => setConfirmation(event.target.value)} /><FieldHelp>برای تأیید حذف، نام بالا را کامل و دقیق وارد کنید؛ فاصله‌ها و حروف باید یکسان باشند.</FieldHelp></label>
      <div className="flex gap-3"><button type="submit" disabled={busy || confirmation !== value.name} className="rounded-lg border border-divider-regular px-4 py-2 text-sm text-text-destructive-secondary disabled:opacity-50">{busy ? 'در حال حذف…' : `حذف ${label}`}</button><button type="button" disabled={busy} className="rounded-lg border border-divider-regular px-4 py-2 text-sm" onClick={close}>انصراف</button></div>
    </form>
  </FormDialog>
}
