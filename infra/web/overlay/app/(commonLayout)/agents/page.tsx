import { getRouteMetadata } from '@/app/route-metadata'
import AgentLibrary from '@/app/components/company-projects/agent-library'
import { Suspense } from 'react'

export function generateMetadata() {
  return getRouteMetadata('agentV2', ($) => $['roster.title'])
}

export default function Page() {
  return <Suspense fallback={<p className="p-5" dir="rtl">در حال دریافت کتابخانهٔ ایجنت‌ها…</p>}><AgentLibrary /></Suspense>
}
