import type { TeamAgent } from './company-agents'
import { get } from '@/service/base'

export type TeamProgram = { id: string; name: string; description: string; available: boolean; library_adapter: boolean; profiles: TeamAgent[] }
export const programTeamApi = {
  list: (project: string) => get<{ can_manage: boolean; programs: TeamProgram[] }>(`/company/projects/${project}/program-team`),
}
