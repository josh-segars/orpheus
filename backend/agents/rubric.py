"""Rubric scoring agent — applies Dimension 1 and Dimension 4 rubrics via Claude.

This is one of two Claude API calls in the pipeline (the other is narrative
generation). Claude receives structured profile and content data and returns
integer scores for each rubric sub-dimension.

Architecture notes (from Andrew's specification):
- Claude must be prompted with the FULL rubric text including scoring notes.
  The rubric criteria are the scoring standard, not optional context.
- Claude applies the rubric as written, not as a general quality judgment.
- Observable-over-inferred: score only what is explicitly present.
- Rare-5 rule: if in doubt between 4 and 5, score 4.
- The scoring engine is identical for all clients — no stream distinction.
"""

import json
from anthropic import Anthropic

from backend.ingestion.types import ZipData


# ============================================================
# Rubric text — verbatim from Andrew's rubric document
# ============================================================

DIM1_SYSTEM_PROMPT = """You are a scoring engine for the Orpheus Social Signal Score system. You apply rubric criteria precisely as written to LinkedIn profile data. You do not make general quality judgments — you follow the scoring standard exactly.

Rules:
1. Score only what is explicitly present in the profile text. Do not infer intent, potential, or unstated qualities.
2. Rare-5 rule: A score of 5 should be awarded sparingly. It represents genuinely exceptional signal. If in doubt between 4 and 5, score 4.
3. All rubrics use a 1-5 scale. A score of 1 is the lowest observable level, not zero performance.
4. Return ONLY valid JSON. No commentary, no explanation."""

