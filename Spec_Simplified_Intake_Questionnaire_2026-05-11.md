# Spec: Simplified Intake Questionnaire (2026-05-11)

**Status:** Approved
**Author:** Josh
**Replaces:** the current 23-question, 7-section questionnaire (shipped under ORPHEUS-18)
**Related work:** narrative-prompt rewrite (`agents/narrative.py`), Groundwork checklist simplification

This document is the source of truth for the simplified intake. The same content lives in Plane under `Spec: Simplified Intake Questionnaire (2026-05-11)`.

## Why

The current 23-question, 7-section questionnaire was designed to capture exhaustive context for narrative generation. In practice it's heavier than needed for a five-minute intake before a Strategic Presence Diagnostic. Andrew's revised intake is leaner (9 questions), more structured (only one free-text question), and frames the engagement explicitly around situation, intent, current LinkedIn behavior, and self-assessment — the dimensions that actually shape the narrative voice.

## Locked decisions

1. **Every question is required.** A user cannot mark the questionnaire complete with any unanswered question.
2. **Q2 has no "leave blank" option.** Instead, a new option *"None of these — I'm not actively pursuing anything right now"* is added so users can affirmatively say nothing applies. The prompt copy *"or leave blank"* is removed.
3. **Q8's "All of the above" is stored literally** as the string `"All of the above"`, not expanded into the four constituent options. Narrative generation reasons about that explicit choice.
4. **Q9's "Nothing to add" pattern.** The user must type something; reasonable answers include "Nothing to add" or "N/A." Empty strings are rejected.
5. **`section_completion` column is dropped.** Questionnaire completion is derived at read time from `answers` (Option B in the data model section below).
6. **`CheckboxQuestion` (no-Other) primitive is removed.** No remaining question uses it; deletion keeps the primitive set lean.
7. **Two tickets, not one or three.** A "questionnaire shape change" ticket (DB migration + frontend port + prototype HTML) ships first as one deliverable. A separate "narrative prompt rewrite" ticket follows.
8. **No Andrew review of the narrative prompt rewrite before merge.** Iterate from the first generated narrative in production instead.

## The 9 questions verbatim

### Intake intro copy

> **Intake Questionnaire**
> Completed prior to your Strategic Presence Diagnostic — approximately 5 minutes
>
> There are no right or wrong answers. The more honestly you respond, the more useful the session will be.

### Q1. Which of the following best describes your current situation? *(Select all that apply.)*

- Employed full-time
- Employed full-time with outside advisory or consulting work
- Independent consultant, advisor, or principal
- Entrepreneur or founder
- Between roles
- Other: ______________

**Type:** multi-select with Other text. **Required:** yes (≥1 selection).

### Q2. Are you actively pursuing any of the following? *(Select all that apply.)*

- New employment
- Board positions
- Advisory or consulting work
- Speaking opportunities
- Thought leadership
- Media or press visibility
- Government or public sector opportunities
- Investor or funding relationships
- **None of these — I'm not actively pursuing anything right now**
- Other: ______________

**Type:** multi-select with Other text. **Required:** yes (≥1 selection). **Copy change:** drop *"or leave blank"* from the prompt.

### Q3. What is driving your interest in this engagement now?

- A specific transition or career moment
- A concrete opportunity I'm pursuing
- General concern that my online presence doesn't reflect my background
- Curiosity — I want to understand how I'm being seen
- Other: ______________

**Type:** radio with Other text. **Required:** yes.

### Q4. How would you describe your current approach to LinkedIn?

- Passive — I have a profile but rarely post, comment, or engage
- Occasional — I engage when something relevant comes up, but not consistently
- Uncertain — I've started participating more but feel unsure about what I'm doing
- Active but adrift — I post regularly but don't feel it's working strategically
- Active and engaged — I post regularly and feel reasonably confident, but want an outside perspective
- Other: ______________

**Type:** radio with Other text. **Required:** yes.

