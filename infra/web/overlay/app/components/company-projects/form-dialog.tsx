'use client'

import type { ReactNode } from 'react'
import { Dialog, DialogBackdrop, DialogClose, DialogContent, DialogDescription, DialogPopup, DialogPortal, DialogTitle } from '@langgenius/dify-ui/dialog'
import { IconButton } from '@langgenius/dify-ui/icon-button'

export function FieldHelp({ children }: { children: ReactNode }) {
  return <span className="mt-2 block text-xs font-normal leading-6 text-text-tertiary">{children}</span>
}

export default function FormDialog({ open, title, description, busy = false, wide = false, error, close, children, keepMounted = false }: {
  open: boolean
  keepMounted?: boolean
  title: string
  description: string
  busy?: boolean
  wide?: boolean
  error?: string
  close: () => void
  children: ReactNode
}) {
  const content = <>
    <DialogTitle className="min-w-0 break-words pe-10 [overflow-wrap:anywhere]">{title}</DialogTitle>
    <DialogDescription className="mt-2 leading-7">{description}</DialogDescription>
    <div className="mt-5">{children}</div>
    {error && <p role="alert" className="mt-4 text-sm leading-7 text-text-destructive-secondary">{error}</p>}
    <DialogClose render={<IconButton aria-label="بستن" size="lg" disabled={busy} className="absolute inset-e-6 top-6"><span aria-hidden className="i-ri-close-line size-4" /></IconButton>} />
  </>
  const className = `max-h-[90dvh] w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain ${wide ? 'max-w-5xl' : 'max-w-2xl'}`
  return <Dialog open={open} onOpenChange={next => { if (!next && !busy) close() }}>
    {keepMounted ? <DialogPortal keepMounted><DialogBackdrop hidden={!open} /><DialogPopup hidden={!open} dir="rtl" className={`fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 p-6 ${className}`}>{content}</DialogPopup></DialogPortal> : <DialogContent dir="rtl" className={className}>{content}</DialogContent>}
  </Dialog>
}
