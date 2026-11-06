import type { ReactNode } from 'react'
import { cn } from '../../lib/cn.ts'

export function Badge({ tone = 'neutral', children }: { tone?: 'neutral' | 'accent'; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        tone === 'accent' ? 'bg-accent/12 text-accent ring-accent/25' : 'bg-soft text-ink ring-line',
      )}
    >
      <span className={cn('size-1.5 rounded-full', tone === 'accent' ? 'bg-accent' : 'bg-muted/60')} />
      {children}
    </span>
  )
}
