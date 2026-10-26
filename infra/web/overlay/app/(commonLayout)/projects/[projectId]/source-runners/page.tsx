import SourceRunners from '@/app/components/company-projects/source-runners'

export const metadata = { title: 'Runnerهای شخصی' }

export default async function Page({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <SourceRunners projectId={projectId} />
}
