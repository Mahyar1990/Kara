import type { CredentialFormSchema } from '@/app/components/header/account-setting/model-provider-page/declarations'
import { del, get, post, put } from '@/service/base'

export type PersonalModel = { id: string; name: string; provider: string; model_name: string; model_type: string; is_default: boolean; revision: number; credentials_configured: boolean; values?: Record<string, unknown> }
export type PersonalProvider = { provider: string; label: Record<string, string>; model_types: string[]; fields: (CredentialFormSchema & { secret: boolean })[] }
export type PersonalModelDraft = { name: string; provider: string; model_name: string; model_type: string; credentials: Record<string, unknown>; is_default: boolean; expected_revision: number }
const base = '/company/me/model-connections'
export const modelConnectionApi = {
  list: () => get<{ data: PersonalModel[] }>(base),
  providers: () => get<{ data: PersonalProvider[] }>(`${base}/providers`),
  runtimeOptions: (capabilities: string[]) => get<{ data: PersonalModel[] }>(`${base}/runtime-options?capabilities=${encodeURIComponent(capabilities.join(','))}`),
  detail: (id: string) => get<PersonalModel>(`${base}/${id}`),
  save: (id: string | null, body: PersonalModelDraft) => id ? put<PersonalModel>(`${base}/${id}`, { body }) : post<PersonalModel>(base, { body }),
  copy: (id: string, body: PersonalModelDraft) => post<PersonalModel>(`${base}/${id}/copy`, { body }),
  remove: (value: PersonalModel) => del(`${base}/${value.id}`, { body: { expected_revision: value.revision } }),
  test: (id: string) => post<{ connected: boolean; message: string }>(`${base}/${id}/test`),
}
