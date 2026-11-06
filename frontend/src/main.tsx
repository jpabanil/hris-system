import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { registerSW } from 'virtual:pwa-register'
import { AppProviders } from './app/providers.tsx'
import { router } from './app/router.tsx'
import './lib/i18n.ts'
import './index.css'

registerSW({ immediate: true })

const root = document.getElementById('root')
if (!root) throw new Error('Missing root element')

createRoot(root).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
