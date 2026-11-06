import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client.ts'
import { isQuiet, useApiQuery, useSession } from '../../api/session.ts'
import { canSee } from '../../api/types.ts'
import { EmptyState } from '../../components/empty-state.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { Button } from '../../components/ui/button.tsx'
import { Tabs } from '../../components/ui/tabs.tsx'
import { display, isRow } from '../../lib/records.ts'

const modules = ['general', 'attendance', 'leave', 'payroll', 'offboarding'] as const

function valuesOf(data: unknown): Record<string, unknown> | null {
  if (!isRow(data)) return null
  return isRow(data.values) ? data.values : null
}

export function SettingsPage() {
  const { t } = useTranslation()
  const session = useSession()
  const queryClient = useQueryClient()
  const [module, setModule] = useState<(typeof modules)[number]>('general')
  const query = useApiQuery(`/settings/${module}`)
  const values = valuesOf(query.data)
  const text = JSON.stringify(values ?? {}, null, 2)
  const [draft, setDraft] = useState(text)
  const [notice, setNotice] = useState('')
  const [parseError, setParseError] = useState('')
  const canEdit = session.data ? canSee(session.data, ['settings.manage']) : false

  useEffect(() => {
    setDraft(text)
    setParseError('')
  }, [text])

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api(`/settings/${module}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: async () => {
      setNotice(t('settings.saved'))
      await queryClient.invalidateQueries({ queryKey: ['api', `/settings/${module}`] })
    },
  })

  return (
    <div>
      <PageHeader title={t('settings.title')} subtitle={t('settings.subtitle')} />
      {notice ? <p className="mb-3 text-sm text-accent">{notice}</p> : null}
      <Tabs
        value={module}
        onChange={(next) => {
          setNotice('')
          setModule(next as (typeof modules)[number])
        }}
        tabs={modules.map((item) => ({ id: item, label: t(`settings.${item}`) }))}
      />
      {query.isLoading ? <SkeletonRows /> : null}
      {query.isError ? <EmptyState title={t('common.error')} /> : null}
      {query.isSuccess && isQuiet(query.data) ? <EmptyState title={t('common.quiet')} /> : null}
      {query.isSuccess && !isQuiet(query.data) && !values ? <EmptyState title={t('settings.empty')} /> : null}
      {values ? (
        <div className="space-y-4">
          <dl className="grid gap-3 sm:grid-cols-2">
            {Object.entries(values).map(([key, value]) => (
              <div key={key} className="rounded-xl bg-soft px-3.5 py-3">
                <dt className="text-xs text-muted">{key}</dt>
                <dd className="mt-1 text-sm break-words">
                  {value != null && typeof value === 'object' ? JSON.stringify(value) : display(value)}
                </dd>
              </div>
            ))}
          </dl>
          {canEdit ? (
            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault()
                try {
                  const parsed: unknown = JSON.parse(draft)
                  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
                    setParseError(t('settings.invalidJson'))
                    return
                  }
                  setParseError('')
                  save.mutate(parsed as Record<string, unknown>)
                } catch {
                  setParseError(t('settings.invalidJson'))
                }
              }}
            >
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-medium text-muted">{t('settings.values')}</span>
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  rows={12}
                  className="w-full rounded-xl border border-line bg-card px-3.5 py-2.5 font-mono text-xs text-ink outline-none backdrop-blur-md transition-all focus:border-accent/60 focus:ring-4 focus:ring-accent/15"
                />
              </label>
              {parseError ? <p className="text-sm text-danger">{parseError}</p> : null}
              {save.isError ? (
                <p className="text-sm text-danger">{save.error instanceof Error ? save.error.message : t('common.error')}</p>
              ) : null}
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? t('common.saving') : t('common.save')}
              </Button>
            </form>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
