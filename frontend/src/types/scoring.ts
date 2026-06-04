/**
 * TypeScript mirror of backend/models/scoring.py (v2 4-dimension architecture).
 *
 * Keep field names and enum string values in sync with the Pydantic models.
 * When the backend starts returning real JSON, this file is the contract.
 */

/**
 * Client-facing signal strength band — tuner metaphor.
 * Renamed 2026-05-29 per ORPHEUS-49 (was Weak/Emerging/Moderate/Strong/Exceptional).
 * Underlying composite-score thresholds are unchanged.
 */
export type SignalBand =
  | 'Dissonant'
  | 'Untuned'
  | 'Tuning'
  | 'Tuned'
  | 'Resonant'

export type ConfidenceLabel =
  | 'CONFIRMED'
  | 'INFERRED'
  | 'PROXY'
  | 'PROVISIONAL'

export type ScoringMethod =
  | 'rubric'
  | 'quantitative'
  | 'quantitative_hybrid'

export interface SubDimensionScore {
  name: string
  score: number
  scale: string // e.g. '1-5' or '0-5'
  method: ScoringMethod
  confidence: ConfidenceLabel
  raw_value: number | null

  /**
   * Narrative fields for the client-facing expandable sub-dimension row.
   * Optional — the UI degrades to the one-liner if none are present.
   * TODO: add to backend ScoringStageOutput / narrative generator.
   */
  summary?: string
  best_practices?: string
  improvements?: string[]
}

export interface DimensionScore {
  name: string
  weight: number // decimal, e.g. 0.35
  confidence: ConfidenceLabel
  normalized_score: number // 0.0–1.0
  contribution: number // normalized_score × weight × 100
  /**
   * Per-dimension band classification (ORPHEUS-22). Server-authoritative;
   * reuses the composite SIGNAL_BANDS thresholds against
   * `normalized_score × 100`. Pre-ORPHEUS-22 the client derived this
   * locally; that helper is now retired.
   */
  band: SignalBand
  sub_dimensions: SubDimensionScore[]
  completeness_floor_applied: boolean
}

export interface ScoredDimensions {
  composite: number // 0–100
  band: SignalBand
  /** Exactly 4 dimensions in v2. */
  dimensions: DimensionScore[]
}

// --- Forward Brief data ----------------------------------------------------

export interface AudienceSegment {
  name: string
  pct: number // 0.0–1.0
}

export interface ViewerActorAffinity {
  concentrated: boolean
  top_targets: string[]
}

export interface VisualProfessionalism {
  photo_present: boolean
}

export interface EngagementInvitation {
  services_present: boolean
  contact_visible: boolean
  cta_in_about: boolean
}

export interface QualitativeFlags {
  viewer_actor_affinity: ViewerActorAffinity
  visual_professionalism: VisualProfessionalism
  engagement_invitation: EngagementInvitation
}

export interface ForwardBriefQuantitative {
  follower_count: number | null
  follower_growth_rate: number | null
  unique_members_reached: number | null
  avg_impressions_per_post: number | null
  avg_engagement_rate: number | null
  top_post_impressions: number | null
  audience_seniority: Record<string, number> | null
  audience_industries: AudienceSegment[] | null
  audience_geography: AudienceSegment[] | null
  top_organizations: string[] | null
  avg_comment_length_words: number | null
  longest_posting_gap_weeks: number | null
  zero_post_week_pct: number | null
}

export interface ForwardBriefData {
  quantitative: ForwardBriefQuantitative
  qualitative_flags: QualitativeFlags
}

export interface ScoringStageOutput {
  scored_dimensions: ScoredDimensions
  forward_brief_data: ForwardBriefData
}

// --- Narratives ------------------------------------------------------------
// Narrative generation returns a dict keyed by dimension name, plus a
// `forward_brief` Markdown string and a structured `cheat_sheet`.
// See backend/agents/narrative.py.

export interface CheatSheetPriority {
  /** Short, imperative title (e.g. "Grow Your Follower Base"). */
  title: string
  /**
   * One-to-two sentence action step. Plain text — no markdown. Bolded
   * target / milestone (if present) should be included as a trailing
   * sentence in the same string so the client can render it with a
   * simple "<strong>…</strong>" marker.
   */
  action: string
}

export interface CheatSheetRhythmSection {
  /** e.g. "Every Day", "Every Week", "Every Month". */
  cadence: string
  /** Checklist items, one line each. */
  items: string[]
}

export interface CheatSheetMilestone {
  value: string
  label: string
}

export interface CheatSheetContent {
  /** Exactly 5 priorities, already ordered by leverage. */
  priorities: CheatSheetPriority[]
  /** Daily / weekly / monthly (or similar) checklist blocks. */
  rhythm: CheatSheetRhythmSection[]
  /** 90-day quantitative targets shown in the dark milestones band. */
  milestones: CheatSheetMilestone[]
}

export interface Narratives {
  /** Keyed by dimension name (matches DimensionScore.name). */
  dimension_narratives: Record<string, string>
  /** Markdown-formatted Forward Brief (400–600 words). */
  forward_brief: string
  /**
   * Structured cheat sheet — printable one-page reference derived from
   * the Forward Brief. Populated by the narrative agent as of
   * ORPHEUS-60 (2026-06-04). The `| null` union persists because legacy
   * complete jobs from before ORPHEUS-60 have no `cheat_sheet`
   * narratives row, so their wire payload still serializes null; on
   * those jobs CheatSheetPage's null-state branch renders the
   * not-ready surface as a graceful fallback. New jobs always carry a
   * populated cheat_sheet.
   */
  cheat_sheet: CheatSheetContent | null
}
