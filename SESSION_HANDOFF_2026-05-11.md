# Session Handoff — 2026-05-11

Jump-in doc for the next Claude session. Replaces SESSION_HANDOFF_2026-05-08.md
(now stale — the work it described has all been committed or superseded).

This session ported ORPHEUS-20 (Analysis-in-Progress holding screen), verified
it end-to-end against a real backend up to the polling step, fixed three
adjacent bugs discovered during verification, and turned the new
intake-questionnaire conversation into a Spec page + two Plane tickets.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-20 | Port Analysis-in-Progress holding screen | ✅ Code complete; pending-state verified end-to-end. Complete-state auto-redirect unverified (blocked by ORPHEUS-35). **Not yet committed.** |
| ORPHEUS-33 | Replace 23-question questionnaire with 9-question intake | ⏳ Filed, not started. Spec at `Spec_Simplified_Intake_Questionnaire_2026-05-11.md`. |
| ORPHEUS-34 | Rewrite narrative-generation prompt for simplified questionnaire shape | ⏳ Filed, depends on ORPHEUS-33. |
| ORPHEUS-35 | Add base-schema migration for jobs/scores/ingested_data/narratives | ⏳ Filed, blocker for full-pipeline verification. |
| Side fix | MSW worker.start gate (frontend/src/main.tsx) | ✅ Code complete, **not yet committed.** |
| Side fix | auth.py ES256 + .well-known JWKS path | ✅ Code complete, **not yet committed.** |
| Side fix | jobs router result-payload gate on `status == 'complete'` | ✅ Code complete, **not yet committed.** |
| Spec | Simplified Intake Questionnaire (2026-05-11) | ✅ Drafted, in repo, **not yet committed.** Not yet pasted into Plane as a page (Plane MCP doesn't expose page creation). |

---

## Pending commits

Five commits, paste locally in this order (sandbox can't write to
`.git/index.lock`). Squashing into one is fine if you'd rather; the
contents are coherent on their own.

```bash
# 1. ORPHEUS-20 — the actual ticket work.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add frontend/src/App.tsx \
          frontend/src/pages/AnalysisPage.tsx \
          frontend/src/pages/AnalysisPage.css && \
  git commit -m "Port Analysis-in-Progress holding screen to React; auto-navigate on complete. Refs ORPHEUS-20."

# 2. MSW gate — frontend/src/main.tsx
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add frontend/src/main.tsx && \
  git commit -m "Skip MSW worker.start when handlers is empty.

The handlers array is intentionally empty in normal dev; previously
worker.start() ran anyway and a stale on-disk mockServiceWorker.js
broke real fetches with an opaque 'Failed to fetch'. Gating on
handlers.length means 'no mocks -> no worker -> no chance of
interception.'"

# 3. auth.py — ES256 + new JWKS path
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add backend/auth.py && \
  git commit -m "Support ES256 + .well-known JWKS path in JWT verification.

Supabase (GoTrue v2) moved JWKS from /auth/v1/jwks to
/auth/v1/.well-known/jwks.json and newer CLIs sign with ES256 (P-256
EC) instead of RS256. auth.py now fetches from the new path,
dispatches on JWK kty to build the right public key (RSA or EC), and
accepts both algorithms in jwt.decode."

# 4. Jobs router — payload gate
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add backend/routers/jobs.py && \
  git commit -m "Gate result-payload build on jobs.status == 'complete'.

GET /jobs/:id was unconditionally querying scores + narratives even
for pending/running/failed jobs. AnalysisPage polls this endpoint
every 3s; a cheap pending response keeps that quiet and avoids
500s when downstream tables aren't yet populated."

# 5. Spec
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add Spec_Simplified_Intake_Questionnaire_2026-05-11.md \
          SESSION_HANDOFF_2026-05-11.md && \
  git commit -m "Spec: simplified 9-question intake questionnaire; session handoff. Refs ORPHEUS-33, ORPHEUS-34."
```

---

## Files added / modified

### ORPHEUS-20

Added:

- `frontend/src/pages/AnalysisPage.tsx` — polls `useJob(jobId)`, auto-navigates to `/jobs/:jobId` (replace) when `state === 'complete'`, renders error UI with `Return to Groundwork` CTA on `state === 'failed'`. Defensive `Navigate to="/groundwork"` if `jobId` missing.
- `frontend/src/pages/AnalysisPage.css` — pulse animation namespaced `orpheus-analysis-pulse`. `prefers-reduced-motion` fallback (steady, dimmed dots).

Modified:

- `frontend/src/App.tsx` — added `<Route path="/jobs/:jobId/analysis" element={<AnalysisPage />} />` above `/jobs/:jobId`. Updated `SmartIndexRedirect` docstring (removed the obsolete "Until ORPHEUS-20 lands…" caveat).

### Side fixes (each one its own commit)

- **MSW gate** — `frontend/src/main.tsx`: `worker.start()` now only runs when `handlers.length > 0`. Empty handlers (the default since ORPHEUS-28) leave the page free of any service worker, removing a class of opaque "Failed to fetch" errors caused by stale `mockServiceWorker.js`.
- **auth.py** — `backend/auth.py`: JWKS URL changed from `/auth/v1/jwks` (404s in current Supabase) to `/auth/v1/.well-known/jwks.json`. New `_public_key_from_jwk()` helper dispatches on `kty` to build either an RSA or EC public key. `jwt.decode` now accepts both `RS256` and `ES256`. Docstring updated. Existing `backend/tests/test_auth.py` (RS256-based) unchanged and still expected to pass.
- **Jobs router** — `backend/routers/jobs.py`: `_build_result_payload(...)` is now only called when `row["status"] == "complete"`. For pending/running/failed jobs, `result=None` is returned without querying `scores` or `narratives`. Cheap pending response for the 3-second poll loop and avoids 500s on partial dev schemas.

### Spec + tickets

- `Spec_Simplified_Intake_Questionnaire_2026-05-11.md` — the 9-question intake replacing the current 23-question questionnaire. Decisions all locked.
- Plane: **ORPHEUS-33** (frontend + migration), **ORPHEUS-34** (narrative prompt, depends on 33), **ORPHEUS-35** (base schema migration, independent).

---

## Pickup plan

Three independent threads available. Pick whichever fits the next session's
goal:

### Option A — Close out ORPHEUS-20 (verification)

Smallest. After ORPHEUS-35 lands a base-schema migration, the full pipeline
can run locally, and the complete-state auto-redirect path of AnalysisPage
can finally be verified end-to-end. Approximate effort: ORPHEUS-35 itself,
then a 10-minute verification walk.

Steps:

1. Pick up ORPHEUS-35: `supabase link --project-ref <ref>`, dump prod schema, save as `backend/migrations/001_base_schema.sql`, reconcile against 003-009 (header comment), apply locally, commit.
2. Re-run the verification walk from this session's transcript (or its compressed form below). With base schema present, the worker should successfully write `scores` and `narratives`, AnalysisPage's `useEffect` should fire on `state === 'complete'`, browser navigates to `/jobs/:id` (Signal Score).
3. Run `pytest backend/` — should be 69 tests green (no regressions from auth.py changes).
4. Mark ORPHEUS-20 done in Plane.

### Option B — Start ORPHEUS-33 (questionnaire shape change)

Largest, most product-impactful. Spec lives at
`Spec_Simplified_Intake_Questionnaire_2026-05-11.md` with all eight decisions
locked. Implementation order per the spec:

1. Migration 010 (TRUNCATE `questionnaire_responses`, DROP `section_completion`).
2. Frontend types (`src/types/questionnaire.ts`) — new `QuestionnaireAnswers` shape.
3. New primitive `CheckboxWithOtherQuestion` in `Questions.tsx`.
4. Prototype HTML — `orpheus-questionnaire-v2.html`, single-page.
5. React port — `QuestionnairePage.tsx`, route consolidation, hook updates.
6. Groundwork checklist update (9 → 3 rows).
7. Cleanup — remove `ScaleQuestion` and `CheckboxQuestion` (no-Other) from `Questions.tsx`.

### Option C — Start ORPHEUS-34 (narrative prompt)

Requires ORPHEUS-33 in place first (the prompt assembly reads from the new
shape). Don't pick this option without -33 done.

---

## Verification status from this session

- **TypeScript:** `npx tsc -b --noEmit` clean against all four code changes.
  Only error is the pre-existing unused `clamp` at `SignalScorePage.tsx:349`
  — same warning the 2026-05-08 handoff flagged. Not from this work.
- **Backend:** sandbox couldn't run `pytest` (PyPI blocked, no installed
  deps), so the auth.py changes are not test-verified yet. The test suite
  uses RS256 with a generated keypair and pre-populates `_jwks_cache._keys`
  directly, so neither the URL change nor the algorithm-list change should
  affect tests. Worth confirming with `pytest backend/` locally.
