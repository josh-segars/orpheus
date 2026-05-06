import { type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { PortalLayout } from './components/layout/PortalLayout'
import { LinkedInUploadProvider } from './contexts/LinkedInUploadContext'
import { useGroundworkProgress } from './hooks/useGroundworkProgress'
import { useSession } from './lib/auth'
import { hasSeenWelcome } from './lib/welcomeFlag'
import { CheatSheetPage } from './pages/CheatSheetPage'
import { ForwardBriefPage } from './pages/ForwardBriefPage'
import { GroundworkPage } from './pages/GroundworkPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { SignalScorePage } from './pages/SignalScorePage'
import { WelcomePage } from './pages/WelcomePage'
import { LinkedInStep1Page } from './pages/linkedin/Step1Page'
import { LinkedInStep2Page } from './pages/linkedin/Step2Page'
import { SignalMeterPlayground } from './pages/design/SignalMeterPlayground'
import {
  Section1Page,
  Section2Page,
  Section3Page,
  Section4Page,
  Section5Page,
  Section6Page,
  Section7Page,
} from './pages/questionnaire/sections'

export default function App() {
  return (
    <Routes>
      {/* Dev-only design playground — no portal shell, no auth gate */}
      <Route path="/design/signal-meter" element={<SignalMeterPlayground />} />

      {/* Public auth route — its own shell */}
      <Route path="/login" element={<LoginPage />} />

      {/* Authenticated portal — LinkedInUploadProvider wraps the layout so
          the in-memory ZIP/XLSX File state persists across navigation
          between Step 1, Step 2, and the Groundwork submit. */}
      <Route
        element={
          <ProtectedRoute>
            <LinkedInUploadProvider>
              <PortalLayout />
            </LinkedInUploadProvider>
          </ProtectedRoute>
        }
      >
        {/*
          Smart index redirect — see SmartIndexRedirect below. Routes the
          signed-in client to Welcome / Groundwork / Analysis / Signal Score
          based on their progress, faithful to the prototype flow.
        */}
        <Route index element={<SmartIndexRedirect />} />
        <Route path="/welcome" element={<WelcomePage />} />
        <Route path="/groundwork" element={<GroundworkPage />} />
        <Route path="/linkedin/step1" element={<LinkedInStep1Page />} />
        <Route path="/linkedin/step2" element={<LinkedInStep2Page />} />
        <Route path="/questionnaire/s1" element={<Section1Page />} />
        <Route path="/questionnaire/s2" element={<Section2Page />} />
        <Route path="/questionnaire/s3" element={<Section3Page />} />
        <Route path="/questionnaire/s4" element={<Section4Page />} />
        <Route path="/questionnaire/s5" element={<Section5Page />} />
        <Route path="/questionnaire/s6" element={<Section6Page />} />
        <Route path="/questionnaire/s7" element={<Section7Page />} />
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

/**
 * Decide where to send a freshly-arrived authenticated user.
 *
 *   no jobs + Welcome unseen   → /welcome
 *   no jobs + Welcome seen     → /groundwork
 *   pending or running job     → /jobs/:id/analysis  (rendered by ORPHEUS-20)
 *   complete job               → /jobs/:id           (Signal Score)
 *   failed job                 → /groundwork         (let the client retry)
 *
 * Until ORPHEUS-20 lands, /jobs/:id/analysis falls through to NotFoundPage,
 * which is acceptable — the only path that produces a pending job is the
 * upload flow that ORPHEUS-16 adds, which doesn't exist yet either.
 */
function SmartIndexRedirect() {
  const { data, isLoading, isError } = useGroundworkProgress()

  if (isLoading) {
    return (
      <main className="main-interior">
        <div className="page-status">Loading your portal&hellip;</div>
      </main>
    )
  }

  // If the lightweight Supabase read fails (e.g. RLS misconfig, network),
  // route to Groundwork rather than blocking the user. They can navigate
  // around manually from there.
  if (isError || !data) {
    return <Navigate to="/groundwork" replace />
  }

  if (data.latestPendingJobId) {
    return <Navigate to={`/jobs/${data.latestPendingJobId}/analysis`} replace />
  }

  if (data.latestCompleteJobId) {
    return <Navigate to={`/jobs/${data.latestCompleteJobId}`} replace />
  }

  if (!hasSeenWelcome()) {
    return <Navigate to="/welcome" replace />
  }

  return <Navigate to="/groundwork" replace />
}
