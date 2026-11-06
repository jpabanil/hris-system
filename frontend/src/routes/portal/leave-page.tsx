import { useMemo } from 'react'
import { standardSchemaResolver } from '@hookform/resolvers/standard-schema'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { isQuiet, useApiQuery, useSession } from '../../api/session.ts'
import { api } from '../../api/client.ts'
import { Card } from '../../components/ui/card.tsx'
import { Button } from '../../components/ui/button.tsx'
import { Checkbox, Input, Select } from '../../components/ui/input.tsx'
import { EmptyState } from '../../components/empty-state.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { Table, Td, Th, Tr } from '../../components/ui/table.tsx'
import { leaveDays, leaveSchema, type LeaveValues } from '../../features/leave/schema.ts'
import { display, idOf, itemsOf, readPath } from '../../lib/records.ts'

const defaults: LeaveValues = {
  leave_type_id: '',
  start_date: '',
  end_date: '',
  reason: '',
  half_day: false,
}

export function PortalLeavePage() {
  const { t } = useTranslation()
  const session = useSession()
  const queryClient = useQueryClient()
  const types = useApiQuery('/leave-types?page=1&page_size=100')
  const mine = useApiQuery('/leave-requests?page=1&page_size=25')
  const typeRows = itemsOf(types.data)
  const requests = itemsOf(mine.data)
  const schema = useMemo(() => leaveSchema(t('common.required'), t('leave.endBefore')), [t])
  const form = useForm<LeaveValues>({
    resolver: standardSchemaResolver(schema),
    defaultValues: defaults,
  })

  const file = useMutation({
    mutationFn: (values: LeaveValues) =>
      api('/leave-requests', {
        method: 'POST',
        body: JSON.stringify({
          employee_id: session.data?.employee_id ?? '',
          leave_type_id: values.leave_type_id,
          start_date: values.start_date,
          end_date: values.end_date,
          half_day: values.half_day,
          days: leaveDays(values.start_date, values.end_date, values.half_day),
          reason: values.reason,
        }),
      }),
    onSuccess: async () => {
      form.reset(defaults)
      await queryClient.invalidateQueries({ queryKey: ['api'] })
    },
  })

  return (
    <div>
      <PageHeader title={t('leave.file')} subtitle={t('leave.subtitle')} />
      <Card title={t('leave.file')}>
        <form className="grid gap-3 sm:grid-cols-2" noValidate onSubmit={form.handleSubmit((values) => file.mutate(values))}>
          {typeRows.length > 0 ? (
            <Select label={t('leave.type')} error={form.formState.errors.leave_type_id?.message} {...form.register('leave_type_id')}>
              <option value="">{t('leave.pickType')}</option>
              {typeRows.map((row) => {
                const id = idOf(row)
                return (
                  <option key={id} value={id}>
                    {readPath(row, 'name') || readPath(row, 'code') || id}
                  </option>
                )
              })}
            </Select>
          ) : (
            <Input label={t('leave.typeId')} error={form.formState.errors.leave_type_id?.message} {...form.register('leave_type_id')} />
          )}
          <Input label={t('leave.start')} type="date" error={form.formState.errors.start_date?.message} {...form.register('start_date')} />
          <Input label={t('leave.end')} type="date" error={form.formState.errors.end_date?.message} {...form.register('end_date')} />
          <Input label={t('leave.reason')} error={form.formState.errors.reason?.message} {...form.register('reason')} />
          <Checkbox label={t('leave.half')} {...form.register('half_day')} />
          {file.isError ? (
            <p className="text-sm text-danger sm:col-span-2">{file.error instanceof Error ? file.error.message : t('common.error')}</p>
          ) : null}
          {file.isSuccess ? <p className="text-sm text-accent sm:col-span-2">{t('leave.filed')}</p> : null}
          <div className="sm:col-span-2">
            <Button type="submit" disabled={file.isPending}>
              {file.isPending ? t('common.saving') : t('common.submit')}
            </Button>
          </div>
        </form>
      </Card>
      <Card title={t('leave.mine')} className="mt-3">
        {mine.isLoading ? <SkeletonRows rows={3} /> : null}
        {mine.isSuccess && (isQuiet(mine.data) || requests.length === 0) ? (
          <EmptyState title={isQuiet(mine.data) ? t('common.quiet') : t('common.empty')} />
        ) : null}
        {requests.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th>{t('leave.type')}</Th>
                <Th>{t('leave.start')}</Th>
                <Th>{t('leave.end')}</Th>
                <Th>{t('common.status')}</Th>
              </tr>
            </thead>
            <tbody>
              {requests.map((row, index) => (
                <Tr key={idOf(row) || index}>
                  <Td>{display(row.leave_type_id)}</Td>
                  <Td>{display(row.start_date)}</Td>
                  <Td>{display(row.end_date)}</Td>
                  <Td>{display(row.status)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Card>
    </div>
  )
}
