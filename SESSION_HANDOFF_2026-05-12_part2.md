# Session Handoff — 2026-05-12 (Part 2)

Jump-in doc for the next Claude session. Replaces `SESSION_HANDOFF_2026-05-12.md` (the part-1 file at the top of this same day) — the threads it described are all closed:

- ORPHEUS-33 / 34 / 35 + decision page: committed and pushed in part 1.
- Apply migration 011 to prod: done during this part-2 session.
- ORPHEUS-36: shipped (this session).
- ORPHEUS-37: shipped (this session).
- ORPHEUS-38 scoping: done (this session). Spec + infra prep both ready for execution next time.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-36 | Schema: invitation_token columns + retire 007's trigger plan | ✅ Done in Plane. Commit `ab0a488` pushed. Migration 012 NOT YET applied to prod. |
| ORPHEUS-37 | Backend auth refactor: get_current_session_roles | ✅ Done in Plane. Commit `df21998` pushed. pytest backend/ 114-green confirmed by user. |
| ORPHEUS-38 | Invitation flow: /clients/invite + /accept-invitation + /invite/:token (Resend) | 📋 Scoped. `Spec_Invitation_Flow_2026-05-12.md` is the ready-to-execute plan. Resend + Vercel infra set up this session. |
| ORPHEUS-39 | Advisor admin UI: /advisor/clients page | ⏳ Filed, unstarted. Depends on 38. |
| ORPHEUS-40/41/42 | Stripe, disconnect, account mgmt | ⏳ Filed, beta-deferred. |

---

## Infrastructure deltas (new this session)

### Migration 011 — applied to prod

Reshaped `public.questionnaire_responses` to the ORPHEUS-33 spec. Andrew's 1 pressure-test row wiped (expected per the spec). Post-shape: `(client_id PK, answers JSONB, updated_at)` with the cascade FK to `clients(id)` preserved.

### Resend (email)

- Account exists, `orpheussocial.com` verified as a sending domain. DNS records (MX + SPF + DKIM + DMARC) live at GoDaddy under `@`, `send`, `resend._domainkey`, `_dmarc`.
- API key `orpheus-prod` generated. **Josh has the value; lives in `backend/.env` as `RESEND_API_KEY=re_...`.** Will need to be added to Railway env when ORPHEUS-38 ships.
- From-line locked: `Orpheus Social <hello@orpheussocial.com>`.

### Vercel custom domain

- `app.orpheussocial.com` wired to the frontend Vercel project. CNAME `app → cname.vercel-dns.com` live at GoDaddy. Let's Encrypt cert auto-issued via ACME.
- Confirmed serving the React app over HTTPS by the user 2026-05-12.
- `APP_BASE_URL=https://app.orpheussocial.com` is the invite-link host for ORPHEUS-38. Will need to be added to Railway env when ORPHEUS-38 ships.

### Schema state (prod)

```
✅ Migration 001 — base schema (snapshot)
✅ Migration 011 — questionnaire_responses aligned to ORPHEUS-33 spec
⏳ Migration 012 — invitation_token columns (dry-runs clean, not yet applied)
```

Apply 012 at commit #11 of ORPHEUS-38 (right before manual e2e), not before. See the Spec doc for the ordering rationale.

---

## Commits this session

In `origin/main` order:

```
df21998 Replace get_current_client with get_current_session_roles. Refs ORPHEUS-37.
ab0a488 Add migration 012: invitation_token columns on clients. Refs ORPHEUS-36.
cad5e0f Session handoff: 2026-05-12. Retire stale 2026-05-08 and 2026-05-11 handoffs.
a1c343c Add decision: self-serve + advisor invite flow.
```

All four pushed to `origin/main`. Railway worker + Vercel frontend auto-deployed against each push.

---

## Files added / modified / deleted this session

### Committed

**ORPHEUS-36:**
- Added `backend/migrations/012_clients_invitation_columns.sql`
- Modified `backend/migrations/007_clients_table.sql` (header note retiring the `on_auth_user_created` trigger)
- Modified `CLAUDE.md` (new Decisions-Made bullet for self-serve + advisor invite, migrations list adds 001/011/012, marks 007–010 HISTORICAL)

**ORPHEUS-37:**
- Modified `backend/auth.py` — removed `CurrentClient` + `get_current_client` + `CurrentClientDep`; added `SessionRoles` + `get_current_session_roles` + `_lookup_role_id`
- Modified `backend/routers/jobs.py` — both handlers now depend on `get_current_session_roles` with inline 403 `is_client()` guards
- Modified `backend/tests/test_auth.py` — full rewrite for the new dependency, four role-permutation tests added
- Modified `CLAUDE.md` (Backend Conventions paragraph for the new auth shape)
- Modified `frontend/src/lib/apiClient.ts` (one-line comment update)

