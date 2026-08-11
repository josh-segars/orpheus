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

/** ORPHEUS-114 (f): one rung of the band ladder — half-open lower bounds. */
export interface MethodologyBand {
  name: string
  min: number
}

/**
 * ORPHEUS-114 (f): generic scoring-methodology facts for the report page's
 * "How this score is computed" section. Deliberately carries no
 * client-specific numbers (bands are the client display, ORPHEUS-128).
 * `snapshot` is true when sourced from the job's own config_snapshot.
 */
export interface Methodology {
  dimension_weights: Record<string, number>
  bands: MethodologyBand[]
  formula: string
  snapshot: boolean
}

export interface JobResultPayload {
  scoring: ScoringStageOutput
  narratives: Narratives
  quality?: ReportQuality
  /** ORPHEUS-114 (f) — absent on cached pre-114 responses. */
  methodology?: Methodology
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
