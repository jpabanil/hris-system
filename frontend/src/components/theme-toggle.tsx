import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '../lib/cn.ts'
import { IconMoon, IconSun } from './icons.tsx'

type Theme = 'light' | 'dark'

function currentTheme(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

function hasStoredTheme(): boolean {
  try {
    return localStorage.getItem('hris-theme') !== null
  } catch {
    return false
  }
}

export function ThemeToggle({ className }: { className?: string }) {
  const { t } = useTranslation()
  const [theme, setTheme] = useState<Theme>(currentTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  // Follow the OS setting until the user picks a theme explicitly.
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event: MediaQueryListEvent) => {
      if (!hasStoredTheme()) setTheme(event.matches ? 'dark' : 'light')
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const dark = theme === 'dark'
  const choose = (next: Theme) => {
    setTheme(next)
    try {
      localStorage.setItem('hris-theme', next)
    } catch {
      /* storage may be blocked */
    }
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label={dark ? t('common.themeToLight') : t('common.themeToDark')}
      title={dark ? t('common.themeToLight') : t('common.themeToDark')}
      onClick={() => choose(dark ? 'light' : 'dark')}
      className={cn(
        'relative inline-flex h-8 w-[3.75rem] shrink-0 items-center rounded-full border border-line bg-soft p-0.5 transition-colors',
        className,
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 left-0.5 size-7 rounded-full bg-card shadow-md ring-1 ring-line transition-transform duration-300',
          dark && 'translate-x-7',
        )}
      />
      <span className={cn('relative z-10 grid size-7 place-items-center transition-colors', dark ? 'text-muted' : 'text-amber-500')}>
        <IconSun width={15} height={15} />
      </span>
      <span className={cn('relative z-10 grid size-7 place-items-center transition-colors', dark ? 'text-accent' : 'text-muted')}>
        <IconMoon width={15} height={15} />
      </span>
    </button>
  )
}
