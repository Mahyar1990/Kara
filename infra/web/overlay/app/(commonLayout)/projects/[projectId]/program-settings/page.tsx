import ProgramTeamSettings from '@/app/components/company-projects/program-team-settings'

export const metadata = { title: 'تنظیمات قبلی برنامه‌ها' }

export default async function Page({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <ProgramTeamSettings projectId={projectId} />
}
