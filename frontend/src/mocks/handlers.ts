import type { RequestHandler } from 'msw'

/**
 * MSW request handlers.
 *
 * Up until ORPHEUS-28 the demo-job handler returned a seeded fixture for any
 * /jobs/{id} request, which let the SignalScorePage render before the
 * FastAPI backend was running. With auth in place we now hit the real
 * backend (VITE_API_BASE_URL=http://localhost:8000), and the handler is no
 * longer wanted — leaving it would mask real 401s and shield us from
 * end-to-end behaviour.
 *
 * The demo fixture itself is preserved at src/mocks/fixtures/signalScoreJob
 * for use by component playgrounds (e.g. design/SignalMeterPlayground).
 *
 * If you need the offline fallback back temporarily (e.g. iterating on UI
 * without the backend running), re-add a handler here following the pattern
 * preserved in git history at this file's previous commit.
 */
export const handlers: RequestHandler[] = []
