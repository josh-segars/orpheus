# Session Handoff — 2026-06-15

Retires `SESSION_HANDOFF_2026-06-12.md`. Its threads resolved as follows:

- **Pickup 1 (ORPHEUS-82, consolidated live validation run)** — still owed, carries forward. Partially pre-cleared since: ORPHEUS-87's fix was live-validated on Andrew's re-run (job `72b11642` → 80.50 / Resonant), and ORPHEUS-89's photo flag will ride the same run.
- **Pickup 2 (ORPHEUS-83, uniqueness-guard migration)** — **shipped** in a later 2026-06-12 session (`0f6f3c3`, migration 014, applied to cloud). Closed in Plane.
- **Pickup 3 (ORPHEUS-84 / 85, roles + growth pair)** — unchanged, carry forward.
- **Not in the 06-12 handoff but shipped right after it:** ORPHEUS-87 (`c31efe1`, ZIP parser member-ID-suffixed CSVs). And two new tickets were filed: ORPHEUS-86 (upload-failure UX) + ORPHEUS-88 (quality gate on critically-deficient data). That 06-12 follow-up session committed code but never wrote its own handoff, so its work + this session's are both folded into CLAUDE.md "Decisions Made" in this commit (3 new entries: 83, 87, 89).

This session shipped **one ticket — ORPHEUS-89** (LinkedIn OIDC profile-photo source).

Commit this session:

```
1094164 ORPHEUS-89: source profile-photo presence from LinkedIn OIDC   ← appears already pushed (origin/main == HEAD)
(this handoff + CLAUDE.md / PRODUCT_CONTEXT.md refresh)                 ← unpushed
```

Session shape: Josh asked whether the profile photo — unreliable to pull from the data export — could be confirmed via LinkedIn SSO → traced the existing photo-presence flag to a single ZIP rich-media heuristic in `_compute_qualitative_flags` → confirmed OIDC `picture` claim is the trustworthy source but only available in the client's own session at submission → drafted the change → Josh: "file and implement, OIDC always winning" → filed ORPHEUS-89, implemented across migration + engine + worker + API + frontend, migration applied to cloud, tests added, committed, closed → wrap.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-89 | Profile-photo presence from LinkedIn OIDC | ✅ **Done.** Commit `1094164`. Migration 015 applied to cloud. |
| ORPHEUS-87 | ZIP parser member-ID-suffixed CSVs | ✅ **Done** (2026-06-12, `c31efe1`). Live-validated. Caught up in CLAUDE.md this session. |
| ORPHEUS-83 | One-clients-row-per-user guard (migration 014) | ✅ **Done** (2026-06-12, `0f6f3c3`). Caught up in CLAUDE.md this session. |
| ORPHEUS-82 | Live validation of 81 (+78, and now +87/+89) | ⏳ Backlog (medium). Combined post-deploy run still owed. |
| ORPHEUS-88 | Quality gate: confident reports on critically-deficient data | ⏳ Backlog (**high**). Delivery-side backstop; Brandon's Basic-archive re-export is the operational follow-up. |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). 85 needs the open-vs-gated decision routed; Decision Log entry due at ship. |
| ORPHEUS-42 / 45 / 48 / 40 / 41 | Account page / edit action / branding / Stripe / disconnect | ⏸ Backlog. Unchanged. |

---

## What this session shipped

### ORPHEUS-89 (`1094164`) — profile-photo presence from LinkedIn OIDC

The Forward Brief `visual_professionalism.photo_present` flag was derived in `backend/scoring/engine.py:_compute_qualitative_flags()` from the ZIP's `rich_media` — `any("profile photo" in item.type.lower() …)` — which only detects a *"You changed your profile photo"* event in `Rich_Media.csv`, not whether the member actually has a photo. Members who set their photo outside the export window read as `False`.

Now captured from the client's LinkedIn OIDC `picture` claim at submission (the one moment OIDC can vouch for it, in the client's own session) and threaded to scoring. **OIDC always wins when present**; the ZIP heuristic is the fallback only when the captured value is NULL (older / advisor-run jobs). The picture URL is never persisted — only the boolean.

- **Migration 015** (`015_jobs_oidc_photo.sql`): nullable `jobs.oidc_photo_present boolean`. **Applied to cloud Supabase via MCP and verified.** `claim_next_job` returns `SELECT *`, so the worker's claimed-job dict carries the new column with no RPC change.
- **`scoring/engine.py`**: `photo_present_override: bool | None = None` threaded through `_compute_qualitative_flags` → `compute_forward_brief` → `run_scoring`; non-None wins over the heuristic.
- **`workers/processor.py`**: `stage_scoring` accepts + forwards the override; `run_pipeline` passes `job.get("oidc_photo_present")`.
- **`routers/jobs.py`**: new `has_profile_photo` Form field on `POST /jobs`, persisted on the job insert. The `Job` response is built from explicit keys, so the extra column is harmless to the response model.
- **`frontend/src/hooks/useCreateJob.ts`**: reads `user_metadata.picture ?? avatar_url` from the live Supabase session, appends the boolean to the multipart form.

