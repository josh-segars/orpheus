# Session Handoff — 2026-06-24 part 2

Retires `SESSION_HANDOFF_2026-06-24.md` (the part-1 housekeeping handoff). All of part 1's still-open threads are carried forward in "Recommended pickup" and "Caveats" below — nothing it described closed *because* of this session except where noted.

This session: **shipped ORPHEUS-98** (report-completion thank-you + feedback email) — code, tests, Plane closeout, live deploy. Filed ORPHEUS-99. This wrap commit re-adds a CLAUDE.md doc line that was lost in a rebase (see Caveats #1), plus the Decisions Made entry + PRODUCT_CONTEXT row + this handoff.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-98 | Report-completion thank-you + feedback email | ✅ **Done this session.** Commit `7a0be51`, pushed. Backend pytest 310 green. `BETA_SURVEY_URL` set live on both Railway services. |
| ORPHEUS-99 | Atomic "Publish report" admin action | ⏳ **Backlog (low). Filed this session** — replaces ORPHEUS-98's implicit last-narrative-flip advisory trigger with an explicit publish action. |
| ORPHEUS-88 | Quality gate: confident reports on critically-deficient data | ⏳ Backlog (**high**). Still the top open thread (carried from part 1). |
| ORPHEUS-82 | Live validation of 81 (+78/87/89/91/95) | ⚠️ Shows **Done** in Plane but the combined post-deploy run may still be owed. See Caveats #3 (carried from part 1). |
| ORPHEUS-96 | Narrative agent asserts profile deficiencies it can't see | ⏳ Backlog (medium). Filed part 1. |
| ORPHEUS-93 / 94 | Resend invalidates prior link / email-mismatch reads as error | ⏳ Backlog (medium / low). Filed 06-19. |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |

---

## What this session did

### ORPHEUS-98 — report-completion feedback email (shipped, closed)

A thank-you + beta-feedback-survey CTA email sent once per client when their report becomes viewable, to strengthen the closed-beta feedback loop at the moment of maximum context (the ORPHEUS-72 nav survey button is always-present but passive; this is the earned, well-timed prompt that reaches them after they've left the app). Single commit `7a0be51`.

- **Template** — `format_report_ready_email(client_name, report_url, survey_url=None)` in `backend/email/templates.py`; mirrors the invitation formatter's `(subject, html, text)` tuple, minimal HTML + line-for-line text, second-person voice (ORPHEUS-77). Feedback CTA block renders only when `survey_url` is set, so an unconfigured URL ships a clean thank-you with no dead link.
- **Send fn** — `send_report_ready_email` in `resend_client.py` reuses the invitation send's sandbox short-circuit + WAF-safe UA + `EmailSendError`.
- **Self-serve path** — `_maybe_send_report_ready_email` at the end of the worker's `run_pipeline`, on a client's first *complete* job, gated to the published path (`is_advisory == False`). Best-effort; never fails/retries the job.
- **Advisory path** — `_maybe_send_report_ready_on_publish` from the admin `PATCH /admin/narratives/{id}`, fires when a status flip leaves *no draft narratives* for the job. The `narratives_select_as_client` RLS policy (`status = 'published'`) confirms a client can't see a draft, so publication is the advisory "ready" moment.
- **Idempotency + once-per-client** — both ride `reports.published_at`: NULL→set+send for advisory; already-set by the worker for self-serve (path no-ops → no double-send); a returning client's later report is stamped but the email suppressed.
- **Env** — new optional `BETA_SURVEY_URL`: added to `config.Settings` (`beta_survey_url`) for the API/advisory path, read straight from `os.environ` by the worker; same Google Form as the frontend's `VITE_BETA_SURVEY_URL`; set on **both** Railway services. Now live in prod.
- **Tests** — +11 backend (4 templates, 3 resend_client, 4 admin publish-trigger). Backend pytest **310 green** (Josh's terminal).
- **Decision locked** — consent footer omitted for the closed beta [Josh, 2026-06-24]: all current testers are personal contacts. The unsubscribe + ToS/Privacy footer requirement reopens before any non-personal-contact send (open enrollment, ORPHEUS-85 self-serve, list sends). Captured as a Plane comment on ORPHEUS-98.

### ORPHEUS-99 — filed (Backlog, low)

The advisory trigger fires implicitly on whichever narrative the admin saves last (no atomic publish action exists; the `/admin` editor flips status per-narrative). Proposed: a `POST /admin/jobs/{job_id}/publish` that flips all narratives + stamps `published_at` + announces once, with a single "Publish report" button. Robustness/UX improvement, not a bug — the implicit trigger is correct for the current single-admin beta. Likely coordinates with the eventual advisor-facing publish flow.

### Docs (this wrap commit)

CLAUDE.md: re-added the lost Railway deploy-mirror `BETA_SURVEY_URL` line (Caveats #1), new "Decisions Made" entry for ORPHEUS-98, "Active phase" tail updated. PRODUCT_CONTEXT.md: ORPHEUS-98 note on the Signup/invitation-flow build-status row.

---

## Pending — your manual step

**Decision Log paste (ORPHEUS-90)** — still owed from part 1. The 4.6-acceptance entry is drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md` (part-1 session's scratch outputs, not in the repo); paste into the Shared Canon Decision Log (doc ID `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`) when convenient — Drive MCP is read-only for doc content. ORPHEUS-98 needs no Decision Log entry (product application; the consent posture is a deferral, not a cross-stakeholder framework decision).

---

## Recommended pickup for next session

1. **ORPHEUS-88** (high) — the quality gate. Highest-priority open thread: the pipeline ships confident reports on critically-deficient data with no client/advisor-facing surface for critical quality flags. Brandon's Basic-archive re-export is the operational follow-up.
2. **ORPHEUS-82 reconciliation** — confirm whether the combined live post-deploy run happened (marked Done since 06-12 but repeatedly listed as owed). A fresh validation ticket is cleaner than reopening 82 if not. Should fold in: ORPHEUS-95 fractional-composite band check, ORPHEUS-91 recency re-check, ORPHEUS-89 photo flag, a 4.6-calibration spot-check, and now a **first live check of the ORPHEUS-98 email** (a self-serve completion or an advisory publish should fire exactly one email with working report + survey links).
3. **ORPHEUS-96** (medium) — narrative-prompt constraint; route the 1B-criterion question to Andrew.
4. **ORPHEUS-93 / 94** (medium / low) — invite-flow polish, batchable.

---

## Caveats / things that will bite

1. **A doc line was lost in a rebase mid-session and re-added in this wrap commit.** The ORPHEUS-98 work hit a messy git sequence: the in-session amend (`9b3823f`, which added a CLAUDE.md Railway deploy-mirror line) was absorbed/dropped during a `pull --rebase` against the day's part-1 handoff, leaving the pushed commit `7a0be51` with only the env-table CLAUDE.md line. This wrap commit re-adds the deploy-mirror line. Root cause of the mess: the `.git/*.lock` mv-workaround also renamed `refs/heads/main.lock` → a bogus ref, and a leftover `HEAD.lock` blocked the rebase; both were cleared manually on Josh's machine. **Lesson:** the lock-cleanup `find .git -name "*.lock"` pattern matches `refs/heads/*.lock` too — scope it to exclude `refs/` if this recurs.
2. **ORPHEUS-98 won't fire for the current beta cohort yet.** They're all advisory, so the email only goes out when an advisory report is *published* (last narrative flips via `/admin`). It has not been exercised live — folds into the ORPHEUS-82 run (pickup #2).
3. **ORPHEUS-82 is the one standing discrepancy** (carried from part 1). Plane has it Done (06-12) but prior handoffs listed the combined post-deploy validation run as owed. Verify before trusting 81/87/89/91/95 are live-validated.
4. **Test baselines:** backend pytest **310 green** (confirmed Josh's terminal this session, +11 from ORPHEUS-98). Frontend vitest unchanged — no frontend changes this session (still 40 + ORPHEUS-92 InviteFlow + ORPHEUS-95 `bands.test.ts`).
5. **4.6 is live for all new jobs** (carried from part 1) — pre-4.6 stored reports are on the old scale; relevant when report-over-report comparison framing gets built.
6. **Decision Log paste still owed** (see above).
7. **Sandbox quirks unchanged:** no SSH push, `.git/*.lock` mv-workaround before commits (and see Caveat #1 — it bit this session), PyPI blocked so pytest runs from Josh's terminal.
8. **Untracked-by-intent files:** `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, survey `.md` + `.gs`, both `rubric_consistency_results_*.json`, compliance drafts. Unchanged — do not `git add`. (The stray `SESSION_HANDOFF_2026-06-23.md` left on disk — already retired in git by `875e220` — was removed this session.)

---

## State of the repo right now (end of session)

ORPHEUS-98 shipped as `7a0be51` (already pushed earlier this session). This wrap commit adds: the CLAUDE.md re-add + Decisions Made entry + Active-phase tail, the PRODUCT_CONTEXT build-status note, and this handoff — and retires `SESSION_HANDOFF_2026-06-24.md`. Working tree is otherwise clean except the intentionally-untracked files above.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry — drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`. ORPHEUS-85 still owes its entry when it ships.
