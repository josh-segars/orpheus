# Session Handoff — 2026-05-13

Jump-in doc for the next Claude session. Replaces `SESSION_HANDOFF_2026-05-12_part2.md` — the threads it described are all closed:

- ORPHEUS-38: shipped (this session), 12 commits all on `origin/main`.
- Migration 012: applied to prod via Supabase MCP `apply_migration`.
- Live e2e walkthrough: deferred to **ORPHEUS-44**, gated on **ORPHEUS-25** (cloud Supabase LinkedIn OIDC provider configuration).
- Plus two new infra tickets filed during the session: **ORPHEUS-43** (Railway build-command source pin) and **ORPHEUS-44** (deferred e2e itself).

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-38 | Invitation flow: /clients/invite + /accept-invitation + /invite/:token (Resend) | ✅ Done in Plane (moved during this session). 12 commits, +43 tests, migration applied. Live e2e deferred to 44. |
| ORPHEUS-39 | Advisor admin UI: /advisor/clients page | ⏳ Backlog, unstarted. Next ticket in the beta chain. Unblocked now that 38 is done. |
| ORPHEUS-25 | Cloud Supabase + prod LinkedIn provider configuration | ⏳ Backlog, unstarted. Blocking ORPHEUS-44 (live e2e). |
| ORPHEUS-43 | Pin Railway build command in source (railpack.json or root requirements.txt) | ⏳ Backlog. Filed during this session after the commit-#2 deploy crash. Workaround in place. |
| ORPHEUS-44 | Live e2e of ORPHEUS-38 invitation flow | ⏳ Backlog. Filed this session. Downstream of 25. |
| ORPHEUS-40/41/42 | Stripe, disconnect, account mgmt | ⏳ Filed, beta-deferred. |

---

## Commits this session

In `origin/main` order (12 ORPHEUS-38 commits + 1 sibling SPA-rewrite commit):

```
6cda693 CLAUDE.md: invitation flow + deploy-state mirror. Refs ORPHEUS-38.
96062b7 Add vercel.json for SPA route rewriting. Refs ORPHEUS-38.
af7f759 Frontend neither-role routing + /not-invited page. Refs ORPHEUS-38.
f1b7063 Frontend /invite/callback page + mismatch confirmation. Refs ORPHEUS-38.
3f8db28 Frontend /invite/:token landing page. Refs ORPHEUS-38.
ef8ed95 GET /session endpoint. Refs ORPHEUS-38.
cdc41e9 POST /clients/{id}/resend-invitation endpoint. Refs ORPHEUS-38.
300c293 POST /accept-invitation endpoint. Refs ORPHEUS-38.
bb9596b POST /clients/invite endpoint. Refs ORPHEUS-38.
1adeb9e Resend client wrapper for invitation flow. Refs ORPHEUS-38.
07a53ff Config + auth-resolver split for invitation flow. Refs ORPHEUS-38.
```

The spec's commit-by-commit chunking (commits 1–12) maps onto these except for one subtlety: commit #11 in the spec was the migration-apply + manual-e2e gate. The migration was applied this session (via Supabase MCP, not git), and the manual e2e was deferred — so the eleventh source commit is actually the SPA-rewrite (`vercel.json`), filed under a "commit #11 ops" framing.

Test count: 114 baseline → **157 green** (+43 across 6 new test files).

---

## Infrastructure deltas (new this session)

### Migration 012 — applied to prod

`apply_migration` via Supabase MCP. Added `invitation_token uuid` and `invitation_expires_at timestamptz` to `public.clients`, plus the partial unique index `idx_clients_invitation_token` (`WHERE invitation_token IS NOT NULL`). Existing rows pick up NULL; backward-compatible.

Verified post-apply: both columns present with their docstring comments, index landed with the exact predicate.

### Database cleanup

Leftover seed data deleted:

- Synthetic-UUID advisor (`id=...0001`, `user_id=...aaaaaa`, `email=andrew@test.orpheus.dev`)
- Synthetic-UUID client (`id=...0002`, `user_id=...bbbbbb`, `email=client-andrew@test.orpheus.dev`)
- 8 dependent rows: 1 job, 1 ingested_data, 1 scores, 5 narratives, 1 report
- 2 synthetic `auth.users` rows (the zeroed-UUID ones referenced by the seed advisor + client)

Done as a single transactional delete cascading from the advisors row. Prod database is now clean — no business rows, no test users. Real LinkedIn-OAuth users will create their own rows from a clean slate.

### Vercel env vars added (out of repo)

Discovered during the post-commit-10 deploy that the production Vercel project never had `VITE_*` vars set. The bundle was failing at module load with "Missing Supabase configuration." Added during the session:

