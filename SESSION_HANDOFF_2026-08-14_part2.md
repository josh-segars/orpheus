# Session Handoff — 2026-08-14 part 2

Replaces `SESSION_HANDOFF_2026-08-14.md` — everything it described carries forward or resolved as follows:

- **Its wrap was not the day's last word — twice.** After it was written, a parallel session shipped **ORPHEUS-132's consent gate** (`8bbc8f0`, pushed) and filed **ORPHEUS-133** (beta-end purge) with no handoff amendment — fully documented on the tickets, invisible to the handoff until this one. Then this session ran the **report-review reconciliation**: Andrew reported issues with his 08-13 report, an independent source-side review ran blind to his findings, his v3 doc arrived, and the two converged.
- Its Pending items carry (renumbered below) except: item 3 (route ORPHEUS-132 to Tim) is **withdrawn** — the gate shipped and the purge decision answered the retrospective half; and item 12's Andrew-comms list gains new entries.
- Its live-validation watches are unchanged (119 / 120 / 130), with 132 now added to the same watch class.
- **This session wrote no code.** Two commits exist since `ff4aee9`: the parallel session's `8bbc8f0` (already pushed) and this wrap.

---

## The parallel session first (because it post-dates the morning handoff)

**ORPHEUS-132 — consent gate shipped** (`8bbc8f0`, frontend-only, vitest 186 → **194 green**). `/invite/:token` is no longer a mount-effect redirect: user-initiated hop behind the same unticked-by-default checkbox as `/login`/`/signup`; version pair rides `redirectTo` via new shared `withAcceptanceParams` (SignupPage moved onto it); downstream verified link-by-link as needing no change. **Forward-only [Josh]** — the roster self-heals at next sign-in, and the retrospective question dissolved under the **beta-purge decision [Josh, 2026-08-14]: beta accounts are purged at beta end, nothing carries into live.** That decision generalizes: beta-era "what about existing rows?" tails default to forward-only, purge as justification. **ORPHEUS-133** (Backlog, medium) holds the purge's execution traps (no FK on storage objects; rosters before advisors; SET-NULL vs CASCADE asymmetry). 132 stays In Progress for one thing: **live validation on the next real invitation acceptance** — and note the invite UX changed (checkbox + button where the link was instant), so Andrew should warn invitees.

## The review reconciliation (this session)

**Setup:** Andrew found issues with his 2026-08-13 report (job `b03ca0f5`, 82.38/Resonant) and withheld them so an independent pass wouldn't be influenced. The source-side review re-derived every figure from raw `ingested_data` (not the persisted operands) and clean-roomed the milestone code; his v3 (rendered-view-only, no-ingestion doctrine, adversarially verified — 6 of 11 draft findings withdrawn before delivery) arrived after. Artifacts: `outputs/Report_Accuracy_Review_b03ca0f5_2026-08-14.md` and `outputs/Review_Reconciliation_b03ca0f5_2026-08-14.md` (gitignored, local only).

**Convergence — the accuracy layer is sound.** Every number verifies via two independent paths (his posting corpus at 0.5–0.7% gaps; raw stored data at exact). Composite reconstructs to 82.38 (his display-only model was one normalization detail off: 0–5 dims are mean/5, not (mean−1)/4). Both 3,550 milestones are correct step-50 rounding collisions. His followers-tile suspicion (reading the impressions variable) is disproven from code — trend projection, `861d581`.

**The headline — claims layer, and its root cause is process.** The Foundational Review (FINAL 2026-07-16, Drive) closed with Specs 1/2 as "proposals, not directives" and they never became tickets: **no Ruling-2/3 guardrail exists anywhere in `narrative.py`** (his Part-1 ask — "which generator carries the guardrail?" — answers *neither*), the Spec-1 sentence is still live at `rubric.py:125`, and the footer exists on no user-facing surface. That is why his sweep found ~20 breaches across every narrative. His inference that the dimension level was "now correctly scoped" is the clean-run trap (07-27 lesson) — nothing is guarded at any level.

