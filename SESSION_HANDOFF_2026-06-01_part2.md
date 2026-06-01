# Session Handoff — 2026-06-01 part 2

Retires `SESSION_HANDOFF_2026-06-01.md`. Its recommended pickup was ORPHEUS-44 (live e2e walk-through, newly unblocked by ORPHEUS-25). This session ran ORPHEUS-44 partially against cloud Supabase, produced six bug tickets, then chose to stop and burn the bugs down in a focused fix-session rather than continue past compounding workarounds.

Unusual session shape: ops/triage only, no code commits. One Plane ticket touched (ORPHEUS-44 moved In Progress → Backlog with a closing comment); six new bug tickets filed; one handoff commit covers the doc refresh.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-44 | Live e2e of invitation + advisor flow | 🟡 **Partial walk done; back in Backlog pending fix-session.** Pre-flight + advisor invite acceptance shipped end-to-end (with workarounds). Full client journey blocked by ORPHEUS-57. Six follow-up bug tickets filed. Closing comment posted with the partial-walk summary, carried state, and recommended re-run shape. |
| ORPHEUS-53 | Bug: ProtectedRoute pre-empts AdminRoute (admin can't reach `/admin` without an advisors/clients row) | 🆕 Filed. Medium. Frontend fix: bypass ProtectedRoute's neither-role branch for admin-allowlisted emails. |
| ORPHEUS-54 | Bug: apiClient silently treats scheme-less `VITE_API_BASE_URL` as a relative path | 🆕 Filed. Medium. Frontend fix: fail-fast at module load in `apiClient.ts`, matching the `supabase.ts` posture. |
| ORPHEUS-55 | Bug: Resend send fails with Cloudflare WAF code 1010 | 🆕 Filed. **High.** Backend fix: add `User-Agent` header to the `urllib.request.Request` in `_post_to_resend`. |
| ORPHEUS-56 | Bug: PortalNav "Manage clients" pill not clickable for advisor-only users off `/advisor/clients` | 🆕 Filed. Medium. Frontend fix: route-conditional rendering — `<Link>` on non-/advisor/clients routes. |
| ORPHEUS-57 | Bug: Questionnaire upsert uses `auth.users.id` instead of `clients.id` (silent RLS reject) | 🆕 Filed. **High.** Frontend fix: read `client_id` from `useSessionRoles()` in `useUpsertQuestionnaire`. Plus follow-up audit pass for other direct-Supabase calls with the same mistake. |
| ORPHEUS-58 | Bug: Post-acceptance redirect lands on `/not-invited` transiently (useSessionRoles refetch race) | 🆕 Filed. Low. Frontend fix: await the `['session']` invalidation refetch in `useAcceptInvitation`'s `onSuccess`. |
| ORPHEUS-25 | Cloud Supabase + prod LinkedIn provider configuration | ✅ Done last session. |
| ORPHEUS-21 | Backend: Extend SubDimensionScore with narrative fields | ⏸ Hold pending Andrew's Forward Brief revisions. Unchanged. |
| ORPHEUS-45 | Advisor admin UI: 'Edit' action on client list rows | ⏳ Forward-Brief-safe. UX. Unchanged. |
| ORPHEUS-48 | Multi-tenant branding | ⏸ Deferred. Unchanged. |
| ORPHEUS-40 / 41 / 42 | Stripe, disconnect, account mgmt | ⏸ Beta-deferred. Unchanged. |

No other tickets touched this session.

---

## What this session shipped

Plane housekeeping + bug triage only. No code commits.

### ORPHEUS-44 — partial live e2e walk-through

Ran the test plan from the morning's handoff in order. Got further than the surface "first ticket" outcome would suggest — five distinct bugs surfaced and were diagnosed in flight before the walk hit an irrecoverable blocker.

**Pre-flight (admin shell + empty cloud DB).** Confirmed `auth.users` + 7 public tables all at 0 rows. Tried to sign in with Josh's existing LinkedIn account (primary email at the time: `josh@segarsfamily.com`); `auth.users.email` got the `segarsfamily.com` value, so the `ADMIN_EMAILS` allowlist check failed. Switched LinkedIn primary to `josh@ess3.ai` and signed back in — Supabase's `auth.users.email` column doesn't refresh on re-sign-in (the OIDC claim updates in `raw_user_meta_data` but the indexed column sticks). Resolved by deleting the `auth.users` row (zero cascade because no dependent rows existed yet) and signing in fresh; new row got `josh@ess3.ai` as the canonical email. Hit `/admin` — bounced to `/not-invited`. Surfaced **ORPHEUS-53** (ProtectedRoute pre-empts AdminRoute). Workaround: INSERTed an advisors row pointing at Josh's `user_id`. Hit `/admin` again — still bounced. Surfaced **ORPHEUS-54** (`VITE_API_BASE_URL` was set in Vercel without `https://`, so apiClient was concatenating to the current origin; Vercel was serving `index.html` for `/orpheus-production-5082.up.railway.app/session` with a 304). Fixed the env var, redeployed Vercel. `/admin` then loaded with the empty clients + jobs tables as expected.

**Advisor invite end-to-end.** Clicked invite, filled in display name + a real second-inbox email. Backend correctly created the clients row but Resend send failed with HTTP 403 + `error code: 1010`. Resend's public error code reference doesn't list 1010 — that's a Cloudflare WAF code ("access denied based on browser signature"). Resend sits behind Cloudflare; the hand-rolled `urllib.request` wrapper in `resend_client.py` sends the default `Python-urllib/3.x` UA which CF's bot-signature rule blocks. Surfaced **ORPHEUS-55**. The 502 fallback on the invite endpoint fired correctly — clients row was created and ready for the resend-invitation retry, exactly as the spec contracts. Workaround: extracted the `invitation_token` from the DB and pasted the URL into a fresh browser session. Mid-walk also surfaced **ORPHEUS-56** (PortalNav `<span>` for advisor-only users on `/admin` — no way back to `/advisor/clients` without typing the URL).

Walked through `/invite/<token>` → LinkedIn OAuth (same LinkedIn account, intentional — exercises the dual-role + mismatch confirmation path that Andrew uses in real life) → `/invite/callback`. Mismatch confirmation card rendered correctly; clicked "Continue anyway"; backend accepted. DB state immediately correct: `clients.invitation_status = 'accepted'`, `clients.user_id = 24e9a547...` (the existing advisors row's user_id) — Josh became a dual-role user. Frontend redirect landed on `/not-invited` transiently (probably the `['session']` refetch race — `useAcceptInvitation`'s `onSuccess` invalidates but doesn't await). Surfaced **ORPHEUS-58**. Workaround: manually navigated to `/`, which routed correctly to `/welcome` via SmartIndexRedirect.

**Full client journey.** Got to the questionnaire. Filled in answers. Reloaded — answers gone. `questionnaire_responses` table empty in the DB. Surfaced **ORPHEUS-57** — `useQuestionnaire.ts:86` upserts with `client_id: session.user.id` (which is `auth.users.id` = 24e9a547...) instead of `clients.id` (= 8480c922...). The schema FKs `questionnaire_responses.client_id → clients(id)` and the RLS policy `qr_insert_as_client` checks `client_id = get_client_id()` (which returns `clients.id`). RLS rejects silently; PostgREST returns empty data; React Query's optimistic write picks up the stale shape; user sees "answers don't save" with no error in console or UI. This was the irrecoverable blocker — can't complete Groundwork without a saved questionnaire, can't trigger analysis, can't reach Signal Score / Forward Brief / Cheat Sheet.

**The choice.** At this point we had four bug tickets to file (53, 54, 56, 57) — actually five with 55 — and three of them (53, 56, 57) were the same shape: frontend regressions from ORPHEUS-36/37's schema split that this e2e finally caught. Continuing the walk would mean another deploy cycle to fix 57, then probably more bugs downstream against an analysis pipeline that's never had a real cloud-Supabase run-through. Stopping and burning the bug list down in one focused fix-session is the cleaner play. Josh chose Option A (stop + triage).

**Ownership clarifications captured during the walk.**
- AdminRoute is "a UX gate, not a security boundary" — the backend re-enforces via `get_current_admin`. But ProtectedRoute's neither-role gate sits *in front of* AdminRoute, breaking the design intent (admin can't reach `/admin` without an advisors/clients row of their own). ORPHEUS-53 captures the fix.
- Resend domain `orpheussocial.com` IS verified — the 1010 was not a domain-verification issue. Important to record because Resend's documented 403 errors are dominated by domain-verification cases; the WAF UA story is non-obvious from the docs.
- Anon key uses the legacy `eyJhbG...` JWT format (per ORPHEUS-25's handoff). Still working as expected.

### New tickets filed

| Ticket | Title | Priority |
|---|---|---|
| ORPHEUS-53 | Bug: ProtectedRoute pre-empts AdminRoute for neither-role admins | medium |
| ORPHEUS-54 | Bug: apiClient silently treats VITE_API_BASE_URL without scheme as relative path | medium |
| ORPHEUS-55 | Bug: Resend send fails with Cloudflare WAF 1010 (likely Python-urllib User-Agent) | **high** |
| ORPHEUS-56 | Bug: PortalNav "Manage clients" pill not clickable off /advisor/clients | medium |
| ORPHEUS-57 | Bug: Questionnaire upsert uses auth.users.id instead of clients.id (silent RLS reject) | **high** |
| ORPHEUS-58 | Bug: Post-acceptance redirect lands on /not-invited transiently | low |

Each ticket has a clear repro section, fix sketch, and (where applicable) a "workaround applied during ORPHEUS-44" note for the record.

---

## Recommended pickup for next session

**Fix-session burning down ORPHEUS-53 through ORPHEUS-58**, then re-running ORPHEUS-44 from the top. Suggested order — high-priority first, then the cluster of same-shape schema-split regressions, then the polish:

1. **ORPHEUS-57** (`useQuestionnaire.ts` client_id source). Highest-impact unblocker — without it the whole client journey is stuck.
2. **ORPHEUS-55** (Resend UA). One-line backend fix. Should be paired with a manual smoke test through the live invite flow once Railway redeploys.
3. **ORPHEUS-53** (ProtectedRoute admin gate). Lighter-touch fix per the ticket's option (a): add `isAdminEmail(session.user.email)` bypass to ProtectedRoute's neither-role branch.
4. **ORPHEUS-56** (PortalNav pill). Route-conditional rendering.
5. **ORPHEUS-54** (apiClient fail-fast). Defensive — won't bite again now that the env var is fixed, but cheap insurance.
6. **ORPHEUS-58** (post-acceptance refetch race). Low priority — workaround is one extra nav. Land if there's time.

**Then re-run ORPHEUS-44** against the existing test data (the advisors row + accepted clients row stay in cloud Supabase, the dual-role state is preserved). Specifically:

- Skip the pre-flight signup dance — Josh's `auth.users` row + advisors + clients row are already linked.
- Start at the questionnaire (now actually saves).
- Complete Groundwork. Need LinkedIn ZIP + XLSX exports — generate the ZIP request first (24-hour lead time on LinkedIn's side).
- Walk through analysis polling → Signal Score render → Forward Brief → Cheat Sheet.
- Switch to advisor view; verify the View report uncloak (ORPHEUS-46).
- Edit a narrative from `/admin` (ORPHEUS-31); confirm persistence.

**The follow-up audit** ORPHEUS-57's ticket flags: focused grep over `frontend/src/` for direct-Supabase calls using `session.user.id` where they need `clients.id` / `advisors.id`. Worth doing as part of the fix-session — if the same regression hit `useGroundworkProgress` or any other hook, we'd want to catch it before the re-run. ORPHEUS-37 closed the backend side of this migration; the frontend may still have other pockets.

**Alternative pickups (unchanged from 2026-06-01 part 1):**

- **ORPHEUS-21 (sub-dim narrative fields)** if Andrew's Forward Brief revisions have landed. Same rationale as prior handoffs.
- **ORPHEUS-45 (Edit action on client rows).** Concrete-but-small advisor UX win.
- **Loading-flicker polish on the PortalNav cluster** (carry-forward).
- **"Prepared for [own name]" on `/advisor/clients` + `/admin`** (carry-forward).
- **CONVENTIONS.md update for same-day handoffs** (carry-forward from 2026-05-30_part3).
- **`frontend/src/assets/waves.jpg` cleanup** (carry-forward from 2026-05-30_part2).
- **AdminRoute tightening** (carry-forward from 2026-05-31_part2).
- **Anon-key format migration to `sb_publishable_*`** (carry-forward from 2026-06-01 part 1).

The fix-session is the clear top recommendation though — ORPHEUS-44 should pass cleanly on the re-run, unblocking the "this works in production" milestone.

---

## Caveats / things that will bite

1. **Cloud Supabase now has test data.** Josh's `auth.users` row (24e9a547-b619-4da3-a56f-ca6ca8a84fbb) is linked to both an advisors row (a1fc0d94-4447-404c-a91c-5e1246e9c55f, `practice_name = "Orpheus Social (test)"`) and an accepted clients row (8480c922-fec3-4415-a815-b36d201cfcd3, `display_name = "Joshua Segars"`, `email = "josh@segarsfamily.com"`, `invitation_status = "accepted"`). This is **intentional** — preserved for the ORPHEUS-44 re-run. If a future test needs a clean DB, delete the auth.users row (cascade clears everything) and start over.
2. **`VITE_API_BASE_URL` on Vercel now permanently has `https://` prefix.** Don't strip it. ORPHEUS-54's fail-fast fix would catch this in the future, but until that lands, it's a manual contract.
3. **Resend domain `orpheussocial.com` is verified.** Doesn't fix ORPHEUS-55 (the WAF UA issue is independent), but confirms the domain-side is clean.
4. **`josh@ess3.ai` is now Josh's primary LinkedIn email.** Off-platform side effect from the e2e — his LinkedIn network sees the ess3.ai email when looking at his profile. If this needs to revert, switch primary back in LinkedIn settings.
5. **ORPHEUS-44 itself stays in Backlog with the closing comment**, not Done — the walk isn't complete. The closing comment is on the ticket as a partial-walk record; the re-run after the fix-session is what closes it.
6. **First HTML-comment posted on ORPHEUS-44 had escaped HTML** (the `comment_html` payload was pre-escaped by mistake). A clean re-post is immediately below it with an "Re-post — prior comment had escaped HTML" preamble. The bad comment is left in place — the Plane MCP doesn't expose a delete-comment tool. Worth knowing if anyone audits the comment thread later.
7. **Sandbox proxy blocks `*.supabase.co`** — carry-forward from 2026-06-01 part 1. The Supabase MCP path works fine; direct `curl`/`web_fetch` against the project URL is blocked.
8. **Sandbox can't run pytest** (PyPI blocked) — carry-forward. Backend pytest baseline unchanged from the ~180-green ORPHEUS-31 baseline. No tests added or removed this session.
9. **`.git/*.lock` workaround still needed before each commit** — same pattern as every prior session.
10. **Compliance drafts at repo root remain intentionally untracked** — Privacy Policy / TOS / DPA drafts. Don't `git add` them.
11. **Andrew's Forward Brief revisions are still pending** — holds ORPHEUS-21.

---

## State of the repo right now (end of session)

After the handoff commit this skill produces:

```
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (<handoff-sha> Session handoff: 2026-06-01 part 2. Retire 2026-06-01.)

Untracked (intentionally — all in .gitignore):
  LinkedIn_BD_DPA_Review_2026-05-07.md
  Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}
  Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}
  Signal_Score_Dimensions_Reference_2026-05-20.md
```

`SESSION_HANDOFF_2026-06-01.md` is retired in this commit.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Latest Decision Log entries:** 2026-05-29 Signal Score redesign + dark mode (ORPHEUS-50); 2026-05-29 band rename (ORPHEUS-49); 2026-05-20 ownership clarification + canon adoption. (No new Decision Log entry drafted this session — ORPHEUS-44's partial walk is execution + bug discovery, not a new cross-stakeholder decision.)
