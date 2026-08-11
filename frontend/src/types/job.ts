import type { Narratives, ScoringStageOutput } from './scoring'

/**
 * Mirrors backend/models/job.py. Plus a typed `result` payload for complete
 * jobs that bundles the scoring output and the generated narratives.
 */

export type JobState = 'pending' | 'running' | 'complete' | 'failed'

/**
 * ORPHEUS-88: data-limited notice for the report banner. `notices` are the
 * human-readable quality messages behind the flag. Absent on pre-88 jobs —
 * treat a missing block as not-limited.
 */
export interface ReportQuality {
  data_limited: boolean
  notices: string[]
}

export interface JobResultPayload {
  scoring: ScoringStageOutput
  narratives: Narratives
  quality?: ReportQuality
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
  /**
   * ORPHEUS-120: complete advisory job whose report the advisor hasn't
   * released yet — `result` is null and the report page shows the
   * "your advisor is reviewing" surface instead of Analysis-in-Progress.
   */
  in_review?: boolean
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
  /** ORPHEUS-88: completed on incomplete/degraded data. Chip on the list. */
  data_limited?: boolean
  /**
   * ORPHEUS-120: complete advisory job awaiting the advisor's release.
   * The row renders an "In review" chip, no band, no report link.
   */
  in_review?: boolean
}
