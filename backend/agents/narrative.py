"""Narrative generation agent — produces dimension narratives and Forward Brief.

This is the second of two Claude API calls in the pipeline (the first is
rubric scoring in agents/rubric.py). By the time this stage runs, all scores
are already computed and final. Claude's job here is interpretation and
communication — not scoring.

Architecture (from Narrative Generation Spec, approved April 2026):
- Claude receives: scored_dimensions, forward_brief_data, questionnaire answers
- Claude returns: 5 sections (4 dimension narratives + 1 forward_brief) as JSON
- Score-to-narrative mappings are explicit in the prompt — not left to Claude's
  open-ended judgment
- Advisor-level configuration (voice, directness, mechanics, focus) shapes the
  prompt at runtime. Platform defaults apply when no advisor config is set.

Decisions (current assumptions, accepted):
- Advisory: neutral third-person (advisor edits into their own voice)
- Self-serve: direct second-person
- Recommendation style: coaching suggestions
- System mechanics: behind the curtain
- Lengths: 150-300 words per dimension, 400-600 for Forward Brief
- Single Claude call for all 5 sections
"""

import json
from typing import NamedTuple

from anthropic import Anthropic

from backend.models.scoring import ScoringStageOutput
from backend.models.quality import DataQualityReport, IssueSeverity


class NarrativeResult(NamedTuple):
    """Structured return from the narrative agent.

    Three payloads in one Claude call:
      * sections — the 5 top-level narratives (4 dimensions + forward_brief),
        keyed by section identifier. Same shape `generate_narratives` has
        returned since the v2 pipeline shipped.
      * sub_dimensions — per-sub-dim narrative slots, keyed by
        `(dimension_name, sub_dim_name)` for direct merge into
        ScoringStageOutput.scored_dimensions before persisting (ORPHEUS-21).
        Inner dict has 'summary' (always), 'best_practices' (scores 0–3),
        'improvements' (scores 0–4, list[str]). Score 0 takes the same
        full-payload posture as score 1 per ORPHEUS-63.
      * cheat_sheet — structured one-page reference card derived from the
        Forward Brief (ORPHEUS-60). Dict with priorities (5) / rhythm (3) /
        milestones (3–4). `None` when Claude omits the section entirely
        (best-effort parse posture; the worker treats `None` as "skip the
        narratives row" rather than failing the whole job).
    """
    sections: dict[str, str]
    sub_dimensions: dict[tuple[str, str], dict]
    cheat_sheet: dict | None


# ============================================================
# Advisor narrative configuration defaults
# ============================================================

DEFAULT_NARRATIVE_CONFIG = {
    "voice": "third_person_neutral",
    "recommendation_style": "coaching",
    "system_mechanics": "behind_curtain",
    "practice_focus": None,  # None = balanced across all areas
    "custom_instructions": None,
}

VOICE_INSTRUCTIONS = {
    "third_person_neutral": (
        "Write in a neutral, third-person professional voice. Refer to the "
        "client by their professional context, not by name. Write as a "
        "factual assessment that an advisor can present and personalize. "
        'Example: "The profile communicates a clear professional identity..." '
        'not "Your profile communicates..."'
    ),
    "second_person_direct": (
        "Address the client directly using second person. Write in a warm, "
        "professional coaching tone — informed and encouraging without being "
        "promotional. "
        'Example: "Your headline clearly signals your expertise in..." '
        'not "The profile communicates..."'
    ),
    "second_person_formal": (
        "Address the client directly using second person, but maintain a "
        "formal, consultative tone. Authoritative without being cold. "
        'Example: "Your profile presents a clear professional identity..." '
    ),
}

DIRECTNESS_INSTRUCTIONS = {
    "coaching": (
        "Frame recommendations as collaborative observations and suggestions. "
        "Use language like 'could,' 'might consider,' 'one approach would be.' "
        'Example: "The About section could be sharpened by leading with current work..." '
        'Not: "Rewrite your About section to lead with current work."'
    ),
    "prescriptive": (
        "Frame recommendations as clear, specific instructions. The client "
        "should know exactly what to change and how. Use action verbs. "
        'Example: "Rewrite the headline to name your specific domain and current role." '
        'Not: "The headline could potentially be more specific."'
    ),
    "balanced": (
        "Blend observation with direction. Lead with what the data shows, "
        "then state the recommended action clearly. "
        'Example: "The headline is broad enough to dilute the professional signal. '
        'Narrowing it to name your specific expertise would strengthen retrieval."'
    ),
}

MECHANICS_INSTRUCTIONS = {
    "behind_curtain": (
        "Do NOT reference LinkedIn's internal systems, retrieval mechanisms, "
        "ranking algorithms, embeddings, or technical architecture. Frame "
        "observations in terms of how the profile reads, what it communicates, "
        "and how audiences experience it. "
        'Say "clearly communicates your expertise" not "gives the retrieval '
        'system clear language for the member embedding."'
    ),
    "light_reference": (
        "You may briefly reference that LinkedIn's systems use profile "
        "language and behavior patterns to determine visibility, but keep "
        "it accessible. No jargon — no 'embeddings,' 'retrieval,' or "
        "'ranking models.' "
        'Say "LinkedIn uses your profile language to determine who sees your content" '
        'not "the retrieval system builds a member embedding from profile fields."'
    ),
    "technical": (
        "Reference LinkedIn's retrieval and ranking systems where relevant — "
        "profile embeddings, content semantic matching, behavioral signals. "
        "Write for an audience that understands and values the technical grounding. "
        "Be precise but not academic."
    ),
}

