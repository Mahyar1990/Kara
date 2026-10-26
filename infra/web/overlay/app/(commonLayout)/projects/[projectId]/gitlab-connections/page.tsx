import GitLabConnections from '@/app/components/company-projects/gitlab-connections'

export const metadata = { title: 'اتصال به گیت‌لب' }

export default async function GitLabConnectionsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <GitLabConnections projectId={projectId} />
}
