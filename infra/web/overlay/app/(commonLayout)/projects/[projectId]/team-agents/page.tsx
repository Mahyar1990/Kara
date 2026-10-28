import { redirect } from '@/next/navigation'

export default async function Page({ params, searchParams }: {
  params: Promise<{ projectId: string }>
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const { projectId } = await params
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(await searchParams)) {
    for (const item of Array.isArray(value) ? value : value === undefined ? [] : [value]) query.append(key, item)
  }
  redirect(`/projects/${projectId}/program-settings${query.size ? `?${query}` : ''}`)
}
