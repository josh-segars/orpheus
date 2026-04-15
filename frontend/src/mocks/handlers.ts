import { HttpResponse, http } from 'msw'
import { demoJob } from './fixtures/signalScoreJob'
import type { Job } from '../types/job'

/**
 * MSW request handlers. Mirror the planned FastAPI surface:
 *   GET /jobs/{id}         → Job (polled by the frontend)
 *
 * Real endpoints will replace these once backend/routers is scaffolded.
 */
export const handlers = [
  http.get('/jobs/:jobId', ({ params }) => {
    const { jobId } = params
    // Single seeded fixture for now; any jobId echoes the demo payload.
    const job: Job = { ...demoJob, id: String(jobId) }
    return HttpResponse.json(job)
  }),
]