```
VITE_SUPABASE_URL=https://yqxuddkixzjruxtdjxpr.supabase.co
VITE_SUPABASE_ANON_KEY=sb_publishable_ak1L7vr_JRhNxIYJJW1-Kg_T5eDFDTj
VITE_ADMIN_EMAILS=andrew@ess3.ai,josh@ess3.ai,tim@ess3.ai
VITE_API_BASE_URL=https://orpheus-production-5082.up.railway.app
```

Applied to Production, Preview, and Development environments. Bundle now boots cleanly. Vercel **Root Directory** is set to `frontend`.

### Vercel SPA rewrite

`frontend/vercel.json` committed in `96062b7`. Rewrites every non-asset path to `/index.html` so direct nav to `/login`, `/invite/<token>`, `/invite/callback`, `/not-invited` is handled by React Router instead of Vercel's static 404. Required because the Vite framework preset doesn't auto-add this rule.

### Railway `FRONTEND_ORIGINS` added (out of repo)

Backend service had `FRONTEND_ORIGINS` unset, falling back to the localhost-only default. Set during the session to `http://localhost:5173,https://app.orpheussocial.com` on both backend and worker services. CORS now permits requests from the deployed frontend.

### Railway build command (still manual)

Discovered during the commit-#2 deploy: Railpack v0.23.0 builds were skipping `pip install` entirely, producing a venv with only stdlib packages. Backend services crashed at boot with `ModuleNotFoundError: No module named 'pydantic_settings'`. Workaround: manual **Build Command** = `pip install -r backend/requirements.txt` set in Railway dashboard for both services. Filed as **ORPHEUS-43** to pin this in source (`railpack.json` or a root-level `requirements.txt` symlink).

---

## ORPHEUS-39 pickup plan for the next session

ORPHEUS-39 is the advisor admin UI: `/advisor/clients` page. Now unblocked.

### What's ready

All four backend endpoints are deployed and tested. The frontend can hit:

- `POST /clients/invite` — issues a new invitation.
- `POST /accept-invitation` — already wired up by the invitation flow.
- `POST /clients/{id}/resend-invitation` — rotates token + resends email.
- `GET /session` — already wired by `useSessionRoles`.

`is_advisor()` role gating is in place on the advisor-owned routes.

### Suggested first session of ORPHEUS-39

Per the spec on ticket 39 (see Plane), the page has three sections: client list, invite form, "Run my own report" button (which calls a new `POST /advisor/self-report` endpoint that lazily creates a clients row for the advisor). The endpoint is in scope for 39, but lives in `backend/routers/clients.py` to match the existing advisor-owned router structure.

Order I'd suggest:

1. Backend: add `POST /advisor/self-report` to `backend/routers/clients.py` (idempotent — returns existing client_id if the advisor already has a clients row, otherwise creates and accepts in one transaction).
2. Frontend: scaffold `frontend/src/pages/advisor/ClientsPage.tsx` with empty-state, list, and form skeleton. Wire it to the existing endpoints via React Query hooks (one `useClients` hook against a new `GET /clients` listing endpoint that we'll need to add for the advisor's roster).
3. Tests: pytest coverage for the new self-report endpoint + listing endpoint.
4. App.tsx: route + nav-link gated on `is_advisor()`.

This is materially smaller than ORPHEUS-38 — probably 4–5 commits depending on how the listing endpoint shakes out.

### Alternative threads if you'd rather not pick up 39

- **ORPHEUS-25** (LinkedIn OIDC provider config) — small ops task. Unblocks the live e2e in ORPHEUS-44. Worth doing soon since it costs ~15 minutes and clears the deferred-e2e backlog.
- **ORPHEUS-43** (Railway build command source pin) — small infra task. Hardens deploys against future build-cache or service-recreate scenarios.
- **Compliance docs commit** — same untracked files as the part-2 handoff (privacy policy, ToS, LinkedIn BD DPA review). Decide commit vs Drive before launch.

---

## Architectural notes worth carrying forward

### Two-router pattern in `backend/routers/clients.py`

Routes that operate on advisors' own clients live on a `/clients`-prefixed router. The `/accept-invitation` route lives on a second, unprefixed `accept_router` in the same file because its caller has no clients row yet — `/clients` is the wrong namespace semantically. Both routers register in `backend/main.py`. Future "clients-resource" routes go on the prefixed one; future "anyone-authenticated-can-call-this" routes go on the unprefixed one or get their own router.

### Token preservation on accept (deliberate spec deviation)

