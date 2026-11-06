import { useTranslation } from 'react-i18next'
import { RecordList } from '../../components/record-list.tsx'

export function AttendancePage() {
  const { t } = useTranslation()
  return (
    <RecordList
      title={t('attendance.title')}
      subtitle={t('attendance.subtitle')}
      basePath="/attendance-days"
      columns={[
        { key: 'date', header: t('attendance.date') },
        { key: 'employee_id', header: t('employees.number') },
        { key: 'status', header: t('common.status'), badge: true },
        { key: 'hours_worked', header: t('attendance.hours') },
        { key: 'late_minutes', header: t('attendance.late') },
      ]}
    />
  )
}
