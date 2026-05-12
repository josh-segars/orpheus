# Spec: Invitation Flow (2026-05-12)

> **Source:** scoping pass for **ORPHEUS-38** done 2026-05-12.
> Companion to `Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md`.
> Target Plane page name: `Spec: Invitation Flow (2026-05-12)`.

## Summary

ORPHEUS-38 implements the advisor-managed invitation flow end-to-end. Three new backend endpoints, one new transactional-email integration (Resend), one new auth-resolver variant (allows neither-role for the pre-acceptance state), two new frontend pages, and one new error UI for the typed "not invited" state.

This is the third ticket of the four-ticket beta chain (36 ✅ → 37 ✅ → **38** → 39).

## Acceptance criteria

Verbatim from the ticket:

1. Resend integration wired in, sandbox-mode test confirms emails send successfully.
2. Three backend endpoints live; `pytest backend/` covers the happy path + email mismatch + expired token + replay (already-accepted token) cases.
3. `/invite/:token` + `/invite/callback` frontend pages live; manual walk: invite → click email link → LinkedIn sign-in → land in portal.
4. Mismatch confirmation UI renders correctly when invitation email differs from LinkedIn email.
5. Error page renders when sign-in resolves to neither role.

Plus a self-imposed criterion: `GET /session` ships in this ticket so the frontend has a clean way to detect the "not invited" state (instead of probing through individual API calls).

## Locked decisions

From the scoping pass:

