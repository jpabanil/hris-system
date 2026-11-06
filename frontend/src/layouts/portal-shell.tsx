import { NavLink, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useSession } from '../api/session.ts'
import { portalOnly } from '../api/types.ts'
import { cn } from '../lib/cn.ts'
import { SessionTools } from '../components/session-tools.tsx'
import { Brand } from '../components/brand.tsx'
import { IconHome, IconCalendar, IconReceipt, IconUser, IconDashboard } from '../components/icons.tsx'

const links = [
  { to: '/portal', label: 'nav.home', end: true, icon: IconHome },
  { to: '/portal/leave', label: 'nav.leave', end: false, icon: IconCalendar },
  { to: '/portal/payslips', label: 'nav.payslips', end: false, icon: IconReceipt },
  { to: '/portal/profile', label: 'nav.profile', end: false, icon: IconUser },
]

export function PortalShell() {
  const { t } = useTranslation()
  const { data } = useSession()
  if (!data) return null
  const showAdmin = !portalOnly(data)

  return (
    <div className="min-h-svh text-ink">
      <header className="sticky top-0 z-10 px-3 pt-3">
        <div className="glass mx-auto flex h-14 w-full max-w-4xl items-center justify-between gap-3 rounded-2xl px-3 sm:px-4">
          <Brand />
          <nav className="hidden items-center gap-1 md:flex">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  cn(
                    'rounded-xl px-3 py-1.5 text-sm font-medium transition-all',
                    isActive ? 'bg-brand-gradient text-white shadow-sm' : 'text-muted hover:bg-soft hover:text-ink',
                  )
                }
              >
                {t(link.label)}
              </NavLink>
            ))}
            {showAdmin ? (
              <NavLink
                to="/admin"
                className="ml-1 inline-flex items-center gap-1.5 rounded-xl border border-dashed border-line px-3 py-1.5 text-sm font-medium text-muted hover:border-accent/50 hover:text-accent"
              >
                <IconDashboard width={15} height={15} />
                {t('nav.dashboard')}
              </NavLink>
            ) : null}
          </nav>
          <SessionTools />
        </div>
      </header>
      {data.is_impersonating ? (
        <p className="mx-auto mt-3 w-[calc(100%-1.5rem)] max-w-4xl rounded-xl border border-accent/30 bg-accent/10 px-4 py-2 text-center text-xs font-medium">
          {t('common.impersonating')}
        </p>
      ) : null}
      <main className="mx-auto w-full max-w-4xl px-3 py-6 pb-28 sm:px-4 md:pb-10">
        <Outlet />
      </main>
      <nav className="glass fixed inset-x-3 bottom-3 z-20 grid grid-cols-4 gap-1 rounded-2xl p-1.5 md:hidden">
        {links.map((link) => {
          const Icon = link.icon
          return (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center gap-1 rounded-xl px-1 py-1.5 text-[11px] font-semibold transition-all',
                  isActive ? 'bg-brand-gradient text-white shadow-sm' : 'text-muted',
                )
              }
            >
              <Icon width={20} height={20} />
              {t(link.label)}
            </NavLink>
          )
        })}
      </nav>
    </div>
  )
}
