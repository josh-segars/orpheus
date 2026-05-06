import { type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { PortalLayout } from './components/layout/PortalLayout'
import { useSession } from './lib/auth'
import { CheatSheetPage } from './pages/CheatSheetPage'
import { ForwardBriefPage } from './pages/ForwardBriefPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { SignalScorePage } from './pages/SignalScorePage'
import { SignalMeterPlayground } from './pages/design/SignalMeterPlayground'

export default function App() {
  return (
    <Routes>
      {/* Dev-only design playground — no portal shell, no auth gate */}
      <Route path="/design/signal-meter" element={<SignalMeterPlayground />} />

      {/* Public auth route — its own shell */}
      <Route path="/login" element={<LoginPage />} />

      {/* Authenticated portal */}
      <Route
        element={
          <ProtectedRoute>
            <PortalLayout />
          </ProtectedRoute>
        }
      >
        {/* Until /jobs/me lands (ORPHEUS-16/17), authenticated users land on
            the seeded demo job; an unowned job will surface as a graceful
            "couldn't load this report" inside SignalScorePage. */}
        <Route index element={<Navigate to="/jobs/demo" replace />} />
        <Route path="/jobs/:jobId" element={<SignalScorePage />} />
        <Route path="/jobs/:jobId/forward-brief" element={<ForwardBriefPage />} />
        <Route path="/jobs/:jobId/cheat-sheet" element={<CheatSheetPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

/**
 * Gate every authenticated route behind a Supabase session. While the session
 * is hydrating from localStorage we show a transient placeholder; refusing to
 * render the layout in that window prevents a flash of the empty portal
 * before the user's data is available.
 */
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useSession()

  if (status === 'loading') {
    return (
      <main className="main-interior">
        <div className="page-status">Checking your session&hellip;</div>
      </main>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
