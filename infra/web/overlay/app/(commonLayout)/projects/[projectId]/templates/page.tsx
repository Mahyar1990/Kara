import ProjectTemplates from '@/app/components/company-projects/templates'
export default async function Page({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <ProjectTemplates projectId={projectId} />
}