**Confirmed factual defect:** recommendations asserted absent (three places, one QRC priority slot) while `Recommendations_Received.csv` sat unread in his archive — capture gap proven from `quality_report.zip_files_found`; Andrew has recommendations. **Root-caused beyond his doc:** the "105 comments excluded due to unparseable dates" line traces verbatim to the quality validator's message, which disagrees with the coverage block (103 unparseable + 2 empty), and the 103 rows are multiline-comment CSV fragments (comment prose in the date field) — share rising 2.5% → 4.0% across his five runs, ~19% marginal on rows added since 07-31, parser unchanged in the window, so corpus not code. His trend question is answered; the data is recoverable at the parser.

**Filed (all Backlog):** **ORPHEUS-134** (Spec 2 prompt guardrails, high — sequence with 131's final-attempt degrade), **135** (footer, high — wording agenda-gated: "Signal Scores" vs ORPHEUS-76's "report"), **136** (Spec 1 sentence swap, high — framework-affecting, consistency-harness re-run + Andrew sign-off on any Dim 4 movement), **137** (absence-assertion ban ships now; ingest-vs-exclude is Andrew's, high), **138** (fragmentation parser hardening + validator label, medium), **139** (80–100 band range / tile window labels / engagement-rate numerator, medium). Cross-link comments on **115** (its fix has a producer-side sibling in 138) and **120** (the reports-index IN REVIEW vs direct-URL oddity Andrew noted is the known dual-role asymmetry — not a leak; optional list advisor-awareness).

**The agenda** for the four decisions tickets can't settle is at `Draft_Claims_Layer_Discussion_Agenda_2026-08-14.md` (repo root, gitignored): (1) footer wording; (2) **milestones under Ruling 2 — the main event** (posts/week is a behavior target and survives; impressions/followers/rate are quantified outcome targets; options behavior-only / benchmark-reframe / keep-behind-footer, plus the compounding and top-50-skew tuning inputs, plus the two weekly-rhythm attribution items); (3) recommendations ingest-vs-exclude (Andrew leans exclude); (4) band-scale visibility (methodology block lets a Resonant member infer composite ≥ 80). Item 5 is open call #7 (cohort roll-up); item 6 is the process fix (rulings → tickets at close). Tim is not needed — his 132 item dissolved.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-134 | Spec 2 narrative-prompt guardrails (Ruling 2/3) | 🆕 Backlog, high |
| ORPHEUS-135 | Signal-legibility footer (never implemented) | 🆕 Backlog, high — wording agenda-gated |
| ORPHEUS-136 | Spec 1: Dim 4 preamble sentence in rubric.py | 🆕 Backlog, high — harness re-run required |
| ORPHEUS-137 | Recommendations absence-assertions + ingest-vs-exclude | 🆕 Backlog, high — part (b) is Andrew's |
| ORPHEUS-138 | Comments.csv fragmentation + validator label | 🆕 Backlog, medium |
| ORPHEUS-139 | 80–100 range, window labels, engagement numerator | 🆕 Backlog, medium |
| ORPHEUS-132 | Invite-flow consent gate | 🔄 In Progress — code shipped (`8bbc8f0`); closes on the next real invitation acceptance |
| ORPHEUS-133 | Beta-end account purge | 🆕 Backlog, medium — execution traps documented |
| ORPHEUS-131 | Prose-gate retry budget | ⏳ Backlog, high — sequence with 134 |
| ORPHEUS-119 / 120 / 130 | unchanged from the morning handoff | 🔄 In Progress — events have not fired |
| ORPHEUS-115 / 111 / 116 / 99 / 94 / 84 / 107 | unchanged | ⏳ Backlog |

Baselines: backend pytest **558 green** (untouched); frontend vitest **194 green** (per `8bbc8f0`; this session added no code).

---

## Pending — manual steps

1. **Schedule the claims-layer discussion** (Josh + Andrew; Tim not needed) — agenda at repo root; pre-reads listed in it. Decisions unblock ORPHEUS-135 wording, 137(b), and the milestone question that gates parts of 134/139.
2. **Send Andrew the two review docs + agenda** (or walk him through the reconciliation) — his v3 asks are all answered in `outputs/Review_Reconciliation_b03ca0f5_2026-08-14.md`.
3. **Confirm the Vercel build** — now covering both `0aca889` and `8bbc8f0` (the API still can't see the project; dashboard job). Blocks items 4–5.
4. **Re-run Tarita** post-deploy: `https://app.orpheussocial.com/signup?code=ORPH-Z32A-K7VA` (closes ORPHEUS-130's event).
5. **Re-invite Karen** (carried) — now double-duty: her acceptance is also ORPHEUS-132's validation event, and she'll see the new checkbox flow (heads-up first).
6. **Andrew publishes `b03ca0f5` from /admin** (carried) — closes ORPHEUS-120's publish half; also the report under review is a draft, so post-discussion edits can land via edited_text before release.
7. **Decision Log pastes owed:** the Ruling-2 outcome now joins the long-carried ORPHEUS-90 (4.6 acceptance) and ORPHEUS-85 (self-serve revision) entries; the beta-purge decision [Josh, 2026-08-14] also deserves an entry.
8. **Two beta testers possibly stuck in the in-app-browser trap** (carried) + the email-vs-DM invitation ops question.
9. **Delete the surplus ORPHEUS-123 Plane comments** (carried; keep `6a6c67ce`).
10. **Tim's confirmation list for Privacy Policy §11 and §7/§9 claims** (carried verbatim).
11. **Empty `_to_delete/`** (carried) — now also contains the retired `SESSION_HANDOFF_2026-08-14.md`.
12. **Andrew comms, carried + new:** (a)–(h) from the morning handoff unchanged (Nicole score-0 posture; Jenn MIME retry; Jodie nudge; growth factors + 112 caveat; the 14 unsent feedback asks; tolerances/registry review; self-serve rosters; recruited beta user), plus (i) invite links now show a consent checkbox — tell invitees; (j) recommendations ingest-vs-exclude is his call on ORPHEUS-137; (k) the Jun 23 consolidated rubric doc refresh rides ORPHEUS-136.

---

## Recommended pickup for next session

1. **Hold the discussion, then implement per its decisions** — ORPHEUS-134 + 135 (+ 136 alongside) is the batch that retires the claims-layer exposure. If the discussion hasn't happened yet, **ORPHEUS-131** first: it's decision-independent, high, small, and 134 raises the retry pressure it fixes (the `error_message`-on-complete cleanup rides along).
2. **ORPHEUS-138** (fragmentation parser hardening) — decision-independent, recovers real data, and kills the mislabeled sentence at its producer. 137's part (a) can ride any prompt-touching session.
3. **ORPHEUS-139** — small, mostly render work; keep its agenda-gated exclusions (milestone baselines, band-scale visibility) out.

---

## Caveats / things that will bite

1. **The claims-layer canon lives in Drive, not the repo** — Foundational Review FINAL 2026-07-16 is Drive doc `1jTnli4JqpbXhNK3vATKgV7usss1TcUFDSoGRa-_kpwI` (Rulings 2/3, Specs 1/2, open call #7); Andrew's v3 findings are doc `1umi0ZztF-Hha44dA-2Y64e1OSM4BxF0CMvDi8-1_rTU`. Read both before touching narrative prompts, milestones, or report copy. The four-week specs-to-nowhere gap is the root cause of the whole claims-layer breach list; the agenda's item 6 proposes the standing fix (rulings → tickets at close).
2. **Every report figure re-derives from `ingested_data` alone** — zip_data/xlsx_data recompute in SQL against jsonb; `quality_report.zip_files_found` is the archive manifest (how the unread Recommendations CSV was caught). Stronger than trusting persisted operands, no file download needed.
3. **An absence-claim in prose needs an ingestion check, not just an operand check** — and prose can quote a wrong input faithfully (the "105" line is the validator's own message; fix producers, not quoters).
4. **Two milestones can legitimately collide on the same value** (step-50 rounding: 3,525.25 and 3,548.25 both → 3,550). Verified correct on `b03ca0f5`; expect the question again.
5. **A clean run still isn't evidence for stochastic prose** (carried, and it caught Andrew's own reviewer this time — v3 read the dimension summary as "correctly scoped" when nothing is guarded).
6. **ORPHEUS-136 is one sentence but framework-affecting** — it edits a temp-0 rubric prompt, so Dim 4 can shift deterministically; harness re-run + Andrew sign-off before trusting scores, possible mini-ORPHEUS-90 scale note.
7. **Milestone split under Ruling 2:** posts/week = behavior (survives); impressions/post, followers, engagement rate = quantified outcome targets. Don't ship milestone work ahead of the discussion.
8. **The dual-role asymmetry now has a user-visible face** — the reports index says IN REVIEW while Andrew's direct URL renders the draft (list has no advisor branch; detail resolves advisor-first). Explained on ORPHEUS-120; not a leak.
9. **Plane MCP quirks** (carried): comment_html double-escapes (pre-escape entities — held across two comments this session); `create_issue` `description_html` does NOT (plain HTML — held across six issues); `list_project_issues` truncates (dump + jq).
10. **Sandbox limits** (carried): no pip / pytest from here; SSH push is Josh's; `.git/*.lock` needs `mv` aside; file tools vs bash mount paths differ. In cloud-Cowork sessions the repo is reached via device tools (stage → edit → commit back) and `device_bash` cannot delete — `mv` to `_to_delete/`.
11. **Untracked-by-intent set** (carried, verified this session): `Draft_*.md` covers the agenda; `outputs/` covers the review docs; `git check-ignore -v` before trusting any new root file. **Never `git add -A`.**
12. **Carried unchanged from the morning handoff:** structural evidence over logs; backfilled rows prove nothing; actor's role can hide the behavior; `jobs.error_message` persists on complete jobs; read a closing ticket's "still owed" list; `jobs`/`scores` column-name traps; closing events fire while nobody watches (validated again — `8bbc8f0` landed mid-day with no handoff); ORPHEUS-119's narrow event (house-advisor first completion); never pin `opsz` / never rename fonts; Resend items; growth factors PROVISIONAL; module-load URL rewrites preserve `location.hash` (now three writers via `withAcceptanceParams` — the helper exists so they can't drift).

---

## State of the repo right now

Two commits since `ff4aee9`: the parallel session's `8bbc8f0` (ORPHEUS-132 gate — already pushed) and this wrap (CLAUDE.md Active phase + two Decisions Made entries; PRODUCT_CONTEXT.md rows for ZIP parser, Narrative generation, Legal & consent; this handoff; retirement of `SESSION_HANDOFF_2026-08-14.md`). Working tree otherwise clean; new local-only files: `Draft_Claims_Layer_Discussion_Agenda_2026-08-14.md` (root, gitignored) and the two review docs in `outputs/` (gitignored).

Plane this session: ORPHEUS-134–139 created (Backlog); cross-link comments on 115 + 120. Nothing closed, nothing moved.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` (Orpheus Social > 06_Operations > Shared Canon)
- **State of the Moment:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA` · **Decision Log:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Foundational Review FINAL 2026-07-16:** `1jTnli4JqpbXhNK3vATKgV7usss1TcUFDSoGRa-_kpwI` · **Andrew's v3 findings (2026-08-13):** `1umi0ZztF-Hha44dA-2Y64e1OSM4BxF0CMvDi8-1_rTU`
- **Landing copy:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk` · **Privacy drafting:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — canonical published text is the repo markdown.
- **Pending pastes:** Ruling-2 outcome (new), beta-purge decision (new), ORPHEUS-90 4.6 acceptance (carried since 06-24), ORPHEUS-85 self-serve revision (overdue).
