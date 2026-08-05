# Session Handoff — 2026-08-05

ORPHEUS-123 is implemented and locally verified but **deliberately not closed**. Replaces `SESSION_HANDOFF_2026-08-03.md`, retired in this commit:

- **ORPHEUS-123 (self-host fonts) built end to end** — 28 files modified, 11 added in `fonts/`. Left **In Progress**, not Done: nothing is deployed, and closing on unpushed code is the 07-27 mistake.
- **`0cb9878` (2026-08-04) is folded in here.** That commit was never covered by a handoff — the 08-03 one predates it and no 08-04 handoff exists. It corrects two false claims in the source-of-truth docs; the account-deletion one is dangerous enough to restate below.
- **Three of ORPHEUS-123's own premises were wrong**, including one that would have produced an actual licence violation if followed as written.
- **A four-ticket GDPR batch (124-127) surrounds this work** and is untouched.
- **Two new environmental caveats**, one of which makes the `orpheus-session-wrap` skill's own step 7 unsafe in this repo.
- **Carried unchanged:** the whole ORPHEUS-114 / 120 / 121 / 115 / 116 cluster, ORPHEUS-119's live-verification remainder, ORPHEUS-111, the ORPHEUS-90 Decision Log paste, the Andrew comms items, untracked-by-intent files.

---

## ORPHEUS-123 — what shipped, and what it actually cost

| | before | after |
|---|---|---|
| Critical path (upright latin, cold cache) | **207.1 KB** across 5 files | **133.0 KB** across 2 |
| Third-party requests | `fonts.googleapis.com` + `fonts.gstatic.com` on 11 pages | none |
| `opsz` axis | 8-60, live | 8-60, unchanged |
| Weights available | 500/700/900 serif, 400/600 sans | 300-900 serif, 200-900 sans |

Google's `css2` URL pins a **weight per file**, which is why the old path was five files: serif 500/700/900 at 58.1 + 58.8 + 55.4 KB, sans 400/600 at 17.4 each. One self-hosted variable file per family covers every weight, so self-hosting was always going to be *smaller* — there was never a payload increase to trade against the privacy fix. The remaining savings came from dropping OpenType features nothing references (`onum`/`frac`/`sups`/`subs`, 32 KB per serif face), **not** from touching `opsz`.

