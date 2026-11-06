import { useTranslation } from 'react-i18next'
import { setLanguage } from '../lib/i18n.ts'
import { cn } from '../lib/cn.ts'

export function LanguageSwitch() {
  const { i18n, t } = useTranslation()
  const current = i18n.language.startsWith('fil') ? 'fil' : 'en'
  return (
    <div
      className="inline-flex h-8 items-center rounded-full border border-line bg-soft p-0.5"
      role="group"
      aria-label={t('common.language')}
    >
      {(['en', 'fil'] as const).map((lng) => (
        <button
          key={lng}
          type="button"
          aria-pressed={current === lng}
          onClick={() => setLanguage(lng)}
          className={cn(
            'h-7 rounded-full px-2.5 text-[11px] font-bold tracking-wide transition-all',
            current === lng ? 'bg-card text-ink shadow-sm ring-1 ring-line' : 'text-muted hover:text-ink',
          )}
        >
          {lng === 'en' ? 'EN' : 'FIL'}
        </button>
      ))}
    </div>
  )
}
