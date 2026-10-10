'use client'

import { useState } from 'react'
import { isAgentV2Enabled } from '@/features/agent-v2/feature-flag'

const primary = 'rounded-xl bg-components-button-primary-bg px-4 py-2 text-sm font-semibold text-components-button-primary-text hover:opacity-90 disabled:opacity-50'
const secondary = 'rounded-xl border border-divider-regular bg-components-panel-bg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-background-default-hover disabled:opacity-50'
const input = 'mt-2 w-full rounded-xl border border-divider-regular bg-components-panel-bg px-3 py-2 text-sm text-text-primary'
const panel = 'rounded-2xl border border-divider-regular bg-components-panel-bg p-6'

export function AppForm({ busy, onSave, onCancel }: { busy: boolean; onSave: (values: { name: string; description: string; mode: string }) => void; onCancel: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [mode, setMode] = useState('workflow')
  return <form className={`${panel} space-y-4`} aria-label="ساخت برنامه در پروژه" onSubmit={event => { event.preventDefault(); if (name.trim()) onSave({ name: name.trim(), description, mode }) }}>
    <h2 className="text-lg font-semibold text-text-primary">برنامهٔ جدید در این پروژه</h2>
    <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm text-text-secondary">نام برنامه<input autoFocus required maxLength={120} value={name} onChange={event => setName(event.target.value)} className={input} /></label><label className="text-sm text-text-secondary">نوع برنامه<select className={input} value={mode} onChange={event => setMode(event.target.value)}><option value="workflow">فرایند</option><option value="advanced-chat">گفتگو با فرایند</option><option value="agent-chat">ایجنت</option>{isAgentV2Enabled() && <option value="agent">ایجنت با ویرایشگر جدید</option>}</select></label></div>
    <label className="block text-sm text-text-secondary">توضیح برنامه<textarea maxLength={400} rows={2} value={description} onChange={event => setDescription(event.target.value)} className={input} /></label>
    <p className="text-xs text-text-tertiary">پس از ساخت، برنامه را باز کنید و مراحل، دستورالعمل و مدل آن را تنظیم کنید.</p>
    <div className="flex gap-3"><button disabled={busy || !name.trim()} className={primary}>{busy ? 'در حال ساخت…' : 'ساخت برنامه'}</button><button type="button" disabled={busy} onClick={onCancel} className={secondary}>انصراف</button></div>
  </form>
}
