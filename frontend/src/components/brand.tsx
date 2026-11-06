import { useTranslation } from 'react-i18next'
import { cn } from '../lib/cn.ts'

export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'bg-brand-gradient grid size-9 shrink-0 place-items-center rounded-xl text-white shadow-[0_6px_16px_-6px_var(--color-brand)]',
        className,
      )}
      aria-hidden="true"
    >
      <svg viewBox="0 0 32 32" width="20" height="20">
        <circle cx="16" cy="12" r="4.5" fill="currentColor" />
        <path d="M7.5 25c1.4-4.6 4.6-7 8.5-7s7.1 2.4 8.5 7" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
    </span>
  )
}

export function Brand() {
  const { t } = useTranslation()
  return (
    <span className="flex items-center gap-2.5">
      <BrandMark />
      <span className="text-lg font-extrabold tracking-tight">{t('app.name')}</span>
    </span>
  )
}

export function Avatar({ email }: { email: string }) {
  const initials = email.split('@')[0]?.split(/[._-]/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || '?'
  return (
    <span className="grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-sky-400 to-violet-500 text-[11px] font-bold text-white ring-2 ring-white/40">
      {initials}
    </span>
  )
}
