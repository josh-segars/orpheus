import { type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { PortalLayout } from './components/layout/PortalLayout'
import { LinkedInUploadProvider } from './contexts/LinkedInUploadContext'
import { useGroundworkProgress } from './hooks/useGroundworkProgress'
import { useSessionRoles } from './hooks/useSessionRoles'
import { useSession } from './lib/auth'
import { hasSeenWelcome } from './lib/welcomeFlag'
import { AnalysisPage } from './pages/AnalysisPage'
import { CheatSheetPage } from './pages/CheatSheetPage'
import { ForwardBriefPage } from './pages/ForwardBriefPage'
import { GroundworkPage } from './pages/GroundworkPage'
import { InviteCallbackPage } from './pages/InviteCallbackPage'
import { InviteLandingPage } from './pages/InviteLandingPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { NotInvitedPage } from './pages/NotInvitedPage'
import { QuestionnairePage } from './pages/QuestionnairePage'
import { SignalScorePage } from './pages/SignalScorePage'
import { WelcomePage } from './pages/WelcomePage'
import { LinkedInStep1Page } from './pages/linkedin/Step1Page'
import { LinkedInStep2Page } from './pages/linkedin/Step2Page'
import { SignalMeterPlayground } from './pages/design/SignalMeterPlayground'

export default function App() {
  return (
    <Routes>
      {/* Dev-only design playground — no portal shell, no auth gate */}
      <Route path="/design/signal-meter" element={<SignalMeterPlayground />} />

      {/* Public auth route — its own shell */}
      <Route path="/login" element={<LoginPage />} />

      {/* Invitation landing — public, side-effect-only redirect into LinkedIn OAuth.
          MUST sit outside ProtectedRoute: the visitor is by definition not yet
          authenticated, and the callback (/invite/callback) needs to run before
          they have a clients row to satisfy ProtectedRoute. */}
      <Route path="/invite/:token" element={<InviteLandingPage />} />

      {/* Post-OAuth callback — calls POST /accept-invitation, then either
          surfaces the email-mismatch confirmation UI or redirects to /.
          Public because the user has a Supabase session but no clients row
          yet; ProtectedRoute would bounce them otherwise. React Router v6
          prioritises static segments, so this path matches before
          /invite/:token. */}
      <Route path="/invite/callback" element={<InviteCallbackPage />} />

      {/* Neither-role landing — ProtectedRoute redirects here when GET
          /session returns no advisor_id and no client_id, OR errors out.
          Public so the page can render even when the session-roles state
          would otherwise bounce. */}
      <Route path="/not-invited" element={<NotInvitedPage />} />

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
        <Route path="/questionnaire" element={<QuestionnairePage />} />
        <Route path="/jobs/:jobId/analysis" element={<AnalysisPage />} />
        <Route path="/jobs/:jobId" element={<SignalScorePage />} />
        <Route path="/jobs/:jobId/forward-brief" element={<ForwardBriefPage />} />
        <Route path="/jobs/:jobId/cheat-sheet" element={<CheatSheetPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

/**
 * Gate every authenticated route behind a Supabase session AND a backend-
 * recognised role.
 *
 * Two distinct gates layered here:
 *
 *   1. Supabase session (useSession). If it's loading, we show a transient
 *      placeholder. If unauthenticated, redirect to /login.
 *   2. Backend session-roles (useSessionRoles → GET /session). Once
 *      authenticated, we check that the caller has at least one of
 *      `advisor_id` / `client_id`. The neither-role response and any
 *      error from /session both route to /not-invited, where the user
 *      can sign out and start over.
 *
 * The hooks must be called unconditionally (rules of hooks); the
 * `enabled` flag on useSessionRoles gates the network call so it's
 * dormant until we know we're authenticated.
 */
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useSession()
  const sessionRolesQuery = useSessionRoles()

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

  // Authenticated — gate on the backend role check.
  if (sessionRolesQuery.isLoading) {
    return (
      <main className="main-interior">
        <div className="page-status">Checking your session&hellip;</div>
      </main>
    )
  }

  // On any /session failure mode (error response, no data, or both role
  // fields null) route to /not-invited rather than rendering an empty
  // portal shell.
  const roles = sessionRolesQuery.data
  if (
    sessionRolesQuery.isError ||
    !roles ||
    (!roles.advisor_id && !roles.client_id)
  ) {
    return <Navigate to="/not-invited" replace />
  }

  return <>{children}</>
}

/**
 * Decide where to send a freshly-arrived authenticated user.
 *
 *   no jobs + Welcome unseen   → /welcome
 *   no jobs + Welcome seen     → /groundwork
 *   pending or running job     → /jobs/:id/analysis  (AnalysisPage polls)
 *   complete job               → /jobs/:id           (Signal Score)
 *   failed job                 → /groundwork         (let the client retry)
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
