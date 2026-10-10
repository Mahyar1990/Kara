import type { CompanyProject } from './company-projects'
import { get } from '@/service/base'

export type SetupSnapshot = {
  project: CompanyProject
  steps: { id: string; title: string; description: string; complete: boolean; required: boolean; href: string }[]
  completed: number
  required: number
  members: number
  apps: number
  model_name: string | null
}
export const adoptionApi = {
  setup: (id: string) => get<SetupSnapshot>(`/company/projects/${id}/setup`),
}
