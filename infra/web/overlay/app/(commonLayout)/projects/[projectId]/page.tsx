import { ProjectDetail } from '@/app/components/company-projects'

export const metadata = { title: 'مدیریت پروژه' }

export default async function ProjectPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <ProjectDetail projectId={projectId} />
}
