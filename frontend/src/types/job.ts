import type { Narratives, ScoringStageOutput } from './scoring'

/**
 * Mirrors backend/models/job.py. Plus a typed `result` payload for complete
 * jobs that bundles the scoring output and the generated narratives.
 */

export type JobState = 'pending' | 'running' | 'complete' | 'failed'

export interface JobResultPayload {
  scoring: ScoringStageOutput
  narratives: Narratives
}

export interface Job {
  id: string
  state: JobState
  created_at: string
  updated_at: string | null
  client_id: string | null
  /** Present when state === 'complete'. */
  result: JobResultPayload | null
  error: string | null
}

/**
 * One row in the client's reports list (GET /jobs, ORPHEUS-81). Mirrors
 * backend JobSummary. `band` is the composite signal band — present only
 * for complete jobs with a scores row. No updated_at — the jobs table
 * doesn't carry that column.
 */
export interface JobSummary {
  id: string
  state: JobState
  created_at: string
  band: string | null
}
