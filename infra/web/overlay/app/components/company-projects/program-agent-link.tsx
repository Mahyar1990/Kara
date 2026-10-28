'use client'
import { useQuery } from '@tanstack/react-query'
import { useAtomValue } from 'jotai'
import Link from '@/next/link'
import { currentWorkspaceIdAtom } from '@/context/workspace-state'
import { projectApi } from '@/service/company-projects'
import { directoryButton } from './team-directory'

export default function ProgramAgentLink({ appId }: { appId?: string }) {
  const workspace = useAtomValue(currentWorkspaceIdAtom)
  const context = useQuery({ queryKey: ['company-context', workspace], queryFn: projectApi.context, enabled: !!workspace })
  const project = context.data?.current_project
  if (!project) return null
  return <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-divider-regular bg-background-body px-5 py-3 text-sm" dir="rtl">{project.can_manage_members && <Link className={directoryButton} href={`/projects/${project.id}/program-agents${appId ? `?program=${appId}` : ''}`}>ایجنت‌های برنامه</Link>}<Link className={directoryButton} href={`/projects/${project.id}/program-settings${appId ? `?program=${appId}` : ''}`}>تنظیمات تیمی</Link><span className="text-xs text-text-tertiary">ایجنت‌های برنامه، دسترسی اعضا و روش‌های مجاز اجرا</span></div>
}
