import { useTranslation } from 'react-i18next'
import { RecordList } from '../../components/record-list.tsx'

export function RecruitmentPage() {
  const { t } = useTranslation()
  return (
    <RecordList
      title={t('recruitment.title')}
      subtitle={t('recruitment.subtitle')}
      basePath="/job-openings"
      columns={[
        { key: 'title', header: t('recruitment.opening') },
        { key: 'location', header: t('recruitment.location') },
        { key: 'employment_type', header: t('employees.type') },
        { key: 'status', header: t('common.status'), badge: true },
      ]}
    />
  )
}
