import type { Device } from '@/service/company-source'

export const panel = 'rounded-2xl border border-divider-regular bg-background-default p-5 md:p-6'
export const dateLabel = (value: string) => new Date(value).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })
export const stateLabels: Record<string, string> = { pending: 'در صف دستگاه', running: 'در حال اجرا', succeeded: 'انجام شد', failed: 'ناموفق', cancelled: 'لغو شد', interrupted: 'ارتباط قطع شد', blocked: 'نیازمند بررسی دسترسی یا نسخه' }

export function connectionState(device: Device) {
  if (device.revoked_at) return 'دسترسی لغوشده'
  if (!device.last_seen_at) return 'هنوز ارتباطی ثبت نشده'
  return Date.now() - new Date(device.last_seen_at).getTime() <= 90000 ? 'ارتباط تازه' : 'ارتباط تازه‌ای ندارد'
}

export function StateBadge({ state }: { state: string }) {
  return <span className={`inline-flex rounded-full border border-divider-regular px-2.5 py-1 text-xs font-medium ${state === 'running' ? 'bg-background-body text-text-accent' : 'text-text-secondary'}`}>{stateLabels[state] || state}</span>
}

export function ConnectionBadge({ device }: { device: Device }) {
  const fresh = !device.revoked_at && !!device.last_seen_at && Date.now() - new Date(device.last_seen_at).getTime() <= 90000
  return <span className="inline-flex items-center gap-2 rounded-full border border-divider-regular px-2.5 py-1 text-xs"><span aria-hidden className={`h-2 w-2 rounded-full ${fresh ? 'bg-text-accent' : 'bg-text-tertiary'}`} />{connectionState(device)}</span>
}