- **Email from-line:** `Orpheus Social <hello@orpheussocial.com>`.
- **Invite-link host:** `https://app.orpheussocial.com` (Vercel custom domain wired during the scoping pass, cert auto-issued).
- **Resend:** account active, `orpheussocial.com` domain verified (SPF + DKIM + MX + DMARC records added at GoDaddy 2026-05-12). API key `orpheus-prod` generated; stored in `backend/.env` as `RESEND_API_KEY`.
- **Test strategy:** mock the Resend HTTP wrapper in pytest. Single manual e2e walkthrough is the only real-network send during this ticket.
- **`GET /session` ships in this ticket** (not deferred to ORPHEUS-39 as originally framed).
- **Token generation:** Python-side `uuid.uuid4()` in the invite handler. DB column has no default — backend owns the value.
- **Token expiry:** 14 days. Configurable via `INVITATION_EXPIRY_DAYS` in `backend.config` so we can shorten in the future without code change.
- **Email comparison:** case-insensitive via `.strip().lower()` on both sides. Trailing-space typos don't trigger soft-confirmation noise.
- **Re-invite resets `invitation_status`** from `expired` (or `pending`) back to `pending`. Same atomic update writes new token + expiry + status.
- **Replay of already-accepted token:** 200 with the existing `client_id` if `user_id` matches the caller; 401 otherwise. Returning-user clicking an old email link lands cleanly; a different user claiming an accepted invite is rejected.
- **Duplicate-invite pre-check:** `POST /clients/invite` returns 409 if a `clients` row already exists for the same `advisor_id` + lowercased email. Prevents ghost rows from advisors retrying the form.
- **Router file:** single new `backend/routers/clients.py` holds all three invite endpoints. `GET /session` lives in its own `backend/routers/session.py` (it's not a clients-resource concern).
- **Resend sandbox mode in dev:** if `RESEND_API_KEY` starts with `test_` or is the literal `test`, the wrapper logs the would-be email and returns a fake message id without making a network call. Keeps local dev and CI offline + deterministic.

## Prerequisites

- **Migration 012 NOT YET applied to prod.** Adds `invitation_token` + `invitation_expires_at` columns + the partial unique index. Apply via Supabase MCP `execute_sql` just before the manual e2e (commit #11). Pre-checked clean via dry-run on 2026-05-12.
- **`backend/.env` updated:** `RESEND_API_KEY=re_...` and `APP_BASE_URL=https://app.orpheussocial.com`. Both are required-at-boot in the new `backend.config`.
- **`https://app.orpheussocial.com` is live and serving the React app over HTTPS.** Verified 2026-05-12.

## Auth-resolver refactor (small but required upfront)

`get_current_session_roles` (ORPHEUS-37) raises 401 if neither role exists. That's wrong for two endpoints in this ticket:

- `POST /accept-invitation` — a freshly-signed-in user with no `clients` row yet (the invitation hasn't been accepted) needs to be able to call this endpoint to convert into a client.
- `GET /session` — the whole point is to return `{advisor_id: null, client_id: null}` so the frontend can route the user to `/not-invited`.

Refactor approach (commit #1 of the ticket):

```python
# backend/auth.py

async def _resolve_session(
    authorization: str | None, *, allow_no_roles: bool
) -> SessionRoles: ...
    # shared JWT verification + two role-table SELECTs

async def get_current_session_roles(
    authorization: str | None = Header(default=None),
) -> SessionRoles:
    return await _resolve_session(authorization, allow_no_roles=False)

async def get_verified_session(
    authorization: str | None = Header(default=None),
) -> SessionRoles:
    return await _resolve_session(authorization, allow_no_roles=True)
```

`get_current_session_roles` keeps its existing behavior (raises on neither). The new `get_verified_session` returns a `SessionRoles` instance with both role fields `None` in the no-roles case. Existing token-verification edge cases still raise 401 in both variants.

Tests: add `test_verified_session_allows_no_roles` + reuse most of the existing fixtures.

## Commit plan

Commit-by-commit. Each commit is self-contained and reviewable in isolation; the chain compiles and tests pass at every boundary.

### Commit 1 — Config + auth-resolver split

**Files:**
- `backend/config.py` — add `resend_api_key` (required), `app_base_url` (required, http(s)-validated), `invitation_expiry_days` (default 14).
- `backend/.env.example` — document both new vars with inline comments.
- `backend/auth.py` — extract `_resolve_session`, add `get_verified_session`.
- `backend/tests/test_config.py` (new) — verify boot fails fast on missing `RESEND_API_KEY` / `APP_BASE_URL`; verify `APP_BASE_URL` URL validator rejects bare strings.
- `backend/tests/test_auth.py` — add `test_verified_session_allows_no_roles` + 2–3 supporting tests confirming JWT-verification edge cases still raise even on the verified variant.

**Tests added:** 4–5.

### Commit 2 — Resend client wrapper

**Files:**
- `backend/email/__init__.py` (empty, package marker).
- `backend/email/resend_client.py` — `EmailSendError` exception; `send_invitation_email(to_email, advisor_name, invite_url) -> str` returns Resend message id; HTTP POST via `urllib.request` (same pattern auth.py's JWKS fetch uses — no new dep).
- Sandbox mode: when `RESEND_API_KEY` starts with `test_` or is literal `test`, log the would-be email and return a deterministic fake id (`test_msg_<uuid4>`).
- `backend/tests/test_resend_client.py` (new) — mock `urllib.request.urlopen`, cover happy path, 4xx response (raises `EmailSendError`), 5xx response (raises), network exception (raises), sandbox mode (no network, returns fake id).

**Tests added:** 5.

### Commit 3 — Email template

**Files:**
- `backend/email/templates.py` — `INVITATION_EMAIL_SUBJECT`, `format_invitation_email(advisor_name, invite_url) -> (subject, html, text)`. Plain HTML + text variants; no images in v1.
- Subject draft: `"{advisor_name} invited you to a Strategic Presence Diagnostic"`. Body content per the decision page §First-time sign-in §2.
- `backend/tests/test_email_templates.py` (new) — snapshot-style tests that pin the subject + key body strings (advisor name + invite URL appear; greeting line; CTA).

**Tests added:** 3.

(Could be merged into commit 2 if you want fewer commits. Splitting it isolates the visual design pass from the wire-up plumbing.)

### Commit 4 — POST /clients/invite

**Files:**
- `backend/routers/clients.py` (new) — `InviteClientRequest(display_name, email)` + `InviteClientResponse(client_id)` Pydantic models. `@router.post("/clients/invite")` handler.
- Depends on `get_current_session_roles`; raises 403 if not `is_advisor()`.
- 409 pre-check: `SELECT 1 FROM clients WHERE advisor_id = roles.advisor_id AND lower(email) = lower(:input)`.
- INSERT with `invitation_token = uuid4()`, `invitation_expires_at = now() + N days`, `invitation_status = 'pending'`, `user_id = NULL`.
- Build `invite_url = f"{settings.app_base_url}/invite/{token}"`.
- Look up advisor display-name (first try `practice_name`, fall back to `email`).
- Call `send_invitation_email(...)`. If it raises, log loudly and return 502 with detail "Failed to send invitation email; the client row was created so you can resend." (We keep the row — the advisor can resend via the dedicated endpoint.)
- Return `{ client_id }`.
- `backend/tests/test_clients_invite.py` (new) — happy path, 403 (client-only), 403 (no roles, since the route requires `is_advisor()`), 409 (duplicate per-advisor), 502 (Resend raises).
- `backend/main.py` — `include_router(clients_router.router)`.

**Tests added:** 5.

### Commit 5 — POST /accept-invitation

**Files:**
- `backend/routers/clients.py` (extended) — `AcceptInvitationRequest(token, confirmed=False)` + `AcceptInvitationResponse(client_id, requires_confirmation, invitation_email?, linkedin_email?)`.
- Depends on `get_verified_session` (allow neither-role, since the user has no `clients` row yet).
- Service-role SELECT by token. 401 if no row.
- 401 if `invitation_expires_at < now()` and `invitation_status != 'accepted'`.
- If `invitation_status == 'accepted'`:
  - `clients.user_id == roles.user_id` → 200 with the existing `client_id` (idempotent replay).
  - Otherwise → 401 (different user trying to claim a token that was already used).
- Compute `mismatch = invitation.email.strip().lower() != roles.email.strip().lower()`. If `mismatch and not request.confirmed`, return 200 with `requires_confirmation=True, invitation_email=invitation.email, linkedin_email=roles.email`.
- UPDATE: `user_id = roles.user_id, invitation_status = 'accepted', invitation_token = NULL, invitation_expires_at = NULL`.
- Return `{ client_id, requires_confirmation: false }`.
- `backend/tests/test_accept_invitation.py` (new) — happy path no-mismatch, mismatch returns `requires_confirmation`, mismatch + confirmed accepts, expired token 401, unknown token 401, replay-by-same-user idempotent 200, replay-by-different-user 401.

**Tests added:** 7.

### Commit 6 — POST /clients/{id}/resend-invitation

**Files:**
- `backend/routers/clients.py` (extended) — `@router.post("/clients/{client_id}/resend-invitation")`.
- Depends on `get_current_session_roles`; raises 403 if not `is_advisor()`.
- SELECT by `id = :client_id AND advisor_id = roles.advisor_id`. 404 if no row. (No leak about advisor mismatch — same response as "no such client".)
- 409 if `invitation_status == 'accepted'`. Resending would orphan the accepted state; advisor should use a different flow if they want to revoke + re-invite.
- UPDATE: new `invitation_token = uuid4()`, new `invitation_expires_at = now() + N days`, `invitation_status = 'pending'`.
- Send email via Resend. If it raises, return 502 with detail "Failed to send the new invitation email; the token has been refreshed so you can try again." (Token is already rotated regardless; the new email is the recovery action.)
- Return `{ client_id }`.
- `backend/tests/test_resend_invitation.py` (new) — happy path, 403 (client-only), 404 (wrong advisor), 404 (unknown client id), 409 (already accepted), 502 (Resend raises).

**Tests added:** 6.

### Commit 7 — GET /session

**Files:**
- `backend/routers/session.py` (new) — `SessionResponse(user_id, email, advisor_id, client_id)`. `@router.get("/session")` depends on `get_verified_session`; returns the dataclass as a Pydantic model. 200 in all cases (including neither-role).
- `backend/main.py` — `include_router(session_router.router)`.
- `backend/tests/test_session.py` (new) — advisor-only, client-only, both, neither (200 with both role fields null), 401 on missing/invalid token.

**Tests added:** 5.

### Commit 8 — Frontend /invite/:token page

**Files:**
- `frontend/src/pages/InviteLandingPage.tsx` (new) — read `:token` from route params, `sessionStorage.setItem('pendingInvitationToken', token)`, then `signInWithLinkedIn(<APP_BASE_URL>/invite/callback)`. No useful UI — just a transient "Redirecting to LinkedIn…" state.
- `frontend/src/App.tsx` — public route `/invite/:token` rendering `InviteLandingPage`, NO `ProtectedRoute` wrapper.

**Tests added:** 0 (manual e2e covers; React component is mostly side-effects).

### Commit 9 — Frontend /invite/callback page + accept-invitation hook

**Files:**
- `frontend/src/hooks/useAcceptInvitation.ts` (new) — React Query mutation calling `POST /accept-invitation` via `apiClient`. Typed response.
- `frontend/src/pages/InviteCallbackPage.tsx` (new) — on mount, read token from `sessionStorage`, call the accept mutation. Three states:
  1. Loading → "Finalizing your invitation…"
  2. `requires_confirmation` → render `EmailMismatchConfirmation` card with Continue / Cancel buttons. Continue re-calls accept with `confirmed: true`.
  3. Success → clear `sessionStorage`, redirect to `/`.
  4. Error → typed error page (sign-out + retry CTA).
- `frontend/src/components/EmailMismatchConfirmation.tsx` (new) — card UI: invitation-email and linkedin-email displayed prominently; Continue / Cancel; Cancel signs out and routes to `/login`.
- `frontend/src/App.tsx` — public route `/invite/callback`, NO `ProtectedRoute`. The page handles its own session state (the user IS authenticated post-OAuth, but has no business-row yet).

**Tests added:** 0 (manual e2e + visual review).

### Commit 10 — Frontend "neither role" error UI + session-roles routing

**Files:**
- `frontend/src/hooks/useSessionRoles.ts` (new) — React Query hook calling `GET /session`. Refetches on auth state change. Returns `{ advisor_id, client_id, email }` or null while loading.
- `frontend/src/pages/NotInvitedPage.tsx` (new) — explanation page ("Your invitation may have expired, or you signed in with a different LinkedIn account than the one you were invited under"), Sign-Out button.
- `frontend/src/App.tsx` — `ProtectedRoute` updated: after authenticated, check `useSessionRoles`. If response has neither role → redirect to `/not-invited`. Add route `/not-invited` outside `ProtectedRoute`.
- `frontend/src/lib/apiClient.ts` (optional) — if we want a typed `NotInvitedError` subclass to surface from API calls, add it here. Probably not needed since `/session` is the canonical signal.

**Tests added:** 0 (visual review).

### Commit 11 — Apply migration 012 + manual e2e

1. Apply `backend/migrations/012_clients_invitation_columns.sql` to prod via Supabase MCP `execute_sql`. Row-count check before/after; verify the partial unique index and both columns appear.
2. Restart backend (Railway redeploy on push). Restart frontend (Vercel redeploy on push). Both auto.
3. Manual e2e:
   - In a SQL tool or Plane comment, note the test invitation's expected email (Josh's, plus a LinkedIn-account email if they differ).
   - As Andrew (or a stand-in advisor), `POST /clients/invite` with `{ display_name: "Test Client", email: "<josh@…>" }` via curl or the /advisor/clients UI when it lands.
   - Receive the invitation email in inbox.
   - Click link. Confirm browser lands on `/invite/<token>` for a beat, then redirects to LinkedIn OAuth.
   - Sign in with LinkedIn.
   - Land on `/invite/callback`. If LinkedIn email differs from the invitation email, the confirmation card appears.
   - Click Continue. Land in portal (smart redirect routes to Welcome or Groundwork based on state).
   - Sanity: refresh portal; session persists.
4. Document the e2e result in the part-3 handoff or the ticket comments.

No new tests, but this is the gate for "shipping" the ticket.

### Commit 12 — CLAUDE.md updates

**Files:**
- `CLAUDE.md` — backend conventions paragraph on the invitation flow (mentions both `get_current_session_roles` and `get_verified_session`, references the new endpoints).
- Project structure tree: add `backend/email/` and the two new router files.
- Decisions Made section: stays (the self-serve + advisor invite bullet from ORPHEUS-36 covers the broader architecture; this ticket implements it, doesn't change the decision).
- Optional: a "Frontend Conventions" line about `useSessionRoles` being the canonical session-state hook.

**Tests added:** 0.

## Test inventory

- `test_config.py` (new): +2
- `test_auth.py` (extended): +3
- `test_resend_client.py` (new): +5
- `test_email_templates.py` (new): +3
- `test_clients_invite.py` (new): +5
- `test_accept_invitation.py` (new): +7
- `test_resend_invitation.py` (new): +6
- `test_session.py` (new): +5

**Total: +36 backend tests.** Brings the backend suite from 114 to ~150.

## Files touched / created

**Backend (new):**
- `backend/email/__init__.py`
- `backend/email/resend_client.py`
- `backend/email/templates.py`
- `backend/routers/clients.py`
- `backend/routers/session.py`
- 5 new test files

**Backend (modified):**
- `backend/config.py` (+3 fields, +validators)
- `backend/auth.py` (extract resolver, add `get_verified_session`)
- `backend/main.py` (register 2 routers)
- `backend/.env.example` (+2 vars documented)
- `backend/tests/test_auth.py` (+3 tests)

**Frontend (new):**
- `frontend/src/pages/InviteLandingPage.tsx`
- `frontend/src/pages/InviteCallbackPage.tsx`
- `frontend/src/pages/NotInvitedPage.tsx`
- `frontend/src/components/EmailMismatchConfirmation.tsx`
- `frontend/src/hooks/useAcceptInvitation.ts`
- `frontend/src/hooks/useSessionRoles.ts`

**Frontend (modified):**
- `frontend/src/App.tsx` (3 new routes, ProtectedRoute updated)

**Docs:**
- `CLAUDE.md` (final commit)
- `Spec_Invitation_Flow_2026-05-12.md` (this file, committed alongside commit #1)

**Database:**
- Apply `backend/migrations/012_clients_invitation_columns.sql` to prod at commit #11.

## Open items deferred to ticket time

- **Email visual design.** v1 ships plain HTML + text. After the first client sees it, do a design pass (logo, brand color, signature, footer link to ToS / Privacy when those ship).
- **Resend send-log monitoring.** Resend's dashboard is good enough for beta. No alerting needed pre-launch.
- **Stripe webhook secret.** N/A this ticket — billed for ORPHEUS-40 (post-beta).

## Watchouts

1. **No DB-level UNIQUE on `clients.user_id`.** Two advisors inviting the same person produces two rows for one auth user. Beta has one advisor; not a practical issue. Worth a partial UNIQUE in a future migration once we have multiple advisors. Flagged for the post-beta backlog.

2. **`sessionStorage` is per-tab.** If the user opens the email link in one tab and LinkedIn redirects them back into a freshly-opened tab (rare but possible), the token is gone. Mitigation: the manual e2e covers the normal path; if real users hit this, we add a fallback ("paste your invitation URL again").

3. **`/invite/callback` runs *outside* `ProtectedRoute`.** Despite the user being authenticated post-OAuth, they have no business-row yet, so `ProtectedRoute`'s session-roles check would 401-bounce them. The callback page is intentionally public and handles its own auth state.

4. **The Resend wrapper's sandbox-mode trigger is the literal API-key prefix `test_`.** Real Resend keys begin with `re_`. CI gets `RESEND_API_KEY=test_ci` injected; pytest runs offline. Local dev with a real key sends real emails — be cautious about repeated runs of the e2e script.

5. **Email mismatch confirmation when the user types nothing.** The Continue button must require an explicit click — don't auto-confirm on a timer. The confirmation is an active acknowledgment.

6. **Migration 012 hasn't been applied to prod yet.** Apply at commit #11 (right before the manual e2e), not earlier. The backend code references the columns from commit #4 onward, but the routes are unreachable without a real user in prod until 012 lands. Local dev needs 012 applied to local Supabase too — the SETUP doc should pick this up in a future tidy pass.

7. **`/clients/invite` builds advisor display-name from `practice_name`, falling back to `email`.** If we add an advisor display-name column later (the data model bakeoff in the decision page suggests it's likely), the fallback chain gets longer. Don't over-engineer this now.

8. **GET /session is called on every protected-route render** (until React Query caches it). The hook should cache aggressively — staleTime of `Infinity` post-login until the session changes. Refetch on `SIGNED_OUT` events.

9. **Resend rate limits.** Free tier: 100 emails/day, 3,000/month. Beta cohort is small enough that we won't hit either. Move to paid tier if Andrew onboards more than ~50 clients/month.

## Manual e2e checklist (commit #11)

Before:
- [ ] All commits 1–10 landed on `main` and deployed (Railway worker + Vercel frontend auto on push).
- [ ] `RESEND_API_KEY` (real `re_...` key) live on Railway env.
- [ ] `APP_BASE_URL=https://app.orpheussocial.com` live on Railway env.
- [ ] Migration 012 dry-run still clean on prod (re-run the `BEGIN; … ROLLBACK;` from ORPHEUS-36's verification).

Apply:
- [ ] Apply 012 to prod via Supabase MCP `execute_sql`.
- [ ] Verify post-shape: `invitation_token uuid`, `invitation_expires_at timestamptz`, partial unique index present.
- [ ] Backend health: `curl https://<railway-host>/health` → `{"status": "ok"}`.

E2E:
- [ ] As Andrew, hit `POST /clients/invite` with `{ display_name: "Josh Test", email: "<josh's email>" }`. Get back `{ client_id }`.
- [ ] Inbox: Resend-sent email arrives within ~30 seconds. From line reads `Orpheus Social <hello@orpheussocial.com>`. Subject + body include Andrew's name and the invite URL.
- [ ] Click the link in the email. Browser navigates to `https://app.orpheussocial.com/invite/<token>`.
- [ ] Brief "Redirecting to LinkedIn…" state, then LinkedIn OAuth.
- [ ] Sign in with Josh's LinkedIn account.
- [ ] Land on `/invite/callback`. If invitation email differs from LinkedIn email, see the mismatch confirmation card.
- [ ] Click Continue. Card disappears; redirected to portal root.
- [ ] Portal lands on `/welcome` or `/groundwork` depending on `hasSeenWelcome()` flag.
- [ ] Refresh the portal page; session persists.
- [ ] Sign out, sign back in via `/login`. Portal lands the same place.
- [ ] As Andrew, hit `POST /clients/<id>/resend-invitation`. Confirm 409 (Josh's row is now `accepted`).

Rollback plan if something breaks during e2e:
- Revert the offending commit on `main`, push, services redeploy.
- Migration 012 is forward-only structural; no need to roll it back even if code is reverted (the columns are nullable and harmless on the old code path).
