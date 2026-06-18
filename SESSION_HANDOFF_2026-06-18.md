# Session Handoff — 2026-06-18

Retires `SESSION_HANDOFF_2026-06-17.md`. That handoff's top recommendation was **ORPHEUS-91 (recency anchor fix)** — shipped and closed this session. Its other open threads are restated below and remain open: **ORPHEUS-90** (model upgrade, pending Andrew's sign-off) and the backlog (ORPHEUS-82 / 88 / 86 / 84 / 85). Nothing from the 06-17 handoff is lost.

This session: **one ticket, one commit.** ORPHEUS-91 fixed — code committed (`44ef366`), ticket moved to Done, CLAUDE.md + PRODUCT_CONTEXT.md updated. The handoff commit retires the 06-17 file in the same commit.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-91 | Recency window anchored to `date.today()` — non-reproducible scores | ✅ **Done this session** (`44ef366`). Live re-run validation folds into ORPHEUS-82. |
| ORPHEUS-90 | Upgrade pipeline model → claude-sonnet-4-6 | 🟡 **Code shipped, OPEN.** Andrew sign-off pending on the band shift. Decision Log draft staged in Josh's outputs. |
| ORPHEUS-82 | Live validation of 81 (+78/+87/+89) — now also covers 91 | ⏳ Backlog (medium). Combined post-deploy run still owed; add the `72b11642` recency re-check to it. |
| ORPHEUS-88 | Quality gate: confident reports on critically-deficient data | ⏳ Backlog (**high**). Thematically adjacent to 91. |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |

---

## What this session did

### ORPHEUS-91 — recency window anchor (shipped, closed)

**The bug.** Recency (Dim 2) counted outbound posts in a trailing `DIM2_RECENCY_WINDOW_DAYS = 60` window relative to `ref_date`, and the worker passed no `ref_date`, so it defaulted to `date.today()`. The window slid forward with the wall clock while uploaded exports stayed frozen — so re-running an identical export days later silently collapsed Recency to 0 and produced the "no original posts recorded" copy on Andrew's 06-17 report despite 301 ingested shares.

**The fix (commit `44ef366`, 4 files, +141).**

- New `_latest_activity_date(zip_data)` + `resolve_ref_date(zip_data)` in `backend/scoring/engine.py`: anchor `ref_date` to the max parsed date across shares/comments/reactions; fall back to `date.today()` only when the export has no dated activity. `run_scoring` uses it for its `ref_date=None` default.
- `backend/workers/processor.py` resolves the anchor once, logs it, passes it explicitly to `run_scoring`, and threads it into `build_config_snapshot(ref_date=...)`.
- `backend/scoring/config.py` `build_config_snapshot` gains an optional `ref_date` param; when supplied it records `ref_date` (ISO) + `ref_date_anchor: "latest_activity"` so the window is reproducible/auditable.
- `backend/tests/test_scoring.py`: +6 cases (`TestResolveRefDate` — latest-across-collections, fallback-to-today, unparseable-date skip, recency reproducible regardless of today; `TestConfigSnapshotRefDate` — ref_date recorded/absent).

**Anchor decision.** Latest-activity (ticket options a + c) — Josh's call, routed from Andrew per the framework-adjacency note. Recorded as a fix comment on the ticket. Semantic note flagged for Andrew (also in the comment): "recent" now means "recent relative to data capture," not "active as of the run date" — a member whose newest post in the export is itself old still gets a window starting there. Intended reproducibility trade-off; a hybrid (cap the anchor at job `created_at`) is a small follow-up if the framework wants it.

---

## Recommended pickup for next session

1. **ORPHEUS-90** — route the band-shift decision to Andrew. He now has two live data points on his own profile (the 4.6 harshness + the recency artifact, both surfaced 06-17, the recency half now fixed). Accept the calibration → close; otherwise pin a dated Sonnet 4 snapshot via `ANTHROPIC_MODEL` (no code change) or recalibrate thresholds. Decision Log draft is staged in Josh's outputs.
2. **ORPHEUS-82** — the combined post-deploy live run, now also the validation home for ORPHEUS-91. Cheapest concrete check: re-run `72b11642`'s export and confirm Recency holds steady (no longer 1→0) and `config_snapshot` carries `ref_date`/`ref_date_anchor`.
3. **ORPHEUS-88** (high) — the quality gate, thematically adjacent to 91 (both about reports presenting confidently on data that warrants a caveat).

ORPHEUS-90 and 91 are intertwined and both ultimately need Andrew; worth routing the 90 decision plus the 91 semantic note to him together.

---

## Caveats / things that will bite

1. **ORPHEUS-91 is shipped but not yet pushed or live-validated.** `py_compile` clean; full pytest unconfirmed from sandbox (PyPI blocked). Expected backend pytest **291 → 297**; confirm from your terminal. The fix is inert until the worker redeploys.
2. **Score comparisons across run dates change meaning now.** Pre-91 jobs scored recency against the run date; post-91 jobs score against the export's latest activity. A re-run of any preserved demo export will now score recency differently (higher/stable) than its original run — that's the fix working, not a data change.
3. **ORPHEUS-90 still in flight** — fresh 4.6 scores near a band boundary remain provisional until Andrew signs off. The recency half of the 06-17 band drop is now addressed; the rubric-harshness half is not.
4. **Push state unverifiable from sandbox** (SSH egress blocked, `git fetch` fails). Local git reports up-to-date with origin/main. The push command below covers `44ef366` + this handoff commit, plus anything still outstanding from prior sessions (`cf679b2`, `8cf24a9`) if those never pushed.
5. **Sandbox quirks unchanged:** no SSH push, `.git/*.lock` mv-workaround before commits, PyPI blocked (no pytest from sandbox).
6. **Untracked-by-intent files:** `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, survey `.md` + `.gs`, both `rubric_consistency_results_*.json`, compliance drafts. Unchanged.

---

## State of the repo right now (end of session)

One code commit this session (`44ef366`, ORPHEUS-91 — 4 backend files). CLAUDE.md "Active phase" + PRODUCT_CONTEXT.md decisions updated in the handoff commit. The 06-17 handoff is retired in the same commit. Backend pytest baseline expected **291 → 297** (still to confirm from Josh's terminal). Frontend vitest **40** (untouched this session).

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 model-upgrade entry (drafted, in Josh's outputs) — paste when Andrew signs off. ORPHEUS-85 still owes its entry when it ships. ORPHEUS-91's anchor change is documented in CLAUDE.md + PRODUCT_CONTEXT.md; a Decision Log entry is optional (Josh's call — it's a reproducibility fix with a minor framework-semantic note, routed from Andrew).
