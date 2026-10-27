import { Suspense } from 'react'
import ProgramAgents from '@/app/components/company-projects/program-agents'

export const metadata = { title: 'ایجنت‌های برنامه' }
export default async function Page({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <Suspense fallback={<p className="p-5" dir="rtl">در حال دریافت اطلاعات برنامه…</p>}><ProgramAgents projectId={projectId} /></Suspense>
}