DIM1_RUBRIC_TEXT = """
## Dimension 1 — Profile Signal Clarity

What it measures: How clearly and specifically the profile's language allows LinkedIn's retrieval system to build an accurate member embedding. The retrieval system reads headline, About, job and education history, skills, industry, location, certifications, and languages as a unified LLM text prompt. Semantic quality matters.

---

### 1A — Headline Clarity

Scoring note: Does the headline clearly communicate professional identity and current expertise? Is it specific enough to anchor the member in a recognizable professional lane without being generic or overly title-driven? Score what is explicitly stated. Do not award credit for what the headline could say or what the member probably does. A charming or memorable hook scores lower than a specific, current professional signal.

| Score | Level | Criteria |
|---|---|---|
| 5 | Exceptional clarity | Specific, current, communicates real expertise and professional value with no ambiguity. A reader — human or AI — immediately understands who this person is and what they do. No competing identity signals. Outcome-oriented or domain-specific language present. |
| 4 | Strong clarity | Clear professional identity with only minor ambiguity. Specific enough to anchor the member in a recognizable lane. May lack outcome-oriented language but the professional domain is immediately readable. |
| 3 | Moderate clarity | Reasonably clear but could be more specific, current, or differentiated. Professional identity is identifiable but requires some inference. May include one competing or diluting element. |
| 2 | Weak clarity | Somewhat vague, generic (Consultant / Advisor / Leader), or relies on jargon without context. Multiple competing identity signals that dilute the professional lane. A reader could not characterize the member's specific expertise from the headline alone. |
| 1 | Minimal clarity | Unclear, significantly outdated, or purely title and employer with no signal of expertise or direction. Professional identity is not readable. A reader gains no useful information about who this person is professionally. |

---

### 1B — About Section Coherence

Scoring note: Does the About section tell a clear, coherent professional story? Does it lead with current focus and expertise, or does it bury the present in historical narrative? Assess whether a reader encountering this section for the first time would understand what the member does now and why they are credible doing it. The About section should make the present legible, using the past as evidence. A section that only describes the past without connecting it to current work scores lower regardless of how impressive the history is.

| Score | Level | Criteria |
|---|---|---|
| 5 | Exceptional coherence | Clear narrative arc. Leads with current expertise and professional direction. Connects past experience to present contribution in a way that is immediately readable and specific. A reader understands who this person is, what they do now, and why their background makes them credible. Voice is consistent. No structural or narrative gaps. |
| 4 | Strong coherence | Clear story with a recognizable arc connecting past to present. Current focus is stated. Minor issues — begins too historically, or current positioning appears late — but the overall narrative does the job. A reader would construct the right professional picture. |
| 3 | Moderate coherence | Professional story is present but partially obscured. Current focus is identifiable but either buried or stated without enough context. Past experience is present but not clearly connected to current work. Reads more like a resume summary than a professional narrative. |
| 2 | Weak coherence | Present but unfocused. Hard to identify what the person does now or why their history is relevant. May lead with firm or institutional description rather than personal value. A reader would struggle to characterize the member's current professional positioning. |
| 1 | Minimal coherence | Missing, minimal, outdated, written in third person, or entirely without a coherent through-line. Provides no useful professional narrative. A reader gains no meaningful picture of who this person is or what they do. |

---

### 1C — Experience Description Quality

Scoring note: Is the current role clearly described with meaningful context? Do past roles support and contextualize current positioning, or do they read as a disconnected job list? Focus primarily on the current role description. Then assess whether past roles tell a coherent trajectory story that builds toward current work. Titles and dates alone are not descriptions. Score what is written, not what could be inferred from an impressive title or employer name.

| Score | Level | Criteria |
|---|---|---|
| 5 | Exceptional quality | Current role clearly described with specific context — what the work actually involves, who it serves, what it produces. Past roles are written as market-facing narratives with outcomes, not as internal job descriptions or duty lists. Experience history tells a coherent story that builds toward current work and professional identity. |
| 4 | Strong quality | Current role well-described with relevant context. Past roles mostly outcome-oriented with at least some narrative framing. Experience history tells a recognizable trajectory story even if some roles are thinner than others. |
| 3 | Moderate quality | Current role clear but description is minimal. Past roles listed with some context but primarily duty-focused rather than outcome-oriented. Experience section tells a partial story — trajectory is visible but not fully articulated. |
| 2 | Weak quality | Current role title present but little or no description. Experience section reads as a chronological list of titles and employers without narrative coherence. A reader can see where the member worked but cannot understand what they did or why it matters. |
| 1 | Minimal quality | Current role unclear, significantly outdated, or missing meaningful context. Experience section is sparse, empty, or so institutional in framing that it provides no useful signal about the member's professional identity or trajectory. |

---

### 1D — Profile Completeness

Scoring note: Are the key structural sections of the profile present and meaningfully filled in? This is a structural check, not a quality assessment. The retrieval system reads specific named fields — if they are absent, the system has less to work with regardless of how strong the populated fields are. Check for the presence and basic substance of each named field. Do not assess quality here — that is covered by the other rubrics. A field counts as present if it contains meaningful content, not if it contains a placeholder or a single word.

| Score | Level | Criteria |
|---|---|---|
| 5 | Fully complete | All major sections present and substantively filled: headline, About, current role with description, at least two past roles with descriptions, education, skills list, industry, location. No obvious structural gaps. |
| 4 | Substantially complete | All critical fields present. Minor gaps — thin skills list, no certifications, one past role without description — that do not significantly impact how the profile is interpreted. |
| 3 | Partially complete | Most sections present but several are thin or missing. Noticeable gaps that limit the retrieval system's ability to build a complete member embedding. Education or skills may be absent. |
| 2 | Incomplete | Significant sections missing or empty. Profile feels structurally sparse. Multiple named retrieval fields absent. The retrieval system has limited material to work with. |
| 1 | Largely incomplete | Profile is a skeleton. Most sections absent or contain only minimal placeholder content. The retrieval system cannot build a meaningful member embedding from what is present. |

---

### 1E — Identity Clarity

Scoring note: What professional identity does the retrieval system construct from reading this profile as a whole? Is the member's professional identity specific, legible, and coherent — or fragmented, diluted, or ambiguous? This rubric assesses the integrated picture that emerges from reading all profile fields together — not any single field in isolation. A profile can have a strong headline and a strong About section but still score low here if the combined signal fragments across too many unrelated professional identities. Ask: could a reader construct one clear, specific professional archetype from this profile?

| Score | Level | Criteria |
|---|---|---|
| 5 | Exceptional identity clarity | One clear, specific, immediately recognizable professional identity emerges from the full profile. Every section reinforces the same picture. The retrieval system could build a highly reliable member embedding. No competing or diluting identity signals present. |
| 4 | Strong identity clarity | A clear professional identity is readable from the profile. Minor competing signals or breadth across related domains does not meaningfully dilute the primary picture. A reader would characterize this member's professional identity consistently and specifically. |
| 3 | Moderate identity clarity | A professional identity is identifiable but not sharp. Two or three related professional signals compete for primacy. The identity is coherent in the sense that the signals are related, but the picture requires more inference than a score 4 or 5 profile. The retrieval system could build a reliable embedding but with some uncertainty. |
| 2 | Weak identity clarity | Professional identity is fragmented across multiple unrelated or loosely related signals. A reader would struggle to characterize this member's professional focus specifically. The retrieval system would have difficulty placing this member in a reliable professional category. |
| 1 | No meaningful identity clarity | No coherent professional identity is readable from the profile. Signals contradict, scatter, or cancel each other out. The retrieval system cannot construct a reliable member embedding from the available profile language. |
"""

