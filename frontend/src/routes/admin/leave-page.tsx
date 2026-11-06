import { useTranslation } from 'react-i18next'
import { RecordList } from '../../components/record-list.tsx'

export function LeavePage() {
  const { t } = useTranslation()
  return (
    <RecordList
      title={t('leave.title')}
      subtitle={t('leave.subtitle')}
      basePath="/leave-requests"
      columns={[
        { key: 'employee_id', header: t('employees.number') },
        { key: 'leave_type_id', header: t('leave.type') },
        { key: 'start_date', header: t('leave.start') },
        { key: 'end_date', header: t('leave.end') },
        { key: 'days', header: t('leave.days') },
        { key: 'status', header: t('common.status'), badge: true },
      ]}
    />
  )
}
