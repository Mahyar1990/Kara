import TeamAgents from '@/app/components/company-projects/team-agents'

export const metadata = { title: 'ایجنت‌های تیم' }

export default async function TeamAgentsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <TeamAgents projectId={projectId} />
}
