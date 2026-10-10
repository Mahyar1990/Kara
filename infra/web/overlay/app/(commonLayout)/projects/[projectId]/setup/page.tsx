import ProjectSetup from '@/app/components/company-projects/setup'
export default async function Page({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <ProjectSetup projectId={projectId} />
}
