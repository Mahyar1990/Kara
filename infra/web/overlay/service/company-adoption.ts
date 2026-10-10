import type { CompanyProject } from './company-projects'
import { get, post } from '@/service/base'

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
  templates: (id: string) => get<TemplateCatalog>(`/company/projects/${id}/templates`),
  copy: (id: string, template: string, body: { name: string; dataset_id?: string }) => post<{ id: string; name: string }>(`/company/projects/${id}/templates/${template}/copies`, { body }),
}
export type StarterTemplate = { id: string; version: string; name: string; description: string; requires_knowledge: boolean; example_input: string }
export type TemplateCatalog = { data: StarterTemplate[]; model_name: string | null; datasets: { id: string; name: string }[] }
