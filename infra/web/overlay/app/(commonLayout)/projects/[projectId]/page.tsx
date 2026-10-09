import { ProjectDetail } from '@/app/components/company-projects'

export const metadata = { title: 'مدیریت پروژه — Dify' }

export default async function ProjectPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <ProjectDetail projectId={projectId} />
}
