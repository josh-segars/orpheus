# Session Handoff — 2026-07-27

Replaces `SESSION_HANDOFF_2026-07-21.md`. Its threads are unchanged except where noted — this was an unplanned incident session, not a continuation of the 07-21 pickup plan.

- **ORPHEUS-118 (transactional email outage): filed, fixed, closed same day.** Ops-only; no code commits.
- **ORPHEUS-119 filed** — no ORPHEUS-98 report-ready email has ever delivered in production. This *answers* the 07-21 handoff's caveat #1 ("verify whether Nicole's report-ready email went out"): it did not.
- **Carried unchanged from 07-21:** ORPHEUS-108's legacy shim removal, ORPHEUS-111, ORPHEUS-90 Decision Log paste, ORPHEUS-107, the Andrew comms items, untracked-by-intent files.
- **Now stale and removed:** the 07-21 "ORPHEUS-8 go-live: Vercel domain + registrar DNS" pending item. The cutover happened — that's what caused this incident.

---

## What this session did

### The incident (ORPHEUS-118)

Josh hit a 502 inviting a new client (Indy Beck). The UI copy is the backend's own `detail` string surfaced verbatim, which placed the failure at Resend rather than in the invite handler.

**Root cause: the ORPHEUS-8 nameserver cutover took email down.** `orpheussocial.com` now delegates to `ns1/ns2.vercel-dns.com`, and the Vercel zone was built with web records only — it carried three CAA records and nothing else. Resend's `resend._domainkey` TXT (DKIM), `send` TXT (SPF) and `send` MX were all gone, so Resend un-verified the sending domain and 403'd every send; `_post_to_resend` normalizes that into `EmailSendError`, which the invite routes turn into the 502.

Confirmed at both ends before touching anything: DoH lookups returned SOA-only (no `Answer`) for each record, and the Resend dashboard independently showed domain status `Failed` with all three records `Failed`.

**Fix** — four records added to the Vercel zone (TTL 60, each commented `… - ORPHEUS-118`):

| Host | Type | Value |
|---|---|---|
| `resend._domainkey` | TXT | DKIM `p=…` (216-char RSA key, copied verbatim from Resend) |
| `send` | TXT | `v=spf1 include:amazonses.com ~all` |
| `send` | MX | `feedback-smtp.us-east-1.amazonses.com`, priority 10 |
| `_dmarc` | TXT | `v=DMARC1; p=none;` |

Resend's Restart flipped SPF MX + TXT to `Verified` in about a minute; DKIM followed on SES's own poll. **Josh sent a real invitation and it delivered** — Indy shows `Delivered` in the send log.

**Decisions locked [Josh, 2026-07-27]:** (1) **no apex MX, deliberately** — nothing sits behind `hello@orpheussocial.com`, it's send-only and replies bounce, so the missing MX flagged in the ticket is not a regression; (2) DMARC added rather than deferred.

### The finding (ORPHEUS-119)

Resend's send log for the trailing 15 days contains **only invitation emails**. No ORPHEUS-98 report-ready email has ever been observed delivering. Three clients are owed one:

| Client | Job | Published |
|---|---|---|
| Nicole Persun | `a8a47ff8-ba4d-4669-b9c4-0002f2255c2b` | 2026-07-20 19:50 UTC |
| Joshua Segars (test) | `c6116df9-6f05-433e-9068-18e0fb6cbbe4` | 2026-07-20 16:11 UTC |
| Francesa Castellanos | `e2b92877-3da5-464a-832a-ea24e362c2d2` | 2026-07-21 18:00 UTC |

Two candidate causes, **not separable from the evidence available**: collateral of this outage (last successful send of any kind was 07-17, so the outage could have begun any time in the 07-17 → 07-27 window), or an independent bug in the ORPHEUS-98 send path. A fresh completion now that sending works will settle it.

### Documentation

New "DNS — the `orpheussocial.com` zone" section in `CREDENTIALS.md`: read-before-you-move warning, the full record table with per-record purpose and source of truth, the deliberate-no-MX note, and a DoH verification snippet (the sandbox has no resolver — `dig` fails with "network unreachable"). The Resend section was refreshed at the same time — it still read "first real send pending" with a blank verified domain — and a step 0 was added to the new-external-system checklist so DNS dependencies get recorded going forward. `CLAUDE.md` gets an Active-phase sentence and a Decisions Made entry.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-118 | Restore Resend DNS after the nameserver cutover | ✅ Done (verified by a real delivered invite) |
| ORPHEUS-119 | Report-ready email never observed sending; back-send owed | ⏳ Backlog (medium) — **new** |
| ORPHEUS-108 | Browser-direct upload | 🔄 In Progress — **only** the legacy multipart `POST /jobs` + `_read_upload` deletion remains |
| ORPHEUS-111 | 50 MB cap vs 150 MB advisory vs 200 MB copy | ⏳ Backlog (medium) |
| ORPHEUS-99 / 94 / 84 / 85 / 107 | (publish action / email-mismatch / invite-advisor / self-serve signup / avatar) | ⏳ Backlog, unchanged |
| ORPHEUS-96 follow-up | CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew) |

