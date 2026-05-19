# Session Handoff — 2026-05-19 (part 2)

Jump-in doc for the next Claude session. Replaces `SESSION_HANDOFF_2026-05-19.md` — all threads it described are closed in code or have moved into CLAUDE.md "Decisions Made":

- ORPHEUS-47 (frontend vitest + RTL test infra): shipped (3 commits, +3 vitest cases, all on local main awaiting push).
- ORPHEUS-46 + the rest of the 2026-05-19 morning's work: already on `origin/main`; nothing left in flight there.

Short session — single ticket, single pickup recommendation, executed exactly as the previous handoff suggested.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-47 | Frontend: stand up vitest + RTL | ✅ Done. 3 commits, +3 vitest cases. Plane: Done. |
| ORPHEUS-21 | Backend: Extend SubDimensionScore with narrative fields | ⏸ Hold pending Andrew's Forward Brief revisions. |
| ORPHEUS-22 | Backend: Dimension-level band classification | ⏸ Needs Andrew's product call. |
| ORPHEUS-25 | Cloud Supabase + prod LinkedIn OIDC provider | ⏳ Backlog. Ops/config. Gates 44. |
| ORPHEUS-31 | `/admin` stopgap (email-allowlisted) | ⏳ Forward-Brief-safe. Medium. ADMIN_EMAILS env exists; route doesn't. |
| ORPHEUS-43 | Pin Railway build command in source | ⏳ Forward-Brief-safe. Smallest, ~1 commit. **Top recommendation for next session.** |
| ORPHEUS-44 | Live e2e walkthrough of invite + advisor flow | ⏳ Gated on 25. Manual, no new code. |
| ORPHEUS-45 | Advisor admin UI: 'Edit' action on client list rows | ⏳ Forward-Brief-safe. UX. Rename-only is smallest scope. |
| ORPHEUS-48 | Multi-tenant branding (logo, colors, narrative voice per practice) | ⏸ Deferred until 2nd advisor practice + narrative-adjacent. |
| ORPHEUS-40 / 41 / 42 | Stripe, disconnect, account mgmt | ⏸ Beta-deferred. |

---

## Commits this session

Three commits awaiting `git push origin main`:

```
28f14a3  ORPHEUS-47: wire vitest into CI + document in CLAUDE.md.
4f4112d  ORPHEUS-47: ClientsPage smoke test.
de190fc  ORPHEUS-47: stand up vitest + RTL test infra.
```

Test counts:

- **Vitest: 3 green** (new). First frontend test runner in the project.
- **Pytest: 173 green** (unchanged — no backend touched).
- `npx tsc -b --noEmit` exits 0.
- `npx vite build` succeeds: 179 modules, production bundle 476 KB. Grep confirms zero references to `vitest` or `@testing-library` leaked into `dist/assets/*.js`.

---

## What ORPHEUS-47 actually shipped

### Test infrastructure

- **Six new devDependencies** in `frontend/package.json`: `vitest ^2.1.5`, `@vitest/coverage-v8 ^2.1.5`, `@testing-library/react ^16.1.0`, `@testing-library/jest-dom ^6.6.3`, `@testing-library/user-event ^14.5.2`, `jsdom ^25.0.1`. Lockfile resolved to vitest 2.1.9.
- **Three new npm scripts**: `test`, `test:watch`, `test:coverage`.
- **Vitest config inline** in `frontend/vite.config.ts` under `test:` (jsdom env, globals enabled). Triple-slash `/// <reference types="vitest" />` directive so the test block is typed off `defineConfig` from `vite`.
- **Setup file** `frontend/src/test-setup.ts` imports `@testing-library/jest-dom/vitest` (for the extended matchers) and registers `afterEach(cleanup)` — vitest does not auto-cleanup the way Jest does.
- **`tsconfig.app.json`** gets `"types": ["vitest/globals", "@testing-library/jest-dom"]` so `tsc -b` resolves `describe`/`it`/`expect`/`vi`/jest-dom matchers as implicit globals.
- **`.gitignore`** picks up `frontend/dist/` + `frontend/vite.config.ts.timestamp-*.mjs` so build artifacts don't slip into commits.

### First smoke test

`frontend/src/pages/advisor/__tests__/ClientsPage.test.tsx` — 3 cases:

| Case | What it asserts |
|---|---|
| renders the page header | `<h1>Manage clients</h1>` is in the document |
| renders the invite form | Name + Email labels + "Send invitation" button all present |
| surfaces View report on non-self complete row | Link with `href="/jobs/<id>"` renders for a non-self client whose `latest_job.status === 'complete'` — ORPHEUS-46 uncloak regression |

`vi.mock`s the four data hooks (`useAdvisorClients`, `useInviteClient`, `useResendInvitation`, `useSelfReport`) plus `lib/auth` (so the Supabase singleton's `VITE_SUPABASE_*` check doesn't fire under jsdom). `MemoryRouter` wraps for `Link` + `useNavigate`. No `QueryClientProvider` needed since all hooks are mocked — the component never reaches React Query.

### CI

`.github/workflows/ci.yml` frontend job gets a new `Test` step running `npm run test -- --run` after `npm run build`. Same job, no extra runner.

### Docs

CLAUDE.md picks up:

- A **Frontend Conventions** paragraph documenting the test infra, command, vi.mock-the-hook convention, and the colocation pattern.
- **File-tree updates**: `src/test-setup.ts` and `src/pages/advisor/__tests__/`.
- **Decisions Made** dated entry for 2026-05-19 ORPHEUS-47 mirroring the recent format.