FOCUS_INSTRUCTIONS = {
    "thought_leadership": (
        "In the Forward Brief, give extra attention to content quality, "
        "topic consistency, audience industry alignment, and engagement depth. "
        "Recommendations should emphasize content strategy and authority building."
    ),
    "business_development": (
        "In the Forward Brief, give extra attention to reach metrics, audience "
        "seniority, geography alignment, and engagement invitation signals. "
        "Recommendations should emphasize visibility to target buyers and "
        "conversion-oriented profile elements."
    ),
    "recruiting": (
        "In the Forward Brief, give extra attention to audience composition, "
        "follower growth, and profile completeness as a talent brand signal. "
        "Recommendations should emphasize employer brand and candidate-facing elements."
    ),
    "career_transition": (
        "In the Forward Brief, give extra attention to profile-behavior alignment, "
        "identity clarity, and how the current content pattern supports or "
        "contradicts the desired professional direction. Recommendations should "
        "emphasize repositioning signals."
    ),
}


# ============================================================
# System prompt
# ============================================================

SYSTEM_PROMPT_TEMPLATE = """You are the narrative generation engine for Orpheus Social, a LinkedIn presence diagnostic platform. You receive fully computed scores and structured data, and your job is to produce clear, grounded narrative text that interprets the scores for the reader.

You are NOT scoring. All scores are final before you see them. Your job is interpretation and communication.

## Core rules

1. Never invent data. Every claim must trace to a specific score, metric, or questionnaire answer in your input.
2. Never recite scores. The reader does not see numeric scores or band labels. Describe what the scores mean in plain language.
3. Be specific. Reference actual profile content, post topics, audience segments, or metric values — not generic observations that could apply to anyone.
4. Observations, not judgments. Describe what the data shows. Do not moralize about what the client "should" be doing.
5. No marketing language. No "unlock your potential," "maximize your impact," or "elevate your brand."
6. When the completeness floor was applied (completeness_floor_applied: true), explicitly acknowledge that missing structural fields limit the overall profile signal, regardless of quality elsewhere.
7. Return ONLY valid JSON matching the required output format. No commentary outside the JSON.

## Score-to-narrative direction

For each sub-dimension, calibrate your language to the score level:

**Score 1 (gap):** Name what is missing or broken. Direct, clear language.
"The headline does not communicate a recognizable professional identity."

**Score 2 (weakness):** Acknowledge what exists but name what's insufficient. Measured but clear.
"While an About section is present, it does not connect past experience to current work."

**Score 3 (partial):** Name what works and what could be sharper. Balanced.
"The experience descriptions communicate a general trajectory but could be more outcome-oriented."

**Score 4 (strength):** Affirm the strength. Note minor refinements only if relevant. Positive.
"The headline clearly signals a specific professional domain. A small refinement might..."

**Score 5 (exceptional):** Brief affirmation. Don't over-explain what's working.
"The profile presents an exceptionally clear and coherent professional identity."

For quantitative sub-dimensions (Dimensions 2 and 3, scale 0–5):

**Score 0:** The behavior is absent or negligible. Name the gap directly.
**Score 1:** Minimal activity present. Note it exists but is far below meaningful levels.
**Score 2:** Some activity present but well below the range where it builds signal.
**Score 3:** Moderate activity — enough to register but not yet building strong signal.
**Score 4:** Strong activity level. Affirm the pattern.
**Score 5:** Exceptional volume. Brief acknowledgment.

## Sub-dimension narratives

In addition to the four dimension narratives and the Forward Brief, you produce per-sub-dimension narrative payloads for **every** sub-dimension in every dimension. There are 13 total: five in Profile Signal Clarity, four in Behavioral Signal Strength, two in Behavioral Signal Quality, two in Profile-Behavior Alignment.

Each sub-dimension narrative has up to three slots. The slot structure is **conditional on score** — slots are present or absent based on the score itself, not calibrated by tone. Do not include placeholder content for an omitted slot.

**Summary** (always present, every sub-dimension, every score):
25–45 words. A data-grounded observation specific to this person on this sub-dimension. For rubric sub-dimensions (Dim 1, Dim 4), reference the specific profile content or content pattern that drove the score. For quantitative sub-dimensions (Dim 2, Dim 3), the raw metric value is surfaced in the input — name it explicitly in the Summary (e.g., "Active in 11 of the last 52 weeks", or "No original posts recorded during the evaluation period").

**Best Practices** (only at scores 0, 1, 2, or 3):
18–35 words. A generic standard for this sub-dimension. What good looks like, evergreen, not personalized. The same Best Practices content for the same sub-dimension across reports is acceptable — this is reference content the client can return to. **Omit entirely at scores 4 and 5.** Do not include a "no changes needed" placeholder.

**Improvements** (only at scores 0, 1, 2, 3, or 4):
3–5 specific bullets at scores 0 or 1; 2–4 at scores 2–3; 1–2 at score 4. Each bullet 15–25 words, written as a concrete action the client could take. Score-aware count — do not pad to hit a minimum, and do not omit useful actions to hit a maximum. **Omit entirely at score 5.** Do not include a "minor polish" stretch bullet.

A score of 0 indicates absent or negligible measurable activity for this sub-dimension. Treat score 0 the same as score 1 for slot structure (full payload of Summary + Best Practices + Improvements). Calibrate the Summary's language to name the absence honestly — "no original posts recorded during the window," not "low posting cadence" — and frame Improvements as starting moves rather than refinements.

Voice / directness / mechanics rules above apply uniformly to dimension narratives and sub-dimension slots. Do not switch register between layers.

The internal sub-dimension names (Headline Clarity, History Depth, Outbound Engagement Presence, etc.) are the canonical identifiers. Some are renamed at display time on the client surface — write against the internal names; the rename does not affect content.

## Cheat Sheet

In addition to the dimension narratives, Forward Brief, and sub-dimension slots above, you produce a structured **cheat sheet** — a printable one-page reference card derived from the Forward Brief. Client receives both: the Forward Brief is long-form prose; the Cheat Sheet is the same conclusions restructured for at-a-glance review. They are complementary, not redundant.

The cheat sheet has three sections:

**Priorities** — exactly 5 entries, ordered by leverage (highest-impact first). Each is a short imperative title (3–6 words, e.g., "Close the Consistency Gap") plus a 1-to-2-sentence action describing the specific move the client should make. If the action carries a measurable target, append a final sentence wrapping the target in `**bold**` markers (e.g., `**Target: 2 new recommendations in 30 days.**`). Plain text — no other markdown formatting in the action string.

The 5 priorities should align with the Forward Brief's Priorities + Quick Wins subsections — they are the same observations rephrased for the cheat sheet's compressed form, not an independent synthesis. If the Forward Brief surfaces fewer than 5 distinct moves, derive the remaining priorities from the highest-leverage dimension narratives.

**Rhythm** — exactly 3 cadence sections in order: "Every Day", "Every Week", "Every Month". Each carries 2–4 checklist items as short imperative sentences (under 12 words each). Items are concrete behaviors the client could do at that cadence, derived from the Quick Wins and ongoing-practice implications of the Forward Brief.

**Milestones** — 3–4 entries representing 90-day quantitative targets. Each is a `value` (short, e.g., "12", "36+", "2") + `label` (e.g., "Weeks without a gap", "Posts published", "New recommendations"). Pick milestones that map to the highest-leverage priorities and the metrics surfaced in Reach / Resonance / Authority where possible.

Voice / directness / mechanics rules apply uniformly to the cheat sheet — match the register of the dimension narratives. The cheat sheet is the only structured output beyond JSON keys, but its strings still read as natural prose.

## Using the intake questionnaire

The questionnaire is a 9-question intake the client completes before the diagnostic. Use it to shape voice, framing, and emphasis — not to drive scoring (scores are final before you see them).

- **Q1 (current situation)** and **Q2 (actively pursuing)** anchor how you frame relevance. A client between roles pursuing board positions reads differently than an active founder pursuing investor relationships.
- **Q3 (what's driving interest in this engagement now)** anchors the opening of the Forward Brief. Use the client's stated motivation as the entry point.
- **Q4 (current LinkedIn approach)** and **Q5 (comfort with current presence)** anchor the dimension narratives. A "passive" or "uncertain" client should hear recommendations framed as low-friction starting points; an "active and engaged" client should hear refinement-level observations.
- **Q6 (familiarity with how LinkedIn works)** and **Q7 (understanding of online-presence impact)** calibrate how much explaining you do. Low familiarity → spell out what the observations mean in plain terms. High familiarity → reference patterns without belaboring them. Combine with the configured system_mechanics setting; never override that setting, just calibrate within it.
- **Q8 (12-month success picture)** anchors the Forward Brief's Priorities and Quick Wins. Recommendations should plausibly move the client toward what they described. If they chose "All of the above," treat all four targets as in scope.
- **Q9** is a wildcard. If the client provided substantive context, acknowledge it explicitly somewhere appropriate. If they wrote "Nothing to add" or similar, ignore it.

Treat the questionnaire as a brief from the client, not as constraints. If the data contradicts what the client said about themselves, name the gap honestly without moralizing.

{voice_instructions}

{directness_instructions}

{mechanics_instructions}

{focus_instructions}

{custom_instructions}

## Output format

Return a JSON object with exactly this structure:
{{
  "sections": [
    {{
      "section": "Profile Signal Clarity",
      "narrative": "..."
    }},
    {{
      "section": "Behavioral Signal Strength",
      "narrative": "..."
    }},
    {{
      "section": "Behavioral Signal Quality",
      "narrative": "..."
    }},
    {{
      "section": "Profile-Behavior Alignment",
      "narrative": "..."
    }},
    {{
      "section": "forward_brief",
      "narrative": "..."
    }}
  ],
  "sub_dimensions": [
    {{
      "dimension": "Profile Signal Clarity",
      "sub_dimension": "Headline Clarity",
      "summary": "...",
      "best_practices": "...",
      "improvements": ["...", "..."]
    }},
    ...
  ],
  "cheat_sheet": {{
    "priorities": [
      {{"title": "Close the Consistency Gap", "action": "..."}},
      {{"title": "...", "action": "..."}},
      {{"title": "...", "action": "..."}},
      {{"title": "...", "action": "..."}},
      {{"title": "...", "action": "..."}}
    ],
    "rhythm": [
      {{"cadence": "Every Day",   "items": ["...", "..."]}},
      {{"cadence": "Every Week",  "items": ["...", "..."]}},
      {{"cadence": "Every Month", "items": ["...", "..."]}}
    ],
    "milestones": [
      {{"value": "...", "label": "..."}},
      {{"value": "...", "label": "..."}},
      {{"value": "...", "label": "..."}}
    ]
  }}
}}

Each dimension narrative should be 150–300 words. The forward_brief should be 400–600 words and may use Markdown headers (## Reach, ## Resonance, ## Authority, ## Priorities, ## Quick Wins) to separate subsections.

The sub_dimensions array must contain exactly 13 entries — one per sub-dimension across all four dimensions. The (dimension, sub_dimension) pair on each entry must exactly match the input sub-dimension names (case- and punctuation-exact). `summary` is required on every entry. `best_practices` is required on entries whose score is 0, 1, 2, or 3 — omit the key entirely on entries whose score is 4 or 5 (do not include it with empty string or null). `improvements` is required on entries whose score is 0, 1, 2, 3, or 4 — omit the key entirely on entries whose score is 5.

The cheat_sheet object is required. priorities must contain exactly 5 entries. rhythm must contain exactly 3 entries with `cadence` values "Every Day", "Every Week", "Every Month" in that order. milestones must contain 3 or 4 entries. All string fields are non-empty."""


