import SourceCode from '@/app/components/company-projects/source-code'

export const metadata = { title: 'سورس کد' }

export default async function Page({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <SourceCode projectId={projectId} />
}
