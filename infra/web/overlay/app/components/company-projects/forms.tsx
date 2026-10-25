'use client'

import { useState } from 'react'
import { isAgentV2Enabled } from '@/features/agent-v2/feature-flag'
import FormDialog, { FieldHelp } from './form-dialog'

const primary = 'rounded-xl bg-components-button-primary-bg px-4 py-2 text-sm font-semibold text-components-button-primary-text hover:opacity-90 disabled:opacity-50'
const secondary = 'rounded-xl border border-divider-regular bg-components-panel-bg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-background-default-hover disabled:opacity-50'
const input = 'mt-2 w-full rounded-xl border border-divider-regular bg-components-panel-bg px-3 py-2 text-sm text-text-primary'

export function AppForm({ busy, error, onSave, onCancel }: { busy: boolean; error?: string; onSave: (values: { name: string; description: string; mode: string }) => void; onCancel: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [mode, setMode] = useState('workflow')
  return <FormDialog open title="ساخت برنامه در پروژه" description="برنامه ابزار انجام یک کار است. نام و نوع آن را مشخص کنید؛ پس از ساخت، مراحل، دستورالعمل، مدل و ورودی‌ها را در ویرایشگر تنظیم می‌کنید." busy={busy} error={error} close={onCancel}>
    <form className="space-y-4" aria-label="ساخت برنامه در پروژه" onSubmit={event => { event.preventDefault(); if (name.trim()) onSave({ name: name.trim(), description, mode }) }}>
      <fieldset disabled={busy} className="space-y-4">
    <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm text-text-secondary">نام برنامه<input autoFocus required maxLength={120} value={name} onChange={event => setName(event.target.value)} className={input} /><FieldHelp>نامی کوتاه و قابل تشخیص برای کاری که برنامه انجام می‌دهد؛ حداکثر ۱۲۰ نویسه.</FieldHelp></label><label className="text-sm text-text-secondary">نوع برنامه<select className={input} value={mode} onChange={event => setMode(event.target.value)}><option value="workflow">فرایند</option><option value="advanced-chat">گفتگو با فرایند</option><option value="agent-chat">ایجنت</option>{isAgentV2Enabled() && <option value="agent">ایجنت با ویرایشگر جدید</option>}</select><FieldHelp>فرایند: اجرای مراحل مشخص با ورودی و خروجی. گفتگو با فرایند: مکالمه با مراحل تعریف‌شده. ایجنت: پاسخ‌گویی با ابزارها. برای ثبت در ایجنت‌های تیم، فرایند با شروع دستی انتخاب کنید.</FieldHelp></label></div>
    <label className="block text-sm text-text-secondary">توضیح برنامه<textarea maxLength={400} rows={2} value={description} onChange={event => setDescription(event.target.value)} className={input} /><FieldHelp>هدف برنامه و نتیجهٔ مورد انتظار را برای همکاران توضیح دهید؛ این متن جای دستورالعمل مدل را نمی‌گیرد.</FieldHelp></label>
    <p className="text-xs text-text-tertiary">پس از ساخت، برنامه را باز کنید و مراحل، دستورالعمل و مدل آن را تنظیم کنید.</p>
    <div className="flex gap-3"><button disabled={busy || !name.trim()} className={primary}>{busy ? 'در حال ساخت…' : 'ساخت برنامه'}</button><button type="button" disabled={busy} onClick={onCancel} className={secondary}>انصراف</button></div>
      </fieldset>
    </form>
  </FormDialog>
}