Test baselines unchanged: backend pytest **392 green**, frontend vitest **79 green**. No code touched this session.

---

## Pending — your manual steps

1. **Push** — the wrap commit only. Command below.
2. **Delete the duplicate ORPHEUS-118 comment.** The first closing comment posted double-escaped (renders as literal HTML source); the corrected repost sits directly below it. Plane's MCP has no delete-comment tool, so it needs the UI.
3. **Andrew comms, carried from 07-21:** (a) Nicole's report is live to her and is the first real-client exercise of the ORPHEUS-63 score-0 posture — worth his read-through; (b) Jenn hasn't retried since the MIME fix; (c) Jodie needs an onboarding nudge, not a fix.
4. **Decision Log paste (ORPHEUS-90)** — still owed (`outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md` from the 06-24 session).

---

## Recommended pickup for next session

1. **ORPHEUS-119** — cheapest path to certainty: run one fresh completion, watch whether the report-ready email lands. That single observation decides whether there's a bug to fix or just three back-sends to do. Do this before it ages further; Francesa's report has been sitting unemailed since 07-21.
2. **Legacy multipart removal** — delete `POST /jobs` multipart + `_read_upload`, drop the pytest cases that exercise it, close ORPHEUS-108. Small, fully unblocked, unchanged from the 07-21 recommendation.
3. **ORPHEUS-111**, then the backlog: ORPHEUS-107, ORPHEUS-94, ORPHEUS-99.

---

## Caveats / things that will bite

1. **Resend's dashboard lists the provider as GoDaddy** and warns about GoDaddy propagation times — stale metadata from when the domain was added in April. The zone is Vercel's now. **Do not use Resend's Auto configure button**; it would write to the wrong provider.
2. **Email outages are invisible from inside the product.** The worker swallows `EmailSendError` by design, and the invite 502 only surfaces if an advisor happens to be inviting someone. This one ran ~10 days undetected. A monitoring sibling (Resend webhook into a log, or a periodic did-we-send-anything check) is captured as a note on ORPHEUS-119 but isn't ticketed on its own.
3. **`reports.published_at` blocks the retry.** All three owed clients have it stamped, so ORPHEUS-98's once-per-client guard will suppress an automatic re-send — back-sending needs a manual send or a deliberate `published_at` reset.
4. **Nicole's narratives auto-published at completion** (carried from 07-21, still open) — if advisory reports were meant to gate on admin publish, that gate didn't hold for her. Relevant to ORPHEUS-119: it's unconfirmed which of the two send paths should have fired.
5. **The part-1-partial sub-question is open** (on ORPHEUS-110): if LinkedIn's 10-minute partial download carries the Complete fingerprint files, a part-1 upload would pass as zero-activity. Needs a real part-1 sample.
6. **Abandoned staging uploads still aren't swept** — Jenn's orphaned `analytics.xlsx` from 07-17 sits in `{client}/staging/`. Harmless at current volume.
7. **Sandbox quirks unchanged** — no pip/pytest (Josh's terminal); no SSH push; `.git/*.lock` needs the `mv` workaround before each commit. **New:** no DNS resolver either — `dig` returns "network unreachable"; use the DoH snippet in `CREDENTIALS.md`.
8. **Untracked-by-intent files** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, `.claude/`, `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`.

---

## State of the repo right now

No code commits this session — the fix lived entirely in the Vercel DNS zone and the Resend dashboard. This wrap commit (handoff swap + `CLAUDE.md` + `CREDENTIALS.md`) is the only unpushed commit. Working tree otherwise clean except the intentionally-untracked files in caveat 8.

**Prod config beyond source:** the four DNS records in the Vercel zone are the only live state not captured in the repo — DNS can't be pinned in source the way migration 019 pinned the bucket config, which is exactly why the `CREDENTIALS.md` record table exists.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry. ORPHEUS-85 still owes its entry when it ships.