# ============================================================
# User prompt construction
# ============================================================

def _format_scored_dimensions(scoring_output: ScoringStageOutput) -> str:
    """Format scored dimensions as readable text for the prompt."""
    sd = scoring_output.scored_dimensions
    parts = [
        f"COMPOSITE SCORE: {sd.composite:.1f} / 100",
        f"SIGNAL BAND: {sd.band.value}",
        "",
    ]

    for dim in sd.dimensions:
        parts.append(f"### {dim.name}")
        parts.append(f"Weight: {dim.weight:.0%} | Contribution: {dim.contribution:.1f} pts | Normalized: {dim.normalized_score:.3f}")
        if dim.completeness_floor_applied:
            parts.append("⚠ COMPLETENESS FLOOR APPLIED — contribution capped at 50% due to missing structural fields")
        parts.append("")

        for sub in dim.sub_dimensions:
            method_label = sub.method.value
            parts.append(
                f"  {sub.name}: {sub.score:.0f} / {sub.scale} [{method_label}]"
            )
            # Surface raw_value on its own line — when present, this is the
            # quantitative grounding the sub-dim Summary should reference
            # directly. Inline parens (the pre-ORPHEUS-21 format) were easy
            # for Claude to skip past; a labeled line keeps it visible.
            if sub.raw_value is not None:
                # Pretty-format integers without trailing .0; keep floats with
                # one decimal so a 1.5 posts/wk reads as "1.5" not "1.50".
                if sub.raw_value == int(sub.raw_value):
                    parts.append(f"      raw value: {int(sub.raw_value)}")
                else:
                    parts.append(f"      raw value: {sub.raw_value:.1f}")

        parts.append("")

    return "\n".join(parts)


