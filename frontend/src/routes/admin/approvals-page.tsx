import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client.ts'
import { isQuiet, useApiQuery } from '../../api/session.ts'
import { EmptyState } from '../../components/empty-state.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { Badge } from '../../components/ui/badge.tsx'
import { Button } from '../../components/ui/button.tsx'
import { Dialog } from '../../components/ui/dialog.tsx'
import { Table, Td, Th, Tr } from '../../components/ui/table.tsx'
import { display, idOf, itemsOf, readPath, type Row } from '../../lib/records.ts'

export function ApprovalsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const query = useApiQuery('/approvals/inbox')
  const [target, setTarget] = useState<Row | null>(null)
  const [remarks, setRemarks] = useState('')
  const [notice, setNotice] = useState('')

  const approve = useMutation({
    mutationFn: (input: { id: string; remarks: string }) =>
      api(`/approvals/${input.id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ remarks: input.remarks }),
      }),
    onSuccess: async () => {
      setNotice(t('approvals.success'))
      setTarget(null)
      setRemarks('')
      await queryClient.invalidateQueries({ queryKey: ['api'] })
    },
  })

  const rows = itemsOf(query.data)
  const quiet = isQuiet(query.data)

  return (
    <div>
      <PageHeader title={t('approvals.title')} subtitle={t('approvals.subtitle')} />
      {notice ? <p className="mb-3 text-sm text-accent">{notice}</p> : null}
      {query.isLoading ? <SkeletonRows /> : null}
      {query.isError ? <EmptyState title={t('common.error')} /> : null}
      {query.isSuccess && (quiet || rows.length === 0) ? (
        <EmptyState title={quiet ? t('common.quiet') : t('approvals.empty')} />
      ) : null}
      {rows.length > 0 ? (
        <Table>
          <thead>
            <tr>
              <Th>{t('approvals.module')}</Th>
              <Th>{t('approvals.subject')}</Th>
              <Th>{t('approvals.step')}</Th>
              <Th>{t('common.status')}</Th>
              <Th>{t('common.actions')}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const id = idOf(row)
              return (
                <Tr key={id || readPath(row, 'subject_id')}>
                  <Td>
                    <Badge tone="accent">{readPath(row, 'module') || '—'}</Badge>
                  </Td>
                  <Td>{[readPath(row, 'subject_type'), readPath(row, 'subject_id')].filter(Boolean).join(' · ') || '—'}</Td>
                  <Td>{display(row.current_step)}</Td>
                  <Td>{readPath(row, 'status') || '—'}</Td>
                  <Td>
                    <Button
                      size="sm"
                      disabled={!id || approve.isPending}
                      onClick={() => {
                        setTarget(row)
                        setRemarks('')
                      }}
                    >
                      {t('common.approve')}
                    </Button>
                  </Td>
                </Tr>
              )
            })}
          </tbody>
        </Table>
      ) : null}
      <Dialog
        open={target !== null}
        title={t('approvals.approveTitle')}
        onClose={() => {
          if (!approve.isPending) setTarget(null)
        }}
      >
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (!target) return
            const id = idOf(target)
            if (!id) return
            approve.mutate({ id, remarks })
          }}
        >
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium text-muted">{t('common.remarks')}</span>
            <textarea
              value={remarks}
              onChange={(event) => setRemarks(event.target.value)}
              placeholder={t('approvals.remarksPlaceholder')}
              rows={3}
              className="w-full rounded-xl border border-line bg-card px-3.5 py-2.5 text-sm text-ink outline-none backdrop-blur-md transition-all placeholder:text-muted/80 focus:border-accent/60 focus:ring-4 focus:ring-accent/15"
            />
          </label>
          {approve.isError ? (
            <p className="text-sm text-danger">{approve.error instanceof Error ? approve.error.message : t('common.error')}</p>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setTarget(null)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={approve.isPending}>
              {t('common.approve')}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
