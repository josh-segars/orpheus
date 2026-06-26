# ORPHEUS-96 — Reproduction: narrative asserts a deficiency it never observed

**Date:** 2026-06-26
**Repro job:** `d91b7c11-2301-42cd-881f-004d6dd9f8fd` (Andrew Segars, 79.13 / Tuned, 2026-06-23 — the same job from the ORPHEUS-95 band-mapping fix)
**Source:** live cloud Supabase (`yqxuddkixzjruxtdjxpr`), no re-run required — the false claim is in the stored report.

## The claim (what the report tells the client)

From the **Profile Signal Clarity** narrative (`narratives` row, stored, client-visible):

> "…no visible contact information and **no call to action in your About section** mean that even engaged visitors don't have an obvious next step."

This is a specific, confident assertion about the *contents* of Andrew's About section.

## The actual About section (what's really there)

From `ingested_data.zip_data.profile.summary` — the real uploaded text, ending with:

> "If any of that resonates, **I'd welcome a conversation.** Or, **if you're ever in Portugal, a meal.**"

That is a clear call to action — an explicit invitation to start a conversation or meet. **The report's claim is factually wrong.**

## Why it's wrong — the narrative agent never saw the About text

The pipeline reduces the upload to numbers in Stage 2/3, and only the numbers reach the narrative agent in Stage 4.

1. **Ingestion heuristic** (`scoring/engine.py → _detect_cta_in_about`) scans the About for a fixed keyword list:

   ```
   "reach out", "contact me", "let's connect", "dm me", "get in touch",
   "email me", "send me", "book a", "schedule a", "connect with me", "@"
   ```

   Andrew's CTA ("I'd welcome a conversation… a meal") is phrased conversationally and matches none of them → the flag is computed as `cta_in_about: false`.

2. **Stored flag** (`scores.forward_brief_data.qualitative_flags.engagement_invitation`):

   ```json
   { "cta_in_about": false, "contact_visible": false, "services_present": false }
   ```

3. **Narrative agent input** — `agents/narrative.py → generate_narratives` receives only `scoring_output` (scores + these numeric/boolean metrics), the questionnaire, and the quality report. It is **never** passed `zip_data` / the About text. `_format_forward_brief_data` renders the flag as `"CTA in About: no"`, and the agent faithfully translates that single boolean into the prose sentence above.

So the model didn't misread the About — it never read it. It restated a boolean, and the boolean was produced by a brittle keyword heuristic that a normal human-written CTA defeats.

## Scope of the pattern in this one report

Every "specific" profile-content claim in the Profile Signal Clarity narrative traces to a flag or a score, not to the text:

- "no call to action in your About section" ← `cta_in_about: false` (**contradicted by the text**)
- "no visible contact information" ← `contact_visible: false` (heuristic = any website URL present; also unreliable)
- "missing Services section" ← `services_present: false` (hardcoded — *never* available in the ZIP, so this is always asserted as missing)
- "Your About section connects your background to your current work… reads coherently" ← paraphrase of the About Section Coherence rubric **score**, not the text (here it happens to be flattering, but it's still ungrounded)

`services_present` is worth flagging separately: `engine.py` sets it to `False` unconditionally ("Not available in ZIP — will be False unless enriched"), so **every** report tells **every** client their Services section is missing, regardless of reality.

## The smoking gun, in one line

The report told Andrew his About has no call to action. His About literally invites the reader to a conversation and a meal. The narrative agent was never given the About — only a `false` boolean from a keyword matcher his phrasing happened to dodge.

## Confirms

ORPHEUS-96 (filed 2026-06-24): *"the narrative agent can assert specific profile deficiencies it never sees… sourced from the questionnaire / a flag, not the profile text."* This is a live, reproduced, factually-wrong instance.