DIM4_SYSTEM_PROMPT = """You are a scoring engine for the Orpheus Social Signal Score system. You apply rubric criteria precisely as written to LinkedIn profile and content data. You do not make general quality judgments — you follow the scoring standard exactly.

Rules:
1. Score only what is explicitly present in the profile text and content. Do not infer intent, potential, or unstated qualities.
2. Rare-5 rule: A score of 5 should be awarded sparingly. It represents genuinely exceptional signal. If in doubt between 4 and 5, score 4.
3. All rubrics use a 1-5 scale. A score of 1 is the lowest observable level, not zero performance.
4. Return ONLY valid JSON. No commentary, no explanation."""

DIM4_RUBRIC_TEXT = """
## Dimension 4 — Profile-Behavior Alignment

What it measures: Whether the member's content and engagement activity is topically and semantically consistent with their declared professional identity. LinkedIn generates a 50-dimensional semantic embedding of every post within minutes of publication. Topic-coherent content directly reinforces the member embedding the profile anchors.

---

### 4A — Topic Consistency

Scoring note: The question is not whether the member posts about one topic. The question is whether a reader — encountering this member's content for the first time — could construct a coherent picture of who this person is professionally. Topics may be plural. Coherence is the requirement, not uniformity. Assess whether the topics cluster around a recognizable professional identity or scatter without connection.

| Score | Level | Criteria |
|---|---|---|
| 5 | Exceptional coherence | All or nearly all posts and comments cohere into a single, immediately recognizable professional identity. Topics may be plural but are so clearly related — semantically, thematically, or through a recognizable professional archetype — that a reader sampling any five posts at random would construct the same picture of who this person is. Comments engage with content in domains directly related to the member's posting themes. No content present that a reasonable reader would find incongruous with the overall professional identity. The system could build a highly reliable member embedding from this content alone. |
| 4 | Strong coherence | The large majority of posts and comments cohere around a recognizable professional identity. A secondary theme or occasional off-topic content appears but does not dilute the primary signal. A reader would identify the member's professional identity clearly and consistently. The semantic relationship between topics is apparent — a reader or AI could explain why these topics belong together for this person. The system could build a reliable member embedding with minor noise. |
| 3 | Moderate coherence | A professional identity is recognizable but not sharp. Two or three themes are present and partially related, but the connection between them requires inference rather than being immediately apparent. A reader could characterize the member's general professional area but would find the identity less clear than a score 4 or 5 profile. Off-topic or loosely related content appears regularly enough to introduce noise into the identity signal. The system could build a member embedding but with meaningful uncertainty. |
| 2 | Weak coherence | No clear professional identity emerges from the content pattern. Multiple unrelated themes compete for presence without a recognizable connecting thread. A reader would struggle to characterize who this person is professionally from their content alone. Professional and personal or generic content appear with roughly equal frequency. The system would have difficulty building a reliable member embedding — the signal is present but fragmented. |
| 1 | No meaningful coherence | Content is scattered across unrelated topics with no recognizable professional identity emerging. No connecting thread is apparent between posts and comments. A reader could not construct a coherent picture of who this person is professionally from their content. The system would be unable to build a reliable member embedding from content signals alone and would fall back entirely on profile language. |

---

### 4B — Profile-Content Coherence

Scoring note: Topic Consistency (4A) assesses whether content coheres internally. This rubric assesses whether content and profile cohere with each other. A member can score well on 4A — producing semantically coherent content — while scoring poorly here if their profile declares a different professional identity than their content signals. Read the member's headline, About section, and current experience description alongside their posts and comments. The question is: does the same professional picture emerge from both sources? The most common pattern for a score of 3 is a profile that accurately reflected a previous role but has not been updated to reflect current work — particularly common for professionals in career transition.

| Score | Level | Criteria |
|---|---|---|
| 5 | Exceptional alignment | The professional identity declared in the profile and the professional identity expressed through content are indistinguishable. The headline, About section, and experience descriptions anticipate the topics the member posts and comments about. A reader encountering the profile first would find exactly what they expected when they read the content, and vice versa. No meaningful gap between declared identity and expressed identity is present. |
| 4 | Strong alignment | The profile and content express the same professional identity with minor inconsistencies. The headline and About section clearly anticipate the member's content themes. A reader moving from profile to content — or content to profile — would recognize the same person. A secondary content theme or occasional post outside the profile's declared identity appears but does not create meaningful confusion. The profile provides a reliable anchor for the content signal. |
| 3 | Moderate alignment | The profile and content are recognizably related but with a noticeable gap. The member's content touches themes present in the profile but also addresses areas the profile does not anticipate or acknowledge. A reader moving from profile to content would recognize some continuity but would also find surprises. Common cause: a profile that has not been updated to reflect the member's current professional focus. |
| 2 | Weak alignment | The profile and content express noticeably different professional identities. The profile declares one focus but the content consistently addresses different themes. The mismatch is apparent without detailed analysis. The system must choose between two conflicting identity signals. |
| 1 | No meaningful alignment | The profile and content express unrelated professional identities. The profile declares a specific professional focus that is absent from or contradicted by the content. The system cannot build a coherent member embedding because the profile signal and the content signal point in different directions. Active misalignment at this level is more structurally damaging than sparse signal — it creates competing embeddings rather than simply weak ones. |
"""


