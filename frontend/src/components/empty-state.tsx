import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { IconInbox } from './icons.tsx'

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-2xl border border-dashed border-line bg-soft/60 px-6 py-12 text-center">
      <div className="mx-auto mb-4 grid size-12 place-items-center rounded-2xl bg-accent/10 text-accent ring-1 ring-accent/20">
        <IconInbox width={22} height={22} />
      </div>
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-xs text-muted">{hint ?? t('common.emptyHint')}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