---

## Architectural notes worth carrying forward

### vi.mock-the-hook is the locked convention

The empty `mocks/handlers.ts` posture (post-ORPHEUS-28) means MSW isn't actively serving anything in the running app — it was preserved only for offline UI playgrounds. Carrying that intent into tests: **mock at the hook layer, not the network layer**. Future component tests should follow the ClientsPage pattern:

1. `vi.mock` each data hook the component imports.
2. `vi.mock` `lib/auth` if the component reads from session — otherwise the Supabase singleton tries to instantiate and the test fails at module-load time.
3. Wrap in `MemoryRouter` if the component renders `Link`s or calls `useNavigate`.
4. Skip `QueryClientProvider` — no real queries are flowing.

If a future test legitimately needs the full fetch path (e.g., to exercise `apiClient`'s bearer-token attachment), that's the right time to stand up `mocks/server.ts` and switch the test to MSW. Don't pre-empt it.

### Tests colocate under `__tests__/`

Decision: tests live in `__tests__/` directories next to the file they test, not in a parallel top-level `tests/` tree. Per the ORPHEUS-47 Plane comment: "Future tests colocate under `__tests__/` next to the component." Keeps test churn local to feature changes and follows the Jest/RTL community convention.

### `tsc -b` and vitest globals

`globals: true` in vitest config means test files don't import `describe`/`it`/`expect`/`vi`. For `tsc -b --noEmit` to accept this, `tsconfig.app.json` must declare both `"types": ["vitest/globals", "@testing-library/jest-dom"]`. Without the jest-dom entry, `toBeInTheDocument` and friends won't resolve.

### `vite build` excludes test files automatically

Verified this session: `vite build` produces a 476 KB bundle with **zero** references to `vitest` or `@testing-library` in the emitted JS. Tree-shaking handles the exclusion — no explicit pattern in vite config is needed. If a future change ever imports a test file from production code, the bundle size will explode and the grep check at `dist/assets/*.js` will catch it.

---

## Pickup plan for next session

The previous handoff's shortlist still applies — ORPHEUS-47 is now off the top.

**Top recommendation: ORPHEUS-43** (Pin Railway build command in source). Smallest scope, ~1 commit. Convert the Railway dashboard's manual `pip install -r backend/requirements.txt` Build Command into a `railpack.json` or root `requirements.txt` shim so a fresh Railway deploy doesn't need dashboard config. Forward-Brief-safe; pure ops infrastructure.

### Alternatives

- **ORPHEUS-45** (Edit action on client list rows). UX work. Previous handoff recommends rename-only as smallest scope: a per-row "Edit" button opens an inline form to change `display_name`; backend `PATCH /clients/{id}` accepts only `display_name`.
- **ORPHEUS-31** (`/admin` stopgap). Backend + frontend. `ADMIN_EMAILS` env already defined; route missing. Needs a scope decision first (read-only operational view of users + jobs is probably the right starting point).
- **First non-ClientsPage vitest test.** Now that the infra is real, every frontend ticket can include a smoke test. Backlog candidates: `SmartIndexRedirect` role-aware branching, `AdvisorRoute` redirect on non-advisor, `InviteCallbackPage` state machine.

---

## Caveats / things that will bite

1. **ORPHEUS-25 still gates the live e2e walks.** Both ORPHEUS-44 and the live ORPHEUS-46 advisor View report demo are local-only until the cloud Supabase LinkedIn OIDC provider is configured. Not a code task — purely Supabase dashboard config.

2. **Andrew's Forward Brief revisions are pending.** Hold on ORPHEUS-21, 22, 48 until they land — they all touch `agents/narrative.py` or the Forward Brief contract.

3. **Sandbox can't run pytest** (PyPI blocked). Backend test execution still happens from Josh's terminal. Baseline for next session: **173 pytest green**.

4. **Sandbox CAN run npm** — verified this session (`npm install`, `npx vitest run`, `npx vite build` all worked). Lockfile updates from the sandbox are safe. The EPERM warnings on cross-platform esbuild binaries are cosmetic (Josh's mac checkout has macOS-specific dirs; the sandbox tried to replace them with linux variants and hit permission errors). The install completed correctly nonetheless.

5. **Sandbox can't push via SSH.** All `git push origin main` operations are manual from Josh's terminal.

6. **`.git/*.lock` files cannot be unlinked** from the sandbox. Use the `find .git -name "*.lock" -type f | while read f; do mv "$f" "$f.moved.$$" 2>/dev/null; done` pattern before each commit. Cosmetic `.git/objects/tmp_obj_*` warnings are safe to ignore.

7. **Plane comment HTML can swallow stray tags from malformed tool payloads.** The opening Plane comment on ORPHEUS-47 had a trailing `</invoke>` slip into the body — cosmetic but visible. The closing comment was clean. Future sessions should double-check the trailing characters of `comment_html` before posting.

---

## State of the repo right now (end of session)

After this commit lands:

```
On branch main
Your branch is ahead of 'origin/main' by 4 commits (the three ORPHEUS-47 commits + this handoff).

Untracked:
  LinkedIn_BD_DPA_Review_2026-05-07.md
  Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}
  Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}
```

The five compliance drafts stay untracked pending the separate commit-vs-Drive decision. Same posture as the previous handoff.

`SESSION_HANDOFF_2026-05-19.md` is retired in this commit.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```
