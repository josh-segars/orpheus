# Session Handoff — 2026-05-19

Jump-in doc for the next Claude session. Replaces `SESSION_HANDOFF_2026-05-18.md` (and finally retires the lingering 2026-05-12 + 2026-05-13 ghosts) — all the threads those docs described are closed in code or have moved into CLAUDE.md "Decisions Made":

- ORPHEUS-46 (advisor-aware `GET /jobs/{id}` + View report uncloak): shipped (3 commits, +5 tests, 173 green, all on `origin/main`).
- ORPHEUS-39, 38, 35, 34, 33, audit closures — all already closed via the 2026-05-18 handoff and rolled into CLAUDE.md.

Short session focused on one ticket. No new follow-ups filed.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-46 | Advisor-aware `GET /jobs/{id}` (View report uncloak) | ✅ Done. 3 commits, +5 tests (168→173). Plane: Done. |
| ORPHEUS-21 | Backend: Extend SubDimensionScore with narrative fields | ⏸ Hold pending Andrew's Forward Brief revisions. Different section of `narrative.py` than FB, but the natural Andrew-led revision would absorb it. |
| ORPHEUS-22 | Backend: Dimension-level band classification | ⏸ Needs Andrew's product call. |
| ORPHEUS-25 | Cloud Supabase + prod LinkedIn OIDC provider | ⏳ Backlog. Ops/config. Gates 44. |
| ORPHEUS-31 | `/admin` stopgap (email-allowlisted) | ⏳ Forward-Brief-safe. Medium. ADMIN_EMAILS env exists; route doesn't. |
| ORPHEUS-43 | Pin Railway build command in source | ⏳ Forward-Brief-safe. Smallest, ~1 commit. |
| ORPHEUS-44 | Live e2e walkthrough of invite + advisor flow | ⏳ Gated on 25. Manual, no new code. |
| ORPHEUS-45 | Advisor admin UI: 'Edit' action on client list rows | ⏳ Forward-Brief-safe. UX. Rename-only is smallest scope. |
| ORPHEUS-47 | Frontend: stand up vitest + RTL | ⏳ Forward-Brief-safe. Compounding return. Top recommendation for next session. |
| ORPHEUS-48 | Multi-tenant branding (logo, colors, narrative voice per practice) | ⏸ Deferred until 2nd advisor practice + narrative-adjacent. |
| ORPHEUS-40 / 41 / 42 | Stripe, disconnect, account mgmt | ⏸ Beta-deferred. |

---

## Commits this session

Four commits on `origin/main`, in dependency order:

```
ec3ea8a  Docs: mark ORPHEUS-46 shipped in CLAUDE.md + PRODUCT_CONTEXT.md. Refs ORPHEUS-46.
ef5d980  Uncloak 'View report' on non-self advisor client rows. Refs ORPHEUS-46.
4e86df3  Advisor-aware GET /jobs/{id}: relax role gate + tests. Refs ORPHEUS-46.
a6de905  Session handoff: 2026-05-18 + onboarding docs for team account.
```

The `a6de905` housekeeping commit closed out the 2026-05-18 working tree (CONVENTIONS.md, CREDENTIALS.md, SESSION_HANDOFF_2026-05-18.md, the ess3.ai email-domain sweep, CLAUDE.md + PRODUCT_CONTEXT.md refreshes). It carried the commit message drafted at the end of `SESSION_HANDOFF_2026-05-18.md`.

Test count: 168 baseline → **173 green** (+5 across one new test file: `test_jobs_get.py`).

`tsc -b --noEmit` exits 0 on the frontend.

`pytest backend/` confirmed 173 green from Josh's terminal end-of-session.

---

## What ORPHEUS-46 actually shipped

### Backend

**`backend/routers/jobs.py` — `get_job` handler** — replaced the `is_client()`-only role gate with an `allowed_client_ids` set construction:

