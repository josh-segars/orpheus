# Session Handoff — 2026-06-23

Retires `SESSION_HANDOFF_2026-06-18.md`. That handoff's top recommendation was **ORPHEUS-90** (model sign-off, still open) and its backlog threads (82 / 88 / 86 / 84 / 85) — all restated below, none lost.

**Also folds in a gap:** a session on **2026-06-19** shipped **ORPHEUS-92** (commit `94825d2`) and filed **ORPHEUS-93** + **ORPHEUS-94**, but left no handoff. Those threads are captured here so they stop being invisible.

This session: **one ticket, one commit.** ORPHEUS-95 (band-mapping gap) fixed — code committed (`6fd93ac`), live cloud row backfilled, ticket moved to Done, CLAUDE.md + PRODUCT_CONTEXT.md updated. This handoff commit retires the 06-18 file.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-95 | Band-mapping gap: fractional composites fall through to Dissonant | ✅ **Done this session** (`6fd93ac`). Code + live backfill + tests. |
| ORPHEUS-92 | Invite token lost across LinkedIn OAuth round-trip | 🟡 **Code shipped 06-19 (`94825d2`), still In Progress in Plane.** No closing comment yet — Josh to confirm it's done & close, or note what's left. |
| ORPHEUS-93 | Resend invitation silently invalidates the previously-sent link | ⏳ Backlog (medium). Filed 06-19 alongside 92. |
| ORPHEUS-94 | Email-mismatch confirmation reads as an error during invite acceptance | ⏳ Backlog (low). Filed 06-19 alongside 92. |
| ORPHEUS-90 | Upgrade pipeline model → claude-sonnet-4-6 | 🟡 **Code shipped, In Progress.** Andrew sign-off pending on the band shift. Decision Log draft staged in Josh's outputs. |
| ORPHEUS-82 | Live validation of 81 (+78/87/89), now also 91 | ⏳ Backlog (medium). Combined post-deploy run still owed; add the `72b11642` recency re-check. |
| ORPHEUS-88 | Quality gate: confident reports on critically-deficient data | ⏳ Backlog (**high**). |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |

---

## What this session did

### ORPHEUS-95 — band-mapping gap (shipped, closed)

**The bug.** `assign_band` (`backend/scoring/engine.py`) tested `lo <= composite <= hi` against the integer-inclusive `SIGNAL_BANDS` ranges (0–24 / 25–44 / 45–64 / 65–79 / 80–100). Those leave one-unit gaps between consecutive bands — (24,25)(44,45)(64,65)(79,80). Composites are floats, so a value in a gap matched no band, exited the loop, and hit the `return SignalBand.DISSONANT` fallback. Surfaced live: Andrew's 2026-06-23 re-run scored **79.13** and read **Dissonant** instead of Tuned. His prior 77.25 was inside 65–79 and read correctly, which is why it only just surfaced.

**The fix (commit `6fd93ac`, 4 files).**

- `assign_band` now treats bands as **half-open lower bounds**: iterate `SIGNAL_BANDS` in reverse, return the highest band whose `lo` the score meets or exceeds. The integer `hi` is documentation only; the top band stays inclusive of 100 (and above). Closes the gaps while preserving the documented integer thresholds exactly — 79.13→Tuned, 24.5→Dissonant, 44.5→Untuned, 64.5→Tuning, 80→Resonant.
- `frontend/src/components/signal-meter/bands.ts` `bandForScore` — a latent identical bug (not the active composite display path post-ORPHEUS-22, but mirrored anyway) — got the same lower-bound logic.
- Tests: +3 backend cases in `TestBandAssignment` (fractional inter-band gaps incl. the live 79.13, fractional-within-band, out-of-range) + new colocated vitest `signal-meter/__tests__/bands.test.ts`.

**Live cloud backfill.** Only one stored row was actually mislabeled: score `8cc136f4` (job `d91b7c11`, 79.13) — corrected Dissonant→Tuned on both `scores.band` and the top-level `dimensions.band`; its four per-dimension bands (65/90/100/62.5) were already correct. The two 24.50 rows (jobs `21c0fc0f`/`b7540d79`) resolve to Dissonant either way (24.5 < 25), so they hit the fallback but displayed the correct label — left unchanged. A table-wide recompute sweep across all 31 stored scores shows **0 band mismatches**.

