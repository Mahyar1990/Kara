import ProjectInbox from '@/app/components/company-projects/inbox'
export default async function Page({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <ProjectInbox projectId={projectId} />
}