def _format_forward_brief_data(scoring_output: ScoringStageOutput) -> str:
    """Format Forward Brief data as readable text for the prompt."""
    fb = scoring_output.forward_brief_data
    q = fb.quantitative
    flags = fb.qualitative_flags
    parts = []

    # Quantitative — XLSX
    parts.append("=== REACH & AUDIENCE (from Analytics) ===")
    if q.follower_count is not None:
        parts.append(f"Followers: {q.follower_count:,}")
    if q.follower_growth_rate is not None:
        parts.append(f"New followers/week: {q.follower_growth_rate:.1f}")
    if q.unique_members_reached is not None:
        parts.append(f"Unique members reached: {q.unique_members_reached:,}")
    if q.avg_impressions_per_post is not None:
        parts.append(f"Avg impressions/post: {q.avg_impressions_per_post:.0f}")
    if q.avg_engagement_rate is not None:
        parts.append(f"Avg engagement rate: {q.avg_engagement_rate:.1%}")
    if q.top_post_impressions is not None:
        parts.append(f"Top post impressions: {q.top_post_impressions:,}")

    if q.audience_seniority:
        parts.append("")
        parts.append("Audience seniority:")
        for level, pct in sorted(q.audience_seniority.items(), key=lambda x: -x[1]):
            parts.append(f"  {level}: {pct:.0%}")

    if q.audience_industries:
        parts.append("")
        parts.append("Top industries:")
        for seg in q.audience_industries[:5]:
            parts.append(f"  {seg.name}: {seg.pct:.0%}")

    if q.audience_geography:
        parts.append("")
        parts.append("Top geographies:")
        for seg in q.audience_geography[:5]:
            parts.append(f"  {seg.name}: {seg.pct:.0%}")

    if q.top_organizations:
        parts.append("")
        parts.append(f"Top follower organizations: {', '.join(q.top_organizations[:10])}")

    # Quantitative — ZIP
    parts.append("")
    parts.append("=== BEHAVIORAL DEPTH (from Archive) ===")
    if q.avg_comment_length_words is not None:
        parts.append(f"Avg comment length: {q.avg_comment_length_words:.1f} words")
    if q.longest_posting_gap_weeks is not None:
        parts.append(f"Longest posting gap: {q.longest_posting_gap_weeks} weeks")
    if q.zero_post_week_pct is not None:
        parts.append(f"Zero-post weeks: {q.zero_post_week_pct:.0%}")

    # Qualitative flags
    parts.append("")
    parts.append("=== QUALITATIVE FLAGS ===")

    va = flags.viewer_actor_affinity
    parts.append(f"Engagement concentration: {'concentrated' if va.concentrated else 'distributed'}")
    if va.top_targets:
        parts.append(f"  Top engagement targets: {', '.join(va.top_targets[:5])}")

    vp = flags.visual_professionalism
    parts.append(f"Profile photo: {'present' if vp.photo_present else 'absent'}")

    ei = flags.engagement_invitation
    parts.append(f"Services section: {'present' if ei.services_present else 'absent'}")
    parts.append(f"Contact info visible: {'yes' if ei.contact_visible else 'no'}")
    parts.append(f"CTA in About: {'yes' if ei.cta_in_about else 'no'}")

    return "\n".join(parts)