Files: 8 woff2 (two slices per face on Google's exact `latin`/`latin-ext` ranges), both OFL texts, and `fonts/build_fonts.py` which reproduces the whole set and **asserts no Reserved Font Name survives**, failing rather than emitting a misnamed file.

---

## The three wrong premises — read before touching this again

1. **`frontend/public/fonts/` doesn't work.** `orpheus-styles.css` lives at repo root and reaches React via `main.tsx`, so a single relative `url()` has to resolve for both Vite and Live Server. Repo-root `fonts/` does; the ticketed path double-emits into `dist`.

2. **The `opsz` rationale for preferring Adobe over Google's slices doesn't hold.** The ticket's own request URL carries the axis (`ital,opsz,wght@0,8..60,500;…`). Adobe was still the right source — provenance, and no dependence on Google's subsetting choices — but not for the stated reason.

3. **The ticket's Notes had the Reserved Font Name clause backwards, and this one bites.** They read *"do not rename the font files… we are not modifying them, so this is only a caution for a future subsetting pass."* OFL condition 3 bars a **Modified Version** from carrying the RFN. Subsetting *is* modification (SIL OFL-FAQ 2.6: "Removing any parts of the font when delivering a webfont to a browser… is considered modification. This is permitted by the OFL but would not normally allow the use of RFNs"). So the moment you subset, renaming stops being forbidden and becomes **required**. An implementer following the note literally would have subset the faces, kept the name "Source", and shipped the violation. Since subsetting is where all the savings are, the note was pointing directly at the trap.

FAQ 5.3 also scopes the restriction to "the font menu name and other mechanisms that specify a font in a document" — which includes CSS `font-family`. That is why the rename had to reach **all 406 declarations** across 24 files, not just the filenames.

---

## `opsz` is a live token — never pin it

The single most important constraint for a future session. An audit found **40+ `font-variation-settings: 'opsz' N` declarations across 14 files**, values from 15 to 60 (LandingPage 60, LoginPage 57, welcome-v6 50, SignalScorePage 44, CheatSheetPage 22/26, and many at 16-20).

Pinning the axis saves **86 KB per serif face** — by far the biggest single lever — and would silently flatten every one of those. It looks like free money and it is not. Verified by pixel diff that the explicit declarations *do* take precedence over automatic optical sizing, so they are load-bearing, not decoration.

Narrowing the range instead of pinning recovers only 10 KB (masters sit at the extremes), so there is no middle option. Don't go looking for one.

---

## The verification shape is the transferable part

The claim that mattered was "subsetting changed nothing visible." That was proved by rendering the subset and the unmodified Adobe original in the same browser, same text, same page, and diffing pixels:

- **subset vs original at `opsz` 8 and at 60: 0 differing pixels, max delta 0**
- **control: `opsz` 8 vs 60 on the same file differs by 35,172 px**

The control is the part worth copying. A null result without one is indistinguishable from a broken harness — the same trap as the 07-27 clean-run false all-clear, in a different medium. An earlier version of this check measured *advance widths* and found zero difference, which looked like proof the axis was dead; it was actually proof that Source Serif 4's `opsz` is metric-compatible. Width was the wrong instrument.

This also settles the ticket's acceptance criterion 3 more strongly than re-measuring would: the ORPHEUS-80 `size-adjust` ratios (100.2% / 92.7%) compare the local fallback against the webfont, and the webfont's outlines are provably unchanged, so the measured ratios still hold.

---

## `0cb9878` (2026-08-04) — the correction no handoff described

Josh's own commit, already pushed, from the 08-03 privacy/ToS review. Restating because a future session would otherwise re-trust what it fixed:

- **Account deletion does not cascade the way CLAUDE.md claimed.** `clients.user_id` is `ON DELETE SET NULL` (`001_base_schema.sql:127`), so deleting a client's auth user **orphans** the clients row and every downstream row. The cascade that *does* fire is the other direction: `advisors.user_id` is `ON DELETE CASCADE` (`:104`) and `clients.advisor_id` is `ON DELETE CASCADE` (`:126`) — deleting an advisor's auth user destroys **every client on that roster and all their reports**, which is 13 other people's data on Andrew's today. Dual-role users hold both rows and hit the destructive path. Storage objects in the uploads bucket are referenced by no foreign key and survive regardless. ORPHEUS-124 scopes deletion as an ordered operation in application code.
- **CREDENTIALS.md analytics row was stale** since ORPHEUS-79 — `@vercel/analytics` and `@vercel/speed-insights` are in the bundle and mounted in `main.tsx` above `<App />`, so they run on the marketing host too.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-123 | Self-host the brand typefaces | 🔄 **In Progress** — built + locally verified; needs push, then DevTools on both hosts |
| ORPHEUS-124 | Self-service account deletion | ⏳ Backlog — **new 08-04**; blocked on the real FK behaviour above, not the claimed cascade |
| ORPHEUS-125 | Publish Privacy Policy + ToS in-product | ⏳ Backlog (high) — **new 08-04**; owns the §9 rewrite that 123 unblocks |
| ORPHEUS-126 | Upload consent / re-base lawful basis | ⏳ Backlog — **new 08-04** |
| ORPHEUS-127 | Data-subject request runbook | ⏳ Backlog — **new 08-04** |
| ORPHEUS-114 | Reconciliation gate + metric source/unit registry | ⏳ Backlog (high) — carries 121's prose reconciliation, Andrew's two label findings, the milestone-vs-metric identity |
| ORPHEUS-121 | Narrative agent fabricates aggregate counts | ⏳ Backlog (high) — rides 114 |
| ORPHEUS-120 | Advisory draft gate doesn't hold on the read path | ⏳ Backlog (high) — dependency of 114 |
| ORPHEUS-115 | Prose mislabels | ⏳ Backlog (medium) — needs 114's registry |
| ORPHEUS-116 | "What Travels" reach-driver evidence layer | ⏳ Backlog (medium) — largest scope, gated on Andrew |
| ORPHEUS-119 | Report-ready email path | 🔄 In Progress — awaiting a first-time completion under `is_individual = true` |
| ORPHEUS-111 | 50 MB cap vs 150 MB advisory vs 200 MB copy | ⏳ Backlog (medium) |
| ORPHEUS-99 / 94 / 84 / 85 / 107 | unchanged | ⏳ Backlog |

Baselines: backend pytest **434 green** (untouched this session — no backend file modified), frontend vitest **79 green**, `tsc -b` clean.

---

## Pending — your manual steps

1. **Push.** Two commits: `0d9420f` (ORPHEUS-123) and this wrap.
2. **`rm SESSION_HANDOFF_2026-08-03.md`.** Its deletion is committed, but the sandbox can't unlink inside the mount so the file is still on disk as untracked. Left there it will trip the "multiple handoff files" check at next session start.
3. **Then finish 123's acceptance:** DevTools on `app.orpheussocial.com` **and** the marketing host showing zero `fonts.googleapis.com` / `fonts.gstatic.com` requests, and confirm `/assets/Orpheus*.woff2` actually serve. Then it can move to Done. Railway is irrelevant here — this is a Vercel-only change.
4. **Delete two double-escaped Plane comments** — ORPHEUS-123 picked up a fresh one this session before I corrected it (the good repost sits directly below, and says so). ORPHEUS-117's and possibly ORPHEUS-118's are still there from prior sessions.
5. **ORPHEUS-125 owns the Privacy Policy §9 rewrite.** The font-CDN paragraph now describes something that doesn't happen. The drafts are untracked at repo root.
6. **Andrew's live report `0007607e` still carries the pre-`861d581` followers milestone** (3,550, not 3,500). `c2df921` corrects it in place.
7. **Decision Log paste (ORPHEUS-90)** — still owed (`outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`). Carried since 06-24; worth deciding whether it's going to happen.
8. **Andrew comms, carried:** (a) Nicole's report is the first real-client exercise of the ORPHEUS-63 score-0 posture; (b) Jenn hasn't retried since the MIME fix; (c) Jodie needs an onboarding nudge; (d) ORPHEUS-120's open question — should the feedback ask wait for advisory publication at all? (e) the ORPHEUS-122 sr-only composite-score question; (f) the growth factors and the ORPHEUS-112 metric-definition caveat.

---

## Recommended pickup for next session

1. **Close out ORPHEUS-123** — it's two DevTools checks after the push, nothing more.
2. **ORPHEUS-120 + ORPHEUS-114 together**, per the standing cross-link — design the publish boundary once. 120 is small alone but shouldn't land twice, and 114's reconciliation identities are the regression net.
3. **ORPHEUS-121 rides 114** — `QUANTITATIVE_METRIC_LABELS` is already the first five entries of 114's unit registry; promote and extend rather than start fresh.
4. **ORPHEUS-125 next if the compliance thread is the priority** — it's high, it's the batch's publication gate, and 123 just removed one of its open items.
5. **ORPHEUS-124 needs the FK correction above baked into its design** before anyone writes an `auth.admin.delete_user()` call.
6. ORPHEUS-115 after 114; ORPHEUS-119's remainder rides the next real first-time completion; ORPHEUS-116 last.

---

## Caveats / things that will bite

1. **Never pin `opsz`.** See the dedicated section above. It is the largest apparent saving in the font stack and it is a trap.
2. **Don't rename the faces back to "Source ...", and don't add a subset under the original name.** The rename is a licence requirement, not a style choice.
3. **`.gitignore` now covers the untracked-by-intent set, but `orpheus-session-wrap` still says `git add -A`.** Fixed this session: `Draft_*.md`, `Scoping_*.md`, `Survey_*.md`, `ORPHEUS-*_Decision_Brief_*.md`, `rubric_consistency_results_*.json`, `create_beta_survey_form.gs`, `outputs/`, `.claude/settings.local.json` are all ignored now — patterns verified against `git ls-files` for zero clashes, so `Decision_*`, `Spec_*` and `ORPHEUS-96_repro_*` stay tracked. A stray `git add -A` is therefore no longer destructive. **The skill text is still wrong in three places** and the corrections are drafted but not applied: step 7 instructs `git add -A`; its compliance-drafts gotcha names only files `.gitignore` already protected, so the guard read as satisfied while covering nothing; and its verification checklist says status should be "clean except for the compliance drafts", an end state that only holds *after* the unintended files have been swept in. Until those land, stage explicitly. Note also that anything **new** dropped at repo root is unprotected unless a pattern covers it — check with `git check-ignore -v <path>` rather than assuming.
4. **The Plane MCP double-escape quirk affects `add_issue_comment`, not just `create_issue`.** Pass **raw** HTML; entity-escaping it yourself produces a comment that renders as visible markup. `comment_stripped` in the response looks correct even when `comment_html` is broken, so check `comment_html`.
5. **`.git/*.lock` files went stale for ~23 hours** and blocked `git add` from Josh's own terminal with the "another git process seems to be running" error. The sandbox can't `rm` them but `mv` works: `find .git -name "*.lock" -type f | while read f; do mv "$f" "$f.moved.$$"; done`. The `tmp_obj_*` unlink warnings that follow are cosmetic — blob integrity was checked against on-disk sizes and `git fsck` was clean.
6. **A clean run does not prove a stochastic prose bug is fixed.** Check the deterministic fingerprint, not the absence of a phrasing.
7. **Verify the deploy before asking anyone to re-run.** Railway's auto-deploy is intermittent; the **worker** is the service that matters for pipeline output.
8. **Growth factors are PROVISIONAL and framework-adjacent** — `MILESTONE_GROWTH_FACTORS`, `MILESTONE_HORIZON_WEEKS`, `FOLLOWER_TREND_STRETCH` are Andrew's to tune.
9. **`python-multipart` is still in `requirements.txt` unused**, deliberately, comment-flagged. Fold the removal into the next backend commit.
10. **Resend's dashboard still lists the provider as GoDaddy.** The zone is Vercel's. **Do not use Resend's Auto configure button.**
11. **Email outages are invisible from inside the product.** Both send paths swallow `EmailSendError` by design. Monitoring scope is folded into ORPHEUS-119.
12. **A returning or advisory client completing a report is NOT an ORPHEUS-119 verification event.**
13. **The part-1-partial sub-question is open** (ORPHEUS-110): if LinkedIn's 10-minute partial download carries the Complete fingerprint files, a part-1 upload would pass as zero-activity. Needs a real part-1 sample.
14. **Abandoned staging uploads still aren't swept** — Jenn's orphaned `analytics.xlsx` from 07-17 sits in `{client}/staging/`.
15. **Sandbox quirks** — no pip/pytest (so the backend count is carried, not measured); no SSH push; `git fetch` fails, so the origin comparison at session start is against a stale ref. `npm`/`vite`/`vitest`/`tsc` all work offline. `vite build` fails on the existing `dist/` because it can't unlink — build to a scratch `--outDir` outside the mount instead.
16. **`orpheus-session-wrap`'s `references/` directory is not installed** — only `SKILL.md` is present, so `closing_comment_template.md` and `session_handoff_template.md` are unavailable. This handoff follows the structure described in the skill body and the 08-03 file's style.
17. **Untracked-by-intent files** are now enforced by `.gitignore` (caveat 3) rather than by memory. `git status` should show exactly one `??` entry — nothing, once `SESSION_HANDOFF_2026-08-03.md` is removed from disk.

---

## State of the repo right now

Two commits this session, deliberately split rather than rolled up so the font change stays independently revertible — matching the repo's pattern of keeping code and bookkeeping apart (`da591f2` was code-only, `ca0fa6a` handoff-only):

- **`0d9420f`** — ORPHEUS-123: the font work plus the doc updates (39 files, +760/-261)
- **this wrap commit** — adds this handoff, retires `SESSION_HANDOFF_2026-08-03.md`

Both carry `Co-Authored-By` / `Claude-Session` trailers, which no prior commit in this repo uses — amend them off if log uniformity matters more.

`0cb9878` and everything before it are already pushed.

`fonts/` is newly tracked: 8 woff2, 2 OFL texts, `build_fonts.py`. Working tree otherwise clean except the caveat-3 files.

**Prod config beyond source:** the four DNS records in the Vercel zone remain the only live state not captured in the repo — hence the `CREDENTIALS.md` record table.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Landing copy doc ID:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk`
- **Andrew's accuracy review (2026-07-27, job `301ba109`):** `160KdpyALqd94Wt36DvDFkh9FYR1sn_673lzw6NMCfvc`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry. ORPHEUS-85 still owes its entry when it ships.
