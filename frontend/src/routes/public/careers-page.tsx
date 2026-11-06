import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { isQuiet, useApiQuery } from '../../api/session.ts'
import { LanguageSwitch } from '../../components/language-switch.tsx'
import { ThemeToggle } from '../../components/theme-toggle.tsx'
import { EmptyState } from '../../components/empty-state.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { Badge } from '../../components/ui/badge.tsx'
import { idOf, itemsOf, readPath } from '../../lib/records.ts'

export function CareersPage() {
  const { t } = useTranslation()
  const { slug = '' } = useParams()
  const query = useApiQuery(slug ? `/public/${encodeURIComponent(slug)}/jobs` : '', Boolean(slug))
  const jobs = itemsOf(query.data)

  return (
    <main className="min-h-svh px-4 py-10 text-ink">
      <div className="mx-auto w-full max-w-3xl">
        <div className="mb-6 flex items-start justify-between gap-3">
          <div>
            <p className="text-brand-gradient text-3xl font-extrabold tracking-tight">{t('app.name')}</p>
            <h1 className="mt-3 text-2xl font-bold tracking-tight">{t('careers.title')}</h1>
            <p className="mt-1 text-sm text-muted">
              {t('careers.subtitle')} · {slug}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <LanguageSwitch />
            <ThemeToggle />
          </div>
        </div>
        {query.isLoading ? <SkeletonRows /> : null}
        {query.isError ? <EmptyState title={t('common.error')} /> : null}
        {query.isSuccess && isQuiet(query.data) ? <EmptyState title={t('careers.missing')} /> : null}
        {query.isSuccess && !isQuiet(query.data) && jobs.length === 0 ? <EmptyState title={t('careers.empty')} /> : null}
        <div className="space-y-3">
          {jobs.map((job, index) => (
            <article key={idOf(job) || index} className="glass rounded-2xl p-5">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-base font-medium">{readPath(job, 'title') || t('recruitment.opening')}</h2>
                {readPath(job, 'employment_type') ? <Badge tone="accent">{readPath(job, 'employment_type')}</Badge> : null}
              </div>
              <p className="mt-1 text-sm text-muted">{readPath(job, 'location') || '—'}</p>
              {readPath(job, 'description') ? <p className="mt-3 text-sm">{readPath(job, 'description')}</p> : null}
            </article>
          ))}
        </div>
      </div>
    </main>
  )
}
