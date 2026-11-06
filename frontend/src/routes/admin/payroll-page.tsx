import { useTranslation } from 'react-i18next'
import { RecordList } from '../../components/record-list.tsx'

export function PayrollPage() {
  const { t } = useTranslation()
  return (
    <RecordList
      title={t('payroll.title')}
      subtitle={t('payroll.subtitle')}
      basePath="/payroll-periods"
      columns={[
        { key: 'type', header: t('payroll.period') },
        { key: 'start', header: t('leave.start') },
        { key: 'end', header: t('leave.end') },
        { key: 'pay_date', header: t('payroll.payDate') },
        { key: 'status', header: t('common.status'), badge: true },
      ]}
    />
  )
}