# Canonical "Other" option label — mirrors frontend OTHER_OPTION constant.
# Defined here (not imported) to keep the backend module self-contained.
_OTHER_OPTION = "Other"


# Verbatim question text from Spec_Simplified_Intake_Questionnaire_2026-05-11.md.
# Ordered as the client encounters them in QuestionnairePage.tsx. The "type"
# values match the JSONB shape: multi → string[], single → string,
# freetext → string. q1..q4 have a parallel `<key>_other` field that holds
# the free-text content when the user selected Other.
QUESTIONNAIRE_QUESTIONS: list[dict] = [
    {
        "key": "q1",
        "text": "Which of the following best describes your current situation? (Select all that apply.)",
        "type": "multi",
        "has_other": True,
    },
    {
        "key": "q2",
        "text": "Are you actively pursuing any of the following? (Select all that apply.)",
        "type": "multi",
        "has_other": True,
    },
    {
        "key": "q3",
        "text": "What is driving your interest in this engagement now?",
        "type": "single",
        "has_other": True,
    },
    {
        "key": "q4",
        "text": "How would you describe your current approach to LinkedIn?",
        "type": "single",
        "has_other": True,
    },
    {
        "key": "q5",
        "text": "How comfortable are you with your current LinkedIn presence?",
        "type": "single",
        "has_other": False,
    },
    {
        "key": "q6",
        "text": "How would you rate your familiarity with how LinkedIn actually works as a professional visibility system?",
        "type": "single",
        "has_other": False,
    },
    {
        "key": "q7",
        "text": "How well do you understand the impact your online presence has on how you're discovered and evaluated by the people who matter most to your work?",
        "type": "single",
        "has_other": False,
    },
    {
        "key": "q8",
        "text": "What does a successful online presence look like for you 12 months from now?",
        "type": "single",
        "has_other": False,
    },
    {
        "key": "q9",
        "text": "Is there anything else you'd like us to know before we begin?",
        "type": "freetext",
        "has_other": False,
    },
]


def _render_other(other_text: str) -> str:
    """Render an "Other" selection with its free-text content."""
    cleaned = (other_text or "").strip()
    if cleaned:
        return f'Other (specified: "{cleaned}")'
    return "Other (no detail provided)"


def _format_questionnaire(questionnaire: dict | None) -> str:
    """Format the 9-question intake (ORPHEUS-33 shape) for the prompt.

    The intake stores answers in a flat JSONB map keyed by q1..q9. q1 and
    q2 are multi-select arrays of canonical option labels. q3..q8 are
    single-select strings. q9 is free text. q1..q4 have a parallel
    `<key>_other` field that holds the free-text content when the user
    picked the literal canonical option "Other". See
    Spec_Simplified_Intake_Questionnaire_2026-05-11.md for the verbatim
    questions and locked decisions.

    Rendering prints each question's full text plus the user's answer in
    a human-readable form so Claude has full context, not opaque keys.
    Missing or empty answers render as "[no answer]" — Claude is
    instructed elsewhere to acknowledge gaps honestly rather than
    fabricate.
    """
    if not questionnaire:
        return "[No questionnaire responses provided]"

    parts = ["=== CLIENT QUESTIONNAIRE ANSWERS ===", ""]

    for q in QUESTIONNAIRE_QUESTIONS:
        key = q["key"]
        qtype = q["type"]
        raw = questionnaire.get(key)
        other_text = questionnaire.get(f"{key}_other", "") if q["has_other"] else ""

        rendered = "[no answer]"

        if qtype == "multi":
            values = raw if isinstance(raw, list) else []
            if values:
                expanded = []
                for v in values:
                    if v == _OTHER_OPTION:
                        expanded.append(_render_other(other_text))
                    else:
                        expanded.append(str(v))
                rendered = "; ".join(expanded)
        elif qtype == "single":
            if isinstance(raw, str) and raw.strip():
                if raw == _OTHER_OPTION:
                    rendered = _render_other(other_text)
                else:
                    rendered = raw
        elif qtype == "freetext":
            if isinstance(raw, str) and raw.strip():
                rendered = raw.strip()

        parts.append(f"{key.upper()}. {q['text']}")
        parts.append(f"   → {rendered}")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def _format_quality_report(quality_report: DataQualityReport | None) -> str:
    """Format data quality issues for the prompt.

    Only includes warnings and critical issues — info-level issues are
    noise that Claude doesn't need to act on in narratives.

    Returns empty string if no actionable issues exist, so the section
    can be omitted from the prompt entirely.
    """
    if not quality_report:
        return ""

    # Filter to warning + critical only
    actionable = [
        i for i in quality_report.issues
        if i.severity in (IssueSeverity.WARNING, IssueSeverity.CRITICAL)
    ]

    if not actionable:
        return ""

    parts = ["=== DATA QUALITY NOTES ===", ""]
    parts.append(
        "The following data quality issues were detected during ingestion. "
        "Acknowledge relevant limitations in your narratives where they affect "
        "the reliability or completeness of observations. Do not fabricate data "
        "to fill gaps — note the limitation and focus on what IS available."
    )
    parts.append("")

    for issue in actionable:
        severity_label = issue.severity.value.upper()
        parts.append(f"[{severity_label}] {issue.message}")
        parts.append(f"  Source: {issue.source}")
        parts.append(f"  Impact: {issue.impact}")
        if issue.rows_affected is not None:
            parts.append(f"  Rows affected: {issue.rows_affected}")
        parts.append("")

    return "\n".join(parts)