- **End-to-end (live stack):** verified through the polling-while-pending
  step. Welcome → Groundwork (all 9 items, real LinkedIn ZIP + XLSX) →
  submit → job created → AnalysisPage renders → polls every 3s → returns
  200 with `state="pending"`. Auto-redirect on complete is unverified
  because the worker can't complete a pipeline run without `scores` and
  `narratives` tables locally (ORPHEUS-35).

---

## Caveats / things that will bite during testing

1. **The fresh-local dev gauntlet is now fixed-ish.** Three independent
   bugs broke `supabase start` → submit → AnalysisPage end-to-end on a
   stock dev environment, all fixed in this session: MSW intercepting
   `POST /jobs`, auth.py hardcoded to RS256+old-JWKS path, jobs router
   500ing on `scores` query for pending jobs. If a future session
   surfaces another "this used to work" symptom after a Supabase CLI
   bump, suspect Supabase changed defaults again.

2. **The `uploads` Supabase Storage bucket must exist before submit.**
   Created manually in this session via Studio. If a future fresh local
   stack returns 502 on submit with "Storage upload failed", that's the
   cause. Worth automating in ORPHEUS-35 if the dump format allows it.

3. **Migration 010 will wipe `questionnaire_responses`.** Pre-launch,
   no data to preserve. If anyone has real prod answers by the time
   ORPHEUS-33 lands, the migration plan needs a real shape-translation
   step instead of TRUNCATE.