**Boundary semantics — one-line confirm owed to Andrew.** A fractional value takes its *lower* band (79.x is Tuned until exactly 80). This is noted on the ticket; the lower-bound reading changes nothing about where any integer lands, so it's a courtesy confirm, not a blocker. Ownership: fix mechanics + backfill are Josh's; thresholds + band concept are Andrew's framework (unchanged).

---

## Recommended pickup for next session

1. **ORPHEUS-92** — decide its state. Code shipped 06-19 (`94825d2`, invite token now rides the OAuth redirect URL, +131 lines of InviteFlow tests) but the ticket is still In Progress with no closing comment. Either close it with a proper comment or note what's outstanding. Its siblings 93/94 are in Backlog if you want to batch the invite-flow polish.
2. **ORPHEUS-90** — route the band-shift decision to Andrew (still the oldest open thread). Accept the 4.6 calibration → close; otherwise pin a Sonnet 4 snapshot via `ANTHROPIC_MODEL` or recalibrate. Decision Log draft staged in Josh's outputs. Worth routing alongside the ORPHEUS-95 boundary-semantics confirm.
3. **ORPHEUS-82** — the combined post-deploy live run. Now also the home for ORPHEUS-95's live re-check (confirm a fresh fractional-composite job lands in the right band) and ORPHEUS-91's recency re-check on `72b11642`.
4. **ORPHEUS-88** (high) — the quality gate.

---

## Caveats / things that will bite

1. **ORPHEUS-95 code is inert for new jobs until the worker redeploys.** The live backfill already self-corrects Andrew's existing report; new jobs pick up the fix on the next worker deploy. Same for any ORPHEUS-91 re-validation.
2. **pytest unconfirmed from sandbox** (PyPI blocked). `py_compile` clean on touched backend files. Expected backend ≈ +3 cases on the 06-18 baseline (291→297 was itself unconfirmed; ORPHEUS-95 adds 3); frontend vitest 40 baseline + ORPHEUS-92's InviteFlow cases + ORPHEUS-95's bands.test.ts — **confirm exact counts from your terminal.**
3. **Push state unverifiable from sandbox** (SSH egress blocked, `git fetch` fails). Local reports `main` == `origin/main` == `6fd93ac`, but that ref can't be trusted without a real fetch. The push command below is a safe no-op if everything's already up; it covers `6fd93ac` + `94825d2` (ORPHEUS-92, 06-19) + this handoff commit if any never pushed.
4. **ORPHEUS-92 is undocumented prior work.** It shipped without a handoff, so the only record before this one was the commit message + the In Progress ticket. If anything about the invite OAuth flow looks surprising, `94825d2` is where it changed.
5. **Stale untracked handoff cruft cleaned this session.** `SESSION_HANDOFF_2026-06-17.md` was sitting untracked on disk even though commit `88ad254` retired it from tracking back on 06-18 — a mount artifact. Removed from the working tree this session along with the FUSE `.fuse_hidden*` files. Tracked history was always correct.
6. **Sandbox quirks unchanged:** no SSH push, `.git/*.lock` mv-workaround before commits, PyPI blocked.
7. **Untracked-by-intent files:** `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, survey `.md` + `.gs`, both `rubric_consistency_results_*.json`, compliance drafts. Unchanged.

---

## State of the repo right now (end of session)

One code commit this session (`6fd93ac`, ORPHEUS-95 — `backend/scoring/engine.py`, `backend/tests/test_scoring.py`, `frontend/src/components/signal-meter/bands.ts`, new `frontend/src/components/signal-meter/__tests__/bands.test.ts`). CLAUDE.md "Active phase" + "Decisions Made" and PRODUCT_CONTEXT.md band-breakpoints note updated in this handoff commit. The 06-18 handoff is retired in the same commit; the stale untracked 06-17 file is removed from the working tree. One live cloud data change (no migration): `scores` row `8cc136f4` band backfill.

Prior unpushed-if-never-pushed commits possibly still riding: `94825d2` (ORPHEUS-92, 06-19).

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 model-upgrade entry (drafted, in Josh's outputs) — paste when Andrew signs off. ORPHEUS-85 still owes its entry when it ships. ORPHEUS-95 is a defect fix that preserves the documented thresholds exactly; a Decision Log entry is optional (Josh's call) — worth one only if Andrew wants the boundary-rounding convention recorded as canon.
