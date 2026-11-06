import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { isQuiet, useApiQuery } from '../../api/session.ts'
import { EmptyState } from '../../components/empty-state.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { Table, Td, Th, Tr } from '../../components/ui/table.tsx'
import { Tabs } from '../../components/ui/tabs.tsx'
import { display, idOf, isRow, itemsOf, personName, readPath, type Row } from '../../lib/records.ts'

const tabs = [
  { id: 'overview', path: (id: string) => `/employees/${id}` },
  { id: 'compensation', path: (id: string) => `/employees/${id}/compensation` },
  { id: 'documents', path: (id: string) => `/employees/${id}/documents` },
  { id: 'movements', path: (id: string) => `/employees/${id}/movements` },
  { id: 'leave', path: (id: string) => `/employees/${id}/leave` },
  { id: 'attendance', path: (id: string) => `/employees/${id}/attendance` },
] as const

function PayloadView({ data }: { data: unknown }) {
  const items = itemsOf(data)
  if (items.length) {
    const first = items[0]
    const keys = first ? Object.keys(first).filter((key) => key !== 'revision' && !key.startsWith('_')).slice(0, 6) : []
    return (
      <Table>
        <thead>
          <tr>
            {keys.map((key) => (
              <Th key={key}>{key}</Th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((row, index) => (
            <Tr key={idOf(row) || index}>
              {keys.map((key) => (
                <Td key={key}>{display(row[key])}</Td>
              ))}
            </Tr>
          ))}
        </tbody>
      </Table>
    )
  }
  if (!isRow(data)) return null
  const entries = Object.entries(data).filter(([key]) => key !== 'quiet')
  if (!entries.length) return null
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-xl bg-soft px-3.5 py-3">
          <dt className="text-xs text-muted">{key}</dt>
          <dd className="mt-1 text-sm break-words">{display(value)}</dd>
        </div>
      ))}
    </dl>
  )
}

function emptyPayload(data: unknown): boolean {
  if (Array.isArray(data)) return data.length === 0
  return isRow(data) && Array.isArray(data.items) && data.items.length === 0
}

function Overview({ row }: { row: Row }) {
  const { t } = useTranslation()
  const contact = isRow(row.contact) ? row.contact : {}
  const fields = [
    [t('employees.number'), readPath(row, 'employee_no')],
    [t('common.name'), personName(row.name)],
    [t('common.status'), readPath(row, 'employment_status')],
    [t('employees.type'), readPath(row, 'employment_type')],
    [t('employees.hired'), readPath(row, 'date_hired')],
    [t('employees.email'), readPath(contact, 'work_email')],
    [t('employees.mobile'), readPath(contact, 'mobile')],
    [t('employees.department'), readPath(row, 'department_id')],
    [t('profile.position'), readPath(row, 'position_id')],
    [t('profile.reportsTo'), readPath(row, 'reports_to')],
  ]
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {fields.map(([label, value]) => (
        <div key={label} className="rounded-xl bg-soft px-3.5 py-3">
          <dt className="text-xs text-muted">{label}</dt>
          <dd className="mt-1 text-sm">{value || '—'}</dd>
        </div>
      ))}
    </dl>
  )
}

export function EmployeeProfilePage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const [tab, setTab] = useState<(typeof tabs)[number]['id']>('overview')
  const current = tabs.find((item) => item.id === tab) ?? tabs[0]
  const query = useApiQuery(id && current ? current.path(id) : '', Boolean(id))
  const overview = useApiQuery(id ? `/employees/${id}` : '', Boolean(id))
  const name = isRow(overview.data) ? personName(overview.data.name) || readPath(overview.data, 'employee_no') : ''

  if (!id) return <EmptyState title={t('profile.notFound')} />

  return (
    <div>
      <PageHeader
        title={name || t('employees.title')}
        subtitle={readPath(isRow(overview.data) ? overview.data : {}, 'employee_no')}
        action={
          <Link to="/admin/employees" className="text-sm text-accent">
            {t('profile.back')}
          </Link>
        }
      />
      <Tabs
        value={tab}
        onChange={(next) => setTab(next as (typeof tabs)[number]['id'])}
        tabs={tabs.map((item) => ({ id: item.id, label: t(`profile.${item.id}`) }))}
      />
      {query.isLoading ? <SkeletonRows /> : null}
      {query.isError ? <EmptyState title={t('common.error')} /> : null}
      {query.isSuccess && isQuiet(query.data) ? <EmptyState title={t('common.quiet')} /> : null}
      {query.isSuccess && !isQuiet(query.data) && tab === 'overview' && isRow(query.data) ? <Overview row={query.data} /> : null}
      {query.isSuccess && !isQuiet(query.data) && tab !== 'overview' && emptyPayload(query.data) ? (
        <EmptyState title={t('common.empty')} />
      ) : null}
      {query.isSuccess && !isQuiet(query.data) && tab !== 'overview' && !emptyPayload(query.data) ? (
        <PayloadView data={query.data} />
      ) : null}
    </div>
  )
}