**Decision + handoff:**
- Added `Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md`
- Added `SESSION_HANDOFF_2026-05-12.md` (the part-1 file, supersedes 05-08 and 05-11 handoffs which were retired in the same commit)

### Uncommitted this session

- `Spec_Invitation_Flow_2026-05-12.md` (new — ready-to-execute plan for ORPHEUS-38)
- `SESSION_HANDOFF_2026-05-12_part2.md` (this file)
- Optional: delete `SESSION_HANDOFF_2026-05-12.md` (the part-1 file) — superseded by this one.

### Still untracked (from prior sessions)

- `LinkedIn_BD_DPA_Review_2026-05-07.md`
- `Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}`
- `Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}`

Pre-launch compliance thread, untouched all session. Same status as the part-1 handoff: decide commit vs Drive when there's room.

---

## ORPHEUS-38 pickup plan for the next session

The whole ticket is laid out in `Spec_Invitation_Flow_2026-05-12.md`. Read that file first; the summary below is just orientation.

### What's ready

- Decisions all locked (from-line, app host, test strategy, GET /session included, token semantics, idempotency rules, 409 pre-check, single router, etc.).
- Infra all set up (Resend domain verified, API key issued, Vercel domain live, both env vars known).
- Migration 012 dry-run verified against prod; ready to apply at commit #11.
- Auth refactor surface area inspected — minor extension needed (`get_verified_session` for endpoints that allow neither-role).

### Suggested first session of ORPHEUS-38

Commits 1–3 from the Spec form a logical first chunk:

1. **Config + auth-resolver split** — adds the three env vars, splits `_resolve_session` into `get_current_session_roles` and `get_verified_session`. Test coverage on both.
2. **Resend client wrapper** — `backend/email/resend_client.py`, sandbox mode for tests/local-dev.
3. **Email template** — subject + HTML + plain-text formatter.

This chunk is ~2 hours of focused work and lands a self-contained "Resend is wired up but no endpoints use it yet" state. Easy to review and merge before the routes start using it.

Commits 4–7 are the three invite endpoints + `GET /session`, a natural second chunk.

Commits 8–10 are the three frontend pages + `useSessionRoles` routing.

Commit 11 is the prod migration apply + manual e2e — gates the ticket.

Commit 12 cleans up CLAUDE.md.

### What to set up before that session starts

- `backend/.env` should already have `RESEND_API_KEY=re_...` and `APP_BASE_URL=https://app.orpheussocial.com`. Josh did this part of the Resend setup this session.
- Railway env: add `RESEND_API_KEY` and `APP_BASE_URL` to the production env vars **before** commit #1 deploys. Otherwise the new required `Settings` fields will block boot.

### Alternative threads if you'd rather not pick up 38

- **Pre-launch compliance docs.** The five untracked files from 2026-05-07 still need a decision (commit vs Drive). 30-min cleanup.
- **CLAUDE.md tidy.** Several smaller items the handoff has noted as follow-ups: the `SETUP_phase1_local_auth.md` doc still references the LinkedIn-1:1 model; the migrations list is now in good shape but the rest of the SETUP doc lags.
- **Wait on 38.** Use the time to design the email template visually (logo, color, signature). The spec calls for "plain HTML" in v1, but a quick design pass before code starts saves a follow-up later.

---

## Architectural notes worth carrying forward

### From this session's ORPHEUS-37 work

