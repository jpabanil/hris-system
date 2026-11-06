export type { ApiPath } from './schema'

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

function readCsrf(): string {
  const match = document.cookie.match(/(?:^|; )hris_csrf=([^;]*)/)
  return match?.[1] ? decodeURIComponent(match[1]) : ''
}

const NO_REFRESH = new Set(['/auth/login', '/auth/refresh', '/auth/logout', '/auth/2fa/verify'])

let refreshing: Promise<boolean> | null = null

function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = fetch('/api/v1/auth/refresh', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': readCsrf(),
      },
    })
      .then((response) => response.ok)
      .catch(() => false)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

export async function api<T>(path: string, init: RequestInit = {}, allowRefresh = true): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (method !== 'GET' && method !== 'HEAD') {
    headers.set('X-CSRF-Token', readCsrf())
  }

  const response = await fetch(`/api/v1${path}`, {
    ...init,
    method,
    headers,
    credentials: 'include',
  })

  const barePath = path.split('?')[0] ?? path
  if (response.status === 401 && allowRefresh && !NO_REFRESH.has(barePath)) {
    const refreshed = await refreshSession()
    if (refreshed) return api<T>(path, init, false)
  }

  if (!response.ok) {
    let code = 'error'
    let message = response.statusText || 'Request failed'
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object') {
        const record = body as { code?: unknown; message?: unknown }
        if (typeof record.code === 'string') code = record.code
        if (typeof record.message === 'string') message = record.message
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, code, message)
  }

  if (response.status === 204) return undefined as T
  const text = await response.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}
