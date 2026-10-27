import { Apps } from '@/app/components/apps'
import { getRouteMetadata } from '@/app/route-metadata'
import ProgramAgentLink from '@/app/components/company-projects/program-agent-link'

export function generateMetadata() {
  return getRouteMetadata('common', ($) => $['menus.apps'])
}

export default function AppsPage() {
  return <div className="flex h-full min-h-0 grow flex-col"><ProgramAgentLink /><div className="flex min-h-0 grow flex-col"><Apps /></div></div>
}
