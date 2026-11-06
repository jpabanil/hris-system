import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client.ts'
import { IconLogout } from './icons.tsx'
import { LanguageSwitch } from './language-switch.tsx'
import { ThemeToggle } from './theme-toggle.tsx'

export function SessionTools() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const logout = useMutation({
    mutationFn: () => api('/auth/logout', { method: 'POST' }),
    onSettled: () => {
      queryClient.setQueryData(['me'], null)
      void navigate('/login', { replace: true })
    },
  })

  return (
    <div className="flex items-center gap-2">
      <LanguageSwitch />
      <ThemeToggle />
      <button
        type="button"
        disabled={logout.isPending}
        onClick={() => logout.mutate()}
        className="inline-flex h-8 items-center gap-1.5 rounded-full border border-line bg-soft px-3 text-xs font-semibold text-ink transition-colors hover:border-danger/40 hover:text-danger disabled:opacity-50"
      >
        <IconLogout width={14} height={14} />
        <span className="hidden sm:inline">{t('auth.logout')}</span>
      </button>
    </div>
  )
}
