'use client'

export default function RuntimeModelParameters({ value, change, disabled }: {
  value: Record<string, unknown>; change: (value: Record<string, unknown>) => void; disabled: boolean
}) {
  const update = (key: string, input: string) => {
    const next = { ...value }
    if (input === '') delete next[key]
    else next[key] = Number(input)
    change(next)
  }
  return <fieldset disabled={disabled} dir="rtl" className="space-y-3 rounded-lg border border-divider-regular p-3">
    <p className="text-sm font-medium">مدل شخصی انتخاب‌شده هنگام اجرا</p>
    <p className="text-xs leading-6 text-text-tertiary">این مرحله از ورودی «مدل اجرای برنامه» استفاده می‌کند. سازگاری مدل و تنظیمات پیش از اجرا بررسی می‌شود.</p>
    <label className="block text-xs">میزان تنوع پاسخ (temperature)<input className="mt-1 block w-full rounded border border-divider-regular bg-background-default p-2" type="number" step="any" value={String(value.temperature ?? '')} onChange={event => update('temperature', event.target.value)} /></label>
    <label className="block text-xs">حداکثر توکن پاسخ<input className="mt-1 block w-full rounded border border-divider-regular bg-background-default p-2" type="number" min={1} step={1} value={String(value.max_tokens ?? '')} onChange={event => update('max_tokens', event.target.value)} /></label>
    <button type="button" className="text-xs underline" onClick={() => change({})}>استفاده از پیش‌فرض‌های مدل برای پارامترهای این مرحله</button>
  </fieldset>
}
