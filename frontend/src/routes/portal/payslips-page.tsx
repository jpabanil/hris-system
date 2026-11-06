import { useTranslation } from 'react-i18next'
import { isQuiet, useApiQuery } from '../../api/session.ts'
import { EmptyState } from '../../components/empty-state.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { Table, Td, Th, Tr } from '../../components/ui/table.tsx'
import { display, idOf, itemsOf } from '../../lib/records.ts'

export function PortalPayslipsPage() {
  const { t } = useTranslation()
  const query = useApiQuery('/payslips?page=1&page_size=25')
  const rows = itemsOf(query.data)

  return (
    <div>
      <PageHeader title={t('payroll.payslips')} subtitle={t('payroll.subtitle')} />
      {query.isLoading ? <SkeletonRows /> : null}
      {query.isError ? <EmptyState title={t('common.error')} /> : null}
      {query.isSuccess && (isQuiet(query.data) || rows.length === 0) ? (
        <EmptyState title={isQuiet(query.data) ? t('common.quiet') : t('payroll.emptySlips')} />
      ) : null}
      {rows.length > 0 ? (
        <Table>
          <thead>
            <tr>
              <Th>{t('payroll.payDate')}</Th>
              <Th>{t('payroll.gross')}</Th>
              <Th>{t('payroll.net')}</Th>
              <Th>{t('common.status')}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <Tr key={idOf(row) || index}>
                <Td>{display(row.pay_date ?? row.period_id)}</Td>
                <Td>{display(row.gross)}</Td>
                <Td>{display(row.net_pay)}</Td>
                <Td>{display(row.status ?? row.is_published)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      ) : null}
    </div>
  )
}
