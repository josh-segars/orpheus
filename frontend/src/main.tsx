import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
// Vercel observability (ORPHEUS-79). Framework-agnostic React builds —
// this is a Vite app, not Next.js, so the /react entrypoints are required.
// Both components no-op outside production Vercel deployments unless the
// corresponding dashboard toggle is enabled (Project → Analytics /
// Speed Insights), so local dev and vitest are unaffected.
import { Analytics } from '@vercel/analytics/react'
import { SpeedInsights } from '@vercel/speed-insights/react'

// Import the shared design-system stylesheet (single source of truth,
// also used by the HTML prototype screens in repo root).
import '../../orpheus-styles.css'

import App from './App'

async function bootstrap() {
  // Start MSW in development only when there are handlers to register.
  // The handlers array is intentionally empty in normal dev (the real
  // FastAPI backend serves /jobs and friends); if we still call
  // worker.start() in that case, the registered service worker has to
  // fall through to passthrough for every request, and stale versions
  // of the on-disk mockServiceWorker.js can break real fetches with an
  // opaque "Failed to fetch". Gating on handlers.length means "no
  // mocks → no worker → no chance of interception."
  //
  // To iterate on UI offline, add a handler in src/mocks/handlers.ts
  // (the file's docstring shows the pattern); the worker will start
  // on next reload.
  if (import.meta.env.DEV) {
    const { handlers } = await import('./mocks/handlers')
    if (handlers.length > 0) {
      const { worker } = await import('./mocks/browser')
      await worker.start({
        onUnhandledRequest: 'bypass',
      })
    }
  }

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
    },
  })

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
        <Analytics />
        <SpeedInsights />
      </QueryClientProvider>
    </StrictMode>,
  )
}

bootstrap()
