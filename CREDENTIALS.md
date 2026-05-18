# Credentials & Out-of-Repo State

Inventory of every external system Orpheus touches. **Actual secrets are not stored in this file** — only the system, the dashboard URL, and a pointer to where the credential lives.

Convention: replace `[password manager: <vault> / <item>]` placeholders with your actual reference once. Anyone with the right vault access can find the credential; this doc lets them know what to look for and where.

---

## Quick checklist for a fresh Claude session

A fresh session can verify it's wired up by:

1. Running `mcp__plane__get_projects` — should return at least the Orpheus project.
2. Running `git remote -v` — should show `git@github.com:josh-segars/orpheus.git`.
3. Reading `backend/.env` (if local-dev) — should have non-empty `SUPABASE_*`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `APP_BASE_URL`.
4. Reading `frontend/.env.local` (if local-dev) — should have non-empty `VITE_SUPABASE_*`, `VITE_API_BASE_URL`.

If any of those fail, see the corresponding section below.

---

## Anthropic

| | |
|---|---|
| **What** | API key for `claude-sonnet-4-…` model calls. Used by `backend/agents/rubric.py` and `backend/agents/narrative.py` in the pipeline. |
| **Where used** | `ANTHROPIC_API_KEY` in `backend/.env` (local) + Railway env vars (deployed). |
| **Dashboard** | https://console.anthropic.com — API Keys. |
| **Credential storage** | `[password manager: <vault> / <item>]` |
| **Team account** | Newly provisioned as of 2026-05-18. Old keys from the individual account may still be in use; check before rotating. |

---

## Plane (project management)

| | |
|---|---|
| **What** | Workspace + project hosting all ORPHEUS-N tickets, decision pages, spec pages. |
| **Workspace slug** | `orpheussocial` |
| **Project name / identifier** | `Orpheus` / `ORPHEUS` (used in commit messages: "Refs ORPHEUS-N") |
| **Workspace UUID** | `be866680-d712-4a3f-a60c-16c237d93ca7` |
| **Project UUID** | `1270ee67-f8f7-4af1-a245-32c8af50c964` |
| **Dashboard** | https://app.plane.so (sign in with the team account) |
| **MCP** | `mcp__plane__*` tools. Connected as of 2026-05-13; used heavily in every session for ticket grooming. |
| **Credential storage** | `[password manager: <vault> / <item>]` for the human login. MCP token lives in the team account's MCP-connection config. |

---

## Supabase (database + auth)

