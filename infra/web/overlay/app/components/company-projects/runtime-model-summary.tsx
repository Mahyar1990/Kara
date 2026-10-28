export default function RuntimeModelSummary({ graph }: { graph?: unknown }) {
  const nodes = (graph as { nodes?: { id: string; data?: { type?: string; title?: string; kara_runtime_runners_used?: Record<string, { device_name: string; device_id: string }>; kara_runtime_model_used?: { version?: number; provider?: string; model_name?: string; models?: Record<string, { provider: string; model_name: string }> }; model?: { completion_params?: Record<string, unknown> } } }[] } | undefined)?.nodes
  if (!Array.isArray(nodes)) return null
  const selection = nodes.find(node => node.data?.type === 'start')?.data?.kara_runtime_model_used
  const runners = nodes.find(node => node.data?.type === 'start')?.data?.kara_runtime_runners_used
  if (!selection && !runners) return null
  return <section dir="rtl" className="m-4 space-y-2 rounded-lg border border-divider-regular p-3 text-sm">
    <h3 className="font-medium">مدل‌های این اجرا</h3>{selection?.version === 2 ? nodes.filter(node => node.data?.type === 'llm').map(node => <p key={node.id}>{node.data?.title || node.id}: <bdi>{selection.models?.[node.id]?.provider} · {selection.models?.[node.id]?.model_name}</bdi></p>) : <p dir="ltr">{selection?.provider} · {selection?.model_name}</p>}
    {runners && <div className="space-y-1"><h4 className="font-medium">Runner هر گام</h4>{Object.entries(runners).map(([id, runner]) => <p key={id}>{nodes.find(node => node.id === id)?.data?.title || id}: {runner.device_name} <bdi className="text-xs text-text-tertiary">{runner.device_id.slice(0, 8)}</bdi></p>)}</div>}
    <details><summary className="cursor-pointer text-xs">پارامترهای ثبت‌شدهٔ مراحل</summary>{nodes.filter(node => node.data?.type === 'llm').map(node => <div key={node.id} className="mt-2"><p className="text-xs">{node.data?.title || node.id}</p><pre dir="ltr" className="mt-1 whitespace-pre-wrap break-words text-xs">{JSON.stringify(node.data?.model?.completion_params || {}, null, 2)}</pre></div>)}</details>
  </section>
}
