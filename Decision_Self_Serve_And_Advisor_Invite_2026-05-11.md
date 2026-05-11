# Decision: Self-Serve + Advisor Invite Flow (2026-05-11)

> **Draft — for Josh's review before publishing to Plane.**
> Category: `Decision`. Target Plane page name: `Decision: Self-serve + advisor invite flow (2026-05-11)`.

## Summary

A single LinkedIn (OIDC) login serves two entry paths into the Orpheus portal:

1. **Invited clients** click an email link from their advisor, sign in with LinkedIn, and land in their existing `clients` row. This is the only path active during beta.
2. **Self-serve users** (post-beta) click a "Sign up" button on the marketing site, sign in with LinkedIn, complete a Stripe checkout, and have their `clients` + `advisors` rows created on success.

One Supabase `auth.users` row can own up to one `advisors` row and up to one `clients` row simultaneously — they're orthogonal roles, not alternatives. Andrew, as both the advisor running a practice *and* a person who runs his own diagnostic, holds both.

This supersedes the LinkedIn-1:1 self-serve model from `Decision: LinkedIn Auth (2026-04-21)` — that decision's `on_auth_user_created` trigger and `clients.id = auth.users.id` PK constraint don't survive the advisor-managed model already in production.

## Context

Production already has an `advisors` / `clients` schema built for an advisor-managed-invite flow that pre-dates ORPHEUS-23. `clients.invitation_status` (`pending` / `accepted` / `expired`) is sitting in the schema waiting for a flow to drive it. The LinkedIn auth decision retrofitted a different conceptual model on top — self-serve LinkedIn 1:1, no advisor in the picture — which works in local dev but doesn't compose with the production schema (see `ORPHEUS-35` for the drift story).

The product reality is closer to the production schema than the LinkedIn auth doc imagined: Andrew runs a practice, invites senior executive clients individually, manages their diagnostic. Self-serve is a future addition, not the primary entry path. Both flows need LinkedIn for verified professional identity; both need to coexist with one shared Supabase `auth.users` row per person.

## Decision

1. **Two entry paths, one auth provider.** Invited clients arrive via `/invite/:token`. Self-serve users arrive via `/signup` (post-beta only). Both use Supabase Auth's LinkedIn (OIDC) provider. Returning users sign in via `/login`.

2. **One `auth.users` row → up to one `advisors` row and up to one `clients` row.** Roles are orthogonal. An advisor running their own diagnostic holds both. The implicit constraint in ORPHEUS-23 (one auth user maps to either advisors or clients) is dropped.

3. **Lazy `advisors` row creation.** The `advisors` row exists only when the user needs one — either because they're an advisor running a practice (created at advisor-onboarding time) or because they've disconnected from their advisor and need to back the FK from their `clients` row. Invited clients never get an `advisors` row.

4. **Disconnect is a single transaction.** A client who wants to leave their advisor for self-serve mode runs an endpoint that (a) get-or-creates an `advisors` row owned by them with `is_individual = true`, and (b) repoints their `clients.advisor_id` to it. The old advisor loses access via RLS the moment the FK updates. Reversible — an advisor can re-invite a self-serve user later.

5. **Email invitations sent via Resend.** Supabase Auth's templated invites assume Supabase OAuth for the redirect; a transactional provider gives us full control over branding and content (which matters for advisor white-labeling later). Resend over Postmark/SendGrid for simpler developer experience at our scale.

6. **Stripe gates self-serve sign-up — but only post-beta.** During beta, every user is invitation-only and the advisor admin UI is the gate. Stripe + the `/signup` path land in a post-beta wave once the beta cohort gives us real pricing signal.

7. **LinkedIn email mismatch → soft confirmation.** When an invited user's LinkedIn-account email differs from the email the advisor sent the invitation to, show "Invitation sent to `<work email>`; you're signing in with LinkedIn account `<linkedin email>`. Continue?" Don't block; mismatches between work email and LinkedIn email are normal.

8. **Advisor admin UI: full `/advisor/clients` page in v1.** No manual Studio-query workaround. Beta launches with the admin UI built — Andrew issues invites through the React app from day one.

9. **Drop migration 007's `on_auth_user_created` trigger.** The trigger auto-creates a `clients` row on every new `auth.users` insert, which is incompatible with the invite-gated model (the row already exists with a pending invitation). All `clients`-row creation moves to explicit backend endpoints.

## Non-Goals

- **Stripe integration in beta.** Deferred. Filed as a post-beta ticket. Beta uses invite-only as the gate.
- **Self-serve sign-up in beta.** Deferred. `/signup` doesn't exist yet during beta.
- **Disconnect flow in beta.** Deferred — there's no self-serve mode for a disconnected client to land in during beta.
- **Multi-advisor per client.** A client belongs to exactly one advisor at a time. Switching advisors is an `UPDATE` of `clients.advisor_id`. No join table.
- **Email magic links, password auth, other OAuth providers.** Unchanged from the LinkedIn auth decision — LinkedIn is the only auth path.
- **Account merging.** If a user accidentally creates two LinkedIn accounts with different emails, we don't attempt to merge them. That's a support ticket, not a product flow.