### Q5. How comfortable are you with your current LinkedIn presence?

- Not comfortable — it doesn't reflect who I am or what I do
- Somewhat comfortable — it's adequate but not optimal
- Neutral — I haven't thought about it much
- Fairly comfortable — but I know there's room to improve
- Very comfortable — I just want an outside perspective

**Type:** radio, no Other. **Required:** yes.

### Q6. How would you rate your familiarity with how LinkedIn actually works as a professional visibility system?

- Low — I use it but don't really understand how it works
- Moderate — I have a general sense but significant gaps
- Fairly high — I understand the basics but not the deeper mechanics
- High — I follow platform developments and understand how the system operates

**Type:** radio, no Other. **Required:** yes.

### Q7. How well do you understand the impact your online presence has on how you're discovered and evaluated by the people who matter most to your work?

- I haven't really considered it
- I suspect it matters but don't fully understand how
- I understand it matters and have tried to address it
- I understand it well — that's precisely why I'm here

**Type:** radio, no Other. **Required:** yes.

### Q8. What does a successful online presence look like for you 12 months from now?

- My profile accurately reflects my expertise and current work
- The right people are finding me and understanding what I offer
- I have a sustainable, comfortable approach to participating professionally
- I feel confident my presence is working for me, not against me
- All of the above

**Type:** radio, no Other. **Required:** yes. **Storage:** literal selected string.

### Q9. Is there anything else you'd like us to know before we begin?

**Type:** free text. **Required:** yes (user may type "Nothing to add" or similar). Empty strings rejected client-side; submitted answer must be non-empty after trim.

## Data model

### `questionnaire_responses.answers` (JSONB) — new shape

```json
{
  "q1": ["string", ...],
  "q1_other": "string",
  "q2": ["string", ...],
  "q2_other": "string",
  "q3": "string",
  "q3_other": "string",
  "q4": "string",
  "q4_other": "string",
  "q5": "string",
  "q6": "string",
  "q7": "string",
  "q8": "string",
  "q9": "string"
}
```

