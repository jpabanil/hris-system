import type { ReactNode } from 'react'
import { cn } from '../../lib/cn.ts'

type CardProps = {
  title?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}

export function Card({ title, action, children, className }: CardProps) {
  return (
    <section className={cn('glass rounded-2xl p-5', className)}>
      {title ? (
        <header className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold tracking-tight text-ink">{title}</h2>
          {action}
        </header>
      ) : null}
      {children}
    </section>
  )
}
