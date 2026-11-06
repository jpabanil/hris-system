import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { ApiError, api } from '../../api/client.ts'
import { LanguageSwitch } from '../../components/language-switch.tsx'
import { ThemeToggle } from '../../components/theme-toggle.tsx'
import { EmptyState } from '../../components/empty-state.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { isRow } from '../../lib/records.ts'

export function VerifyPage() {
  const { t } = useTranslation()
  const { code = '' } = useParams()
  const query = useQuery({
    queryKey: ['api', 'verify', code],
    enabled: Boolean(code),
    queryFn: async () => {
      try {
        return await api<unknown>(`/public/documents/verify/${encodeURIComponent(code)}`)
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
  })
  const doc = isRow(query.data) ? query.data : null

  return (
    <main className="min-h-svh px-4 py-10 text-ink">
      <div className="mx-auto w-full max-w-lg">
        <div className="mb-6 flex items-start justify-between gap-3">
          <div>
            <p className="text-brand-gradient text-3xl font-extrabold tracking-tight">{t('app.name')}</p>
            <h1 className="mt-3 text-2xl font-bold tracking-tight">{t('verify.title')}</h1>
            <p className="mt-1 text-sm text-muted">{code}</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <LanguageSwitch />
            <ThemeToggle />
          </div>
        </div>
        {query.isLoading ? <SkeletonRows rows={3} /> : null}
        {query.isError ? <EmptyState title={t('common.error')} /> : null}
        {query.isSuccess && query.data === null ? <EmptyState title={t('verify.invalid')} hint={code} /> : null}
        {doc ? (
          <section className="glass rounded-2xl p-5">
            <p className="text-sm text-accent">{t('verify.valid')}</p>
            <dl className="mt-4 space-y-3">
              <div>
                <dt className="text-xs text-muted">{t('verify.type')}</dt>
                <dd className="text-sm">{typeof doc.doc_type === 'string' ? doc.doc_type : '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">{t('verify.number')}</dt>
                <dd className="text-sm">{typeof doc.sequence_no === 'string' ? doc.sequence_no : '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">{t('verify.issued')}</dt>
                <dd className="text-sm">{typeof doc.issued_at === 'string' ? doc.issued_at : '—'}</dd>
              </div>
            </dl>
          </section>
        ) : null}
      </div>
    </main>
  )
}
