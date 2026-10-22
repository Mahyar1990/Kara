import TeamRuns from '@/app/components/company-projects/team-runs'

export const metadata = { title: 'اجرای تیمی' }

export default async function TeamRunsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <TeamRuns projectId={projectId} />
}
