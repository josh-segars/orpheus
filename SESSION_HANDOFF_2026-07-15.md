# Session Handoff — 2026-07-15 (updated in place: part 2, ORPHEUS-108)

Replaces `SESSION_HANDOFF_2026-07-13.md` — its threads are resolved or carried below:

- **ORPHEUS-93 / 97 / 86 (frontend half) / 105 / 106** — all shipped and documented; their Vercel + Railway redeploys are still the pending manual step (carried).
- **ORPHEUS-8 go-live** — the "migrations 017/018 not applied to cloud" caveat was **stale**: part 1 verified both are applied (ladder shows 2026-07-02, harmless idempotent re-apply 2026-07-08) and the table shape matches the migration files exactly. Remaining go-live steps are the Vercel domain + registrar DNS wiring only. Carried, reduced.
- **ORPHEUS-108** — no longer blocked: **shipped in part 2** (see below). In Progress pending live validation.
- **ORPHEUS-107** — still Backlog (low), wants Tim privacy check. Carried.
- **ORPHEUS-90 Decision Log paste** — still owed. Carried.
- **Untracked-by-intent files** — unchanged (see "State of the repo").

Two sessions today: **part 1** shipped and closed ORPHEUS-104 (waitlist admin view) and cleared the stale 017/018 caveat; **part 2** shipped ORPHEUS-108 (browser-direct upload) without waiting on Andrew's failure data.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-108 | Large multipart uploads die at the edge | 🔄 **In Progress — code shipped part 2 (`c406c00` + `48261ce`, both pushed).** Browser-direct upload to Storage; stays open pending live validation + legacy multipart removal. |
| ORPHEUS-104 | Waitlist admin view: surface `public.waitlist` in /admin | ✅ Done (part 1, `cd6eb94`). Live once Railway backend redeploys. |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | 🔄 In Progress. Frontend half shipped 07-13 (`4edf25f`); ORPHEUS-108's live validation is what closes it. |
| ORPHEUS-102 | Live validation of the gate trio (88/100/101) | ⏳ Backlog (medium). Unblocked; fold in the ORPHEUS-97 model-key spot-check + first live `GET /admin/waitlist`. |
| ORPHEUS-93 / 97 / 105 / 106 | (resend messaging / config_snapshot model / UI polish / LIMITED DATA proportionality) | ✅ Done, deploys pending (same Vercel + Railway redeploys). |
| ORPHEUS-99 | Atomic "Publish report" admin action | ⏳ Backlog (low). |
| ORPHEUS-94 | Email-mismatch reads as an error | ⏳ Backlog (low). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |
| ORPHEUS-107 | Persist LinkedIn avatar past OIDC picture-URL expiry | ⏳ Backlog (low). Wants Tim privacy check. |
| ORPHEUS-96 | Andrew question: forward-facing CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew's call). |

---

## What part 2 did — ORPHEUS-108, commits `c406c00` + `48261ce` (pushed)