4. **The PortalNav still shows "Jane Doe" placeholder in the HTML
   prototype.** The React app reads the LinkedIn name from the Supabase
   session. The prototype HTML is purely visual; don't be alarmed by
   the placeholder showing in `orpheus-*.html` Live Server previews.

5. **`/jobs/:jobId/analysis` is the entrypoint, not `/jobs/:jobId`.**
   SmartIndexRedirect routes pending jobs to `/analysis`. The
   complete-job redirect from AnalysisPage uses `replace: true` so the
   back button won't return to the polling page.

6. **Plane MCP doesn't expose page creation.** Decision/Spec markdown
   files live in the repo and have to be pasted into Plane manually if
   you want them as pages there. The markdown file is the source of
   truth either way.

---

## Architectural notes worth carrying forward

- **`backend/auth.py` is now algorithm-agnostic** within RS256/ES256.
  If Supabase introduces a third algorithm we'll see "Unsupported JWK
  key type" 503s; the fix is one branch in `_public_key_from_jwk`.
- **`useJob` polls every 3s while `state` is `pending` or `running`,
  stops otherwise.** AnalysisPage relies on this to short-circuit the
  poll loop on completion. No manual refetch needed — React Query
  cancels via the `refetchInterval` returning `false`.
- **`AnalysisPage` navigates via `useEffect`, not during render.**
  Necessary for clean React Router commits; navigating during render
  causes warnings. `replace: true` avoids a stale entry in browser
  history.
- **`_build_result_payload` is now gated on `status == 'complete'`,
  not on whether the data exists.** This is a correctness improvement
  unrelated to the local schema gap — even with a complete prod schema,
  polling a pending job 20 times shouldn't run 20 join queries against
  scores + narratives.
- **The intake questionnaire's `answers` JSONB shape will change
  meaningfully under ORPHEUS-33.** All `q1`–`q23` references in
  `agents/narrative.py` will be stale post-merge of -33. Plan for the
  -34 rewrite simultaneously even though they're separate tickets, so
  no merge sits with a known-bad prompt for long.

---

## Suggested CLAUDE.md updates (optional)

Not blocking, but the file has some staleness worth correcting at some
point:

- The "Active phase" line still says "porting the prototype's product
  flow." After ORPHEUS-20 commits, the active phase is the
  questionnaire shape change (ORPHEUS-33/34) plus the schema gap
  (ORPHEUS-35).
- The "Production Stack → Backend Conventions" RLS posture paragraph
  could note that auth.py now supports both RS256 and ES256, in case
  the prod project has been on ES256 too.
- The "Decisions Made" list could absorb "Intake questionnaire
  simplified to 9 questions on 2026-05-11; see ORPHEUS-33."

Hold this for whenever ORPHEUS-33 lands — then update CLAUDE.md as
part of that ticket so the description matches the actual code.