USER_PROMPT_TEMPLATE = """Generate narrative text for the following Signal Score report. Use the scored dimensions, Forward Brief data, and questionnaire answers to produce grounded, specific narratives.

## Scored Dimensions

{scored_dimensions}

## Forward Brief Data

{forward_brief_data}

## Client Context (Questionnaire)

{questionnaire}
{quality_section}
---

Generate all 5 sections (4 dimension narratives + forward_brief) as a single JSON object. Remember:
- Dimension narratives: 150–300 words each. Interpret the scores — don't recite them.
- Forward Brief: 400–600 words. Use ## headers for Reach, Resonance, Authority, Priorities, and Quick Wins subsections.
- Every observation must trace to specific data in the input above.
- Calibrate language intensity to the score level (see system prompt mappings).
- If data quality issues are noted above, acknowledge limitations honestly without overstating them."""


# ============================================================
# Prompt assembly with advisor config
# ============================================================

def _build_system_prompt(narrative_config: dict | None = None) -> str:
    """Assemble the system prompt with advisor-level configuration.

    Platform defaults apply for any missing config values.
    """
    cfg = {**DEFAULT_NARRATIVE_CONFIG, **(narrative_config or {})}

    voice = VOICE_INSTRUCTIONS.get(
        cfg["voice"],
        VOICE_INSTRUCTIONS["third_person_neutral"]
    )
    directness = DIRECTNESS_INSTRUCTIONS.get(
        cfg["recommendation_style"],
        DIRECTNESS_INSTRUCTIONS["coaching"]
    )
    mechanics = MECHANICS_INSTRUCTIONS.get(
        cfg["system_mechanics"],
        MECHANICS_INSTRUCTIONS["behind_curtain"]
    )

    focus = ""
    if cfg.get("practice_focus") and cfg["practice_focus"] in FOCUS_INSTRUCTIONS:
        focus = FOCUS_INSTRUCTIONS[cfg["practice_focus"]]

    custom = ""
    if cfg.get("custom_instructions"):
        custom = f"## Additional advisor instructions\n\n{cfg['custom_instructions']}"

    return SYSTEM_PROMPT_TEMPLATE.format(
        voice_instructions=f"## Voice\n\n{voice}",
        directness_instructions=f"## Recommendation style\n\n{directness}",
        mechanics_instructions=f"## System mechanics\n\n{mechanics}",
        focus_instructions=f"## Practice focus\n\n{focus}" if focus else "",
        custom_instructions=custom,
    )


# ============================================================
# Response parsing
# ============================================================

EXPECTED_SECTIONS = {
    "Profile Signal Clarity",
    "Behavioral Signal Strength",
    "Behavioral Signal Quality",
    "Profile-Behavior Alignment",
    "forward_brief",
}


