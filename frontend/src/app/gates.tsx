import { Navigate, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useSession } from '../api/session.ts'
import { portalOnly } from '../api/types.ts'
import { Button } from '../components/ui/button.tsx'
import { EmptyState } from '../components/empty-state.tsx'
import { SkeletonRows } from '../components/skeleton.tsx'

export function RequireAuth() {
  const { t } = useTranslation()
  const session = useSession()
  if (session.isLoading) {
    return (
      <div className="bg-paper p-6">
        <SkeletonRows rows={6} />
      </div>
    )
  }
  if (session.isError) {
    return (
      <div className="bg-paper p-6">
        <EmptyState
          title={t('common.error')}
          action={
            <Button variant="secondary" onClick={() => void session.refetch()}>
              {t('common.retry')}
            </Button>
          }
        />
      </div>
    )
  }
  if (!session.data) return <Navigate to="/login" replace />
  return <Outlet />
}

export function HomeRedirect() {
  const session = useSession()
  if (!session.data) return <Navigate to="/login" replace />
  return <Navigate to={portalOnly(session.data) ? '/portal' : '/admin'} replace />
}