- `qN_other` fields exist only when `"Other"` was chosen in the corresponding question. The literal canonical option string `"Other"` (not the user's typed text) appears in the parent array or value.
- `q1` and `q2` are string arrays of canonical option labels. Order matches the option order shown to the user, not selection order. This keeps the data deterministic for narrative prompts.
- `q8`'s "All of the above" is stored exactly as `"All of the above"`.

### `questionnaire_responses.section_completion` — dropped

The column is removed in migration 010. Frontend derives `questionnaireComplete: boolean` at read time by checking that all 9 required keys are populated in `answers`. Single source of truth, no persisted state to keep in sync.

### Migration 010 plan

Pre-launch, no prod data to preserve.

```sql
-- 010_questionnaire_simplified.sql
BEGIN;

-- Wipe existing answers (incompatible shape from ORPHEUS-18's 23-question schema).
TRUNCATE TABLE public.questionnaire_responses;

-- Drop section_completion — completion is now derived from answers content.
ALTER TABLE public.questionnaire_responses
  DROP COLUMN IF EXISTS section_completion;

COMMIT;
```

If we ever do have prod data at migration time, this becomes a real shape-translation migration. The migration file should call that out in its header comment.

## Frontend impact

### New primitive: `CheckboxWithOtherQuestion`

Multi-select with an "Other" option that reveals a text input when selected. Used by Q1 and Q2. API mirrors `RadioWithOtherQuestion`:

```ts
interface CheckboxWithOtherQuestionProps {
  id: string                              // 'q1', 'q2'
  label: string
  helper?: string
  options: readonly string[]              // canonical labels, in display order
  otherLabel: string                      // 'Other' option label
  value: string[]                         // currently-selected canonical labels
  otherValue: string                      // free-text content
  onChange: (value: string[]) => void
  onOtherChange: (otherValue: string) => void
  required: boolean
}
```

The "None of these…" option in Q2 is a regular canonical option; no special-casing.

### Primitives to remove

- `ScaleQuestion` — no scale questions remain.
- `CheckboxQuestion` (no-Other) — neither remaining multi-select uses it.

Retain: `TextQuestion`, `RadioQuestion`, `RadioWithOtherQuestion`. Add: `CheckboxWithOtherQuestion`.

### Pages and routes

- Delete `frontend/src/pages/questionnaire/sections.tsx` and the 7 named exports.
- Replace with a single `frontend/src/pages/QuestionnairePage.tsx`.
- `App.tsx`: collapse `/questionnaire/s1..s7` routes to a single `/questionnaire`.
- `useGroundworkProgress`: replace per-section reads with a single derived `questionnaireComplete` boolean (Option B in data model).
- `useQuestionnaire` hook stays. `useSectionDraft` is renamed to `useQuestionnaireDraft` and tracks one draft instead of seven. Autosave debounce unchanged (700 ms).

### Groundwork checklist

Drops from 9 rows to **3 rows**:

1. Questionnaire
2. LinkedIn data — Step 1 (Archive)
3. LinkedIn data — Step 2 (Analytics)

The "My Groundwork is Complete" CTA gating logic simplifies to *all three rows complete*.

### Prototype HTML

The seven `orpheus-questionnaire-sN.html` files become obsolete. Replace with one new file as the visual source of truth, consistent with how `orpheus-welcome-v6.html` and `orpheus-groundwork-v1.html` were built before the React port:

- `orpheus-questionnaire-v2.html` (or similar versioned name)

Build the new file first; React port follows.

## Backend impact

### Narrative-generation prompt (`agents/narrative.py`)

The current prompt threads specific questions into specific narrative sections — e.g., Q8–10 for audience context, Q11 for goals, Q18–20 for voice. None of those questions exist in the new questionnaire.

What the new 9 questions give us:

- **Q1, Q2** — what kind of career, what opportunities pursued. Anchors how the narrative frames relevance.
- **Q3** — the *why now*. Useful for the opening of the Forward Brief.
- **Q4, Q5** — current behavior + self-assessment of LinkedIn presence. Anchors the dimension-1 (Profile Signal Clarity) and dimension-2/3 (Behavioral Signal) narratives.
- **Q6, Q7** — meta-awareness (does the user understand the system, the stakes). Affects how technical we can be in the narrative and what we need to explain vs. assume.
- **Q8** — the desired 12-month state. Anchors the Forward Brief's action plan.
- **Q9** — wildcard. The prompt should reflect it explicitly when the client provided substantive context.

Per locked decision #8, the rewritten prompt does **not** require Andrew's review before merge. We iterate from the first generated narrative in production.

## Implementation order

1. **Migration 010** — DB shape change. Foundational; nothing else can land first.
2. **Frontend types** (`src/types/questionnaire.ts`) — new contract.
3. **New primitive** (`CheckboxWithOtherQuestion`).
4. **Prototype HTML** (`orpheus-questionnaire-v2.html`) — visual source of truth.
5. **React port** — `QuestionnairePage.tsx`, route consolidation, hook updates.
6. **Groundwork checklist update** — 9 → 3 rows.
7. **Cleanup** — remove `ScaleQuestion` and `CheckboxQuestion` (no-Other).
8. **Narrative prompt rewrite** (`agents/narrative.py`) — under the second ticket.

Steps 1–7 are scope for the first ticket. Step 8 is scope for the second.

## Tickets to file

- **ORPHEUS-? (first ticket):** "Replace 23-question questionnaire with 9-question intake." Scope: migration 010, prototype HTML, frontend port, primitive add/remove, groundwork checklist update.
- **ORPHEUS-? (second ticket):** "Rewrite narrative-generation prompt for simplified questionnaire shape." Scope: `agents/narrative.py` prompt block, accompanying tests if any. Iterate from first generated narrative in production.
