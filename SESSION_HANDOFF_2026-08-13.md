# Session Handoff — 2026-08-13

Replaces `SESSION_HANDOFF_2026-08-12_part2.md` — everything it described carries forward or closed as follows:

- **Its Pending item 1 (the /signup deploy sequence) was already done when this session started** and the handoff didn't know. Push, Railway/Vercel redeploy, `HOUSE_ADVISOR_ID`, and minting the first code all completed on 08-12; `/signup` has been live in production since ~17:20 UTC that day.
- **Its "five tickets riding two events" framing was half-satisfied and unrecorded.** The first real code-gated sign-up happened 2026-08-12 19:02 UTC. **ORPHEUS-85 + ORPHEUS-129 are closed** on that evidence (this session, retroactively, from the database). The other three — 121 / 114 / 119 — have NOT advanced, because that client never submitted an archive.
- **This session's work: ORPHEUS-130**, filed and shipped in one arc — in-app browsers are blocked from the LinkedIn OIDC hop. Committed as `0aca889` and **pushed on the third attempt** after two consecutive failures (see caveat 3); Vercel should be building it.
- **Two commits from 08-12 that the previous handoff never mentioned** — `0fe2de9` and `2c99f9d` — landed after its wrap commit and are already on origin. Nothing was lost; the handoff simply stopped describing the repo 40 minutes before the session stopped changing it.
- ORPHEUS-126's per-upload consent leg, ORPHEUS-120's first real publish, Karen's re-invite, Tim's §11 list, the ORPHEUS-90 Decision Log paste, `_to_delete/`, and the Andrew comms items all carry unchanged (see Pending).

---

## ORPHEUS-130 — in-app browser breaks LinkedIn OIDC (In Progress, closes on deploy + live check)

**The report read as a login loop and was not one.** Tarita Bennett Kenny, over LinkedIn DM: *"it jumps to LI and then I see a very quick flash of a screen about Orpheus before LI kicks in again and my profile and feed pop up. I don't even get an opportunity to engage with the Orpheus screen at all."* The tell is that the sequence **terminates inside LinkedIn**, on her own feed. A loop in our app would have left her on our login card.

**The diagnosis came from an absent log line, not a present one.** Supabase auth logs for her four attempts (2026-08-13 01:19–01:26 UTC): **four `/authorize` "Redirecting to external provider" hits, zero `/callback` hits.** No `auth.users` row exists for her at all, so not one line of our code has ever executed on her behalf. That single fact eliminated ORPHEUS-126's hash-strip outage (which produced real callbacks), the consent gate, and the access code, without touching any of them. The contrast case is one row above in the same log: Adam Tousley, 08-12 19:02, one `/authorize` → `/callback` → `/token`, user created, clean pass.

**Root cause:** the link is tapped inside the LinkedIn app, so it opens in LinkedIn's in-app browser; when we hand off to `linkedin.com/oauth/v2/authorization` the app deep-link-intercepts its own domain, cannot render an OAuth consent screen inside itself, and drops the user on the feed. The report arriving *as a LinkedIn DM screenshot* is itself the evidence for the channel.

**Shipped** (`0aca889`, 9 files, +950): `frontend/src/lib/inAppBrowser.ts` (UA detection for LinkedIn / Instagram / Facebook / Messenger / Slack / X / generic Android WebView, platform resolution, session override) and `frontend/src/components/InAppBrowserNotice.{tsx,css}` (the guard card, exporting `useInAppBrowserGuard`), wired into `/login`, `/signup` and `/invite/:token`; one new `content_copy` entry in MaterialIcon.

