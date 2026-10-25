'use client'

import type { ReactNode } from 'react'
import type { ModelProviderPluginSummaryResponse } from '@dify/contracts/api/console/workspaces/types.gen'
import PersonalModelConnections from '@/app/components/company-projects/model-connections'

export type ModelProviderPluginSummary = ModelProviderPluginSummaryResponse & { latestVersion?: string; latestUniqueIdentifier?: string }
type Props = { layout?: (parts: { body: ReactNode; toolbar: ReactNode }) => ReactNode; searchText: string; onOpenMarketplace?: () => void; onSearchTextChange?: (value: string) => void; stickyToolbar?: boolean; hideSystemModelSelectorProviderSettingsFooter?: boolean }

export default function ModelProviderPage({ layout }: Props) {
  const body = <PersonalModelConnections />
  return layout ? layout({ body, toolbar: null }) : body
}
