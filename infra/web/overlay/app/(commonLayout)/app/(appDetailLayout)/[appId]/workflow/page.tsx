import WorkflowApp from '@/app/components/workflow-app'
import ProgramAgentLink from '@/app/components/company-projects/program-agent-link'

export default async function Page({ params }: { params: Promise<{ appId: string }> }) {
  const { appId } = await params
  return <div className="flex size-full min-h-0 flex-col"><ProgramAgentLink appId={appId} /><div className="min-h-0 grow overflow-x-auto"><WorkflowApp /></div></div>
}
