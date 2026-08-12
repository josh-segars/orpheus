# Session Handoff — 2026-08-12 part 2

Replaces `SESSION_HANDOFF_2026-08-12.md` — everything it described carries forward or closed as follows:

- **The three live-validation waits carry unchanged** (ORPHEUS-120 / 114 / 121, all In Progress) — plus this session added a fourth and fifth to the same watch: ORPHEUS-85 + 129 close on the first real code-gated sign-up. A single new real submission through /signup followed by completion would now advance **five** tickets at once (85, 129, 121, 114, and 119 if the client is first-time under `is_individual=true` — which every house-advisor self-serve client is).
- **This session's work: self-serve sign-up (ORPHEUS-85) + the sign-up code system (ORPHEUS-129)**, built in one arc — the interim single-env-code design was replaced by the codes table the same day, before first deploy, so `BETA_ACCESS_CODE` never existed in prod. All code is in-tree and committed with this wrap; **nothing is deployed yet** (see Pending).
- **The `python-multipart` caveat (carried since 07-27) is RESOLVED** — removed from `requirements.txt` in this session's code commit, verified by uninstalling it in the cloud sandbox: app imports clean, full suite green without it.
- **ORPHEUS-126's per-upload consent leg and ORPHEUS-119's first-time-completion email remain event-gated** (carried). Karen's re-invite, Tim's §11 confirmation list, the ORPHEUS-90 Decision Log paste, the `_to_delete/` cleanup, and the Andrew comms items all carry (see Pending).
- **Context: `2cbf9d0` (ORPHEUS-126 consent-block styling fix) landed after the morning handoff** and was already pushed before this session's work began. No open thread.

---

## ORPHEUS-85 — self-serve client sign-up (In Progress, closes on first real sign-up)

Revises the [2026-05-11] "beta is invitation-only (no /signup)" decision. **A Decision Log entry is owed at go-live** (the ticket flags it as cross-stakeholder; pricing/metering implications are Tim-adjacent).

**Backend:** `POST /signup/complete` (new `backend/routers/signup.py`, registered in main), gated by `get_verified_session` like /accept-invitation — the completion IS the clients-row creation step. Decision tree: fail-closed feature gate (503 unless `HOUSE_ADVISOR_ID` set) → **idempotent replay for already-linked callers BEFORE the code check** (a rotated/disabled code must not lock a returning client out; ORPHEUS-83 one-row-per-user) → code validation (see 129) → advisor resolution + existence probe (503 over FK-500) → INSERT born `invitation_status='accepted'` with `invitation_token NULL` → 23505 race backstop refetches by user_id. Display name from LinkedIn OIDC metadata, email-local-part fallback.

**Frontend:** public `/signup` (beta code + ToS checkbox + LinkedIn OIDC; the code and consent versions ride the OAuth `redirectTo` URL per the ORPHEUS-92 carrier pattern, sessionStorage fallback) and `/signup/callback` (mirrors InviteCallbackPage, including the hash-preserving URL strip — the caveat-6 outage mechanism). A missing or wrong code is **recoverable inline**: the callback re-prompts without an OAuth re-run. Already-authenticated neither-role users (from /not-invited's new "sign up directly" link) complete in place on /signup — no OAuth round trip; their ToS acceptance posts directly to /consent/terms (TermsAcceptanceRecorder's once-per-mount effect has already run by then). /login gains a "New to Orpheus? Sign up" crosslink.