# ============================================================
# Data formatting — prepare profile/content for the prompt
# ============================================================

def _format_profile_for_dim1(zip_data: ZipData) -> str:
    """Format profile data for Dimension 1 rubric scoring."""
    parts = []

    # Headline
    headline = zip_data.profile.headline.strip()
    parts.append(f"HEADLINE: {headline}" if headline else "HEADLINE: [not provided]")

    # About / Summary
    summary = zip_data.profile.summary.strip()
    parts.append(f"ABOUT SECTION:\n{summary}" if summary else "ABOUT SECTION: [not provided]")

    # Industry
    industry = zip_data.profile.industry.strip()
    parts.append(f"INDUSTRY: {industry}" if industry else "INDUSTRY: [not provided]")

    # Location
    location = zip_data.profile.geo_location.strip()
    if location:
        parts.append(f"LOCATION: {location}")

    # Experience / Positions
    if zip_data.positions:
        parts.append("EXPERIENCE:")
        for i, pos in enumerate(zip_data.positions):
            title = pos.title or "[no title]"
            company = pos.company_name or "[no company]"
            dates = ""
            if pos.started_on:
                dates = f" ({pos.started_on}"
                dates += f" – {pos.finished_on})" if pos.finished_on else " – present)"
            desc = pos.description.strip() if pos.description else "[no description]"
            parts.append(f"  {i+1}. {title} at {company}{dates}")
            parts.append(f"     {desc}")
    else:
        parts.append("EXPERIENCE: [no positions listed]")

    # Skills
    if zip_data.skills:
        parts.append(f"SKILLS: {', '.join(zip_data.skills[:30])}")
        if len(zip_data.skills) > 30:
            parts.append(f"  ({len(zip_data.skills)} total skills)")
    else:
        parts.append("SKILLS: [none listed]")

    return "\n\n".join(parts)


def _format_content_for_dim4(zip_data: ZipData, max_posts: int = 30, max_comments: int = 20) -> str:
    """Format profile + content data for Dimension 4 rubric scoring.

    Includes profile fields (for profile-content coherence assessment)
    plus a sample of recent posts and comments.
    """
    parts = []

    # Profile summary for coherence comparison
    parts.append("=== PROFILE ===")
    parts.append(f"HEADLINE: {zip_data.profile.headline.strip() or '[not provided]'}")
    about = zip_data.profile.summary.strip()
    if about:
        parts.append(f"ABOUT: {about[:1000]}")  # Cap at 1000 chars
    if zip_data.positions:
        current = zip_data.positions[0]
        parts.append(f"CURRENT ROLE: {current.title} at {current.company_name}")
        if current.description:
            parts.append(f"ROLE DESCRIPTION: {current.description[:500]}")

    # Posts (most recent first, up to max_posts)
    parts.append("\n=== POSTS (most recent first) ===")
    posts = sorted(zip_data.shares, key=lambda s: s.date, reverse=True)[:max_posts]
    if posts:
        for i, post in enumerate(posts):
            text = post.share_commentary.strip()
            if text:
                # Cap each post at 300 chars to keep prompt manageable
                display = text[:300] + "..." if len(text) > 300 else text
                parts.append(f"Post {i+1} ({post.date}): {display}")
    else:
        parts.append("[No posts found]")

    # Comments (most recent first, up to max_comments)
    parts.append("\n=== COMMENTS (most recent first) ===")
    comments = sorted(zip_data.comments, key=lambda c: c.date, reverse=True)[:max_comments]
    if comments:
        for i, comment in enumerate(comments):
            text = comment.message.strip()
            if text:
                display = text[:200] + "..." if len(text) > 200 else text
                parts.append(f"Comment {i+1} ({comment.date}): {display}")
    else:
        parts.append("[No comments found]")

    return "\n".join(parts)


