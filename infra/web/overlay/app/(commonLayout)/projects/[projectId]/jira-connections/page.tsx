import JiraConnections from '@/app/components/company-projects/jira-connections'

export const metadata = { title: 'اتصال به جیرا' }

export default async function JiraConnectionsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <JiraConnections projectId={projectId} />
}
