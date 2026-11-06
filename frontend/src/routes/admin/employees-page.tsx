import { useEffect, useMemo, useState } from 'react'
import { standardSchemaResolver } from '@hookform/resolvers/standard-schema'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api } from '../../api/client.ts'
import { useSession } from '../../api/session.ts'
import { canSee } from '../../api/types.ts'
import { RecordList } from '../../components/record-list.tsx'
import { Button } from '../../components/ui/button.tsx'
import { Dialog } from '../../components/ui/dialog.tsx'
import { Input, Select } from '../../components/ui/input.tsx'
import {
  employeeSchema,
  employmentStatusOptions,
  employmentTypeOptions,
  type EmployeeValues,
} from '../../features/employees/schema.ts'
import { idOf, labelState, personName, readPath, type Row } from '../../lib/records.ts'

const defaults: EmployeeValues = {
  employee_no: '',
  first: '',
  middle: '',
  last: '',
  suffix: '',
  employment_type: 'regular',
  employment_status: 'active',
  date_hired: '',
  work_email: '',
  mobile: '',
}

function CreateEmployeeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const schema = useMemo(() => employeeSchema(t('common.required'), t('auth.emailInvalid')), [t])
  const form = useForm<EmployeeValues>({
    resolver: standardSchemaResolver(schema),
    defaultValues: defaults,
  })

  useEffect(() => {
    if (open) form.reset(defaults)
  }, [open, form])

  const create = useMutation({
    mutationFn: (values: EmployeeValues) =>
      api('/employees', {
        method: 'POST',
        body: JSON.stringify({
          employee_no: values.employee_no,
          name: {
            first: values.first,
            middle: values.middle,
            last: values.last,
            suffix: values.suffix,
          },
          employment_type: values.employment_type,
          employment_status: values.employment_status,
          date_hired: values.date_hired,
          contact: {
            work_email: values.work_email,
            mobile: values.mobile,
          },
        }),
      }),
    onSuccess: async () => {
      form.reset(defaults)
      onClose()
      await queryClient.invalidateQueries({ queryKey: ['api'] })
    },
  })

  return (
    <Dialog open={open} title={t('employees.add')} onClose={onClose}>
      <form className="grid gap-3 sm:grid-cols-2" noValidate onSubmit={form.handleSubmit((values) => create.mutate(values))}>
        <Input label={t('employees.number')} error={form.formState.errors.employee_no?.message} {...form.register('employee_no')} />
        <Input label={t('employees.first')} error={form.formState.errors.first?.message} {...form.register('first')} />
        <Input label={t('employees.middle')} error={form.formState.errors.middle?.message} {...form.register('middle')} />
        <Input label={t('employees.last')} error={form.formState.errors.last?.message} {...form.register('last')} />
        <Input label={t('employees.suffix')} error={form.formState.errors.suffix?.message} {...form.register('suffix')} />
        <Input label={t('employees.hired')} type="date" error={form.formState.errors.date_hired?.message} {...form.register('date_hired')} />
        <Select label={t('employees.type')} error={form.formState.errors.employment_type?.message} {...form.register('employment_type')}>
          {employmentTypeOptions.map((option) => (
            <option key={option} value={option}>
              {t(`states.${option}`)}
            </option>
          ))}
        </Select>
        <Select
          label={t('common.status')}
          error={form.formState.errors.employment_status?.message}
          {...form.register('employment_status')}
        >
          {employmentStatusOptions.map((option) => (
            <option key={option} value={option}>
              {t(`states.${option}`)}
            </option>
          ))}
        </Select>
        <Input label={t('employees.email')} type="email" error={form.formState.errors.work_email?.message} {...form.register('work_email')} />
        <Input label={t('employees.mobile')} error={form.formState.errors.mobile?.message} {...form.register('mobile')} />
        {create.isError ? (
          <p className="text-sm text-danger sm:col-span-2">
            {create.error instanceof Error ? create.error.message : t('common.error')}
          </p>
        ) : null}
        {create.isSuccess ? <p className="text-sm text-accent sm:col-span-2">{t('employees.created')}</p> : null}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? t('common.saving') : t('common.create')}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

export function EmployeesPage() {
  const { t } = useTranslation()
  const session = useSession()
  const [open, setOpen] = useState(false)
  const canCreate = session.data ? canSee(session.data, ['employees.manage']) : false

  return (
    <>
      <RecordList
        title={t('employees.title')}
        subtitle={t('employees.subtitle')}
        basePath="/employees"
        action={
          canCreate ? (
            <Button
              onClick={() => setOpen(true)}
            >
              {t('employees.add')}
            </Button>
          ) : null
        }
        columns={[
          { key: 'employee_no', header: t('employees.number') },
          {
            key: 'name',
            header: t('common.name'),
            render: (row: Row) => {
              const id = idOf(row)
              const label = personName(row.name) || readPath(row, 'employee_no') || '—'
              return id ? (
                <Link className="text-accent underline-offset-2 hover:underline" to={`/admin/employees/${id}`}>
                  {label}
                </Link>
              ) : (
                label
              )
            },
          },
          {
            key: 'employment_status',
            header: t('common.status'),
            render: (row) => labelState(t, readPath(row, 'employment_status')),
          },
          { key: 'employment_type', header: t('employees.type') },
          { key: 'date_hired', header: t('employees.hired') },
        ]}
      />
      <CreateEmployeeDialog open={open} onClose={() => setOpen(false)} />
    </>
  )
}
