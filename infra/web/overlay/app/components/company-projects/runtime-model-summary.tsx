export default function RuntimeModelSummary({ graph }: { graph?: unknown }) {
  const nodes = (graph as { nodes?: { id: string; data?: { type?: string; title?: string; kara_runtime_model_used?: { provider: string; model_name: string }; model?: { completion_params?: Record<string, unknown> } } }[] } | undefined)?.nodes
  if (!Array.isArray(nodes)) return null
  const selection = nodes.find(node => node.data?.type === 'start')?.data?.kara_runtime_model_used
  if (!selection) return null
  return <section dir="rtl" className="m-4 space-y-2 rounded-lg border border-divider-regular p-3 text-sm">
    <h3 className="font-medium">مدل این اجرا</h3><p dir="ltr">{selection.provider} · {selection.model_name}</p>
    <details><summary className="cursor-pointer text-xs">پارامترهای ثبت‌شدهٔ مراحل</summary>{nodes.filter(node => node.data?.type === 'llm').map(node => <div key={node.id} className="mt-2"><p className="text-xs">{node.data?.title || node.id}</p><pre dir="ltr" className="mt-1 whitespace-pre-wrap break-words text-xs">{JSON.stringify(node.data?.model?.completion_params || {}, null, 2)}</pre></div>)}</details>
  </section>
}