| | |
|---|---|
| **What** | Postgres database + auth (LinkedIn OIDC provider). |
| **Project ref** | `yqxuddkixzjruxtdjxpr` |
| **API URL** | `https://yqxuddkixzjruxtdjxpr.supabase.co` |
| **Dashboard** | https://supabase.com/dashboard/project/yqxuddkixzjruxtdjxpr |
| **Credentials needed** | Project DB password (for `supabase link --project-ref`), service role key (for backend), anon key (for frontend), JWT secret (for local-dev Supabase via CLI). |
| **MCP** | `mcp__eed0d52b-…-supabase__*` tools (the UUID is the connection's own — appears as `mcp__supabase__*` in the available-tools list). Used 2026-05-13 to apply migration 012 directly to prod. |
| **Credential storage** | `[password manager: <vault> / <item>]` |
| **Notes** | Migrations 003-006 are baked into the prod schema and won't show in `supabase db diff`. Migrations 007-010 are HISTORICAL — see `001_base_schema.sql` header for the fresh-DB recipe. |

---

## Railway (backend hosting)

| | |
|---|---|
| **What** | Hosts the FastAPI backend service and the worker (job processor) service. |
| **Dashboard** | https://railway.app/dashboard |
| **Account login** | `[password manager: <vault> / <item>]` |
| **Services** | Two services: backend (web), worker (background). Both deploy from `main` branch on GitHub auto-push. |
| **Env vars (set in dashboard, on BOTH services)** | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `APP_BASE_URL`, `FRONTEND_ORIGINS`, `SUPABASE_JWT_AUDIENCE`. |
| **Build command (manual)** | `pip install -r backend/requirements.txt` — set per-service in Settings → Build. Source-pin tracked as ORPHEUS-43. |
| **Backend public URL** | `https://orpheus-production-5082.up.railway.app` (subject to change if service is recreated) |

---

## Vercel (frontend hosting)

| | |
|---|---|
| **What** | Hosts the React frontend at the production URL. |
| **Dashboard** | https://vercel.com/dashboard |
| **Account login** | `[password manager: <vault> / <item>]` |
| **Project** | Orpheus frontend. **Root Directory = `frontend`** (must be set in Settings → General). |
| **Env vars (set in dashboard, for Production / Preview / Development)** | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_ADMIN_EMAILS`, `VITE_API_BASE_URL`. Baked into the bundle at build time. |
| **Production URL** | `https://app.orpheussocial.com` (custom domain — verify in Vercel before relying on this) |
| **SPA fallback** | `frontend/vercel.json` adds the rewrite rule Vercel's Vite preset doesn't auto-add. Required for `/login`, `/invite/*`, etc. to resolve via React Router. |

---

## Resend (transactional email)

| | |
|---|---|
| **What** | Sends invitation emails for the ORPHEUS-38 invitation flow. |
| **Dashboard** | https://resend.com |
| **Account login** | `[password manager: <vault> / <item>]` |
| **API key** | `RESEND_API_KEY` in `backend/.env` + Railway env vars. Real keys start with `re_`. Sandbox keys start with `test_` and trigger sandbox mode in `backend/email/resend_client.py` (logs the call, doesn't send). |
| **Verified sender domain** | `[fill in once verified]` |
| **First real send** | Pending — deliverability dashboards show 0/0/0 until ORPHEUS-44 runs. |

---

## LinkedIn Developer (OIDC provider)

| | |
|---|---|
| **What** | OAuth provider for client + advisor sign-in (LinkedIn OIDC, `openid profile email` scopes). |
| **Dashboard** | https://www.linkedin.com/developers/apps |
| **Apps needed** | Two: one dev app (callback `http://127.0.0.1:54321/auth/v1/callback`), one prod app (callback `https://yqxuddkixzjruxtdjxpr.supabase.co/auth/v1/callback`). |
| **Credentials needed** | Client ID + Primary Client Secret per app. Pasted into Supabase Auth → Providers → LinkedIn OIDC. |
| **Credential storage** | `[password manager: <vault> / <item>]` (one entry per app) |
| **Local-dev env vars** | `SUPABASE_AUTH_EXTERNAL_LINKEDIN_OIDC_CLIENT_ID`, `SUPABASE_AUTH_EXTERNAL_LINKEDIN_OIDC_SECRET` in `backend/.env`. Interpolated into `supabase/config.toml` at `supabase start`. |
| **Notes** | The cloud-Supabase prod LinkedIn provider is **not yet configured** — that's ORPHEUS-25, which blocks ORPHEUS-44 (the live e2e). |

---

## GitHub

| | |
|---|---|
| **What** | Source repository + GitHub Actions CI/CD. |
| **Repo** | `git@github.com:josh-segars/orpheus.git` |
| **Branch policy** | `main` is the only branch. Direct push from `main` deploys backend (Railway) and frontend (Vercel). |
| **SSH key** | `[password manager: <vault> / <item>]` if needed for new machine setup. Recommend `ssh-keygen -t ed25519` + add to GitHub account. |
| **Account login** | `[password manager: <vault> / <item>]` |
| **MCP** | None currently. CLI access via the workspace `bash` tool; SSH egress is blocked from the sandbox, so `git push` must happen from Josh's terminal. |

---

## Anthropic Plane / Cowork (this Claude account)

| | |
|---|---|
| **What** | The Claude team account itself — Cowork / Claude Code subscription. |
| **Dashboard** | https://claude.ai (sign in with team email) |
| **Account login** | `[password manager: <vault> / <item>]` |
| **MCPs to connect on a fresh setup** | Plane, Supabase, Resend (optional — backend wraps Resend's REST API directly), GitHub (optional), workspace `bash`, Claude in Chrome. See `CLAUDE.md` "First-session quickstart" for the full expected list with one-line descriptions. |
| **Skills to install** | The `anthropic-skills` pack (pdf, docx, xlsx, pptx, schedule, setup-cowork, skill-creator). |

---

## Other / future

| System | Purpose | Status |
|---|---|---|
| **Stripe** | Self-serve billing (post-beta — ORPHEUS-40) | Not provisioned yet. Account creation deferred until ORPHEUS-40 picks up. |
| **PagerDuty / OpsGenie** | On-call alerting | Not provisioned. Single-engineer project, manual monitoring for now. |
| **Sentry / error tracking** | Backend error tracking | Not provisioned. Railway logs + Supabase logs are the current ground truth. |
| **Analytics / product telemetry** | Client behavior tracking | Not provisioned. Product is currently outcome-measured by Andrew, not telemetered. |
| **Domain registrar** | `orpheussocial.com` ownership | `[fill in registrar — Namecheap / Cloudflare / etc.]` |

---

## Conventions for adding a new external system

When you add a new external system to the project:

1. Add a section to this file with the same five-row template (What / Where used / Dashboard / Credentials / Notes).
2. If it's added to `.env`, also add an entry to `backend/.env.example` or `frontend/.env.local.example` with an inline comment.
3. If it ships secrets that must be set in deploy dashboards, add a note under the Railway / Vercel section above.
4. If it has an MCP integration, add it to the "MCPs to connect" list in `CLAUDE.md`'s "First-session quickstart" section.
5. Commit this file with a `Refs ORPHEUS-N` tag if it's tied to a ticket.