def _parse_narrative_response(
    raw_text: str,
    scoring_output: ScoringStageOutput | None = None,
) -> NarrativeResult:
    """Parse Claude's JSON response into a NarrativeResult.

    Validates two payloads:
      * 5 top-level sections matching EXPECTED_SECTIONS (4 dim narratives
        + forward_brief). Empty narratives raise.
      * 13 sub-dimension entries (when scoring_output is provided), each
        keyed by (dimension, sub_dimension). Conditional slot validation
        is cross-referenced against the score:
          - summary required on every entry
          - best_practices required iff score in {1, 2, 3}
          - improvements required iff score in {1, 2, 3, 4}
        Stray entries that don't match a real sub-dim raise; missing
        required slots raise; unexpected slots on a score-5 entry are
        tolerated but logged-and-dropped (Claude occasionally over-emits).

    When scoring_output is None, sub-dimension validation is best-effort:
    we still parse the array but skip the score-keyed conditional checks
    and the 13-entry-exact requirement. That mode exists so the existing
    response-parsing test suite can hold pre-ORPHEUS-21 fixtures green.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    data = json.loads(text)

    if "sections" not in data:
        raise ValueError("Response missing 'sections' key")

    sections: dict[str, str] = {}
    for entry in data["sections"]:
        section = entry.get("section", "")
        narrative = entry.get("narrative", "")

        if section not in EXPECTED_SECTIONS:
            raise ValueError(f"Unexpected section: '{section}'")
        if not narrative or not narrative.strip():
            raise ValueError(f"Empty narrative for section: '{section}'")

        sections[section] = narrative.strip()

    missing = EXPECTED_SECTIONS - set(sections.keys())
    if missing:
        raise ValueError(f"Missing sections: {missing}")

    sub_dimensions = _parse_sub_dimension_payload(
        data.get("sub_dimensions") or [], scoring_output
    )

    cheat_sheet = _parse_cheat_sheet_payload(data.get("cheat_sheet"))

    return NarrativeResult(
        sections=sections,
        sub_dimensions=sub_dimensions,
        cheat_sheet=cheat_sheet,
    )


def _parse_sub_dimension_payload(
    entries: list[dict],
    scoring_output: ScoringStageOutput | None,
) -> dict[tuple[str, str], dict]:
    """Validate and structure the sub_dimensions array from Claude's response.

    Returns a dict keyed by (dim_name, sub_dim_name) → slot dict with
    keys 'summary' (always), 'best_practices' (optional), 'improvements'
    (optional). Conditional-slot rules are enforced against the score
    when scoring_output is provided; otherwise this is a best-effort
    parse for legacy callers that don't pass scoring context.
    """
    # Build the score lookup so we can validate the conditional curve.
    score_lookup: dict[tuple[str, str], int] = {}
    expected_pairs: set[tuple[str, str]] = set()
    if scoring_output is not None:
        for dim in scoring_output.scored_dimensions.dimensions:
            for sub in dim.sub_dimensions:
                key = (dim.name, sub.name)
                expected_pairs.add(key)
                score_lookup[key] = int(round(sub.score))

    result: dict[tuple[str, str], dict] = {}
    seen: set[tuple[str, str]] = set()

    for entry in entries:
        dim_name = entry.get("dimension", "")
        sub_name = entry.get("sub_dimension", "")
        key = (dim_name, sub_name)

        if scoring_output is not None and key not in expected_pairs:
            raise ValueError(
                f"Unexpected sub-dimension entry: dimension={dim_name!r}, "
                f"sub_dimension={sub_name!r}"
            )

        if key in seen:
            raise ValueError(
                f"Duplicate sub-dimension entry: dimension={dim_name!r}, "
                f"sub_dimension={sub_name!r}"
            )
        seen.add(key)

        summary = entry.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError(
                f"Sub-dimension {dim_name}/{sub_name}: 'summary' is required "
                "on every entry."
            )

        slot: dict = {"summary": summary.strip()}

        has_bp = "best_practices" in entry and entry["best_practices"] is not None
        has_imp = "improvements" in entry and entry["improvements"] is not None

        if has_bp:
            bp = entry["best_practices"]
            if not isinstance(bp, str) or not bp.strip():
                raise ValueError(
                    f"Sub-dimension {dim_name}/{sub_name}: "
                    "'best_practices' present but empty."
                )
            slot["best_practices"] = bp.strip()

        if has_imp:
            imp = entry["improvements"]
            if not isinstance(imp, list) or not imp:
                raise ValueError(
                    f"Sub-dimension {dim_name}/{sub_name}: "
                    "'improvements' present but empty or not a list."
                )
            cleaned: list[str] = []
            for bullet in imp:
                if not isinstance(bullet, str) or not bullet.strip():
                    raise ValueError(
                        f"Sub-dimension {dim_name}/{sub_name}: "
                        "improvements list contains an empty entry."
                    )
                cleaned.append(bullet.strip())
            slot["improvements"] = cleaned

        # Conditional-slot enforcement: cross-reference against the score.
        # Score 0 (ORPHEUS-63): treated identically to score 1 — full slot
        # payload (Summary + Best Practices + Improvements). The prompt is
        # responsible for calibrating Summary language to acknowledge the
        # absence of measurable activity vs. score 1's "below the standard"
        # framing; the parser only enforces slot presence.
        if key in score_lookup:
            score = score_lookup[key]
            if score in (0, 1, 2, 3) and "best_practices" not in slot:
                raise ValueError(
                    f"Sub-dimension {dim_name}/{sub_name} score {score}: "
                    "'best_practices' is required at scores 0–3."
                )
            if score in (0, 1, 2, 3, 4) and "improvements" not in slot:
                raise ValueError(
                    f"Sub-dimension {dim_name}/{sub_name} score {score}: "
                    "'improvements' is required at scores 0–4."
                )
            # Tolerate (and drop) over-emitted slots at score 5. Claude
            # sometimes can't resist adding a "minor polish" bullet
            # even when instructed to omit; better to silently drop it
            # than to fail the whole response.
            if score == 5:
                slot.pop("best_practices", None)
                slot.pop("improvements", None)
            # Drop best_practices on score-4 entries the same way.
            if score == 4:
                slot.pop("best_practices", None)

        result[key] = slot

    # When we have scoring context, require complete coverage — every
    # expected (dim, sub_dim) pair must have an entry. Pre-ORPHEUS-21
    # callers (scoring_output=None) skip this so the response-parsing
    # tests can hold green on the 5-section-only shape.
    if scoring_output is not None:
        missing_pairs = expected_pairs - seen
        if missing_pairs:
            preview = ", ".join(f"{d}/{s}" for d, s in sorted(missing_pairs)[:5])
            raise ValueError(
                f"Missing {len(missing_pairs)} sub-dimension entries "
                f"(e.g., {preview})"
            )

    return result


# Expected rhythm cadence labels in canonical order. Claude is instructed
# to emit exactly these three; the parser enforces both presence and order
# so the frontend layout (which renders left-to-right top-to-bottom) stays
# stable across reports.
_EXPECTED_CHEAT_SHEET_CADENCES = ("Every Day", "Every Week", "Every Month")


def _parse_cheat_sheet_payload(raw: object) -> dict | None:
    """Validate Claude's `cheat_sheet` object into a wire-shaped dict.

    Best-effort posture for missing input — `None` propagates through so
    legacy / partial fixtures don't break the parser. When the field IS
    present, we validate the shape strictly: 5 priorities, 3 rhythm
    sections in the canonical cadence order, 3–4 milestones, all string
    fields non-empty.

    Returns the structured dict on success or `None` if `raw` is missing
    or `None`. Malformed payloads raise ValueError so the agent retries.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("cheat_sheet must be an object.")

    # --- Priorities ---------------------------------------------------
    priorities_raw = raw.get("priorities")
    if not isinstance(priorities_raw, list) or len(priorities_raw) != 5:
        raise ValueError(
            f"cheat_sheet.priorities must be a list of exactly 5 entries "
            f"(got {type(priorities_raw).__name__} of length "
            f"{len(priorities_raw) if isinstance(priorities_raw, list) else 'n/a'})."
        )
    priorities: list[dict] = []
    for idx, entry in enumerate(priorities_raw):
        if not isinstance(entry, dict):
            raise ValueError(
                f"cheat_sheet.priorities[{idx}] must be an object."
            )
        title = entry.get("title")
        action = entry.get("action")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(
                f"cheat_sheet.priorities[{idx}].title is required."
            )
        if not isinstance(action, str) or not action.strip():
            raise ValueError(
                f"cheat_sheet.priorities[{idx}].action is required."
            )
        priorities.append({"title": title.strip(), "action": action.strip()})

    # --- Rhythm -------------------------------------------------------
    rhythm_raw = raw.get("rhythm")
    if (
        not isinstance(rhythm_raw, list)
        or len(rhythm_raw) != len(_EXPECTED_CHEAT_SHEET_CADENCES)
    ):
        raise ValueError(
            f"cheat_sheet.rhythm must be a list of "
            f"{len(_EXPECTED_CHEAT_SHEET_CADENCES)} entries."
        )
    rhythm: list[dict] = []
    for idx, (entry, expected_cadence) in enumerate(
        zip(rhythm_raw, _EXPECTED_CHEAT_SHEET_CADENCES)
    ):
        if not isinstance(entry, dict):
            raise ValueError(
                f"cheat_sheet.rhythm[{idx}] must be an object."
            )
        cadence = entry.get("cadence")
        if cadence != expected_cadence:
            raise ValueError(
                f"cheat_sheet.rhythm[{idx}].cadence must be "
                f"{expected_cadence!r} (got {cadence!r})."
            )
        items_raw = entry.get("items")
        if not isinstance(items_raw, list) or not items_raw:
            raise ValueError(
                f"cheat_sheet.rhythm[{idx}].items must be a non-empty list."
            )
        items: list[str] = []
        for j, item in enumerate(items_raw):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"cheat_sheet.rhythm[{idx}].items[{j}] must be a "
                    "non-empty string."
                )
            items.append(item.strip())
        rhythm.append({"cadence": cadence, "items": items})

    # --- Milestones ---------------------------------------------------
    milestones_raw = raw.get("milestones")
    if (
        not isinstance(milestones_raw, list)
        or not (3 <= len(milestones_raw) <= 4)
    ):
        raise ValueError(
            "cheat_sheet.milestones must be a list of 3 or 4 entries."
        )
    milestones: list[dict] = []
    for idx, entry in enumerate(milestones_raw):
        if not isinstance(entry, dict):
            raise ValueError(
                f"cheat_sheet.milestones[{idx}] must be an object."
            )
        value = entry.get("value")
        label = entry.get("label")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"cheat_sheet.milestones[{idx}].value is required."
            )
        if not isinstance(label, str) or not label.strip():
            raise ValueError(
                f"cheat_sheet.milestones[{idx}].label is required."
            )
        milestones.append({"value": value.strip(), "label": label.strip()})

    return {
        "priorities": priorities,
        "rhythm": rhythm,
        "milestones": milestones,
    }