- Client-only caller → `{roles.client_id}`
- Advisor-only caller → `SELECT id FROM clients WHERE advisor_id = roles.advisor_id` (service-role lookup; RLS on `clients` would otherwise hide the roster from the advisor's session token)
- Dual-role caller (Andrew = advisor + own self-clients row) → union; idempotent because the self-row is in the advisor's managed roster
- Neither role → defense-in-depth 403 (unreachable via `get_current_session_roles` which 401s upstream)

Jobs query then filters via `.in_("client_id", list(allowed_client_ids))`. Switched the handler from `user_scoped_supabase` to `get_service_client` to match the pattern in `GET /clients`; downgrades RLS-as-defense-in-depth on the original client path, which the ticket explicitly accepts ("explicit-handler path is easier to reason about for a single endpoint"). The 404-not-403 leak-resistance contract is preserved by the handler.

File-level docstring and the imports were updated alongside; `user_scoped_supabase` is no longer imported in this file.

### Tests

**`backend/tests/test_jobs_get.py` (new, +5 cases)** — mirrors the `FakeSupabase` + handler-direct-invocation pattern from `test_clients_list.py`:

| Case | Roles | FakeSupabase responses | Expected |
|---|---|---|---|
| advisor viewing own client's job | advisor_id only | clients → [{id: C1}], jobs → [job(C1)] | 200, `tables_queried == ["clients", "jobs"]` |
| advisor viewing other advisor's client's job | advisor_id only | clients → [{id: C1}], jobs → [] | 404, no leak |
| advisor with no managed clients | advisor_id only | clients → [] | 404, `tables_queried == ["clients"]` (short-circuit before jobs query) |
| client viewing own job (regression) | client_id only | jobs → [job(C1)] | 200, `tables_queried == ["jobs"]` (no clients expansion for client-only) |
| client viewing other client's job (regression) | client_id only | jobs → [] | 404 |

All five use non-`complete` job statuses so `_build_result_payload` doesn't fire — the ticket is about role-gating, not payload assembly.

### Frontend

**`frontend/src/pages/advisor/ClientsPage.tsx`** — dropped the `client.is_self &&` guard on the View report `<Link>`. Button now renders for any row with `latest_job.status === 'complete'`. Rewrote the stale code comment that explained the self-only restriction to point at the new backing endpoint. `tsc -b --noEmit` clean.

### Docs

- **CLAUDE.md** — "Active phase" paragraph trimmed (ORPHEUS-46 removed from open code-work list, advisor-aware GET noted in shipped list). "Decisions Made" gets a new dated entry for ORPHEUS-46 mirroring the ORPHEUS-39 style. The known-gaps tail of the ORPHEUS-39 entry was trimmed (advisor visibility now closed; Edit action still tracked as ORPHEUS-45).
- **PRODUCT_CONTEXT.md** — Build Status `API routes` row updated to reflect the closed gate ("accepts both client-self and advisor-owns-client paths post-ORPHEUS-46").

### Plane

ORPHEUS-46 moved to Done with a closing comment citing all three implementation commits, the test count delta, and the two open-questions-from-ticket-time resolutions (published-vs-draft narrative filter deferred until the advisor edit UX is real; `GET /clients/{id}/jobs` list view out of scope).

---

## Architectural notes worth carrying forward

### The `allowed_client_ids` pattern

For any future advisor-facing endpoint that needs to query data scoped by client (a hypothetical `GET /clients/{id}/jobs` for full history; per-client analytics; etc.), follow the same shape:

```python
allowed_client_ids: set[str] = set()
if roles.is_client():
    allowed_client_ids.add(roles.client_id)
if roles.is_advisor():
    rows = service.table("clients").select("id").eq("advisor_id", roles.advisor_id).execute()
    for r in rows.data or []:
        allowed_client_ids.add(str(r["id"]))
if not allowed_client_ids:
    raise HTTPException(404, ...)  # not 403 — preserve leak resistance
# then filter the downstream query with .in_("client_id", list(allowed_client_ids))
```

Don't try to push this into RLS — the explicit-handler path is consistently easier to reason about, and that's what both `GET /clients` and now `GET /jobs/{id}` do.

### Service-role vs user-scoped, the trend

The codebase is converging on **service-role + explicit handler ownership checks** for any endpoint that serves more than one role. `user_scoped_supabase` remains the right tool for **single-role client endpoints** where RLS is doing meaningful work (e.g. `POST /jobs`). The cost is that defense-in-depth via RLS is downgraded; the benefit is one code path per endpoint and easier reasoning. Current opinion: this is a worthwhile trade for any endpoint that touches the advisor role.

### Forward-Brief blast radius

Andrew has pending Forward Brief revisions; any code touching narrative generation, FB structured data, or the scored-output assembly is at risk of rework. The safe subset is anything purely UI, auth/role-gating, deploy infra, or admin stopgaps. ORPHEUS-21 (sub-dim narratives) is the closest call — different section of `agents/narrative.py` than the Forward Brief section, but the natural Andrew-led revision would absorb it, so defer.

Forward-Brief-safe shortlist for next session: **ORPHEUS-47, 43, 45, 31**.

---

## Pickup plan for next session

**Top recommendation: ORPHEUS-47** (frontend test infra). Every frontend ticket this year has skipped "add a smoke test if scaffolding allows" because vitest doesn't exist yet. Now that the advisor admin UI is feature-complete and there's no pending Forward Brief blast radius, this is the highest-leverage compounding investment.

Order of operations:

1. `npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom @vitest/coverage-v8` in `frontend/`.
2. Add `vitest.config.ts` (or extend `vite.config.ts` with a `test` block). Configure jsdom environment, `globals: true`, point at `src/test-setup.ts`.
3. Add `src/test-setup.ts` — imports `@testing-library/jest-dom`, registers `afterEach(cleanup)`.
4. Add npm scripts: `test`, `test:watch`, `test:coverage`.
5. Write a smoke test for `ClientsPage.tsx` — render with a React Query wrapper, mocked GET /clients via MSW or `vi.mock('../../hooks/useAdvisorClients')`. Assert: (a) header renders, (b) View report Link surfaces for any row with `latest_job.status === 'complete'` (regression-test on the ORPHEUS-46 uncloak while we're here), (c) invite form is present.
6. Update `.github/workflows/` (whichever runs frontend CI today) to run `npm run -w frontend test -- --run` on PR.
7. Update CLAUDE.md "Frontend Conventions" with the test infra setup.

Expected commit count: ~3 (deps + config; smoke test; CI + docs).

### Alternatives

- **ORPHEUS-43** (Railway build pin) — 1 commit. Convert the dashboard's manual `pip install -r backend/requirements.txt` into a `railpack.json` or root `requirements.txt` shim so a fresh Railway deploy doesn't need dashboard config.
- **ORPHEUS-45** (Edit action on client list rows) — UX work. The previous handoff recommends rename-only as smallest scope: a per-row "Edit" button opens an inline form to change `display_name`; backend PATCH /clients/{id} accepts only `display_name`.
- **ORPHEUS-31** (`/admin` stopgap) — backend + frontend. ADMIN_EMAILS env var already defined; no admin route. Needs a scope decision first (probably: list users + jobs, no actions — read-only operational view).

---

## Caveats / things that will bite

1. **ORPHEUS-25 still gates the live e2e walks.** Both ORPHEUS-44 and the live ORPHEUS-46 advisor View report demo are local-only until the cloud Supabase LinkedIn OIDC provider is configured. Not a code task — purely Supabase dashboard config.

2. **Andrew's Forward Brief revisions are pending.** Hold on ORPHEUS-21, 22, 48 until they land — they all touch `agents/narrative.py` or the Forward Brief contract.

3. **Sandbox can't run pytest** (PyPI blocked). Test execution still happens from Josh's terminal. Test count baseline for next session: **173 green**.

4. **Sandbox can't push via SSH.** All `git push origin main` operations are manual from Josh's terminal.

5. **`.git/*.lock` files cannot be unlinked** from the sandbox. Use the `find .git -name "*.lock" -type f | while read f; do mv "$f" "$f.moved.$$" 2>/dev/null; done` pattern before each commit. There are several `.lock.moved.<pid>` orphans in `.git/` now — harmless but worth a one-time `find .git -name "*.moved.*" -delete` from Josh's terminal.

6. **The Linux sandbox's `.git/objects/tmp_obj_*` warnings are cosmetic** — same unlink-permission issue as the lock files. Don't worry about them.

---

## State of the repo right now (end of session)

After this commit lands:

```
On branch main
Your branch is ahead of 'origin/main' by 1 commit (this handoff).

Untracked:
  LinkedIn_BD_DPA_Review_2026-05-07.md
  Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}
  Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}
```

The four older `SESSION_HANDOFF_2026-05-{12,12_part2,13,18}.md` files are retired in this commit. The previous session's handoff intended to retire the 2026-05-12 pair but they hadn't actually been deleted in git history — caught and cleaned up here.

The five compliance drafts (LinkedIn DPA review, Privacy Policy, Terms of Service) stay untracked pending a separate decision on commit vs Drive — same posture as the previous handoff.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```
