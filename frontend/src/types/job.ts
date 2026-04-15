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
