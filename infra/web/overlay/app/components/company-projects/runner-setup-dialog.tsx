'use client'

import { Button } from '@langgenius/dify-ui/button'
import { useState } from 'react'
import FormDialog from './form-dialog'

export type RunnerGuide = 'download' | 'run' | 'code' | 'harness' | 'storage'
const titles: Record<RunnerGuide, string> = { download: 'دریافت و آماده‌سازی بستهٔ Runner', run: 'اجرای Runner روی دستگاه', code: 'راه‌اندازی محیط اجرای کد', harness: 'استفاده از هارنس شخصی', storage: 'فایل‌ها و دسترسی‌های Runner' }

export function RunnerCommand({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState(false)
  return <div className="rounded-lg border border-divider-regular bg-background-body p-3"><pre dir="ltr" className="overflow-x-auto whitespace-pre text-left text-xs leading-6">{value}</pre><button className="mt-2 text-xs text-text-accent" type="button" onClick={async () => { try { await navigator.clipboard.writeText(value); setCopied(true); setError(false) } catch { setError(true) } }}>{copied ? 'کپی شد · کپی دوباره' : 'کپی دستور'}</button>{error && <p role="status" className="mt-2 text-xs">کپی خودکار در دسترس نیست؛ متن دستور را انتخاب و کپی کنید.</p>}</div>
}

export default function RunnerSetupDialog({ guide, busy, error, download, close }: { guide: RunnerGuide; busy: boolean; error: string; download: () => Promise<boolean>; close: () => void }) {
  const [downloaded, setDownloaded] = useState(false)
  return <FormDialog open title={titles[guide]} description="دستورها را روی همان کامپیوتر یا VDI که می‌خواهید کارها را انجام دهد اجرا کنید." busy={busy} error={error} close={close}>
    <div className="space-y-4 text-sm leading-7">
      {guide === 'download' && <><p>Python نسخهٔ ۳.۱۰ یا بالاتر و Git لازم است. در Windows از WSL استفاده کنید. بسته را در پوشه‌ای خصوصی باز و دستورهای زیر را در همان پوشه اجرا کنید.</p><Button variant="primary" loading={busy} onClick={async () => { setDownloaded(false); setDownloaded(await download()) }}>{busy ? 'در حال دریافت بسته…' : 'دریافت بستهٔ Runner'}</Button>{downloaded && !busy && !error && <p role="status" className="text-xs text-text-secondary">دریافت بسته آغاز شد؛ فایل ZIP را در پوشهٔ خصوصی دستگاه مقصد باز کنید.</p>}<RunnerCommand value={'python3 -m venv .venv\nsource .venv/bin/activate\npython -m pip install -r requirements.txt'} /><p className="text-xs text-text-secondary">برای دستگاه تازه از «اتصال دستگاه تازه» کد بگیرید. برای به‌روزرسانی دستگاه متصل، فایل خصوصی تنظیمات قبلی را حفظ کنید؛ اتصال دوباره لازم نیست.</p></>}
      {guide === 'run' && <><p>پس از آماده‌کردن بسته و اتصال دستگاه، این دستور را در پوشهٔ بسته اجرا کنید:</p><RunnerCommand value="python -m kara_source_runner run" /><p>ترمینال را باز نگه دارید. سپس در «مقصد اجرای پروژه» دستگاه را انتخاب و ذخیره کنید. برای دریافت مخزن‌ها، Runner را هنگام آماده‌سازی در صفحهٔ «سورس کد» انتخاب کنید.</p><p className="text-xs text-text-secondary">با بستن ترمینال یا خاموش‌شدن دستگاه، Runner متوقف می‌شود. اجرای قطع‌شده خودکار تکرار نمی‌شود.</p></>}
      {guide === 'code' && <><p>محیط اجرای گره‌های کد را روی همان دستگاه آماده کنید. قابلیت‌های کارت دستگاه پس از اجرای Runner به‌روز می‌شوند.</p><h3 className="font-semibold">با Docker</h3><p>دستورها را در پوشهٔ بسته اجرا کنید. گرهٔ کد در کانتینر جدا و بدون شبکه اجرا می‌شود؛ تصویرها هنگام کار خودکار دریافت نمی‌شوند.</p><RunnerCommand value={'docker build -f Dockerfile.code -t kara/code-python:2.0 .\ndocker pull node:22-alpine\npython -m kara_source_runner run'} /><h3 className="font-semibold">بدون Docker؛ برای برنامه‌های مورد اعتماد</h3><p>این حالت sandbox سیستم‌عامل ندارد؛ کد با دسترسی فایل و شبکهٔ حساب شما اجرا می‌شود و به فعال‌سازی صریح نیاز دارد. JavaScript به Node نصب‌شده نیاز دارد.</p><RunnerCommand value="python -m kara_source_runner run --code-backend process --allow-local-code" /><p className="text-xs text-text-secondary">برای نوشتن در worktree در حالت Docker، گزینهٔ <bdi>--allow-worktree-write</bdi> را اضافه کنید. بدون محیط لازم، کارهای نیازمند کد منتظر می‌مانند.</p></>}
      {guide === 'harness' && <><p>بستهٔ تازهٔ Runner شامل راهنمای هارنس و نمونهٔ تنظیم خصوصی است. برای Codex و OpenCode نصب‌شده یا ابزار دیگر، پروفایل را روی همان دستگاه تعریف کنید؛ فرمان و اطلاعات ورود به کارا ارسال نمی‌شوند.</p><RunnerCommand value="python -m kara_source_runner run --allow-harness" /><p>این گزینه اجازهٔ اجرای هارنس با دسترسی حساب سیستم شماست؛ محیط کد Docker به‌تنهایی هارنس را جدا نمی‌کند. برای کار تعاملی، در تسک «هارنس شخصی» و سپس «تعاملی در ابزار خودم» را انتخاب و پس از انجام، نتیجه را در همان تسک تحویل دهید.</p></>}
      {guide === 'storage' && <><p>ریشهٔ پیش‌فرض سورس‌ها <bdi>~/KaraSourceWorkspaces</bdi> است؛ با <bdi>--root /your/private/path</bdi> تغییر می‌کند. آماده‌سازی اولیه پوشه می‌سازد و به‌روزرسانی همان worktree روی همان Runner در همان پوشه انجام می‌شود.</p><p>توکن دستگاه در <bdi>~/.config/kara-source-runner/device.json</bdi> نگهداری می‌شود. Runner اعتبارنامهٔ شخصی لازم را برای کار واگذارشده دریافت و وضعیت و خروجی را به کارا می‌فرستد. به بازکردن پورت محلی نیاز ندارد.</p><p>لغو دسترسی، فایل‌های محلی را پاک نمی‌کند. اتصال دوباره به کد و تنظیمات تازهٔ دستگاه نیاز دارد.</p></>}
    </div>
  </FormDialog>
}
