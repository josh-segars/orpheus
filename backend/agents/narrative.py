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
from anthropic import Anthropic

from backend.models.scoring import ScoringStageOutput
from backend.models.quality import DataQualityReport, IssueSeverity


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
  ]
}}

Each dimension narrative should be 150–300 words. The forward_brief should be 400–600 words and may use Markdown headers (## Reach, ## Resonance, ## Authority, ## Priorities, ## Quick Wins) to separate subsections."""


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
            raw_note = f" (raw value: {sub.raw_value})" if sub.raw_value is not None else ""
            parts.append(f"  {sub.name}: {sub.score:.0f} / {sub.scale} [{method_label}]{raw_note}")

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


def _format_questionnaire(questionnaire: dict) -> str:
    """Format questionnaire answers for the prompt.

    Questionnaire responses are stored as a JSONB dict. Keys vary but
    typically map to question numbers or section names.
    """
    if not questionnaire:
        return "[No questionnaire responses provided]"

    parts = ["=== CLIENT QUESTIONNAIRE ANSWERS ===", ""]

    # Try to present in a readable order
    for key in sorted(questionnaire.keys(), key=str):
        value = questionnaire[key]
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        parts.append(f"{key}: {value}")

    return "\n".join(parts)


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


def _parse_narrative_response(raw_text: str) -> dict[str, str]:
    """Parse Claude's JSON response into a section → narrative mapping.

    Returns dict with exactly 5 keys matching EXPECTED_SECTIONS.
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

    result = {}
    for entry in data["sections"]:
        section = entry.get("section", "")
        narrative = entry.get("narrative", "")

        if section not in EXPECTED_SECTIONS:
            raise ValueError(f"Unexpected section: '{section}'")
        if not narrative or not narrative.strip():
            raise ValueError(f"Empty narrative for section: '{section}'")

        result[section] = narrative.strip()

    missing = EXPECTED_SECTIONS - set(result.keys())
    if missing:
        raise ValueError(f"Missing sections: {missing}")

    return result


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
) -> dict[str, str]:
    """Generate all narrative sections for a Signal Score report.

    Args:
        client: Anthropic API client.
        scoring_output: Complete output from the scoring engine
            (scored_dimensions + forward_brief_data).
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
        Dict mapping section identifiers to narrative text.
        Keys: "Profile Signal Clarity", "Behavioral Signal Strength",
        "Behavioral Signal Quality", "Profile-Behavior Alignment",
        "forward_brief".
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
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text

        try:
            return _parse_narrative_response(raw_text)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            last_error = e
            if attempt < max_retries:
                continue

    raise ValueError(
        f"Failed to parse narrative response after {1 + max_retries} attempts. "
        f"Last error: {last_error}"
    )
