'use client'

import { useQueryClient } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import { useCallback, useEffect, useState } from 'react'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import dynamic from '@/next/dynamic'
import { usePathname } from '@/next/navigation'
import FormDialog from './form-dialog'
import { useCompanyNavigation } from './navigation'
import { ProgramDialogState } from './program-dialog-state'

const AgentComposer = dynamic(() => import('./program-agents').then(module => module.ProgramAgentComposer), { ssr: false, loading: () => <p role="status">در حال دریافت ایجنت‌ها…</p> })
export type ProgramOption = { id: string; title: string; description?: string; icon: string; onClick: () => void }

export function useProgramOptions(app: { id: string; name?: string | null; mode?: string | null }) {
  const cache = useQueryClient()
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const pathname = usePathname()
  const { project } = useCompanyNavigation()
  const [open, setOpen] = useState(false)
  const [visited, setVisited] = useState(false)
  const [pending, setPending] = useState(0)
  const [definitionChanged, setDefinitionChanged] = useState(false)
  const change = useCallback((delta: number) => setPending(value => Math.max(0, value + delta)), [])
  useEffect(() => { setOpen(false); setVisited(false); setPending(0); setDefinitionChanged(false) }, [workspace, project?.id, app.id])
  const show = () => {
    void cache.invalidateQueries({ queryKey: ['program-roles'] })
    setVisited(true); setOpen(true)
  }
  const close = () => {
    if (pending) return
    setOpen(false)
    if (definitionChanged && pathname.includes(`/app/${app.id}/`)) window.location.reload()
  }
  const operations: ProgramOption[] = project?.can_manage_members && app.mode === 'workflow' ? [
    { id: 'company-program-agents', title: 'ایجنت‌های داخل برنامه', description: 'انتخاب ایجنت برای مراحل برنامه', icon: 'i-ri-robot-line', onClick: show },
  ] : []
  return {
    operations,
    dialogs: project && visited ? <ProgramDialogState.Provider value={{ busy: pending > 0, change }}><FormDialog open={open} keepMounted wide busy={pending > 0} title={`ایجنت‌های داخل برنامه · ${app.name || 'برنامه'}`} description="ایجنت را به مرحلهٔ همین برنامه وصل کنید. ابتدا تغییرات طراح را ذخیره کنید؛ پس از تغییر اتصال و بستن دیالوگ، طراح تازه می‌شود." close={close}>
      <div><AgentComposer project={project.id} appId={app.id} onDefinitionChanged={() => setDefinitionChanged(true)} /></div>
      <div className="mt-5 flex justify-end border-t border-divider-regular pt-4"><button type="button" disabled={pending > 0} className="rounded-lg border border-divider-regular px-4 py-2 text-sm disabled:opacity-50" onClick={close}>{definitionChanged && pathname.includes(`/app/${app.id}/`) ? 'بستن و تازه‌کردن طراح' : 'بستن'}</button></div>
    </FormDialog></ProgramDialogState.Provider> : null,
  }
}
