import { useTranslation } from 'react-i18next'
import { isQuiet, useApiQuery, useSession } from '../../api/session.ts'
import { EmptyState } from '../../components/empty-state.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { display, isRow, personName, readPath } from '../../lib/records.ts'

export function PortalProfilePage() {
  const { t } = useTranslation()
  const session = useSession()
  const employeeId = session.data?.employee_id
  const path = employeeId ? `/employees/${employeeId}` : '/portal/profile'
  const query = useApiQuery(path, Boolean(session.data))
  const row = isRow(query.data) && !isQuiet(query.data) ? query.data : null
  const contact = row && isRow(row.contact) ? row.contact : {}

  const fields = [
    [t('auth.email'), session.data?.email ?? ''],
    [t('common.name'), row ? personName(row.name) : ''],
    [t('employees.number'), row ? readPath(row, 'employee_no') : ''],
    [t('common.status'), row ? readPath(row, 'employment_status') : ''],
    [t('employees.type'), row ? readPath(row, 'employment_type') : ''],
    [t('employees.hired'), row ? readPath(row, 'date_hired') : ''],
    [t('employees.mobile'), readPath(contact, 'mobile')],
    [t('employees.department'), row ? readPath(row, 'department_id') : ''],
  ]

  return (
    <div>
      <PageHeader title={t('nav.profile')} subtitle={session.data?.roles.join(', ')} />
      {!employeeId && !query.isLoading ? <p className="mb-3 text-sm text-muted">{t('portal.noEmployee')}</p> : null}
      {query.isLoading ? <SkeletonRows /> : null}
      {query.isError ? <EmptyState title={t('common.error')} /> : null}
      {query.isSuccess && isQuiet(query.data) && !employeeId ? <EmptyState title={t('common.quiet')} /> : null}
      {session.data ? (
        <dl className="grid gap-3 glass rounded-2xl p-5 sm:grid-cols-2">
          {fields.map(([label, value]) => (
            <div key={label} className="rounded-xl bg-soft px-3.5 py-3">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="mt-1 text-sm">{value ? display(value) : '—'}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  )
}