## Alternatives Considered

**Eager `advisors`-row creation.** Every new LinkedIn sign-in creates an `advisors` row alongside the `clients` row. Pros: every user starts in a fully-coherent state. Cons: most invited-only clients never use their `advisors` row — it's dead inventory, and it surfaces awkward UI affordances ("welcome to your practice dashboard") to users who only want to be clients. Rejected.

**Sentinel "self-serve" advisor row.** All disconnected clients point to a single shared `advisors` row representing "no advisor." Cleaner row count but worse RLS — the SECURITY DEFINER `get_advisor_id()` helper assumes one user per advisor row, which the sentinel breaks. Rejected.

**Match invitation email to LinkedIn email strictly.** Reject sign-in if they don't match. Rejected: work-email-on-invite-but-personal-LinkedIn-email is a common real scenario, and the email check adds friction without a clear security gain (the token is already a one-time secret in the email).

**Stripe at beta launch.** Considered for "build the full picture once." Rejected because (a) Andrew can guess at pricing tiers but the beta cohort gives real signal, (b) Stripe is a meaty integration that doesn't earn its keep during a free beta, and (c) the schema doesn't lock anything in — `subscription_status` / `stripe_customer_id` can be added later without painful migrations.

**Manual Studio-query workaround for v1 invitations.** Andrew types the SQL by hand for the first invite, ships the UI later. Rejected — the admin UI is small enough that "build it now" is cheaper than "build it later, with two flows to test (manual + UI)." Plus the UI doubles as the QA tool for the invitation flow itself.

## Architecture

### Data model post-decision

```
auth.users (1)  ──┬──>  advisors (0..1)   ──── advisor's own diagnostic gets a clients row pointing back
                  └──>  clients  (0..1)   ──── always exists for anyone who's been invited or self-served
```

Pure invited client: `clients` row, no `advisors` row.
Pure advisor running a practice: `advisors` row, no `clients` row (until they click "Run my own report" → lazy creation).
Pure self-serve individual (post-beta): both rows, `advisors.is_individual = true`.
Andrew, running a practice + analyzing himself: both rows, `advisors.is_individual = false`.

### First-time sign-in by an invited client

1. Advisor creates a `clients` row with `advisor_id`, `display_name`, `email`. Backend generates `invitation_token` (uuid) and `invitation_expires_at` (now + 14 days). `invitation_status = 'pending'`.
2. Backend sends an email via Resend: "Andrew Segars invited you to a Strategic Presence Diagnostic. Click here: `https://app.orpheus.social/invite/<token>`."
3. Client clicks. Frontend at `/invite/:token` stores the token, redirects to LinkedIn OAuth via Supabase.
4. LinkedIn returns. Supabase creates the `auth.users` row. Frontend reads the stored token and calls `POST /accept-invitation` with `{ token }`.
5. Backend validates the token (exists, not expired, not yet accepted). Backend compares the invitation email to the LinkedIn email; if they differ, response includes `requires_confirmation: true`. Frontend shows soft-confirmation UI. On user confirm, frontend re-calls `POST /accept-invitation` with `{ token, confirmed: true }`.
6. Backend updates the `clients` row: `user_id = auth.uid()`, `invitation_status = 'accepted'`, clears `invitation_token` and `invitation_expires_at`.
7. Frontend lands in the portal. Subsequent `get_current_session_roles()` resolves `auth.uid()` to the `clients` row.

### Returning sign-in

1. Client clicks "Sign in with LinkedIn" on `/login`.
2. LinkedIn OAuth completes. Supabase finds the existing `auth.users` row (no new row created).
3. Frontend asks backend for session roles. Backend resolves `auth.uid()` to a `clients` row (and/or `advisors` row), responds with `{ advisor_id, client_id }`.
4. Frontend routes to the appropriate landing page. If neither role resolves (no row exists yet), show a "Your invitation may have expired, or you signed in with a different LinkedIn account than the one you were invited under. Contact your advisor." error page.

### Disconnect (post-beta)

1. Client clicks "Disconnect from my advisor" in their account settings.
2. Backend opens a transaction:
   - Get-or-create an `advisors` row with `user_id = auth.uid()`, `is_individual = true`.
   - `UPDATE clients SET advisor_id = <new advisors.id> WHERE id = <client's clients.id>`.
   - Commit.
3. From this point forward, the client is self-serve. The old advisor can no longer see them (RLS).

### Self-serve sign-up (post-beta)

