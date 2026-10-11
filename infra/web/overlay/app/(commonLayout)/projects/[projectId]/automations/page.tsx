import ProjectAutomations from '@/app/components/company-projects/automations'

export default async function Page({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <ProjectAutomations projectId={projectId} />
}