Forward Brief data only — no composite-score impact. Product application (Josh's call).

### Verification

- Frontend: `tsc -b` clean, vitest **40 green** (unchanged — the hook change is covered indirectly; no new frontend cases).
- Backend: py_compile clean; **+7 cases** (5 scoring override + 2 worker passthrough). Expected pytest **284 → 291** — **unconfirmed, run from Josh's terminal** (PyPI blocked in sandbox).
- Cloud: migration 015 applied + column existence verified via information_schema.

---

## Recommended pickup for next session

1. **ORPHEUS-82** — the consolidated live validation run, now even denser: a fresh job from a preserved profile covers the 81 run-guard + in-flight row, second-person register (77), word specs (66), temp-0 determinism, the 76/78 visual+copy checks, **and now ORPHEUS-89's OIDC photo flag** (confirm `photo_present` reflects the signed-in member's actual LinkedIn photo, not the rich-media event). Confirm Railway carries `1094164` and Vercel the post-`1094164` build first.
2. **ORPHEUS-88** (high) — the quality gate. Reports currently ship confidently even when critical data-quality flags fire; needs a client/advisor-facing surface. Brandon's Basic-archive re-export is the live trigger.
3. **ORPHEUS-86** — upload-failure UX (network-level fetch failures with actionable guidance).
4. **ORPHEUS-84 / 85** — roles + growth pair; 85 needs the open-vs-gated sign-up decision routed (Tim/Josh on cost posture) before build.

---

## Caveats / things that will bite

1. **Backend pytest count unconfirmed** — 291 expected (284 post-87 + 7 from 89). Correct the baseline if Josh's terminal disagrees.
2. **ORPHEUS-89 sends an explicit `false` for photo-less accounts** — so OIDC overrides even the no-photo case, not just the has-photo case. Consistent with "OIDC always wins," but if Josh prefers "only override when a photo exists," it's a one-line change in `useCreateJob.ts` (drop the field when `hasProfilePhoto` is false).
3. **The 06-12 follow-up session (83/87/86/88) never wrote a handoff** — its work is reconstructed into CLAUDE.md here from the Plane closing comments. If anything from that session feels under-documented, the Plane tickets are the fuller record.
4. **Andrew's advisors `practice_name` is still NULL** — invite emails + admin labels fall back to his email until he sets it.
5. **`POST /advisor/self-report` vs. migration 014** — flagged on ORPHEUS-83: a dual-role user whose clients row lives under a *different* advisor would 500 against the new unique index. Post-repair data can't produce that shape, but ORPHEUS-84's invite-advisor flow must decide the behavior before it ships.
6. **Free re-runs + (soon) free sign-up = unmetered pipeline cost** — the single-in-flight guard is the only throttle until ORPHEUS-85's gate decision / ORPHEUS-40 Stripe. ORPHEUS-88's quality gate is also unmetered-adjacent (bad data still burns a full pipeline run).
7. **Sandbox quirks unchanged:** no SSH push, `.git/*.lock` mv-workaround before commits, PyPI blocked (no pytest from sandbox).
8. **Untracked-by-intent files unchanged:** survey `.md` + `.gs`, `rubric_consistency_results_2026-06-10_112327.json` (keep/delete call still pending), compliance drafts.

---

## State of the repo right now (end of session)

`origin/main` is at `1094164` (ORPHEUS-89) — that commit appears already pushed. This handoff + doc-refresh commit is the only new unpushed work.

CLAUDE.md updated: Active phase gained a sentence covering 83/87/89 + the 86/88 open follow-ups; three new "Decisions Made" entries (ORPHEUS-83, ORPHEUS-87 catch-up, ORPHEUS-89). PRODUCT_CONTEXT.md updated: the `photo_present` qualitative-flag line now documents the OIDC source + NULL fallback. CONVENTIONS.md / CREDENTIALS.md untouched.

`SESSION_HANDOFF_2026-06-12.md` is retired in this commit.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** none from this session (ORPHEUS-89 is product application, no cross-stakeholder decision). ORPHEUS-85 still owes a Decision Log entry when it ships (revises the invitation-only-beta decision).