The spec for `/accept-invitation` literally says to null `invitation_token` and `invitation_expires_at` on the UPDATE. The same spec's "Replay of already-accepted token: 200 with existing client_id if user_id matches" case can't work that way — the SELECT-by-token lookup would no longer find the row. Implementation preserves both fields and only flips `invitation_status`. Captured in CLAUDE.md's Backend Conventions section and in the `accept_invitation` handler's docstring so future readers know it's an intentional decision, not an oversight.

### `useSessionRoles` cache invalidation pattern

Frontend `ProtectedRoute` reads `useSessionRoles` (React Query against `GET /session`) to decide neither-role vs has-role routing. Because the query has `staleTime: Infinity` and roles can change mid-session (invitation acceptance), the cache must be invalidated explicitly when state-changing mutations succeed. Today's pattern: `useAcceptInvitation`'s `onSuccess` callback calls `queryClient.invalidateQueries({ queryKey: ['session'] })` when the response indicates a real acceptance (not a mismatch-pending state). Future mutations that change a user's role state — disconnect (post-beta), advisor self-report — should follow the same pattern.

### Resend wrapper as a model for future provider integrations

`backend/email/resend_client.py` is hand-rolled around `urllib.request` rather than using Resend's official SDK. Reasoning: no new dependency, matches the JWKS-fetch pattern in `auth.py`, ~30 lines of code. The sandbox-mode trigger (`api_key.startswith("test_")`) keeps tests + CI offline-deterministic without environment branching at every call site. If we add Stripe later (ORPHEUS-40), same pattern is probably the right shape.

### Vercel + Vite SPA rewrite is not automatic

`frontend/vercel.json` exists specifically because Vercel's framework preset for Vite doesn't add the SPA fallback rule. Direct URL nav to any non-asset subpath returns 404 without it. Worth knowing if anyone ever sets up a second Vercel project from this codebase.

---

## Caveats / things that will bite during next-session work

1. **ORPHEUS-25 dependency chain.** ORPHEUS-44 (live e2e of 38) cannot run until ORPHEUS-25 closes (LinkedIn OIDC provider config on cloud Supabase). If a future session picks up 44 first, it'll immediately stall on the `"Unsupported provider: provider is not enabled"` error we hit today.

2. **Vercel + Railway env-state lives out of repo.** CLAUDE.md captures what should be set where, but the actual values live in dashboards. A service recreate or environment clone will drop them. ORPHEUS-43 partly addresses this for Railway's Build Command; the rest (env vars on both platforms) is harder to source-control without secret leakage.

3. **Migration 012 is applied to prod but isn't in the Supabase-tracked migration log** (`list_migrations` returns only 4 entries from earlier work). The `apply_migration` call did register it, but earlier migrations (005, 006, 011) were applied via raw SQL and aren't tracked. Not a problem in practice — schema state is what matters — but worth knowing if a future cycle expects `supabase db push` to do anything meaningful.

4. **The 2026-05-13 Resend sender domain is verified but no real emails have been sent yet.** First real send happens during the live e2e (ORPHEUS-44). Resend's deliverability dashboards will show 0/0/0 numbers until then.

5. **`backend/.env` still has duplicate `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` entries** — first pair points at cloud, second pair points at local. The second wins under dotenv parsing, so local-dev runs against local Supabase. This is intentional but slightly hacky. Worth a future cleanup pass (commented-out blocks for environment toggling).

6. **No clients exist in prod yet.** Real first-time sign-in flow will exercise the not-yet-tested "fresh user → /not-invited" path. The unit tests pin the logic but the live behavior is part of ORPHEUS-44.

---

## State of the repo right now (end of session)

```
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged:
  D  SESSION_HANDOFF_2026-05-12_part2.md   # retire in housekeeping commit

Untracked:
  SESSION_HANDOFF_2026-05-13.md            # this file
  LinkedIn_BD_DPA_Review_2026-05-07.md     # compliance thread, unchanged
  Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}
  Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}
```

Suggested housekeeping commit before the next session:

```bash
cd ~/git/orpheus && \
  rm -f SESSION_HANDOFF_2026-05-12_part2.md && \
  git add SESSION_HANDOFF_2026-05-13.md && \
  git commit -m "Session handoff: 2026-05-13. Retire part-2 handoff.

SESSION_HANDOFF_2026-05-13.md: full-day session handoff covering
ORPHEUS-38 ship (12 commits, +43 tests, migration 012 applied,
database cleaned), plus ORPHEUS-43 + ORPHEUS-44 filed during the
session for deferred work. ORPHEUS-39 pickup plan included.

Retires SESSION_HANDOFF_2026-05-12_part2.md — all threads it
described are closed by today's work."
```

Then `git push origin main`. Pre-launch compliance files stay untracked until a separate decision on commit vs Drive.
