# Decision: LinkedIn Auth (2026-04-21)

> **Draft — for Josh's review before publishing to Plane.**
> Category: `Decision`. Target Plane page name: `Decision: LinkedIn Auth (2026-04-21)`.

## Summary

Clients authenticate into the Orpheus portal via **Supabase Auth with the LinkedIn (OIDC) provider**, using only identity scopes (`openid profile email`). No passwords, no email fallback, no additional providers in this phase. Advisor (Andrew's) authentication is out of scope for this decision and will be handled separately.

## Context

The frontend currently redirects the root path to a seeded demo job (`/jobs/demo`) and the backend has only a `/health` endpoint — there is no auth, no user model, and no isolation between clients. Before Andrew delivers live engagements we need a login flow that routes each client to their own data.

Clients are senior executives. They are low-friction-tolerant and will not create passwords, wait for magic-link emails, or download authenticator apps. Every target client has a LinkedIn account. Supabase (which we already use for the jobs queue and scoring data) ships a native LinkedIn (OIDC) provider.

## Decision

1. Clients sign in via `supabase.auth.signInWithOAuth({ provider: 'linkedin_oidc' })`.
2. Supabase manages the OAuth handshake, issues a JWT, and maintains a session in browser storage.
3. The FastAPI backend verifies Supabase JWTs on each request via a `get_current_client` dependency and executes queries through a user-scoped Supabase client so row-level-security policies apply.
4. Business data lives in `public.clients`, keyed on `auth.users.id`. A trigger populates the row on first login.
5. Sign-up is **fully self-serve**: any client who arrives at `/login` and authenticates successfully with LinkedIn (OIDC) gets a `clients` row created for them. No pre-populated invitation stubs. Andrew distributes the portal URL privately.
6. Clients whose LinkedIn response includes `email_verified = false` are **blocked at the gate**. We require a verified LinkedIn email before a `clients` row is usable.
7. Andrew gets a **minimal `/admin` page in the same React app** as a stopgap — email-allowlisted, no separate auth path. Covers his near-term operational needs (review clients, inspect jobs, edit narratives) until the separate advisor-auth decision lands.

## Non-Goals

- **LinkedIn data APIs / archive automation.** The ZIP archive and Analytics XLSX upload flow in Groundwork stays manual. LinkedIn no longer exposes the scopes required to pull a member's full activity history for non-partner apps.
- **Advisor authentication.** Deferred. Likely a separate decision covering role-based access, an admin dashboard, and whether to use Supabase Auth with a staff role or a separate mechanism.
- **Multi-advisor / multi-tenant.** The design is single-practice. A multi-advisor model would add an `advisors` table and an `advisor_id` foreign key on `clients`; that can be added later without breaking this design.
- **Additional providers.** No Google, no email magic-link, no password. If a client cannot sign in with LinkedIn they cannot use the portal in this phase.

## Alternatives Considered

**Email magic-link only.** Lower-friction in theory but higher in practice for executives: inbox delays, spam filters, assistants gating email. Rejected primarily on UX; every target client has a LinkedIn account.

**Google OAuth.** Many senior execs have personal Gmail accounts they would not want tied to their professional presence. LinkedIn is the account that matches the product's professional framing.

**Custom LinkedIn OAuth in FastAPI.** More portable and more work. We would maintain the callback handshake, state parameter validation, token rotation, and JWT signing — all of which Supabase Auth provides for free. Portability cost is only incurred if we ever leave Supabase; revisit then.

**Supabase Auth with LinkedIn + email magic-link as fallback.** Reasonable, but adds surface area (two sign-in paths to test, two account-recovery stories, possible account linking) before we have live clients to learn from. Can be added in a follow-up if we hit a client who refuses LinkedIn.

## Architecture

Sequence of a client's first login:

1. Client lands on `/login` (new page). Single "Continue with LinkedIn" button.
2. Click → frontend calls `supabase.auth.signInWithOAuth({ provider: 'linkedin_oidc', options: { redirectTo } })`.
3. Supabase redirects to `linkedin.com/oauth/v2/authorization?...` with `openid profile email`.
4. Client authorizes (if they haven't already granted the Orpheus app consent).
5. LinkedIn redirects to Supabase's callback URL with the auth code.
6. Supabase exchanges code for tokens, fetches OIDC userinfo, upserts a row in `auth.users`, issues a Supabase JWT, and redirects the client back to the configured `redirectTo`.
7. First-time login fires the `on_auth_user_created` trigger, which inserts a row into `public.clients`.
8. Frontend rehydrates session from storage, reads client info, and renders the Groundwork Checklist.

Subsequent requests:

- Frontend attaches the Supabase JWT to `Authorization: Bearer` headers when calling the FastAPI backend.
- Backend's `get_current_client` dependency verifies the JWT (RS256, public keys from Supabase JWKS), extracts `sub` (which is the `auth.users.id`), fetches the matching `public.clients` row, and hands both down to the route handler.
- Backend executes Supabase queries via a user-scoped client configured with the same JWT so RLS policies see `auth.uid() = <client_id>`.

## Data Model

**`auth.users`** — managed by Supabase. Relevant fields Supabase stores for us:
- `id uuid` (primary key) — same value we use as `public.clients.id`.
- `email`, `email_confirmed_at` — email and verification status from LinkedIn.
- `raw_user_meta_data jsonb` — contains `name`, `picture`, `given_name`, `family_name` from the LinkedIn userinfo response.
- `raw_app_meta_data jsonb` — `provider = 'linkedin_oidc'`, `providers = ['linkedin_oidc']`.

**`public.clients`** — new app-owned table. Seeded with every OIDC field LinkedIn makes available under `openid profile email`.

| column | type | notes |
| --- | --- | --- |
| `id` | `uuid` | PK, FK → `auth.users(id)` `on delete cascade` |
| `linkedin_sub` | `text` | LinkedIn member URN (OIDC `sub`). Stable even if email changes |
| `display_name` | `text` | From OIDC `name`; advisor can override |
| `given_name` | `text null` | From OIDC `given_name` |
| `family_name` | `text null` | From OIDC `family_name` |
| `profile_picture_url` | `text null` | From OIDC `picture`; advisor can override |
| `locale` | `text null` | From OIDC `locale` (e.g. `en-US`) |
| `groundwork_completed_at` | `timestamptz null` | Existing flow marker |
| `created_at` | `timestamptz` | `default now()` |
| `updated_at` | `timestamptz` | `default now()`; touched on profile refresh |

Email is **not** duplicated on `clients` — it lives on `auth.users.email` and we read it from the JWT claims or a join. Advisor-editable fields (`display_name`, `profile_picture_url`) are separate from the LinkedIn-sourced values so a profile refresh doesn't clobber manual edits; we can split those out in a follow-up schema step if and when that's needed.

Trigger `on_auth_user_created` (executes after insert on `auth.users`) populates the `clients` row from `raw_user_meta_data` and `raw_app_meta_data`. The trigger also enforces the email-verified gate: if `email_confirmed_at IS NULL`, the `auth.users` row is deleted in the same transaction and an exception raised, producing a clean failure for the frontend to catch.

Fields **not available** via OIDC scopes (`headline`, `about`, current `position`, `company`, `industry`, `location`, vanity URL, etc.) stay where they already live — either advisor-entered during Groundwork curation or extracted from the uploaded ZIP archive. Making any of those available at login would require LinkedIn partner scopes we've ruled out as a non-goal.

**`public.jobs`** — existing. Add FK: `jobs.client_id references public.clients(id) on delete cascade`. Confirm current type matches.

**RLS policies** (new):

- `public.clients` — `select` and `update` where `id = auth.uid()`. No `insert` from clients (trigger only). No `delete` from clients (account-deletion flow TBD).
- `public.jobs` — `select` where `client_id = auth.uid()`. `insert` via API only with `client_id = auth.uid()`. No client `update` / `delete` (job state machine is server-owned).
- `public.ingested_data`, `public.scores`, `public.narratives` — `select` via join-through to `jobs.client_id = auth.uid()`. No client writes.
- Worker uses the Supabase service-role key, bypassing RLS; no change needed.

## Frontend Changes

- Add `@supabase/supabase-js` dependency (no other new deps).
- New `src/lib/supabase.ts` — shared Supabase browser client initialized from `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
- New `src/pages/LoginPage.tsx` — simple page with the wordmark, a short explainer sentence, and a single "Continue with LinkedIn" button. Surfaces a clear error message if LinkedIn returned an unverified email (blocked at the auth gate). Follows existing design system (Source Serif 4, warm palette).
- New `src/lib/auth.ts` — `useSession()` hook wrapping `supabase.auth.onAuthStateChange`. React Query integration.
- `src/App.tsx` — replace the `Navigate to /jobs/demo` default with a protected-route wrapper that redirects unauthenticated users to `/login` and, once authenticated, routes them to `/jobs/:jobId` where `jobId` is resolved server-side from `auth.uid()`.
- `src/components/layout/PortalNav.tsx` — show the signed-in client's name + picture in the right-hand area, with a sign-out dropdown. Replace the current hardcoded "Jane Doe" literal.
- `src/lib/apiClient.ts` — attach `Authorization: Bearer <supabase access token>` to every outgoing request.
- Remove the MSW demo-job fallback from `src/mocks/handlers.ts` for authenticated routes; keep only for unauthenticated dev playgrounds.

### Minimal `/admin` page (advisor stopgap)

Lives inside the same React app, under the same Supabase session. Not a separate auth path.

- New `src/pages/AdminPage.tsx` at `/admin`. Gated by checking whether the signed-in user's email is in an allowlist sourced from `VITE_ADMIN_EMAILS` (comma-separated). Non-allowlisted users are redirected to their own Signal Score.
- Surface area for v1: a table of clients (name, email, joined date, Groundwork status, latest job state, link to their Signal Score) and an inline narrative editor that updates `public.narratives`.
- Calls backend endpoints that use a separate admin-scoped dependency (`get_current_admin`) — same JWT verification as clients plus an allowlist check server-side (belt-and-braces; the frontend allowlist alone is not a security boundary).
- Explicitly a stopgap: no role model, no audit log, no delegation. Designed to be replaced cleanly by the separate advisor-auth decision without leaving orphaned code.

## Backend Changes

- Add `PyJWT` and `cryptography` to `requirements.txt` for RS256 JWT verification.
- New `backend/auth.py` — two FastAPI dependencies:
  - `get_current_client` verifies JWT signature against Supabase JWKS (cached), extracts `sub`, fetches `public.clients` row via service-role client, raises 401 if missing, returns a `CurrentClient(user_id, client_id, email)` value object.
  - `get_current_admin` runs the same JWT verification and then additionally checks the email against an `ADMIN_EMAILS` allowlist in env. Raises 403 if not an admin.
- New `backend/db.py` pattern (if not already present) — `user_scoped_supabase(access_token)` returns a Supabase client configured with the user's JWT so RLS applies.
- New `backend/routers/` directory (per CLAUDE.md convention):
  - `jobs.py` — `/jobs/{id}` endpoint the frontend already expects. Depends on `get_current_client`.
  - `admin.py` — `/admin/clients`, `/admin/jobs`, `/admin/narratives/{id}` endpoints for the stopgap advisor page. Depends on `get_current_admin`. Uses service-role client to bypass RLS intentionally.
- Register the routers in `backend/main.py`.
- Tighten CORS: replace `allow_origins=["*"]` with the frontend origin(s) from settings.

## Development Environment

Two Supabase environments, isolated:

- **Local (dev).** Supabase CLI + Docker on your machine. `supabase start` brings up Postgres + Studio + GoTrue + the rest locally. Migrations run via `supabase db push`. The LinkedIn provider is configured in `supabase/config.toml` and points at a separate LinkedIn Developer "dev" app with `localhost` callback URLs. Zero cloud cost, works offline, safe to drop and reseed.
- **Cloud (prod).** One Supabase project hosted on supabase.com. Migrations promoted from local via `supabase db push --linked`. LinkedIn provider points at the production LinkedIn Developer app.

Staging as a third environment is explicitly not set up — we don't need it at this stage, and promoting directly from local dev to a cloud prod is simpler. If that ever hurts we can add Supabase Branching (Pro-tier feature) without reworking the dev setup.

Prereqs for the first developer onboarding:

1. Install Docker Desktop.
2. `npm i -g supabase` (or Homebrew / scoop depending on platform).
3. `supabase start` in the repo root — populates the local Supabase instance.
4. Copy the printed anon/service-role keys into `frontend/.env.local` and `backend/.env`.

## Supabase Cloud (prod) Dashboard Changes (Josh)

Manual operations in the production Supabase dashboard:

1. **Authentication → Providers → LinkedIn (OIDC)** — enable, paste `Client ID` and `Client Secret` from the production LinkedIn Developer app.
2. **Authentication → URL Configuration** — set the site URL to the production frontend origin and add the production redirect URL only. (Localhost URLs live on the local Supabase instance, not the cloud one.)
3. **Authentication → Email** — confirm "Confirm email" is **off** (LinkedIn OIDC provides `email_verified`, no need for our own confirmation).
4. **Project Settings → API** — capture `anon` key for the production `VITE_SUPABASE_ANON_KEY`.

## LinkedIn Developer Portal Changes (Josh)

Two LinkedIn apps — one for dev (callback to local Supabase), one for prod (callback to cloud Supabase). Same setup steps for each.

1. Create a LinkedIn app at `linkedin.com/developers`.
2. Under **Products**, request access to **Sign In with LinkedIn using OpenID Connect** (auto-approved).
3. Under **Auth → OAuth 2.0 settings**, add the appropriate callback URL:
   - Dev: `http://127.0.0.1:54321/auth/v1/callback` (Supabase CLI's default local port).
   - Prod: `https://<project>.supabase.co/auth/v1/callback`.
4. Confirm scopes `openid`, `profile`, `email` are available.
5. Note each `Client ID` and `Client Secret` — dev goes in `supabase/config.toml`, prod into the cloud Supabase dashboard.

## Migration Plan

Phased so each step is independently reviewable and revertable.

1. **Local Supabase + dev LinkedIn app** (Josh). Install Docker + Supabase CLI, `supabase start`, create the dev LinkedIn app, wire the config. Unblocks local development.
2. **Cloud Supabase + prod LinkedIn provider config** (Josh, dashboard). Mirrors step 1 against the production project. Can happen in parallel with steps 3–5.
3. **`clients` table migration** (`007_clients_table.sql`). Creates `public.clients`, the `on_auth_user_created` trigger (including the `email_confirmed_at` verification gate), and FK on `jobs.client_id`. RLS policies disabled initially.
4. **Backend auth dependency + `/jobs/{id}` router**. Wire `get_current_client`, add the router, keep RLS off for now so we can test incrementally.
5. **Frontend: Supabase client + LoginPage + protected route wrapper**. At this point a user can actually log in end-to-end; the backend still answers for any authenticated user regardless of ownership. Surfaces the unverified-email error.
6. **Enable RLS policies** (`008_rls_enable.sql`). Gates access; must be deployed together with a backend using the user-scoped client pattern.
7. **PortalNav signed-in state + sign-out**. Polish pass.
8. **Backend admin router + `/admin` frontend page**. Stopgap advisor UI (email-allowlisted). Can ship after step 6 whenever Andrew's operational need first surfaces.
9. **Tighten CORS and env validation**. Production-readiness pass.

## Security & Privacy Considerations

- **HTTPS only in production.** Enforced via Supabase / Vercel / Railway defaults.
- **Token storage.** Supabase defaults to browser `localStorage`. Acceptable for this threat model (no high-value financial transactions). Noted in case we later add device-trust or session-binding.
- **Email verification gate.** `on_auth_user_created` trigger requires `email_confirmed_at IS NOT NULL` (populated by Supabase from LinkedIn's `email_verified` claim). Unverified sign-ins fail closed — the trigger deletes the orphan `auth.users` row in the same transaction and the frontend surfaces a clear error.
- **Self-serve surface area.** Anyone with a verified LinkedIn account who discovers the portal URL can create a `clients` row. Andrew distributes the URL privately; this is the access-control boundary. If that becomes insufficient we can add an allowlist migration later without rewriting the auth path.
- **Account deletion.** Hard cascade: Supabase admin API deletes the `auth.users` row → `clients` row cascades → all `jobs`, `ingested_data`, `scores`, `narratives` cascade. The Signal Score "durable record" principle (from CLAUDE.md) applies to the client's copy of the deliverable, which Andrew retains out-of-band as a PDF. No server-side retention after deletion.
- **Admin page.** The advisor `/admin` stopgap relies on an email allowlist in both the frontend (UX gate) and backend (`get_current_admin` dependency). The server check is the real boundary; the frontend check is purely to avoid flashing the wrong UI. Allowlist lives in env, not committed to the repo.
- **PII handling.** Name, email, picture, given/family name, and locale from LinkedIn are PII and stored on Supabase (region per the production project). LinkedIn archive data already contains richer PII; the authentication layer does not change the privacy posture meaningfully.

## Resolutions (2026-04-21 review)

The six open questions from the first draft were resolved in a review pass with Josh. Captured here for the record:

1. **Invitation model — fully self-serve.** No pre-populated stub rows. Andrew distributes the portal URL privately; any client who successfully authenticates with LinkedIn gets a `clients` row. No `invited_email` column.
2. **Verification gate — block unverified emails.** If LinkedIn returns `email_verified = false`, the `on_auth_user_created` trigger raises and the `auth.users` row is deleted in the same transaction. Frontend surfaces a friendly error.
3. **Advisor access stopgap — minimal `/admin` page.** Email-allowlisted page in the same React app, backed by a `get_current_admin` dependency. Explicitly a stopgap until the separate advisor-auth decision lands; designed to be replaced cleanly.
4. **Account deletion — hard-cascade.** Delete `auth.users` → cascade to `clients` → cascade to `jobs` and dependents. Signal Score durability is preserved via Andrew's out-of-band PDF copy, not server-side retention.
5. **Profile seeding — as much as OIDC scopes allow.** `name`, `given_name`, `family_name`, `picture`, `locale` all seeded into `clients` on first login. Richer fields (headline, company, etc.) are not available via `openid profile email` and stay with the existing advisor-entered / ZIP-extracted path.
6. **Environments — local Supabase (Docker) for dev + single cloud project for prod.** No staging tier. Two LinkedIn Developer apps (dev + prod), one Supabase cloud project, local Supabase via CLI on each developer's machine.

## Plane Tickets (proposed)

Drafted as sibling tickets under the Orpheus project — I'll create them only after you confirm this plan.

1. `Local Supabase + dev LinkedIn app setup` — Josh: Docker, Supabase CLI, local `config.toml`, dev LinkedIn Developer app. Unblocks local dev.
2. `Cloud Supabase + prod LinkedIn provider configuration` — Josh: production Supabase dashboard + prod LinkedIn Developer app. Can run parallel to 3–5.
3. `Schema: clients table + trigger + FK on jobs` — migration `007_clients_table.sql`, including the `email_confirmed_at` verification gate.
4. `Backend: JWT verification dependency + jobs router` — new `backend/auth.py` and `backend/routers/jobs.py`.
5. `Frontend: Supabase browser client + LoginPage + protected route wrapper`. Ends with a working local sign-in flow.
6. `Schema: RLS policies on clients, jobs, ingested_data, scores, narratives` — migration `008_rls_enable.sql`.
7. `Frontend: PortalNav signed-in state + sign-out`.
8. `Backend + Frontend: /admin stopgap (email-allowlisted)` — `backend/routers/admin.py` + `src/pages/AdminPage.tsx`. Sequenceable after step 6; ship when Andrew's operational need first surfaces.
9. `Security: CORS allowlist + env validation`.

## Deferred / Follow-ups

- Advisor authentication — separate decision.
- Multi-advisor model.
- LinkedIn data API exploration (if LinkedIn ever re-opens scopes).
- Account linking (if we later add email / Google).
- Session binding / device trust (if threat model changes).