**House advisor decided [Josh, 2026-08-12]: a dedicated row, NOT Andrew's practice row.** Post-ORPHEUS-120, `is_individual` controls report visibility — Andrew's advisory row would gate every self-serve report behind his manual /admin publish, where the dedicated row (`is_individual=true`) auto-publishes at completion and fires the ORPHEUS-98 email. Created in cloud prod via the Supabase MCP: advisors row **`6b9922b9-9222-4774-86b6-5148405cedc4`** (practice_name "Orpheus Social"), owned by new auth user `e68769d8` / house@orpheussocial.com — email-confirmed, unusable password, no LinkedIn identity, domain has no mailboxes (ORPHEUS-118), so the account is unclaimable. String token columns set to `''` not NULL (the GoTrue NULL-scan issue would break `auth.admin.list_users()`, which /admin's advisor-email resolver calls). **Consequence: self-serve clients surface in /admin (god-mode), not on any advisor's roster** — supersedes the session's earlier "visible in the house advisor's roster" framing; flagged for Andrew.

**Closes on:** the first real self-serve sign-up — new user completes /signup with a live code, lands in the portal, clients row sits under the expected advisor.

---

## ORPHEUS-129 — sign-up code system (In Progress, shares 85's live event)

**Migration 022 (`signup_codes` + `code_redemptions`) — applied to cloud 2026-08-12 via the Supabase MCP** (ladder entry `signup_codes`). Codes carry label, optional `advisor_id` routing override, optional `expires_at` / `max_uses`, `disabled_at` kill switch, `created_by` (admin email, text not FK). Redemptions are one-per-client (unique index), CASCADE with the client (ORPHEUS-124 deletion takes attribution with it), and are **the source of use counts — there is deliberately no counter column to drift**. RLS enabled with no policies on both tables (service-role only, the waitlist posture).

**Gate:** `_find_active_code` validates existence → disabled → expiry → max-uses with **one generic 403 for all four** (no enumeration help). Lookup is case-insensitive via `ilike` with wildcard escaping (`_escape_ilike` — a vanity code containing `%`/`_` must match literally; pinned by test). Advisor resolution: code override → house default; a code whose advisor was deleted falls back to house via ON DELETE SET NULL. Redemption insert is **best-effort after the clients row exists** — bookkeeping never unwinds an account; failure logs loudly.

**Admin surface:** `GET/POST /admin/codes` + `PATCH /admin/codes/{id}` (disable/enable only — in-place editing deliberately out of scope; mint a new code instead). Generated codes are `ORPH-XXXX-XXXX` from a no-lookalikes alphabet (I/L/O/0/1 excluded, ~2^39.6 space); vanity codes allowed (409 on case-insensitive collision). AdminPage Codes section follows the ORPHEUS-104 waitlist pattern: create form, minted-code notice with the shareable `/signup?code=…` link, list with redemption counts + routing labels + per-row Disable/Enable. `/signup?code=` prefills the input so a business cohort gets one link.

**Punted [Josh, 2026-08-12]: free-report codes** — they redeem at job submission and imply an entitlements/credits model that shouldn't be designed ahead of ORPHEUS-40/Stripe. Recorded in the ticket as explicitly out of scope.

**Closes on:** same event as 85 — /admin shows the redemption count tick up and the client lands under the expected advisor.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-85 | Self-serve client sign-up | 🔄 In Progress — in-tree + committed; closes on first real code-gated sign-up |
| ORPHEUS-129 | Sign-up code system (codes table + admin surface) | 🔄 In Progress — migration applied to cloud; shares 85's live event |
| ORPHEUS-120 | Advisory draft gate | 🔄 In Progress — carried; closes on Andrew's first real publish |
| ORPHEUS-114 | Reconciliation gate + registry | 🔄 In Progress — carried; closes on first worker-run job |
| ORPHEUS-121 | Prose-number gate | 🔄 In Progress — carried; closes on first real generation |
| ORPHEUS-126 | Route A consent capture | 🔄 In Progress — carried; per-upload leg event-gated |
| ORPHEUS-119 | Report-ready email path | 🔄 In Progress — carried; **a house-advisor self-serve client's first completion IS this event** |
| ORPHEUS-115 | Prose mislabels (bug D) | ⏳ Backlog (medium) — unblocked, carried |
| ORPHEUS-111 | Upload size caps misaligned | ⏳ Backlog (medium) — carried |
| ORPHEUS-116 / 99 / 94 / 84 / 107 | unchanged | ⏳ Backlog |

Baselines: backend pytest **558 green** (526 → 558; test_signup.py 20 + new test_admin_codes.py 13), frontend vitest **150 green** (132 → 150), `tsc -b` + vite production build clean. **Measured** — cloud Cowork session; Josh's terminal should match. `python-multipart` verified absent (suite runs without it installed).

---

## Pending — manual steps

1. **Deploy sequence for /signup (in order):** (a) push this wrap's two commits; (b) confirm Railway backend + worker and Vercel all redeploy green — note `requirements.txt` changed, so Railpack does a fresh dependency resolve (python-multipart drops out; expected); (c) `HOUSE_ADVISOR_ID` is already set on the Railway backend service (2026-08-12, pre-push — the running old code ignores it harmlessly); (d) **mint the first code** (closed beta) in /admin's new Codes section — until one exists, /signup rejects everyone; (e) optional sanity check: wrong code → inline re-prompt, right code → portal.
2. **Watch for the live-validation events** — now five tickets riding two events: a real code-gated sign-up (85 + 129) whose subsequent submission + completion also exercises 121, 114, 126's consent leg, and — because house-advisor clients are `is_individual=true` first-timers — ORPHEUS-119's email verification. **A single recruited beta user through /signup is the highest-leverage validation action available.** Andrew's first review-then-release (120) remains separate.
3. **ORPHEUS-85 Decision Log entry at go-live** (revises the 2026-05-11 invitation-only decision) — joins the long-carried ORPHEUS-90 paste. Draft language exists in the ticket's comments.
4. **Re-invite Karen** from the test roster when she wants a fresh report (carried).
5. **Delete the surplus ORPHEUS-123 Plane comments** (dashboard job; keep `6a6c67ce`) (carried).
6. **Tim's confirmation list for Privacy Policy §11 and §7/§9 claims** (carried verbatim).
7. **Empty `_to_delete/`** at repo root — now also contains `orpheus_snapshot_085.tar.gz` (~12 MB), this session's staging tarball; safe to delete.
8. **Andrew comms, carried + new:** (a) Nicole / ORPHEUS-63 score-0 posture; (b) Jenn MIME retry; (c) Jodie onboarding nudge; (d) growth factors + ORPHEUS-112 caveat; (e) the 14 backfilled clients' feedback asks permanently unsent; (f) reconciliation tolerances + registry descriptions open to his review; **(g) new: self-serve sign-up exists** — clients arriving through it are NOT on his roster (visible in /admin only), his invitation flow is unchanged, and a group/business code can route a cohort under his practice row if he ever wants that (it would put those reports behind his review-then-release, by design); **(h) new: whether he wants a recruited beta user pushed through /signup** to bank the five-ticket validation event.

---

## Recommended pickup for next session

1. **If the live events fired between sessions, close tickets first** — the progress comments on each state the exact evidence required. The /signup event alone could close 85 + 129 and advance 121/114/119.
2. **ORPHEUS-115** (prose mislabels) — unchanged top code recommendation from the morning handoff: the 114 registry's canonical labels are its substrate, the 121 gate is its enforcement pattern.
3. **ORPHEUS-111** (upload size caps) — small, self-contained, long-carried.

---

## Caveats / things that will bite

1. **/signup is fail-closed in two independent ways:** `HOUSE_ADVISOR_ID` unset → 503; no active `signup_codes` row → every code 403s. Both must be true to open the funnel. The 503 detail says "ask your advisor for an invitation" — correct copy for the closed state.
2. **Self-serve clients rows have `invitation_token IS NULL`** — any future flow assuming every clients row was minted by /clients/invite (e.g. a resend sweep) must tolerate that. Their `invitation_status` is 'accepted' from birth.
3. **`signup_codes` + `code_redemptions` are service-role only** (RLS enabled, no policies) — /admin/codes is their only in-app surface; a frontend query against them returns nothing, not an error.
4. **`max_uses` is check-then-insert, not atomic** — concurrent redemptions of a code's last seat can over-redeem by 1. Accepted at beta scale, documented on migration 022; the claim_next_job RPC is the pattern if it ever matters.
5. **The house auth user (`e68769d8`) is load-bearing and deliberately unclaimable** — unusable password, no LinkedIn identity, no mailbox behind the domain. Do NOT delete it: `advisors.user_id` is NOT NULL and CASCADE, so deleting the auth user deletes the house advisor row and every self-serve client under it. Its token columns are `''` not NULL on purpose (GoTrue list_users NULL-scan).
6. **Code lookup goes through `ilike` with escaping** — if a future change replaces `_find_active_code`'s lookup, preserve both the case-insensitivity (migration 022's unique index is on `lower(code)`) and the wildcard escaping (pinned by `test_escape_ilike_neutralizes_wildcards`).
7. **`python-multipart` is GONE from requirements.txt** (this session, code commit) — if a future route reintroduces `Form`/`File`/`UploadFile`, FastAPI fails loudly at import telling you to install it. That's the designed failure.
8. **`reports.published_at` is load-bearing on the read path** (carried) — and self-serve completions now depend on the worker stamping it (that's what makes house-advisor reports instantly visible).
9. **A reconciliation failure fails the job by design; `PROSE_NUMBER_GATE` is the prose gate's valve** (carried verbatim from the morning handoff, both unchanged).
10. **The jobs-router FIFO test queues include a `reports` read** (carried); **pre-114 stored rows are never retro-checked** (carried).
11. **Module-load URL rewrites must preserve `location.hash`** (carried — and `/signup/callback`'s code-strip explicitly preserves it; keep it that way).
12. **The document effective date is load-bearing in three places** (carried); **committed ≠ applied for migrations** (carried — 021 and 022 are both applied; ladder and repo agree today).
13. **Cross-session work may arrive without its tests run; cloud Cowork sessions can run both suites** (carried — this session measured 558/150); the on-device sandbox limitations (no pip, no SSH push, `git fetch` fails, unlink quirks) still apply.
14. **Device-bridge file transfer can't unlink; stale `.git/index.lock` files recur** (carried — `mv` aside before commits).
15. **Legal/public pages use the canonical `nav / main-interior / footer` column** (carried). `/signup` + `/signup/callback` use the `login-shell` card scaffold like /login and /not-invited — they're auth surfaces, not legal pages.
16. **Untracked-by-intent set unchanged** from the morning handoff: `Draft_*.md`, `Scoping_*.md`, `Survey_*.md`, `ORPHEUS-*_Decision_Brief_*.md`, `rubric_consistency_results_*.json`, `create_beta_survey_form.gs`, `outputs/`, `.claude/settings.local.json`, `_to_delete/` (all gitignored). `git check-ignore -v <path>` before trusting any new root file.
17. **Plane MCP double-escape quirk** (carried — held correct across four comments this session); **never pin `opsz`; never rename the faces back to "Source ..."** (carried); **a clean run doesn't prove a stochastic prose bug fixed; verify the deploy before asking anyone to re-run; growth factors are PROVISIONAL** (carried).
18. **Email-path items carried:** outages invisible from inside the product; a returning/advisory client completing is NOT an ORPHEUS-119 verification event — but a house-advisor self-serve client's first completion IS; the ORPHEUS-110 part-1-partial sub-question needs a real sample; do not use Resend's Auto configure button.

---

## State of the repo right now

Two commits this session, on top of `2cbf9d0`:

- **ORPHEUS-85 + ORPHEUS-129 code commit** — self-serve sign-up behind admin-generated access codes: `backend/routers/signup.py`, migration 022, `/admin/codes` endpoints, `/signup` + `/signup/callback` pages, `/admin` Codes section, tests (backend +33 net, frontend +18 net), `python-multipart` removal.
- **This wrap commit** — session handoff 2026-08-12 part 2, CLAUDE.md / PRODUCT_CONTEXT.md / CREDENTIALS.md refreshes, retire the morning handoff.

**Neither commit is pushed** — the push command is the session's final manual step, and the deploy sequence in Pending item 1 follows it.

**Prod config beyond source (all done this session, all pre-deploy by design):** migration 022 applied to the cloud DB via the Supabase MCP; house advisor row `6b9922b9…` + auth user `e68769d8` created in cloud prod; `HOUSE_ADVISOR_ID` set on the Railway backend service. The four DNS records in the Vercel zone unchanged. **No code deploy has happened** — the Railway restart Josh observed 2026-08-12 was the env-var change against the old code.

New modules this session: `backend/routers/signup.py`, `backend/migrations/022_signup_codes.sql`, `backend/tests/test_signup.py` (reworked), `backend/tests/test_admin_codes.py`, `frontend/src/lib/signup.ts`, `frontend/src/hooks/useCompleteSignup.ts`, `frontend/src/pages/SignupPage.{tsx,css}`, `frontend/src/pages/SignupCallbackPage.tsx`, `frontend/src/pages/__tests__/SignupFlow.test.tsx`.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Landing copy doc ID:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk`
- **Privacy Policy drafting Doc:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting Doc:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — drafting surfaces only; **the canonical published text is the repo markdown** at `frontend/src/content/legal/`.
- **Pending pastes:** ORPHEUS-90 4.6-acceptance entry (carried since 06-24); **ORPHEUS-85 owes its entry at go-live** (revises the 2026-05-11 invitation-only decision; draft language in the ticket comments).
