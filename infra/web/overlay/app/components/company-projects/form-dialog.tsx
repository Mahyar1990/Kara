'use client'

import type { ReactNode } from 'react'
import { Dialog, DialogBackdrop, DialogClose, DialogContent, DialogDescription, DialogPopup, DialogPortal, DialogTitle } from '@langgenius/dify-ui/dialog'
import { IconButton } from '@langgenius/dify-ui/icon-button'

export function FieldHelp({ children }: { children: ReactNode }) {
  return <span className="mt-2 block text-xs font-normal leading-6 text-text-tertiary">{children}</span>
}

export default function FormDialog({ open, title, description, busy = false, wide = false, error, close, children, keepMounted = false, fixedBody = false, footer, header, closeLabel = 'بستن' }: {
  open: boolean
  keepMounted?: boolean
  fixedBody?: boolean
  footer?: ReactNode
  header?: ReactNode
  closeLabel?: string
  title: string
  description: string
  busy?: boolean
  wide?: boolean
  error?: string
  close: () => void
  children: ReactNode
}) {
  const content = <>
    {header && <div className="mb-3 shrink-0 pe-10">{header}</div>}
    <DialogTitle className="min-w-0 shrink-0 break-words pe-10 [overflow-wrap:anywhere]">{title}</DialogTitle>
    <DialogDescription className="mt-2 shrink-0 leading-7">{description}</DialogDescription>
    <div className={fixedBody ? 'mt-4 min-h-0 flex-1 overflow-hidden' : 'mt-5'}>{children}</div>
    {error && <p role="alert" className="mt-4 text-sm leading-7 text-text-destructive-secondary">{error}</p>}
    {footer && <div className="mt-4 shrink-0 border-t border-divider-regular pt-4">{footer}</div>}
    <DialogClose render={<IconButton aria-label={closeLabel} size="lg" disabled={busy} className="absolute inset-e-6 top-6"><span aria-hidden className="i-ri-close-line size-4" /></IconButton>} />
  </>
  const className = `${fixedBody ? 'flex h-[min(58rem,94dvh)] max-h-[94dvh] flex-col overflow-hidden' : 'max-h-[90dvh] overflow-y-auto overscroll-contain'} w-[calc(100vw-2rem)] ${wide ? (fixedBody ? 'max-w-7xl' : 'max-w-5xl') : 'max-w-2xl'}`
  return <Dialog open={open} onOpenChange={next => { if (!next && !busy) close() }}>
    {keepMounted ? <DialogPortal keepMounted><DialogBackdrop hidden={!open} /><DialogPopup hidden={!open} dir="rtl" className={`fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 p-6 ${className}`}>{content}</DialogPopup></DialogPortal> : <DialogContent dir="rtl" className={className}>{content}</DialogContent>}
  </Dialog>
}