# ============================================================
# API call
# ============================================================

async def generate_narratives(
    client: Anthropic,
    scoring_output: ScoringStageOutput,
    questionnaire: dict,
    narrative_config: dict | None = None,
    quality_report: DataQualityReport | None = None,
    model: str = "claude-sonnet-4-20250514",
    max_retries: int = 2,
) -> NarrativeResult:
    """Generate all narrative sections for a Signal Score report.

    Single Claude call emits both top-level sections (4 dimension narratives
    + forward_brief) and per-sub-dim narrative payloads (13 entries, one per
    sub-dimension across the four dimensions). ORPHEUS-21 introduced the
    sub-dim layer; the existing five-section return is unchanged in content.

    Args:
        client: Anthropic API client.
        scoring_output: Complete output from the scoring engine
            (scored_dimensions + forward_brief_data). Required so the parser
            can cross-reference Claude's sub-dim entries against the actual
            score-list and enforce the conditional slot curve.
        questionnaire: Client's questionnaire responses as a dict.
        narrative_config: Optional advisor-level configuration overrides.
            Keys: voice, recommendation_style, system_mechanics,
            practice_focus, custom_instructions.
        quality_report: Optional data quality report from ingestion.
            When present, warnings and critical issues are included in
            the prompt so Claude can acknowledge data limitations.
        model: Claude model to use.
        max_retries: Number of retries on parse failure.

    Returns:
        NarrativeResult — `sections` (5 entries, same keys as pre-ORPHEUS-21)
        and `sub_dimensions` (13 entries, keyed by (dim_name, sub_dim_name)
        with conditional slot contents).
    """
    system_prompt = _build_system_prompt(narrative_config)

    quality_section = _format_quality_report(quality_report)
    if quality_section:
        quality_section = f"\n## Data Quality Notes\n\n{quality_section}\n"

    user_message = USER_PROMPT_TEMPLATE.format(
        scored_dimensions=_format_scored_dimensions(scoring_output),
        forward_brief_data=_format_forward_brief_data(scoring_output),
        questionnaire=_format_questionnaire(questionnaire),
        quality_section=quality_section,
    )

    last_error = None
    for attempt in range(1 + max_retries):
        response = client.messages.create(
            model=model,
            # Bumped from 4096 to 8192 in ORPHEUS-21. 4 dim narratives
            # (~225w each) + forward_brief (~500w) + 13 sub-dim payloads
            # (avg ~120w each) lands around 3000 words / ~4000 tokens —
            # right at the old ceiling, with no margin for JSON overhead
            # or retries. 8192 gives comfortable headroom.
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text

        try:
            return _parse_narrative_response(raw_text, scoring_output)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            last_error = e
            if attempt < max_retries:
                continue

    raise ValueError(
        f"Failed to parse narrative response after {1 + max_retries} attempts. "
        f"Last error: {last_error}"
    )
