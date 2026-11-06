import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { isQuiet, useApiQuery } from '../api/session.ts'
import { idOf, itemsOf, labelState, readPath, totalOf, type Row } from '../lib/records.ts'
import { Badge } from './ui/badge.tsx'
import { Button } from './ui/button.tsx'
import { Table, Td, Th, Tr } from './ui/table.tsx'
import { fieldClass } from './ui/input.tsx'
import { IconSearch } from './icons.tsx'
import { cn } from '../lib/cn.ts'
import { EmptyState } from './empty-state.tsx'
import { PageHeader } from './page-header.tsx'
import { SkeletonRows } from './skeleton.tsx'

export type Column = {
  key: string
  header: string
  badge?: boolean
  render?: (row: Row) => ReactNode
}

function columnsFor(rows: Row[], columns: Column[], translate: (key: string, options: { name: string }) => string): Column[] {
  const used = columns.filter((column) => rows.some((row) => column.render || readPath(row, column.key)))
  if (used.length || !rows.length) return columns
  const first = rows[0]
  if (!first) return columns
  return Object.keys(first)
    .filter((key) => key !== 'revision' && !key.startsWith('_'))
    .slice(0, 6)
    .map((key) => ({ key, header: translate('common.column', { name: key }) }))
}

export function RecordList({
  title,
  subtitle,
  basePath,
  columns,
  action,
  empty,
}: {
  title: string
  subtitle?: string
  basePath: string
  columns: Column[]
  action?: ReactNode
  empty?: string
}) {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(q.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [q])

  useEffect(() => {
    setPage(1)
  }, [debounced])

  const params = new URLSearchParams({ page: String(page), page_size: '25' })
  if (debounced) params.set('q', debounced)
  const joiner = basePath.includes('?') ? '&' : '?'
  const path = `${basePath}${joiner}${params.toString()}`
  const query = useApiQuery(path)
  const rows = itemsOf(query.data)
  const quiet = isQuiet(query.data)
  const total = totalOf(query.data)
  const pages = Math.max(1, Math.ceil(total / 25))
  const shown = columnsFor(rows, columns, t)

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} action={action} />
      <label className="relative mb-4 block max-w-sm">
        <span className="sr-only">{t('common.search')}</span>
        <IconSearch className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-muted" width={16} height={16} />
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={t('common.search')}
          className={cn(fieldClass, 'pl-10')}
        />
      </label>
      {query.isLoading ? <SkeletonRows /> : null}
      {query.isError ? (
        <EmptyState
          title={t('common.error')}
          hint={query.error instanceof Error ? query.error.message : undefined}
          action={
            <Button variant="secondary" onClick={() => void query.refetch()}>
              {t('common.retry')}
            </Button>
          }
        />
      ) : null}
      {query.isSuccess && (quiet || rows.length === 0) ? (
        <EmptyState title={quiet ? t('common.quiet') : (empty ?? t('common.empty'))} />
      ) : null}
      {query.isSuccess && !quiet && rows.length > 0 ? (
        <>
          <div className="glass overflow-hidden rounded-2xl">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="text-xs font-semibold text-muted tabular-nums">{t('common.total', { count: total })}</p>
          </div>
          <Table>
            <thead>
              <tr>
                {shown.map((column) => (
                  <Th key={column.key}>{column.header}</Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <Tr key={idOf(row) || index}>
                  {shown.map((column) => (
                    <Td key={column.key}>
                      {column.render ? (
                        column.render(row)
                      ) : column.badge ? (
                        <Badge tone={readPath(row, column.key) === 'pending' ? 'accent' : 'neutral'}>
                          {labelState(t, readPath(row, column.key))}
                        </Badge>
                      ) : (
                        readPath(row, column.key) || '—'
                      )}
                    </Td>
                  ))}
                </Tr>
              ))}
            </tbody>
          </Table>
          {pages > 1 ? (
            <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-3">
              <p className="text-xs text-muted">{t('common.page', { page, pages })}</p>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>
                  {t('common.previous')}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= pages}
                  onClick={() => setPage((current) => current + 1)}
                >
                  {t('common.next')}
                </Button>
              </div>
            </div>
          ) : null}
          </div>
        </>
      ) : null}
    </div>
  )
}
