import { useTranslation } from 'react-i18next'
import { isQuiet, useApiQuery } from '../../api/session.ts'
import { Card } from '../../components/ui/card.tsx'
import { EmptyState } from '../../components/empty-state.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { StatusChart } from '../../components/status-chart.tsx'
import { Table, Td, Th, Tr } from '../../components/ui/table.tsx'
import { display, idOf, itemsOf, statusCounts } from '../../lib/records.ts'

export function ReportsPage() {
  const { t } = useTranslation()
  const employees = useApiQuery('/employees?page=1&page_size=100')
  const reports = useApiQuery('/reports')
  const chart = statusCounts(itemsOf(employees.data))
  const rows = itemsOf(reports.data)
  const first = rows[0]
  const keys = first ? Object.keys(first).filter((key) => key !== 'revision' && !key.startsWith('_')).slice(0, 5) : []

  return (
    <div>
      <PageHeader title={t('reports.title')} subtitle={t('reports.subtitle')} />
      <Card title={t('dashboard.chart')}>
        {employees.isLoading ? <SkeletonRows rows={4} /> : null}
        {!employees.isLoading && chart.length === 0 ? <p className="text-sm text-muted">{t('dashboard.noChart')}</p> : null}
        {chart.length > 0 ? (
          <div className="h-56">
            <StatusChart data={chart} />
          </div>
        ) : null}
      </Card>
      <Card title={t('reports.feed')} className="mt-3">
        {reports.isLoading ? <SkeletonRows /> : null}
        {reports.isError ? <EmptyState title={t('common.error')} /> : null}
        {reports.isSuccess && (isQuiet(reports.data) || rows.length === 0) ? (
          <EmptyState title={isQuiet(reports.data) ? t('reports.unavailable') : t('common.empty')} />
        ) : null}
        {rows.length > 0 ? (
          <Table>
            <thead>
              <tr>
                {keys.map((key) => (
                  <Th key={key}>{t('common.column', { name: key })}</Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <Tr key={idOf(row) || index}>
                  {keys.map((key) => (
                    <Td key={key}>{display(row[key])}</Td>
                  ))}
                </Tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Card>
    </div>
  )
}