# ============================================================
# Prompt construction
# ============================================================

DIM1_USER_TEMPLATE = """Apply the Dimension 1 — Profile Signal Clarity rubrics to the following LinkedIn profile data. Score each of the five sub-dimensions on a 1-5 scale using the criteria provided.

{rubric_text}

---

## Profile Data

{profile_data}

---

Return your scores as a JSON object with exactly these keys:
{{
  "Headline Clarity": <1-5>,
  "About Section Coherence": <1-5>,
  "Experience Description Quality": <1-5>,
  "Profile Completeness": <1-5>,
  "Identity Clarity": <1-5>
}}"""

DIM4_USER_TEMPLATE = """Apply the Dimension 4 — Profile-Behavior Alignment rubrics to the following LinkedIn profile and content data. Score each of the two sub-dimensions on a 1-5 scale using the criteria provided.

{rubric_text}

---

## Profile and Content Data

{content_data}

---

Return your scores as a JSON object with exactly these keys:
{{
  "Topic Consistency": <1-5>,
  "Profile-Content Coherence": <1-5>
}}"""


# ============================================================
# API calls
# ============================================================

DIM1_EXPECTED_KEYS = {
    "Headline Clarity",
    "About Section Coherence",
    "Experience Description Quality",
    "Profile Completeness",
    "Identity Clarity",
}

DIM4_EXPECTED_KEYS = {
    "Topic Consistency",
    "Profile-Content Coherence",
}


def _parse_scores(raw_text: str, expected_keys: set[str]) -> dict[str, int]:
    """Parse Claude's JSON response into validated integer scores."""
    # Strip markdown code fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    scores = json.loads(text)

    # Validate keys
    missing = expected_keys - set(scores.keys())
    if missing:
        raise ValueError(f"Missing rubric scores: {missing}")

    # Validate values are integers 1-5
    validated = {}
    for key in expected_keys:
        val = scores[key]
        if not isinstance(val, int) or val < 1 or val > 5:
            raise ValueError(f"Score for '{key}' must be integer 1-5, got {val}")
        validated[key] = val

    return validated


async def score_dimension_1(
    client: Anthropic,
    zip_data: ZipData,
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, int]:
    """Apply Dimension 1 rubrics via Claude.

    Returns dict mapping sub-dimension names to integer scores (1-5).
    """
    profile_data = _format_profile_for_dim1(zip_data)
    user_message = DIM1_USER_TEMPLATE.format(
        rubric_text=DIM1_RUBRIC_TEXT,
        profile_data=profile_data,
    )

    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=DIM1_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return _parse_scores(response.content[0].text, DIM1_EXPECTED_KEYS)


async def score_dimension_4(
    client: Anthropic,
    zip_data: ZipData,
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, int]:
    """Apply Dimension 4 rubrics via Claude.

    Returns dict mapping sub-dimension names to integer scores (1-5).
    """
    content_data = _format_content_for_dim4(zip_data)
    user_message = DIM4_USER_TEMPLATE.format(
        rubric_text=DIM4_RUBRIC_TEXT,
        content_data=content_data,
    )

    response = client.messages.create(
        model=model,
        max_tokens=128,
        system=DIM4_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return _parse_scores(response.content[0].text, DIM4_EXPECTED_KEYS)


async def score_rubrics(
    client: Anthropic,
    zip_data: ZipData,
    model: str = "claude-sonnet-4-20250514",
) -> tuple[dict[str, int], dict[str, int]]:
    """Score both Dimension 1 and Dimension 4 rubrics.

    Returns (dim1_scores, dim4_scores) — each a dict mapping
    sub-dimension names to integer scores (1-5).

    These feed directly into the scoring engine:
        engine.build_dimension_1_from_rubrics(dim1_scores, zip_data)
        engine.build_dimension_4_from_rubrics(dim4_scores)
    """
    dim1 = await score_dimension_1(client, zip_data, model)
    dim4 = await score_dimension_4(client, zip_data, model)
    return dim1, dim4
