import type { ComponentType, SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { IconCheck, IconUsers, IconWallet } from '../../components/icons.tsx'
import { isQuiet, useApiQuery } from '../../api/session.ts'
import { Card } from '../../components/ui/card.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { StatusChart } from '../../components/status-chart.tsx'
import { itemsOf, openPeriodCount, statusCounts, totalOf } from '../../lib/records.ts'

const tones = {
  indigo: 'from-indigo-500 to-violet-500',
  pink: 'from-fuchsia-500 to-pink-500',
  teal: 'from-teal-400 to-emerald-500',
}

function Stat({
  label,
  loading,
  error,
  quiet,
  value,
  icon: Icon,
  tone,
}: {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  tone: keyof typeof tones
  label: string
  loading: boolean
  error: boolean
  quiet: boolean
  value: number
}) {
  const { t } = useTranslation()
  return (
    <Card className="relative overflow-hidden">
      <div
        className={`pointer-events-none absolute -top-10 -right-10 size-32 rounded-full bg-gradient-to-br opacity-20 blur-2xl ${tones[tone]}`}
        aria-hidden="true"
      />
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-muted">{label}</h2>
        <span className={`grid size-10 place-items-center rounded-xl bg-gradient-to-br text-white shadow-lg ${tones[tone]}`}>
          <Icon width={19} height={19} />
        </span>
      </div>
      {loading ? <SkeletonRows rows={2} /> : null}
      {!loading && error ? <p className="text-sm text-muted">{t('common.error')}</p> : null}
      {!loading && !error ? <p className="font-display text-4xl font-bold tracking-tight tabular-nums text-ink">{quiet ? '—' : value}</p> : null}
      {!loading && !error && quiet ? <p className="mt-2 text-xs text-muted">{t('common.quiet')}</p> : null}
    </Card>
  )
}

export function DashboardPage() {
  const { t } = useTranslation()
  const employees = useApiQuery('/employees?page=1&page_size=100')
  const approvals = useApiQuery('/approvals/inbox')
  const periods = useApiQuery('/payroll-periods?page=1&page_size=100')
  const chart = statusCounts(itemsOf(employees.data))

  return (
    <div>
      <PageHeader title={t('dashboard.title')} subtitle={t('dashboard.subtitle')} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label={t('dashboard.headcount')}
          icon={IconUsers}
          tone="indigo"
          loading={employees.isLoading}
          error={employees.isError}
          quiet={isQuiet(employees.data)}
          value={totalOf(employees.data)}
        />
        <Stat
          label={t('dashboard.pending')}
          icon={IconCheck}
          tone="pink"
          loading={approvals.isLoading}
          error={approvals.isError}
          quiet={isQuiet(approvals.data)}
          value={totalOf(approvals.data)}
        />
        <Stat
          label={t('dashboard.periods')}
          icon={IconWallet}
          tone="teal"
          loading={periods.isLoading}
          error={periods.isError}
          quiet={isQuiet(periods.data)}
          value={openPeriodCount(periods.data)}
        />
      </div>
      <Card title={t('dashboard.chart')} className="mt-4">
        {employees.isLoading ? <SkeletonRows rows={4} /> : null}
        {!employees.isLoading && chart.length === 0 ? <p className="text-sm text-muted">{t('dashboard.noChart')}</p> : null}
        {chart.length > 0 ? (
          <div className="h-64">
            <StatusChart data={chart} />
          </div>
        ) : null}
      </Card>
    </div>
  )
}
