import { useQuery } from '@tanstack/react-query'
import { projectApi } from './company-projects'

export function useCompanyMemberScope(workspaceId: string | null | undefined) {
  const context = useQuery({ queryKey: ['company-context', workspaceId], queryFn: projectApi.context, enabled: !!workspaceId })
  return { ready: context.isSuccess, product: context.data?.root_workspace_id === workspaceId }
}
