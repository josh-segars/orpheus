# Session Handoff — 2026-06-24

Retires `SESSION_HANDOFF_2026-06-23.md`. That handoff's threads are all carried forward below; its top two pickups (ORPHEUS-92 decide-its-state, ORPHEUS-90 route-to-Andrew) are **both closed this session**.

This session: **no code — Plane housekeeping only.** Closed ORPHEUS-92 and ORPHEUS-90, filed ORPHEUS-96, drafted the ORPHEUS-90 Decision Log entry, updated CLAUDE.md + PRODUCT_CONTEXT.md. This handoff commit retires the 06-23 file. The 06-23 push caveat is **resolved**: `git fetch` now confirms local `main` == `origin/main` at `30f5f7d`, so `6fd93ac` (ORPHEUS-95) and `94825d2` (ORPHEUS-92) are both on origin.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-90 | Upgrade pipeline model → claude-sonnet-4-6 (+ revalidation) | ✅ **Done this session.** Option A — 4.6 calibration accepted (Andrew's call). No code; closing comment posted. |
| ORPHEUS-92 | Invite token lost across LinkedIn OAuth round-trip | ✅ **Done this session.** Code was already shipped 06-19 (`94825d2`); closing comment posted, 06-19 open item considered satisfied. |
| ORPHEUS-96 | Narrative agent asserts profile deficiencies it can't see | ⏳ **Backlog (medium). Filed this session** — split out of ORPHEUS-90's rubric-review finding. |
| ORPHEUS-93 | Resend invitation silently invalidates the previously-sent link | ⏳ Backlog (medium). Filed 06-19 alongside 92. |
| ORPHEUS-94 | Email-mismatch confirmation reads as an error during invite acceptance | ⏳ Backlog (low). Filed 06-19 alongside 92. |
| ORPHEUS-88 | Quality gate: confident reports on critically-deficient data | ⏳ Backlog (**high**). Now the top open thread. |
| ORPHEUS-82 | Live validation of 81 (+78/87/89/91) | ⚠️ Shows **Done** in Plane (since 06-12) but the combined post-deploy run was still owed per the 06-23 handoff. See "Drift / discrepancy" below. |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |

---

## What this session did

### ORPHEUS-90 — Sonnet 4.6 calibration accepted (closed, no code)

The standing Andrew sign-off gate was resolved: **Option A — accept the 4.6 calibration as the new, correct baseline.** The harsher 4.6 reading of the two Claude rubric dimensions is a stricter reading of the *same* rubrics (near-uniform one-notch downgrade across 6 of 7 rubric sub-dims, ordering preserved, all `CONFIRMED`); temp-0 determinism survives the swap (0.00 stdev). No threshold change — Option C (recalibrate `SIGNAL_BANDS`) was considered and declined.

**Consequence recorded on the ticket + in the docs:** reports scored under the retired `claude-sonnet-4-20250514` snapshot are no longer scale-comparable to 4.6 reports — a returning client can see a lower band on unchanged behavior (Andrew's profile: 80.50/Resonant → 66.50/Tuned on identical data). The interim "hold near-boundary reports" caveat is lifted.

### ORPHEUS-92 — invite-token fix confirmed closed (no code)

Code was already shipped 06-19 (`94825d2` — token rides the OAuth `redirectTo` as `?token=`, callback resolves URL-first with sessionStorage fallback; +131 lines of InviteFlow tests, vitest 40→47). The 06-19 comment's lone open item (live in-app-browser re-test) was **considered satisfied** — closed as Done, no separate live-validation ticket owed.

### ORPHEUS-96 — filed (Backlog, medium)

Split out of ORPHEUS-90's 2026-06-18 rubric-review finding: the narrative agent can assert specific profile deficiencies it never sees (its inputs are `scored_dimensions` + `forward_brief_data` + questionnaire, **not** the profile text). Live example: Andrew's About scored 3 and the narrative said "no call to action / what you're available for" — that clause is sourced from his Q2 ("Advisory or consulting work" + "Speaking opportunities"), not from the rubric or the actual About text. Scope: a narrative-prompt constraint to stop the agent asserting unobservable deficiencies. Open framework question for Andrew (carried on the ticket): whether forward-facing positioning / CTA should become an explicit sub-dim 1B criterion.

### Docs

CLAUDE.md "Active phase" + a new "Decisions Made" entry for the 4.6 acceptance / 92 / 96; PRODUCT_CONTEXT.md Open Question 4 appended with the 4.6 revalidation + acceptance.

---

## Pending — your manual step

**Decision Log paste (ORPHEUS-90).** The 4.6-acceptance entry is drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md` (this session's scratch outputs, not in the repo). It's cross-stakeholder (revises a framework calibration), tagged `[Andrew, 2026-06-24]`, with the required "Implications for product" field. Paste it into the Shared Canon Decision Log (doc ID `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`) — the Drive MCP is read-only for doc content, so this stays manual. Offered to also drop it as a tracked `Decision_*.md` at repo root (matching `Decision_LinkedIn_Auth_*`); you didn't take that up, so it's outputs-only for now.

---

## Recommended pickup for next session

1. **ORPHEUS-88** (high) — the quality gate. Now the highest-priority open thread: the pipeline ships confident reports on critically-deficient data with no client/advisor-facing surface for critical quality flags. Brandon's Basic-archive re-export is the operational follow-up here.
2. **ORPHEUS-82 reconciliation** — confirm whether the combined live post-deploy run actually happened (it's marked Done but the 06-23 handoff said it was owed). If not, a fresh validation ticket is cleaner than reopening 82. The run should fold in: ORPHEUS-95 fractional-composite band check, ORPHEUS-91 recency re-check on `72b11642`, ORPHEUS-89 photo flag, and now a first 4.6-calibration spot-check on a fresh job.
3. **ORPHEUS-96** (medium) — the narrative-prompt constraint; route the 1B-criterion question to Andrew.
4. **ORPHEUS-93 / 94** (medium / low) — invite-flow polish, batchable.

---

## Caveats / things that will bite

1. **ORPHEUS-82 is the one real discrepancy.** Plane has it Done (updated 06-12) but the 06-23 handoff repeatedly listed the combined post-deploy validation run as still owed. Either the live run happened and wasn't reflected in the handoff, or 82 was closed prematurely. Verify before trusting that 81/87/89/91/95 are live-validated.
2. **No code this session** → test baselines unchanged from the 06-23 handoff: backend pytest ~297 (unconfirmed from sandbox, PyPI blocked), frontend vitest 40 + ORPHEUS-92's InviteFlow cases (47 per `94825d2`) + ORPHEUS-95's `bands.test.ts`. Confirm exact counts from your terminal if it matters.
3. **4.6 is live for all new jobs.** Any report generated from here scores on the accepted-harsher calibration; pre-4.6 stored reports are on the old scale. Relevant the moment report-over-report comparison framing gets built.
4. **Decision Log paste still owed** (see above) — the only loose end from this session.
5. **Sandbox quirks unchanged:** no SSH push, `.git/*.lock` mv-workaround before commits (an `index.lock` warning appeared this session — cosmetic), PyPI blocked.
6. **Untracked-by-intent files:** `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, survey `.md` + `.gs`, both `rubric_consistency_results_*.json`, compliance drafts. Unchanged — do not `git add`.

---

## State of the repo right now (end of session)

No code commits this session. CLAUDE.md ("Active phase" + a new "Decisions Made" entry) and PRODUCT_CONTEXT.md (Open Question 4) updated in this handoff commit. The 06-23 handoff is retired in the same commit. Working tree is otherwise clean except the intentionally-untracked files above.

Local `main` == `origin/main` == `30f5f7d` before this commit (verified via fetch). This handoff commit is the only new commit.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry — drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`, paste when convenient. ORPHEUS-85 still owes its entry when it ships.
