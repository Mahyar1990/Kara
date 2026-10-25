import TeamRequests from '@/app/components/company-projects/team-requests'

export const metadata = { title: 'درخواست‌های پروژه' }

export default async function TeamRequestsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <TeamRequests projectId={projectId} />
}