- `SessionRoles` is the new canonical session shape. Both role fields are independently optional. The dataclass is sealed (`frozen=True`) — mutate at construction time only.
- The role lookups now key on `user_id` (FK to `auth.users`), NOT on `id`. Prod `clients.id` and `advisors.id` are surrogate uuids; the JWT `sub` matches their `user_id` column. This was a key semantic shift from the pre-2026-05-12 model.
- All client-facing routes that need a specific role gate themselves with `if not roles.is_client(): raise HTTPException(403, ...)`. Same shape for `is_advisor()`. We considered building dedicated `require_client` / `require_advisor` dependencies but the inline guard is fine for the small number of routes we have.
- `get_verified_session` (post-ORPHEUS-38 commit #1) will be the variant for routes that can legitimately serve neither-role users (`/accept-invitation`, `GET /session`). Keep this distinction sharp: 99% of authenticated routes use `get_current_session_roles` (and reject neither-role); 1% use `get_verified_session`.

### From the Resend / Vercel infra setup

- GoDaddy's relative-name DNS quirk: when adding records like `send.orpheussocial.com`, the Name field expects `send` (the prefix), not the full FQDN. Same for `resend._domainkey` and `_dmarc`. Resend's "Add Domain" page is unambiguous about the full hostname; the translation happens at GoDaddy.
- Vercel custom domain wiring is one CNAME record + Vercel's auto-ACME flow. Total time-to-live cert: ~5–15 min once the CNAME propagates.
- Resend's free tier (100/day, 3000/month) is more than enough for beta. Watch the limits before scaling.

### From ORPHEUS-38 scoping

- The "neither role" case has a real test path: a freshly-signed-in user with no business-row yet must be able to call `/accept-invitation` to convert. This is why `get_verified_session` exists.
- The frontend's `/invite/callback` page lives OUTSIDE `ProtectedRoute`. The callback page handles its own auth state because `ProtectedRoute` would otherwise 401-bounce a newly-authenticated user with no roles.
- `GET /session` always returns 200 (with neither-role being a valid result). The frontend uses this as the canonical "is the user invited" check.

---

## Open threads / things to decide later

1. **Pre-launch compliance docs.** Untracked since 2026-05-07. Decide commit-path before launch.
2. **Plane native relations.** Dependencies still encoded in ticket descriptions, not the relations graph. Wire by hand if the dependency-graph view is useful.
3. **Email template design.** Plain HTML in v1 (commit #3 of ORPHEUS-38). Real design pass after the first client sees it.
4. **`clients.user_id` UNIQUE constraint.** No DB-level enforcement that one auth user maps to one clients row. Beta-fine; add a partial UNIQUE in a future migration when we have multiple advisors.
5. **Stripe + pricing.** Open for ORPHEUS-40 (post-beta).

---

## Caveats / things that will bite during next-session testing

1. **Migration 012 is dry-run-verified but not applied to prod.** Apply it via Supabase MCP execute_sql at ORPHEUS-38 commit #11 — NOT earlier in the commit chain. Local dev needs it too if you run the backend against local Supabase.

2. **`RESEND_API_KEY` and `APP_BASE_URL` are required-at-boot in the new `Settings`.** Add them to Railway env before deploying commit #1 of ORPHEUS-38, or the backend will refuse to start with a clear Pydantic `ValidationError`.

3. **The Spec doc's "sandbox mode" for Resend keys triggers on the literal prefix `test_`.** Real production keys start with `re_`. If someone in CI accidentally sets `RESEND_API_KEY=re_abc123` thinking it's a fake, they'll send a real email. Be careful with the CI env value.

4. **`get_current_session_roles` already implemented.** `get_verified_session` does NOT exist yet — it's the first thing ORPHEUS-38 adds. Don't reach for `get_verified_session` in any code you write before commit #1 of 38 lands.

5. **The part-1 handoff (`SESSION_HANDOFF_2026-05-12.md`) is still tracked.** Either retire it in this part-2's housekeeping commit, or leave it as a same-day pairing. Both are defensible — I'd retire to match the existing pattern of "one handoff per session," but the call's yours.

---

## State of the repo right now (end of session)

```
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged:
  (none — Resend + Vercel infra changes are out-of-repo)

Untracked:
  Spec_Invitation_Flow_2026-05-12.md          # NEW this session; commit alongside ORPHEUS-38 commit #1
  SESSION_HANDOFF_2026-05-12_part2.md         # NEW (this file)

  SESSION_HANDOFF_2026-05-12.md               # part-1 from earlier today; retire in this session's housekeeping commit
  LinkedIn_BD_DPA_Review_2026-05-07.md        # compliance thread, unchanged
  Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}
  Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}
```

Suggested housekeeping commit before the next session:

```bash
cd ~/git/orpheus && \
  rm -f SESSION_HANDOFF_2026-05-12.md && \
  git add SESSION_HANDOFF_2026-05-12_part2.md Spec_Invitation_Flow_2026-05-12.md && \
  git commit -m "Spec: invitation flow. Session handoff part 2.

Spec_Invitation_Flow_2026-05-12.md: ready-to-execute implementation
plan for ORPHEUS-38 (Resend wrapper, three invite endpoints, GET
/session, two frontend pages, neither-role error UI). Locked decisions,
prerequisites, commit-by-commit file changes, test inventory, manual
e2e checklist.

SESSION_HANDOFF_2026-05-12_part2.md: session handoff capturing
ORPHEUS-36 + 37 shipped, ORPHEUS-38 scoped + infra prepped (Resend
domain verified, Vercel custom domain live). Retires the part-1
handoff from earlier this day."
```

Then `git push origin main`. The Spec doc + handoff are ready to land — neither blocks the ORPHEUS-38 implementation in the next session.
