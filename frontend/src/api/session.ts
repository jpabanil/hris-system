import { useQuery } from '@tanstack/react-query'
import { ApiError, api } from './client.ts'
import type { SessionUser } from './types.ts'

export type Quiet = { quiet: true; items: []; total: 0 }

export function isQuiet(data: unknown): data is Quiet {
  return typeof data === 'object' && data !== null && 'quiet' in data && data.quiet === true
}

export async function quietGet(path: string): Promise<unknown> {
  try {
    return await api<unknown>(path)
  } catch (error) {
    if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
      return { quiet: true, items: [], total: 0 }
    }
    throw error
  }
}

export function useApiQuery(path: string, enabled = true) {
  return useQuery({
    queryKey: ['api', path],
    queryFn: () => quietGet(path),
    enabled,
  })
}

export function useSession() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await api<SessionUser>('/auth/me')
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null
        throw error
      }
    },
    retry: false,
    staleTime: 30_000,
  })
}