1. User clicks "Sign up" on marketing site.
2. LinkedIn OAuth via Supabase. `auth.users` row created.
3. Frontend lands user in a "subscription required" state. Stripe Checkout is the only action available.
4. User completes Stripe Checkout (`client_reference_id = auth.uid()`).
5. Stripe webhook fires `checkout.session.completed`. Backend validates signature, reads `client_reference_id`, creates the `advisors` row (`is_individual = true`) and `clients` row (`advisor_id = new advisor.id`, `user_id = auth.uid()`).
6. Stripe success URL redirects user back to portal. Frontend polls session roles until they resolve, then lands in the portal.

(Flow order — LinkedIn-first vs Stripe-first — is deferred to ticket time. LinkedIn-first is the leading candidate.)

### Backend session resolution

`get_current_client` is replaced by `get_current_session_roles`:

```python
@dataclass
class SessionRoles:
    user_id: UUID                   # always auth.uid()
    email: str                      # always from JWT
    access_token: str               # always from header
    advisor_id: UUID | None         # set if advisors row exists
    client_id: UUID | None          # set if clients row exists

    def is_advisor(self) -> bool: return self.advisor_id is not None
    def is_client(self) -> bool:  return self.client_id is not None
```

Routes declare which role(s) they require:

- `/jobs/{id}` requires `is_client()` — client owns the job (or `is_advisor()` if it's their client's job).
- `/clients/invite` requires `is_advisor()`.
- `/clients/disconnect` requires `is_client()`.
- `/admin/*` requires `is_advisor()` AND `email in ADMIN_EMAILS` (existing pattern).

### Frontend role-based UI

Post-OAuth the frontend calls `GET /session` once. The response shapes navigation:

- `is_advisor && is_client` → tab toggle ("Manage clients" / "My report").
- `is_client only` → standard portal (Groundwork → Diagnostic).
- `is_advisor only` → `/advisor/clients` dashboard.
- `neither` → error page (above).

## Schema changes

Two columns on `public.clients`:

```sql
ALTER TABLE public.clients
    ADD COLUMN invitation_token       uuid,
    ADD COLUMN invitation_expires_at  timestamptz;
CREATE UNIQUE INDEX idx_clients_invitation_token
    ON public.clients (invitation_token)
    WHERE invitation_token IS NOT NULL;
```

No new tables in v1. No new RLS policies (the existing `clients_*` policies already cover token-bearer reads via the SECURITY DEFINER pattern, and the `/accept-invitation` endpoint uses the service-role client to look up by token).

Migration 007's `on_auth_user_created` trigger is *not* part of the production schema (it's never been applied — see `ORPHEUS-35`). The decision to drop it is therefore a code-only change: remove it from the planned migration set, and document that it's incompatible with this design.

## Beta scope vs. post-beta scope

**Beta (4 tickets):**

1. **Schema** — `invitation_token` + `invitation_expires_at` columns on `clients`, plus the index. Drop migration 007's trigger from the planned migration set.
2. **Backend auth refactor** — `get_current_session_roles` replaces `get_current_client`. All existing routes that depend on the current client dependency get updated.
3. **Invitation flow** — `/clients/invite` (advisor-authenticated, generates token + sends email via Resend), `/accept-invitation` (validates token, links the clients row, handles soft-confirmation), `/invite/:token` frontend page that drives the LinkedIn OAuth dance.
4. **Advisor admin UI** — `/advisor/clients` React page. List clients with their `invitation_status`, "Invite client" form, "Resend invitation" button on pending invites, "View report" link on accepted ones with completed jobs.

**Post-beta (3 tickets, beta-deferred):**

5. **Stripe billing + self-serve sign-up** — `/signup` page, Stripe Checkout integration, `checkout.session.completed` webhook, success/failure URL handling. Adds `stripe_customer_id` to `advisors` and a `subscription_status` enum somewhere queryable.
6. **Disconnect flow** — `/clients/disconnect` endpoint + button in the client account settings.
7. **Self-serve account management** — account settings page covering subscription status, billing portal link (Stripe-hosted), email/display-name editing.

## Open questions deferred to ticket time

- **LinkedIn-first vs Stripe-first** in the self-serve sign-up flow. (Leaning LinkedIn-first; rationale in this conversation's transcript. Settle when ticket #5 starts.)
- **Email content and visual design** for the Resend invitation template. Drafted at ticket #3 implementation time.
- **Advisor billing.** Does Andrew (or future advisors) pay Stripe per-seat or per-report or not at all? Self-serve only is the simplest first integration; the advisor question can be revisited after beta closes.
- **Cleanup of ghost `auth.users` rows** for bailout sign-ins that never complete acceptance. Defer to operations — Supabase's existing "delete inactive users" cron likely handles it. Revisit only if ghosts become a meaningful issue.
