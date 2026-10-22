import TeamFlows from '@/app/components/company-projects/team-flows'

export const metadata = { title: 'فلوهای تیم' }

export default async function TeamFlowsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <TeamFlows projectId={projectId} />
}
