import { Navigate, Route, Routes } from 'react-router-dom'
import { PortalLayout } from './components/layout/PortalLayout'
import { SignalScorePage } from './pages/SignalScorePage'
import { ForwardBriefPage } from './pages/ForwardBriefPage'
import { CheatSheetPage } from './pages/CheatSheetPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { SignalMeterPlayground } from './pages/design/SignalMeterPlayground'

export default function App() {
  return (
    <Routes>
      {/* Dev-only design playgrounds — no portal shell */}
      <Route path="/design/signal-meter" element={<SignalMeterPlayground />} />

      <Route element={<PortalLayout />}>
        {/* Default to a seeded demo job until auth/job-list exists */}
        <Route index element={<Navigate to="/jobs/demo" replace />} />
        <Route path="/jobs/:jobId" element={<SignalScorePage />} />
        <Route
          path="/jobs/:jobId/forward-brief"
          element={<ForwardBriefPage />}
        />
        <Route
          path="/jobs/:jobId/cheat-sheet"
          element={<CheatSheetPage />}
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
