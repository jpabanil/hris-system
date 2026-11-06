import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { ApiError } from '../api/client.ts'

export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(() => {
    const queryClient = new QueryClient({
      queryCache: new QueryCache({
        onError: (error) => {
          if (error instanceof ApiError && error.status === 401 && window.location.pathname !== '/login') {
            queryClient.setQueryData(['me'], null)
          }
        },
      }),
      defaultOptions: {
        queries: {
          refetchOnWindowFocus: false,
          retry: (count, error) => {
            if (error instanceof ApiError && error.status < 500) return false
            return count < 1
          },
        },
      },
    })
    return queryClient
  })

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
