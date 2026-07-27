# Session Handoff — 2026-07-27

Covers **two sessions on the same day**, updated in place rather than split into a second dated file (precedent: `Session handoff: 2026-07-15 part 2`). Replaces `SESSION_HANDOFF_2026-07-21.md`, retired in the part-1 commit.

- **Part 1 — ORPHEUS-118 (transactional email outage): filed, fixed, closed.** Ops-only; no code commits.
- **Part 2 — ORPHEUS-119 diagnosed, ORPHEUS-120 filed, ORPHEUS-108 closed and deployed.** One code commit (`8f1b890`).
- **Now resolved from part 1:** the "three clients owed a report-ready email" item (it's two, and the back-send is dropped), and the standing question of whether Nicole's narratives auto-publishing was a gate failure (it wasn't).
- **Newly surfaced during the wrap:** ORPHEUS-112–117, filed 2026-07-22 by a session that left no handoff, invisible to the canon until now.
- **Carried unchanged:** ORPHEUS-111, the ORPHEUS-90 Decision Log paste, ORPHEUS-107, the Andrew comms items, untracked-by-intent files.

---

## Part 1 — the email outage (ORPHEUS-118)

Josh hit a 502 inviting a new client (Indy Beck). **Root cause: the ORPHEUS-8 nameserver cutover took email down.** `orpheussocial.com` now delegates to Vercel, and the rebuilt zone carried web records only — Resend's DKIM TXT, SPF TXT and `send` MX were all gone, so Resend un-verified the domain and 403'd every send. Fixed by re-adding four records (DKIM, SPF, `send` MX → `feedback-smtp.us-east-1.amazonses.com` priority 10, plus `_dmarc`); Josh's live invite to Indy delivered.

**Decisions locked [Josh, 2026-07-27]:** no apex MX, deliberately (`hello@orpheussocial.com` is send-only, replies bounce); DMARC added rather than deferred.

Prevention shipped as the new "DNS — the `orpheussocial.com` zone" section in `CREDENTIALS.md`. Full detail is in CLAUDE.md's Decisions Made entry — not repeated here.

---

## Part 2 — what this session did

### ORPHEUS-119: cause established, no send-path bug (left In Progress)

The ticket named two candidate causes and couldn't separate them. **The evidence that separates them:** Tatiana Rossova's `clients` row was created **2026-07-20 16:13:58 UTC** with `invitation_status = 'pending'` and no delivery in the Resend log. Since `POST /clients/invite` always attempts a send and deliberately does *not* roll the row back on `EmailSendError`, a persisted row with no delivery is the signature of a failed send. That dates the outage to before all three publications — two minutes after the Josh-test one, 3.5 hours before Nicole's, a day before Francesa's. **Cause 1 confirmed; both send paths read correctly against live data.**

Two corrections to the ticket:

- **The owed list is two, not three.** Josh's test client `8480c922` has **7 complete jobs**, so `_is_first_complete_job` suppressed its email correctly as a re-run. Not a miss.
- **The worker path is the one that should have fired** for Nicole and Francesa — their advisor row carries `is_individual = true` → `is_advisory = False`. This also resolves the 07-21 handoff's open question about Nicole's narratives auto-publishing: correct behavior for that advisor row, not a gate failure.

**Back-send dropped [Josh, 2026-07-27]** — Josh has been in direct personal contact with both clients, so the feedback ask is covered out-of-band. No `published_at` reset, no manual send. This is written onto the ticket as "future sessions should not attempt this," because the ticket description still lists the three clients.

**Worker env pre-flight confirmed** — `APP_BASE_URL` and `BETA_SURVEY_URL` are set on both Railway services, so neither silent-skip branch in `_maybe_send_report_ready_email` can fire.

### ORPHEUS-120 filed (high) — the real finding

ORPHEUS-98 deferred the advisory email to publication on the premise that "a client genuinely can't see a draft," verified at the time against the `narratives_select_as_client` RLS policy (`status = 'published'`). **That policy is dead code for that surface.** `_build_result_payload` reads narratives with the *service-role* client and never filters on `status`, and no frontend surface reads narratives direct-to-Supabase — so `GET /jobs/{id}` serves `draft` narratives to the report subject the moment the pipeline finishes.

**Two defects have been cancelling each other out.** 13 clients on Andrew's roster (`is_individual = false`, which is *correct* per `Decision_Self_Serve_And_Advisor_Invite_2026-05-11` — not a misconfiguration) have `reports.published_at IS NULL`, never received the feedback ask, and have been reading their reports since 2026-06-16 anyway.

Nothing has broken because **nobody has run a report through advisor approval yet** [Josh]. Reports finish in a minute or two while the client watches, so the email was never a readiness notification in practice and the leak stayed invisible. But the gate won't hold the first time review-then-release is actually used — which is the core of the advisory practice model.

**Cross-linked as a dependency of ORPHEUS-114** [Josh]: a reconciliation pre-publish gate has no pre-publish window to occupy until 120 restores the boundary. Comments posted on both tickets.

Left on 120 as a note for Josh + Andrew, deliberately undecided: whether the feedback ask should be gated on advisory publication at all, given the client is already reading the report. The 13 missing asks self-resolve if Andrew ever publishes — `_maybe_send_report_ready_on_publish` fires on the narrative flip — so they're unsent, not unsendable.

### ORPHEUS-108 closed — multipart shim deleted (`8f1b890`, deploy green)

Removed: the multipart `create_job` handler (176 lines), `_read_upload`, the now-unused `Annotated`/`File`/`Form`/`UploadFile` imports, and the frontend's `apiPostMultipart` (dead since `useCreateJob` moved to `uploadToSignedUrl`; its docstring pointed at the deleted endpoint). `_apply_submission_gates` stays — transport-independent accept/reject policy in one place.

**Test decision worth knowing about:** the handoff plan said "drop the pytest cases that exercise it," but `test_jobs_post.py`'s 12 cases were the *only* detailed coverage of the ORPHEUS-88/100/101 gate policy (`test_jobs_uploads.py` has just the handler-level parity smoke). They were **retargeted** onto the gate function as `test_submission_gates.py` — 11 cases, preserving Basic-filename rejection, filename-date-over-XLSX precedence, the XLSX fallback, the 14/15-day boundaries, Shares-vs-Profile guidance. The one dropped case is the handler-level 403, already covered for both live handlers. Passing a gate is now asserted as "returns the parsed payload" instead of the old proxy of "500s later at an unmocked insert."

Backend pytest **391 green** (was 392), frontend vitest **79 green**, `tsc -b` clean, deploy confirmed green by Josh.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-118 | Restore Resend DNS after the nameserver cutover | ✅ Done (part 1) |
| ORPHEUS-108 | Browser-direct upload | ✅ Done — shim deleted, deploy green |
| ORPHEUS-119 | Report-ready email path | 🔄 In Progress — cause established; awaiting live verification + monitoring |
| ORPHEUS-120 | Advisory draft gate doesn't hold on the read path | ⏳ Backlog (high) — **new**; dependency of 114 |
| ORPHEUS-112–117 | Metric-accuracy cluster (bugs A/B/D/E, reconciliation gate, evidence layer) | ⏳ Backlog — 4 high; **filed 07-22, undocumented until now** |
| ORPHEUS-111 | 50 MB cap vs 150 MB advisory vs 200 MB copy | ⏳ Backlog (medium) |
| ORPHEUS-99 / 94 / 84 / 85 / 107 | (publish action / email-mismatch / invite-advisor / self-serve signup / avatar) | ⏳ Backlog, unchanged |
| ORPHEUS-96 follow-up | CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew) |

Baselines: backend pytest **391 green**, frontend vitest **79 green**.

---

## Pending — your manual steps

1. **Nothing to push.** `8f1b890` is already pushed and deployed; this wrap commit is the only outstanding one.
2. **Delete the duplicate ORPHEUS-118 comment** (carried from part 1, if not already done). The first closing comment posted double-escaped; the corrected repost sits below it. Plane's MCP has no delete-comment tool.
3. **Decision Log paste (ORPHEUS-90)** — still owed (`outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md` from the 06-24 session).
4. **Andrew comms, carried:** (a) Nicole's report is live to her and is the first real-client exercise of the ORPHEUS-63 score-0 posture — worth his read-through; (b) Jenn hasn't retried since the MIME fix; (c) Jodie needs an onboarding nudge, not a fix. **New:** (d) ORPHEUS-120's open question — should the feedback ask wait for advisory publication at all?

---

## Recommended pickup for next session

1. **Triage ORPHEUS-112–117 into the canon.** Six tickets, four high, filed 07-22 with no handoff behind them — the highest-value next move is establishing what that session found and getting it into CLAUDE.md, because right now the canon is blind to a metric-accuracy cluster that includes a scoring bug affecting already-delivered reports (112, "regenerate affected reports").
2. **ORPHEUS-120 + ORPHEUS-114 together.** Design the publish boundary once. 120 is small on its own (filter `status` for client callers in `_build_result_payload`, plus an "advisor is reviewing this" surface) but shouldn't land twice.
3. **ORPHEUS-119's remainder** rides the next real completion — no action until then, then the monitoring sibling.
4. Then ORPHEUS-111, ORPHEUS-107, ORPHEUS-94, ORPHEUS-99.

---

## Caveats / things that will bite

1. **A returning or advisory client completing a report is NOT an ORPHEUS-119 verification event.** The send fires only on a client's *first* completion and only under an `is_individual = true` advisor. `survey=no` in the worker log would be the one real surprise (env var not reaching the process despite being set).
2. **`python-multipart` is now unused but still in `requirements.txt`**, deliberately, comment-flagged. Retained one deploy cycle rather than changing the Railway build in the commit that removed the endpoint (ORPHEUS-43 history). Fold the removal into the next backend commit; don't give it a dedicated deploy.
3. **A browser on the pre-108 bundle now gets 405 on `POST /jobs`.** That window is what the shim covered and it closed deliberately — a hard refresh fixes it, but it explains any failed submit reported right after the deploy.
4. **Resend's dashboard still lists the provider as GoDaddy** and warns about GoDaddy propagation — stale metadata from April. The zone is Vercel's now. **Do not use Resend's Auto configure button.**
5. **Email outages are invisible from inside the product.** Both send paths swallow `EmailSendError` by design, and the invite 502 only surfaces if an advisor happens to be inviting someone. The last one ran ~10 days undetected. Monitoring scope is folded into ORPHEUS-119.
6. **Sessions that skip the wrap cost real money.** The 07-22 cluster went five days invisible, and the 06-26 session before it forced ORPHEUS-96 to be closed retroactively. Related: **run the full Plane list at session start** — this session fetched ORPHEUS-119 directly and so missed the 112–117 drift until the wrap.
7. **The part-1-partial sub-question is open** (on ORPHEUS-110): if LinkedIn's 10-minute partial download carries the Complete fingerprint files, a part-1 upload would pass as zero-activity. Needs a real part-1 sample.
8. **Abandoned staging uploads still aren't swept** — Jenn's orphaned `analytics.xlsx` from 07-17 sits in `{client}/staging/`. Harmless at current volume.
9. **Sandbox quirks unchanged** — no pip/pytest (Josh's terminal); no SSH push; `.git/*.lock` needs the `mv` workaround before each commit; no DNS resolver (use the DoH snippet in `CREDENTIALS.md`). **New:** `rm` inside the mount needs delete permission granted for the folder before it will work.
10. **Untracked-by-intent files** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, `.claude/`, `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`.

---

## State of the repo right now

One code commit this session (`8f1b890`, pushed and deployed) plus this wrap commit. Working tree otherwise clean except the intentionally-untracked files in caveat 10.

**Prod config beyond source:** the four DNS records in the Vercel zone remain the only live state not captured in the repo — which is why the `CREDENTIALS.md` record table exists.

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
