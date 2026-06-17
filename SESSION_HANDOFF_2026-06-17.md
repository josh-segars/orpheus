# Session Handoff — 2026-06-17

Retires `SESSION_HANDOFF_2026-06-15_part2.md`. That session's one open thread (ORPHEUS-90, model upgrade pending Andrew's sign-off) is restated below and is still open. Nothing from part 2 is lost.

This was a **diagnostic-only session — no code, no doc changes.** Output lives entirely in Plane: a findings comment on ORPHEUS-90 and a new bug ticket, **ORPHEUS-91**. There is no code commit from this session; the only committed artifact is this handoff (retiring the part-2 handoff).

Session shape: Josh flagged that after the Sonnet 4.6 upgrade, Andrew's latest report read "No original posts are recorded in the most recent period" despite Andrew being a prolific poster → investigated the live cloud data → root-caused two distinct effects → recorded the model half on ORPHEUS-90 and filed the recency half as ORPHEUS-91.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-91 | Recency sub-dim anchors its 60-day window to `date.today()` — re-running an identical export later silently changes the score | 🆕 **Filed this session.** Backlog, high. Fix not started — anchor decision routes to Andrew. |
| ORPHEUS-90 | Upgrade pipeline model → claude-sonnet-4-6 | 🟡 **Code shipped, OPEN.** Andrew sign-off pending on the band shift. Now confirmed band-crossing on a live client report (comment added this session). |
| ORPHEUS-89 | Profile-photo presence from LinkedIn OIDC | ✅ Done (`1094164`). Migration 015 on cloud. |
| ORPHEUS-82 | Live validation of 81 (+78/+87/+89) | ⏳ Backlog (medium). Combined post-deploy run still owed. |
| ORPHEUS-88 | Quality gate: confident reports on critically-deficient data | ⏳ Backlog (**high**). |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |

---

## What this session did (no code)

### Diagnosed Andrew's "no posts" report — two separate effects

Compared Andrew's latest job (`28d59a7e`, 2026-06-17, Sonnet 4.6) against the preserved prior run on the **same uploaded export** (`72b11642`, 2026-06-12, Sonnet 4). Ingested data byte-identical both times: 301 shares / 1,821 comments / 8,528 reactions. The posts are fully ingested — this is not an ORPHEUS-87-style parse regression.

**Effect 1 — the "no original posts in the most recent period" line is NOT the model.** It's the deterministic Recency sub-dim (Dim 2, `quantitative_hybrid`). Recency counts outbound posts in the trailing 60 days anchored to `date.today()` (`backend/scoring/engine.py:751–752`; worker passes no `ref_date`). Same export: Recency = 1 (raw 12) on 06-12, Recency = 0 (raw 0) on 06-17 — the window slid past his latest posts as the calendar advanced. History Depth scored 5/5 (raw 4,667) both runs. The narrative agent truthfully described a recency score of 0 using the ORPHEUS-63 score-0 wording. **→ filed as ORPHEUS-91.**

**Effect 2 — the band drop (80.50/Resonant → 66.50/Tuned, −14) IS mostly the 4.6 swap.** The two Claude rubric dimensions each fell a band on identical data: Profile Signal Clarity 0.85→0.60 (contrib 29.75→21.0), Profile-Behavior Alignment 0.75→0.50 (11.25→7.50). Deterministic Dim 3 unchanged; Recency 1→0 shaved ~1.5 more pts off Dim 2. This is the ORPHEUS-90 "4.6 runs harsher" finding, now confirmed band-crossing on a real high-activity profile (the framework author's own). **→ recorded as a comment on ORPHEUS-90.**

### ORPHEUS-91 filed (high, Backlog)

Recency window anchored to `date.today()` makes scores non-reproducible on identical data and produces alarming client-facing copy. Proposed fix: anchor `ref_date` to the export's latest-activity date (or job `created_at`) and persist `ref_date` into `config_snapshot` for auditability. The definition of "recent" is framework-adjacent — Andrew should confirm the anchor before code lands.

---

## Recommended pickup for next session

Josh said he'll open the next ticket in a new session. Most likely candidates:

1. **ORPHEUS-91** — the recency anchor fix. Gate on Andrew's call for what "recent" anchors to (data-capture date vs. processing date), then it's a contained change in `engine.py` + `processor.py` call site + `config_snapshot`. Repro is easy: re-run `72b11642`'s export today and watch Recency 1→0.
2. **ORPHEUS-90** — route the band-shift decision to Andrew now that there's a live client example. The Decision Log draft is staged in Josh's outputs. Accept the calibration → close; otherwise pin a dated Sonnet 4 snapshot via `ANTHROPIC_MODEL` (no code change) or recalibrate thresholds.
3. **ORPHEUS-88** (high) — the quality gate, which is thematically adjacent to 91 (both are about reports presenting confidently on data that warrants a caveat).

ORPHEUS-90 and ORPHEUS-91 are intertwined — both showed up on the same Andrew report, both touch how much to trust a band, and both ultimately need Andrew. Worth routing them to him together.

---

## Caveats / things that will bite

1. **Andrew's 06-17 report is band-crossed low** by the combination of the 4.6 harshness and the recency-window artifact. Until ORPHEUS-90 + ORPHEUS-91 resolve, treat fresh 4.6 scores near a band boundary as provisional — especially on older uploaded exports.
2. **ORPHEUS-91 is data-date-sensitive.** Any re-run of a preserved demo export will now score recency lower than its original run purely because of calendar drift. Don't read that as a behavior change in the data.
3. **Push state unverifiable from sandbox** (SSH egress blocked, `git fetch` fails). Local git reports up-to-date with origin/main, but the part-2 handoff's commits (`cf679b2` ORPHEUS-90, `575b02c` handoff) may still be unpushed if the earlier push never ran. The push command below covers everything outstanding.
4. **Stray untracked `SESSION_HANDOFF_2026-06-15.md`** (part 1) sat in the working tree — already git-removed in the part-2 commit, so it's a leftover copy. Cleaned up / staged for non-tracking this session.
5. **Sandbox quirks unchanged:** no SSH push, `.git/*.lock` mv-workaround before commits, PyPI blocked (no pytest from sandbox).
6. **Untracked-by-intent files:** survey `.md` + `.gs`, both `rubric_consistency_results_*.json`, compliance drafts. Unchanged.

---

## State of the repo right now (end of session)

No code or doc files changed this session. The only new tracked file is this handoff; the part-2 handoff is retired in the same commit. Backend pytest baseline unchanged (expected **291**, still unconfirmed from Josh's terminal — no tests added since). Frontend vitest **40**.

Unpushed commits possibly outstanding from the prior session (`cf679b2`, `575b02c`) plus this handoff commit.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 model-upgrade entry (drafted, in Josh's outputs) — paste when Andrew signs off. The 06-17 live-report finding strengthens that entry's evidence. ORPHEUS-85 still owes its entry when it ships.
