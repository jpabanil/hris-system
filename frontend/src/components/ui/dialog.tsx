import { useEffect, useId, useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { IconX } from '../icons.tsx'

type DialogProps = {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}

export function Dialog({ open, title, onClose, children }: DialogProps) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      className="glass-strong m-auto w-[min(36rem,calc(100vw-2rem))] rounded-2xl p-0 text-ink shadow-2xl"
      onClose={onClose}
    >
      <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
        <h2 id={titleId} className="text-lg font-semibold tracking-tight">
          {title}
        </h2>
        <button
          type="button"
          aria-label={t('common.close')}
          className="grid size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-soft hover:text-ink"
          onClick={onClose}
        >
          <IconX />
        </button>
      </div>
      <div className="p-5">{children}</div>
    </dialog>
  )
}