**Decisions locked [Josh, 2026-08-13]:** hard block with an escape hatch (not an advisory banner — the failure is silent from the user's side, so a warning above a live button gets clicked straight through); LinkedIn plus the common set, not LinkedIn alone; all three doors, including the invite landing page.

**Three implementation notes worth keeping:**

1. The guard is a **value, not a wrapper component**, because `/invite/:token` had to *suppress a mount-time effect*, not swap markup. A wrapper could not have reached it.
2. The override keeps an **in-memory mirror** of its sessionStorage flag. These webviews are exactly the environments that partition or throw on storage (the ORPHEUS-92 lesson), so a storage-only override could evaporate and re-trap the user behind the block meant to release them.
3. Copy-link copies `window.location.href`, not the origin — an invitation token or `?code=` prefill has to survive the move into the real browser, or a one-tap fix becomes "ask your advisor to resend the invitation."

**Verification:** frontend vitest **154 → 186 green** (+22 detection, +10 page-level), `tsc -b` clean, vite production build clean (to a scratch outDir — see caveat 3). No backend change. No prototype backport: the auth surfaces are React-only, the ORPHEUS-76 precedent.

**Closes on:** deploy, then Tarita completing sign-up. Note she is a **/signup user, not an invitee** — she has no clients row, so her path is `https://app.orpheussocial.com/signup?code=ORPH-Z32A-K7VA`, opened in a real browser.

---

## ORPHEUS-85 + ORPHEUS-129 — closed 2026-08-13 on found evidence

Both were In Progress awaiting "the first real code-gated sign-up." It had already happened and nobody had looked.

**The event:** Adam Tousley, auth user `4cdef43c` (LinkedIn OIDC) at 2026-08-12 19:02:33 UTC; clients row `176450e3` at 19:02:35.563; `code_redemptions` row against `ORPH-Z32A-K7VA` at 19:02:35.678.

Every design claim is legible in the row shape: `advisor_id = 6b9922b9…` (the dedicated house row, practice "Orpheus Social" — not Andrew's practice, which post-ORPHEUS-120 would have parked the report behind manual publish), `invitation_status='accepted'` with `invitation_token IS NULL` (born accepted), exactly one clients row for the user (ORPHEUS-83's invariant holding through a path that didn't exist when the index was written). The **113 ms gap** between the clients row and the redemption row is the specified best-effort-after-the-account-exists ordering, visible in production data — worth preserving as evidence if anyone later proposes making redemption a precondition of row creation.

**What it did not close:** Adam has **zero jobs**. ORPHEUS-121, 114, 119 and 126's per-upload leg all still want the same thing — one self-serve client who uploads and completes.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-130 | In-app browser breaks LinkedIn OIDC | 🔄 In Progress — `0aca889` in tree, **unpushed**; closes on deploy + live check |
| ORPHEUS-85 | Self-serve client sign-up | ✅ **Done 2026-08-13** — Decision Log entry still owed |
| ORPHEUS-129 | Sign-up code system | ✅ **Done 2026-08-13** |
| ORPHEUS-120 | Advisory draft gate | 🔄 In Progress — carried; closes on Andrew's first real publish |
| ORPHEUS-114 | Reconciliation gate + registry | 🔄 In Progress — carried; closes on first worker-run job |
| ORPHEUS-121 | Prose-number gate | 🔄 In Progress — carried; closes on first real generation |
| ORPHEUS-126 | Route A consent capture | 🔄 In Progress — carried; per-upload leg event-gated |
| ORPHEUS-119 | Report-ready email path | 🔄 In Progress — carried; a house-advisor client's first completion IS this event |
| ORPHEUS-115 / 111 / 116 / 99 / 94 / 84 / 107 | unchanged | ⏳ Backlog |

Baselines: frontend vitest **186 green** (154 → 186; measured on Josh's machine this session), `tsc -b` + vite production build clean. Backend pytest **558 green**, untouched this session.

---

## Pending — manual steps

1. **Confirm the Vercel build went green** for `0aca889` and that the guard renders in production. The push landed on the third attempt (see caveat 3), so the frontend deploy should already be running; this wrap commit is docs-only and needs a routine `git push origin main`.
2. **Re-run Tarita once the deploy is confirmed.** Send her `https://app.orpheussocial.com/signup?code=ORPH-Z32A-K7VA` — she is a `/signup` user with no clients row, so the invite path is not hers. Her completing sign-up is what closes ORPHEUS-130.
3. **Two other beta testers may be silently stuck in the same trap.** The guard cannot help anyone who already gave up. Worth a direct nudge once it's live — and worth deciding whether beta invitations should travel by email rather than LinkedIn DM, which is an ops choice the guard makes survivable either way but does not eliminate.
4. **ORPHEUS-85's Decision Log entry is now overdue** (revises the 2026-05-11 invitation-only decision; draft language in the ticket's comments). "At go-live" has passed. Joins the long-carried ORPHEUS-90 4.6-acceptance paste.
5. **The live-validation watch, restated accurately:** one self-serve client who *uploads and completes* advances 121 + 114 + 126's consent leg + 119 in a single run. Andrew's first review-then-release (120) remains separate. A sign-up alone does nothing further — that half is spent.
6. **Re-invite Karen** from the test roster when she wants a fresh report (carried).
7. **Delete the surplus ORPHEUS-123 Plane comments** (dashboard job; keep `6a6c67ce`) (carried).
8. **Tim's confirmation list for Privacy Policy §11 and §7/§9 claims** (carried verbatim).
9. **Empty `_to_delete/`** at repo root, including `orpheus_snapshot_085.tar.gz` (~12 MB) (carried).
10. **Andrew comms, carried:** (a) Nicole / ORPHEUS-63 score-0 posture; (b) Jenn MIME retry; (c) Jodie onboarding nudge; (d) growth factors + ORPHEUS-112 caveat; (e) the 14 backfilled clients' feedback asks permanently unsent; (f) reconciliation tolerances + registry descriptions open to his review; (g) self-serve sign-up exists and those clients are NOT on his roster (visible in `/admin` only); (h) whether he wants a recruited beta user pushed through `/signup` — **still the highest-leverage validation action available**, and now known to require a completed *report*, not just an account.

---

## Recommended pickup for next session

1. **Confirm the deploy and close ORPHEUS-130** on the live check — Tarita completing sign-up in a real browser is the acceptance event.
2. **ORPHEUS-115** (prose mislabels) — unchanged top code recommendation across three handoffs now: the 114 registry's canonical labels are its substrate, the 121 gate is its enforcement pattern.
3. **ORPHEUS-111** (upload size caps: 50 MB Storage reality vs 150 MB advisory vs 200 MB copy) — small, self-contained, long-carried.

---

## Caveats / things that will bite

1. **Do not put `blocked` from `useInAppBrowserGuard` in a dependency array.** It is a fresh object every render; `InviteLandingPage` derives the primitive `isBlocked` for exactly that reason. Getting this wrong re-fires the OAuth redirect on every render.
2. **The in-app detection is a UA heuristic and always will be.** That is why the hard block ships with a visible escape hatch, and why the test suite's negative half (eight mainstream UAs pinned as non-matches) is the load-bearing part. Adding a pattern — WeChat, Line, Snapchat, TikTok, Pinterest, the Google app — is a one-line change to `IN_APP_PATTERNS`; loosening one is how you hard-block Safari.
3. **Two consecutive push failures on 2026-08-13 resolved on a plain third retry — don't over-diagnose this one next time.** Attempt 1 (14:40 UTC) returned GitHub `500 Internal Server Error` (Request ID `d7faad12f713afe820d8d7c550251236`) *after* writing 19 objects and resolving deltas server-side, dying at the ref-update step. Attempt 2 (~14:45) returned `git@github.com: Permission denied (publickey)`. GitHub Status was green throughout, and the ssh-agent triage (`ssh -T git@github.com`, `ssh-add -l`, keychain re-add) turned out not to be needed. Worth remembering the shape: a push that authenticates, transfers, and then fails at ref update is server-side, and a publickey error immediately after a successful authentication is more likely transient than a real key problem. Escalation ladder if it does recur and persist: `ssh -T git@github.com` → `ssh-add --apple-use-keychain ~/.ssh/id_ed25519` (plus `AddKeysToAgent yes` / `UseKeychain yes` in `~/.ssh/config`) → HTTPS remote via `gh auth login` → `git push origin main --no-thin` for a repeat 500 on a healthy key.

4. **`npm run build` fails from the device sandbox** with `EPERM: unlink` when `dist/` already exists — the same can't-unlink limitation as `.git/*.lock`. Build to a scratch path instead: `./node_modules/.bin/vite build --outDir /tmp/<name> --emptyOutDir`. `tsc -b` and `vitest run` both run fine in place.
5. **A wrap is not a stop signal.** The 08-12 handoff was written at 17:08 and two more commits landed at 17:30 and 17:47, so it under-described `main` for a day. If work continues after the wrap ritual, amend the handoff or write a part-2 — a future session trusts that document over the repo.
6. **Closing events can fire while nobody is looking.** ORPHEUS-85/129's evidence sat in production for a day. When a ticket's closing condition is a *user action* rather than a deploy, check the database at session start rather than waiting to be told.
7. **`GET /jobs`-style Plane and log tooling truncates.** `list_project_issues` and 24h `query_logs` dumps both exceed the tool output cap; filter or aggregate in the query (`toStartOfHour`, `group by`) rather than pulling raw rows.
8. **Self-serve clients rows have `invitation_token IS NULL`** and `invitation_status='accepted'` from birth (carried) — any future flow assuming every clients row came from `/clients/invite` must tolerate that.
9. **`signup_codes` + `code_redemptions` are service-role only**; `max_uses` is check-then-insert, not atomic (carried); the house auth user `e68769d8` is load-bearing and deliberately unclaimable — deleting it CASCADEs away the house advisor and every self-serve client under it (carried).
10. **Module-load URL rewrites must preserve `location.hash`** (carried — `/signup/callback` and `consent.ts` both do; keep it that way, it was a live sign-in outage on 08-11).
11. **The document effective date is load-bearing in three places** (documents, `lib/consent.ts`, `backend/consent_versions.py`) — bump together (carried). **Committed ≠ applied for migrations** (carried; 021 and 022 are both applied).
12. **A reconciliation failure fails the job by design; `PROSE_NUMBER_GATE` is the prose gate's valve** (carried unchanged).
13. **Sandbox limits** (carried): no `pip install`, so backend pytest runs from Josh's terminal; SSH egress blocked, so `git fetch`/`push` can't run here — note that `refs/remotes/origin/main` is still readable and is how this session established that `0fe2de9`/`2c99f9d` were already pushed; `.git/*.lock` needs `mv` aside before each commit; `.git/objects/tmp_obj_*` warnings are cosmetic.
14. **Untracked-by-intent set unchanged:** `Draft_*.md`, `Scoping_*.md`, `Survey_*.md`, `ORPHEUS-*_Decision_Brief_*.md`, `rubric_consistency_results_*.json`, `create_beta_survey_form.gs`, `outputs/`, `.claude/settings.local.json`, `_to_delete/` (all gitignored — `git status --short` shows no `??` entries, which is the expected state, not a sign they're missing). `git check-ignore -v <path>` before trusting any new root file. **Never `git add -A`.**
15. **Plane MCP double-escape quirk** (carried — held correct across three comments this session: pre-escape the HTML entities). **Never pin `opsz`; never rename the faces back to "Source …"** (carried). **A clean run doesn't prove a stochastic prose bug fixed; verify the deploy before asking anyone to re-run; growth factors are PROVISIONAL** (carried).
16. **Email-path items carried:** transactional-email outages are invisible from inside the product; a returning or advisory client completing is NOT an ORPHEUS-119 verification event, but a house-advisor self-serve client's first completion IS; do not use Resend's Auto configure button (the dashboard still names GoDaddy; the zone is Vercel's).

---

## State of the repo right now

Two commits this session, on top of `2c99f9d`:

- **`0aca889`** — ORPHEUS-130, the in-app browser guard (9 files, +950).
- **This wrap commit** — session handoff 2026-08-13, CLAUDE.md + PRODUCT_CONTEXT.md refreshes, retire the 08-12 part-2 handoff.

`0aca889` is **pushed** (third attempt — caveat 3); the wrap commit is not yet. `origin/main` was at `2c99f9d` before this session.

No prod configuration changed this session. No migrations. No backend change. Plane: ORPHEUS-130 created (In Progress, high), ORPHEUS-85 + ORPHEUS-129 moved to Done with closing comments.

New modules this session: `frontend/src/lib/inAppBrowser.ts`, `frontend/src/components/InAppBrowserNotice.{tsx,css}`, `frontend/src/lib/__tests__/inAppBrowser.test.ts`, `frontend/src/pages/__tests__/InAppBrowserGuard.test.tsx`.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Landing copy doc ID:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk`
- **Privacy Policy drafting Doc:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting Doc:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — drafting surfaces only; **the canonical published text is the repo markdown** at `frontend/src/content/legal/`.
- **Pending pastes:** ORPHEUS-90 4.6-acceptance entry (carried since 06-24); **ORPHEUS-85's entry is now overdue** — sign-up is live in production.
