import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client.ts'
import { isQuiet, useApiQuery, useSession } from '../../api/session.ts'
import { Card } from '../../components/ui/card.tsx'
import { Button } from '../../components/ui/button.tsx'
import { EmptyState } from '../../components/empty-state.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { Table, Td, Th, Tr } from '../../components/ui/table.tsx'
import { display, idOf, itemsOf } from '../../lib/records.ts'

export function PortalHomePage() {
  const { t } = useTranslation()
  const session = useSession()
  const queryClient = useQueryClient()
  const logs = useApiQuery('/attendance-logs?page=1&page_size=8')
  const rows = itemsOf(logs.data).slice(0, 8)

  const clock = useMutation({
    mutationFn: (type: 'in' | 'out') =>
      api('/attendance/clock', {
        method: 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ type, source: 'pwa' }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['api'] })
    },
  })

  return (
    <div>
      <PageHeader title={t('portal.hello')} subtitle={session.data?.email} />
      <Card title={t('portal.today')}>
        <p className="mb-3 text-sm text-muted">{t('portal.hint')}</p>
        <p className="mb-3 text-xs text-muted">{t('attendance.source')}</p>
        <div className="flex gap-2">
          <Button disabled={clock.isPending} onClick={() => clock.mutate('in')}>
            {t('attendance.clockIn')}
          </Button>
          <Button variant="secondary" disabled={clock.isPending} onClick={() => clock.mutate('out')}>
            {t('attendance.clockOut')}
          </Button>
        </div>
        {clock.isSuccess ? <p className="mt-3 text-sm text-accent">{t('attendance.clocked')}</p> : null}
        {clock.isError ? (
          <p className="mt-3 text-sm text-danger">{clock.error instanceof Error ? clock.error.message : t('common.error')}</p>
        ) : null}
      </Card>
      <Card title={t('attendance.recent')} className="mt-3">
        {logs.isLoading ? <SkeletonRows rows={3} /> : null}
        {logs.isSuccess && (isQuiet(logs.data) || rows.length === 0) ? (
          <EmptyState title={isQuiet(logs.data) ? t('common.quiet') : t('common.empty')} />
        ) : null}
        {rows.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th>{t('attendance.date')}</Th>
                <Th>{t('common.status')}</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <Tr key={idOf(row) || index}>
                  <Td>{display(row.logged_at ?? row.date)}</Td>
                  <Td>{display(row.type ?? row.status)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Card>
    </div>
  )
}