**Decision [Josh]: proceed without Andrew's file-size/time-to-failure data, browser-direct upload over server-side streaming.** Research finding that drove it: Railway's published specs document *no* edge body-size limit (only a 60s proxy keep-alive + 15-min max request duration), so the mechanism was never actually confirmed — and server-side streaming (the ticket's original "likely primary") wouldn't fix a mid-transfer connection/timeout death since the body still crosses the same edge. Browser-direct sidesteps every candidate mechanism.

- **`POST /jobs/upload-urls`** — role gate + concurrent-run guard *before* any bytes move, then mints signed Storage upload URLs for `{client_id}/staging/{upload_id}/` (uuid4; validated on the way back in to block path traversal). Signed URLs = no storage RLS migration; backend keeps sole path authority.
- **Browser → Storage direct** — `useCreateJob` rewritten: mint targets → `uploadToSignedUrl` both files (parallel) → submit. A failed transfer throws the ORPHEUS-86 `NetworkError`, so GroundworkPage's connection/large-archive guidance fires unchanged.
- **`POST /jobs/from-uploads`** (small JSON body: `upload_id`, `archive_filename`, `has_profile_photo`) — stats the staged objects (size caps re-checked server-side; signed URLs can't enforce them), downloads Railway↔Supabase, runs the identical three gates via the extracted **`_apply_submission_gates`** helper (shared with the multipart handler so the entry points can't drift; the ORPHEUS-101 filename gate rides the browser filename in the body since staged objects are always `archive.zip`), mints the job row, then **moves** the objects to `{client_id}/{job_id}/` — the worker is untouched. Gate rejections best-effort delete the staged files.
- **Legacy multipart `POST /jobs` stays** as a deploy-skew shim (the Railway auto-deploy quirk makes a hard cutover risky). **Follow-up: remove after live validation.**
- `48261ce` renamed both 413 sites to `HTTP_413_CONTENT_TOO_LARGE` (Starlette deprecation, same family as ORPHEUS-88's `610df1a`).
- **Tests:** +10 pytest (`test_jobs_uploads.py`), +2 vitest (`useCreateJob` sequence + NetworkError). Backend pytest **387 green** (Josh's terminal), frontend vitest **76 green**, `tsc -b` clean.

Files touched: `backend/routers/jobs.py`, `backend/tests/test_jobs_uploads.py`, `frontend/src/hooks/useCreateJob.ts`, `frontend/src/hooks/__tests__/useCreateJob.test.tsx`.

## What part 1 did — ORPHEUS-104, commit `cd6eb94` (pushed), closed

New `GET /admin/waitlist` (service-role read of the anon-INSERT-only `public.waitlist`, gated by `get_current_admin`) + a read-only Waitlist section below the existing AdminPage panes with header stats (signup count + beta_access/live_workshop breakdown) and interest display labels. +3 pytest, +2 vitest. En route: the "migrations 017/018 not applied" caveat found stale — both already applied and verified, so ORPHEUS-8's remaining go-live step is the Vercel domain/DNS wiring only.

---

## Pending — your manual steps

1. **Push** — the wrap commit only (`c406c00`, `48261ce`, `cd6eb94` are already pushed). Command below.
2. **Railway backend redeploy** — now carries `GET /admin/waitlist` + the two new upload endpoints. **Do this before or with the Vercel redeploy**: the new frontend flow 404s against a stale backend (the reverse skew is safe — the legacy multipart shim covers an old frontend on a new backend). Watch the auto-deploy quirk. Worker redeploy still owed too (ORPHEUS-97 model key + 106 banner clear); 108 doesn't touch the worker.
3. **Vercel redeploy** — picks up the 108 direct-upload flow + the carried 07-13 bundle (86 frontend half, 93 inline resend confirm, 105 UI batch) + 104's admin waitlist section.
4. **Supabase file-size limit check** — dashboard → Storage settings: confirm the project's global file-upload size limit accommodates real Complete archives. It binds browser-direct uploads exactly as it bound the old server-side write; if Andrew's archive exceeds it, the failure is now at least a clear storage error instead of a dead connection.
5. **ORPHEUS-8 go-live, remaining** — Vercel Domains: add `orpheussocial.com` + `www.`; registrar DNS off the GoDaddy placeholder; confirm SSL + the `isMarketingHost()` branch; test a waitlist submit e2e.
6. **Decision Log paste (ORPHEUS-90)** — still owed. Drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`.

---

## Recommended pickup for next session

1. **ORPHEUS-108 live validation** — after the redeploys: a real submission through the new flow (ideally Andrew's large archive — this is the failing case, and his file-size/time-to-failure numbers would confirm the diagnosis retroactively). Success closes ORPHEUS-86 and unlocks the legacy-multipart-removal follow-up; then close 108.
2. **ORPHEUS-102** (live validation of the gate trio) — needs a real Basic archive for the reject path; fold in the ORPHEUS-97 model-key spot-check and the first live `GET /admin/waitlist` check.
3. **ORPHEUS-8 go-live finish** — domain/DNS is manual (yours); a session can verify the hostname branch + waitlist submit right after.

---

## Caveats / things that will bite

1. **Deploy ordering matters this time** — new frontend + old backend = 404 on `/jobs/upload-urls` at submit. Redeploy Railway backend first (or together). Old frontend + new backend is safe via the multipart shim.
2. **The legacy multipart POST /jobs is still live** — remove it (and its now-redundant `_read_upload` path) in a follow-up commit once 108 validates; the shared `_apply_submission_gates` makes that a clean deletion.
3. **Abandoned staging uploads aren't swept** — a browser that uploads but never submits leaves orphans under `{client_id}/staging/`. Periodic cleanup is a follow-up only if the bucket accumulates.
4. **TUS resumable upload is the escalation path** if very large files still fail browser→Storage (standard signed-URL PUT for now).
5. **Nothing from 07-13 or today is validated in prod yet** — the redeploys are the gate. The waitlist still has 0 rows until ORPHEUS-8's DNS step.
6. **AdminPage test mock is whole-module** — `vi.mock('../../hooks/useAdmin')` must list every hook AdminPage imports.
7. **Sandbox quirks unchanged** — no `pip install` / pytest (Josh's terminal); no SSH push; `.git/*.lock` needs the `mv`-workaround before each commit; `tmp_obj` unlink warnings cosmetic.
8. **Untracked-by-intent files** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, the local `.claude/` cache, `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`.

---

## State of the repo right now (end of part 2)

Part 1: `cd6eb94` (ORPHEUS-104) + `45d1986` (wrap). Part 2: `c406c00` (ORPHEUS-108) + `48261ce` (413 deprecation) — **all four pushed**. This wrap commit (handoff update in place, CLAUDE.md + PRODUCT_CONTEXT.md refresh) is the only unpushed commit. Backend pytest **387 green** (Josh's terminal), frontend vitest **76 green**, `tsc -b` clean. Working tree otherwise clean except the intentionally-untracked files in caveat 8.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry (drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`). ORPHEUS-85 still owes its entry when it ships.
