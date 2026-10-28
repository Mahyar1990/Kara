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

const TeamEditor = dynamic(() => import('./program-team-settings').then(module => module.ProgramTeamEditor), { ssr: false, loading: () => <p role="status">در حال دریافت تنظیمات…</p> })
const AgentComposer = dynamic(() => import('./program-agents').then(module => module.ProgramAgentComposer), { ssr: false, loading: () => <p role="status">در حال دریافت ایجنت‌ها…</p> })
export type ProgramOption = { id: string; title: string; icon: string; onClick: () => void }

export function useProgramOptions(app: { id: string; name?: string | null; mode?: string | null }) {
  const cache = useQueryClient()
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const pathname = usePathname()
  const { project } = useCompanyNavigation()
  const [panel, setPanel] = useState<'team' | 'agents'>('team')
  const [open, setOpen] = useState(false)
  const [visited, setVisited] = useState({ team: false, agents: false })
  const [pending, setPending] = useState(0)
  const [definitionChanged, setDefinitionChanged] = useState(false)
  const change = useCallback((delta: number) => setPending(value => Math.max(0, value + delta)), [])
  useEffect(() => { setOpen(false); setVisited({ team: false, agents: false }); setPending(0); setDefinitionChanged(false) }, [workspace, project?.id, app.id])
  const show = (next: 'team' | 'agents') => {
    void cache.invalidateQueries({ queryKey: next === 'team' ? ['program-team', workspace, project?.id] : ['program-roles'] })
    setPanel(next); setVisited(value => ({ ...value, [next]: true })); setOpen(true)
  }
  const close = () => {
    if (pending) return
    setOpen(false)
    if (definitionChanged && pathname.includes(`/app/${app.id}/`)) window.location.reload()
  }
  const operations: ProgramOption[] = project && app.mode === 'workflow' ? [
    { id: 'company-team-execution', title: 'اجرای تیمی', icon: 'i-ri-team-line', onClick: () => show('team') },
    ...(project.can_manage_members ? [{ id: 'company-program-agents', title: 'ایجنت‌های این برنامه', icon: 'i-ri-robot-line', onClick: () => show('agents') } satisfies ProgramOption] : []),
  ] : []
  return {
    operations,
    dialogs: project && (visited.team || visited.agents) ? <ProgramDialogState.Provider value={{ busy: pending > 0, change }}><FormDialog open={open} keepMounted wide busy={pending > 0} title={`${panel === 'team' ? 'اجرای تیمی' : 'ایجنت‌های برنامه'} · ${app.name || 'برنامه'}`} description={panel === 'team' ? 'نسخه، دسترسی اعضا و روش‌های مجاز اجرای همین برنامه را تنظیم کنید.' : 'ایجنت کتابخانه را به مرحلهٔ همین برنامه وصل کنید. ابتدا تغییرات طراح را ذخیره کنید؛ پس از تغییر اتصال و بستن دیالوگ، طراح تازه می‌شود.'} close={close}>
      {visited.team && <div hidden={panel !== 'team'}><TeamEditor projectId={project.id} appId={app.id} /></div>}
      {visited.agents && <div hidden={panel !== 'agents'}><AgentComposer project={project.id} appId={app.id} onDefinitionChanged={() => setDefinitionChanged(true)} /></div>}
      <div className="mt-5 flex justify-end border-t border-divider-regular pt-4"><button type="button" disabled={pending > 0} className="rounded-lg border border-divider-regular px-4 py-2 text-sm disabled:opacity-50" onClick={close}>{definitionChanged && pathname.includes(`/app/${app.id}/`) ? 'بستن و تازه‌کردن طراح' : 'بستن'}</button></div>
    </FormDialog></ProgramDialogState.Provider> : null,
  }
}
