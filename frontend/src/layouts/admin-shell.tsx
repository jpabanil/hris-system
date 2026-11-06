import { useEffect, useState, type ComponentType, type SVGProps } from 'react'
import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useSession } from '../api/session.ts'
import { canSee, portalOnly, type SessionUser } from '../api/types.ts'
import { cn } from '../lib/cn.ts'
import { SessionTools } from '../components/session-tools.tsx'
import { Avatar, Brand } from '../components/brand.tsx'
import {
  IconBriefcase,
  IconCalendar,
  IconChart,
  IconCheck,
  IconClock,
  IconDashboard,
  IconMenu,
  IconOrg,
  IconSettings,
  IconSwap,
  IconUsers,
  IconWallet,
  IconX,
} from '../components/icons.tsx'

type NavItem = {
  to: string
  label: string
  end?: boolean
  permissions: string[]
  icon: ComponentType<SVGProps<SVGSVGElement>>
}

const links: NavItem[] = [
  { to: '/admin', label: 'nav.dashboard', end: true, permissions: [], icon: IconDashboard },
  { to: '/admin/approvals', label: 'nav.approvals', permissions: ['approvals.act'], icon: IconCheck },
  { to: '/admin/org', label: 'nav.org', permissions: ['org.view', 'org.manage'], icon: IconOrg },
  { to: '/admin/employees', label: 'nav.employees', permissions: ['employees.view', 'employees.view_team', 'employees.manage'], icon: IconUsers },
  { to: '/admin/attendance', label: 'nav.attendance', permissions: ['attendance.view', 'attendance.view_team', 'attendance.manage'], icon: IconClock },
  { to: '/admin/leave', label: 'nav.leave', permissions: ['leave.view', 'leave.view_team', 'leave.manage', 'leave.approve'], icon: IconCalendar },
  { to: '/admin/payroll', label: 'nav.payroll', permissions: ['payroll.view', 'payroll.compute', 'payroll.approve', 'payroll.tables'], icon: IconWallet },
  { to: '/admin/recruitment', label: 'nav.recruitment', permissions: ['recruitment.view', 'recruitment.manage'], icon: IconBriefcase },
  { to: '/admin/reports', label: 'nav.reports', permissions: ['reports.view', 'reports.export'], icon: IconChart },
  { to: '/admin/settings', label: 'nav.settings', permissions: ['settings.view', 'settings.manage'], icon: IconSettings },
]

function visible(user: SessionUser) {
  return links.filter((link) => canSee(user, link.permissions))
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
    isActive
      ? 'bg-brand-gradient text-white shadow-[0_8px_18px_-8px_var(--color-brand)]'
      : 'text-muted hover:bg-soft hover:text-ink',
  )

export function AdminShell() {
  const { t } = useTranslation()
  const { data } = useSession()
  const location = useLocation()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  if (!data) return null
  if (portalOnly(data)) return <Navigate to="/portal" replace />

  const showPortal = data.permissions.includes('self.service') || Boolean(data.employee_id)

  return (
    <div className="min-h-svh text-ink">
      {open ? (
        <button
          type="button"
          className="fixed inset-0 z-20 bg-black/30 backdrop-blur-sm md:hidden"
          aria-label={t('common.close')}
          onClick={() => setOpen(false)}
        />
      ) : null}
      <aside
        className={cn(
          'glass fixed inset-y-3 left-3 z-30 w-64 flex-col rounded-3xl transition-transform duration-300 md:flex md:translate-x-0',
          open ? 'flex translate-x-0' : 'hidden -translate-x-[110%] md:flex',
        )}
      >
        <div className="flex h-16 items-center justify-between px-5">
          <Brand />
          <button
            type="button"
            className="grid size-8 place-items-center rounded-lg text-muted hover:bg-soft md:hidden"
            aria-label={t('common.close')}
            onClick={() => setOpen(false)}
          >
            <IconX />
          </button>
        </div>
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 pb-3">
          {visible(data).map((link) => {
            const Icon = link.icon
            return (
              <NavLink key={link.to} to={link.to} end={link.end} className={navClass}>
                <Icon className="shrink-0" />
                {t(link.label)}
              </NavLink>
            )
          })}
        </nav>
        <div className="space-y-3 border-t border-line p-3">
          {showPortal ? (
            <NavLink
              to="/portal"
              className="flex items-center gap-3 rounded-xl border border-dashed border-line px-3 py-2.5 text-sm font-medium text-muted transition-colors hover:border-accent/50 hover:text-accent"
            >
              <IconSwap className="shrink-0" />
              {t('nav.portal')}
            </NavLink>
          ) : null}
          <div className="flex items-center gap-3 rounded-xl bg-soft px-3 py-2.5">
            <Avatar email={data.email} />
            <p className="min-w-0 truncate text-xs font-medium text-muted">{data.email}</p>
          </div>
        </div>
      </aside>
      <div className="md:pl-[17.5rem]">
        <header className="sticky top-0 z-10 px-3 pt-3 md:pr-3 md:pl-0">
          <div className="glass flex h-14 items-center justify-between gap-3 rounded-2xl px-3 sm:px-4">
            <div className="flex min-w-0 items-center gap-2">
              <button
                type="button"
                aria-label={t('nav.menu')}
                className="grid size-9 place-items-center rounded-xl text-ink hover:bg-soft md:hidden"
                onClick={() => setOpen(true)}
              >
                <IconMenu />
              </button>
              <span className="md:hidden">
                <Brand />
              </span>
              <p className="hidden truncate text-sm font-medium text-muted md:block">{data.email}</p>
            </div>
            <SessionTools />
          </div>
        </header>
        {data.is_impersonating ? (
          <p className="mx-3 mt-3 rounded-xl border border-accent/30 bg-accent/10 px-4 py-2 text-xs font-medium text-ink md:ml-0">
            {t('common.impersonating')}
          </p>
        ) : null}
        <main className="mx-auto w-full max-w-7xl px-3 py-6 sm:px-5 md:pl-2">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
