# Session Handoff — 2026-06-15 (part 2)

Retires `SESSION_HANDOFF_2026-06-15.md` (part 1, ORPHEUS-89). That session is fully shipped + pushed (`1094164`, ORPHEUS-89 Done in Plane); its still-open carry-forward threads are restated below. Nothing from part 1 is lost.

This session shipped **one ticket's code — ORPHEUS-90** (pipeline model upgrade to Claude Sonnet 4.6), which is **intentionally left open** pending Andrew's sign-off on a band recalibration the revalidation surfaced.

Session shape: Josh asked whether the service was on a dated Claude model → traced the hardcoded `claude-sonnet-4-20250514` across `rubric.py` (3 defaults), `narrative.py` (1), and `scripts/rubric_consistency.py` (`PRODUCTION_MODEL`) → filed ORPHEUS-90 → implemented an env-overridable `DEFAULT_MODEL` (`claude-sonnet-4-6`, `ANTHROPIC_MODEL` override) in `backend/agents/__init__.py` and pointed all call sites at it → Josh ran the consistency harness against 4.6 from his terminal → drafted the Decision Log entry with the harness verdict → wrap.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-90 | Upgrade pipeline model → claude-sonnet-4-6 | 🟡 **Code shipped, ticket OPEN.** Andrew sign-off pending on the band shift. |
| ORPHEUS-89 | Profile-photo presence from LinkedIn OIDC | ✅ Done (part 1, `1094164`). Migration 015 on cloud. |
| ORPHEUS-82 | Live validation of 81 (+78/+87/+89) | ⏳ Backlog (medium). Combined post-deploy run still owed. |
| ORPHEUS-88 | Quality gate: confident reports on critically-deficient data | ⏳ Backlog (**high**). |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). 85 owes a Decision Log entry + open-vs-gated decision at ship. |
| ORPHEUS-42 / 45 / 48 / 40 / 41 | Account page / edit action / branding / Stripe / disconnect | ⏸ Backlog. Unchanged. |

---

## What this session shipped

### ORPHEUS-90 — pipeline model upgrade to Claude Sonnet 4.6 (code committed, ticket open)

Both Claude calls in the pipeline (rubric scoring for Dim 1 + 4; narrative generation) were pinned to `claude-sonnet-4-20250514` — the original May 2025 Sonnet 4 snapshot. Current Sonnet is 4.6.

- **New `backend/agents/__init__.py`**: `DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")`. Read at import time, so it works as a function default and is overridable per-deploy without a code change. Matches the worker's existing direct-`os.environ` posture (the worker doesn't go through `config.get_settings()`).
- **`backend/agents/rubric.py`**: 3 signature defaults (`score_dimension_1`, `score_dimension_4`, `score_rubrics`) → `DEFAULT_MODEL`.
- **`backend/agents/narrative.py`**: `generate_narratives` default → `DEFAULT_MODEL`.
- **`backend/scripts/rubric_consistency.py`**: `PRODUCTION_MODEL = DEFAULT_MODEL` (tracks the pipeline default; `--model` flag still overrides for A/B runs).
- **`backend/.env.example`**: documented the optional `ANTHROPIC_MODEL` var.
- The worker calls `score_rubrics(...)` and `generate_narratives(...)` without a `model=` arg, so it picks up 4.6 through the defaults automatically — no worker code change needed.

**Why the ticket is still open — the revalidation surfaced a band shift.** ORPHEUS-75 pinned the rubric calls at temperature 0 to kill band-crossing variance, and that determinism was measured against Sonnet 4. Josh re-ran `backend/scripts/rubric_consistency.py` against 4.6 (N=10 per arm, 2 arms, 2 preserved demo profiles, results at `rubric_consistency_results_2026-06-15_171218.json`, untracked):

| Profile | Sonnet 4 (prior) | 4.6 temp-0 | 4.6 api-default |
|---|---|---|---|
| Josh demo (`e11eff50`) | 27 / Untuned | **21.5 / Dissonant** (stdev 0.00) | 21.5 / Dissonant (stdev 0.00) |
| Andrew demo (`710b14be`) | 75.75 / Tuned | **74.25 / Tuned** (stdev 0.00) | 70.5–74.25 / Tuned (stdev 1.12) |

Two findings: (1) **temp-0 determinism survives the swap** — 0.00 stdev on both profiles, so the ORPHEUS-75 property holds under 4.6; (2) **4.6 runs marginally harsher**, enough to push Josh's profile across the Untuned→Dissonant boundary (24/25). Andrew's profile held Tuned and is now *stably* Tuned even at default temp (under Sonnet 4 it swung Tuned/Resonant at default).

The band shift is framework-visible → **Andrew's call** before 4.6 is trusted for client-facing reports.

### Verification

- `py_compile` clean on all 5 touched files; `from backend.agents import DEFAULT_MODEL` resolves to `claude-sonnet-4-6`; `ANTHROPIC_MODEL=…` override confirmed working.
- No new tests — the change is a constant swap and no test asserts the model string. Backend pytest baseline unchanged (expected **291** from ORPHEUS-89, still unconfirmed from Josh's terminal). Frontend untouched (vitest 40).
- Only remaining `claude-sonnet-4-20250514` literal in source is a historical note in the `agents/__init__.py` docstring.

---

## Recommended pickup for next session

1. **ORPHEUS-90 — route the band-shift decision to Andrew, then close or escalate.** The Decision Log draft (Josh's outputs folder, `decision_log_ORPHEUS-90_model_upgrade.md`) is paste-ready with the harness table. If Andrew accepts 4.6's harsher low-end calibration → paste the entry, close ORPHEUS-90. If not → escalation paths are pin a specific dated Sonnet 4 snapshot (`ANTHROPIC_MODEL` revert, no code change) or recalibrate band thresholds (framework change, Andrew's domain).
2. **ORPHEUS-82** — the consolidated live validation run (covers 81 run-guard, 77 voice, 66 word specs, temp-0, 76/78 visual+copy, 89's OIDC photo flag, and — once it deploys — 90's model). Confirm Railway carries the latest commit + the worker redeployed before relying on a fresh job.
3. **ORPHEUS-88** (high) — the quality gate. Reports ship confidently even when critical data-quality flags fire.
4. **ORPHEUS-86** — upload-failure UX.
5. **ORPHEUS-84 / 85** — roles + growth pair; 85 needs the open-vs-gated sign-up decision routed (Tim/Josh on cost posture).

---

## Caveats / things that will bite

1. **ORPHEUS-90 code is committed but the model change is NOT live until the worker redeploys** on Railway. Until then, production still scores with Sonnet 4. Don't expect new jobs to reflect 4.6 (or the band shift) before the worker picks up the commit. Railway has needed a manual redeploy click historically.
2. **Andrew sign-off gates ORPHEUS-90.** Treat 4.6 scores as provisional until then — particularly near the low band boundary, where the calibration shifted.
3. **Backend pytest count unconfirmed** — 291 expected (carried from part 1); ORPHEUS-90 added no tests. Correct if Josh's terminal disagrees.
4. **ORPHEUS-89 sends an explicit `false` for photo-less accounts** (OIDC overrides even the no-photo case). One-line change in `useCreateJob.ts` if Josh prefers "only override when a photo exists."
5. **Andrew's advisors `practice_name` is still NULL** — labels fall back to his email.
6. **`POST /advisor/self-report` vs. migration 014** — a dual-role user whose clients row lives under a different advisor would 500 against the unique index; ORPHEUS-84's invite-advisor flow must decide the behavior before it ships.
7. **Free re-runs + (soon) free sign-up = unmetered pipeline cost** — single-in-flight guard is the only throttle until ORPHEUS-85's gate / ORPHEUS-40 Stripe.
8. **Sandbox quirks unchanged:** no SSH push, `.git/*.lock` mv-workaround before commits, PyPI blocked (no pytest from sandbox).
9. **Untracked-by-intent files:** survey `.md` + `.gs`, **both** `rubric_consistency_results_*.json` (06-10 + the new 06-15), compliance drafts. The 06-15 results file is the ORPHEUS-90 evidence — keep it around until 90 closes.

---

## State of the repo right now (end of session)

`origin/main` was at `1094164` (ORPHEUS-89, pushed) plus the part-1 handoff commit `d693f23` (also pushed). This session adds two unpushed commits:

1. `ORPHEUS-90: bump pipeline model to claude-sonnet-4-6 via env-overridable DEFAULT_MODEL` — the 5 code files.
2. `Session handoff: 2026-06-15 part 2. Retire 2026-06-15.` — this handoff (retiring part 1) + CLAUDE.md refresh.

CLAUDE.md updated: Active phase gained an ORPHEUS-90 sentence (model bump + open Andrew sign-off + harness verdict); `ANTHROPIC_MODEL` added to the env-var reference. No new "Decisions Made" entry yet — that lands when ORPHEUS-90 closes (the Decision Log draft is staged in Josh's outputs). PRODUCT_CONTEXT.md / CONVENTIONS.md / CREDENTIALS.md untouched.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 model-upgrade entry (drafted, in Josh's outputs) — paste when Andrew signs off. ORPHEUS-85 still owes its entry when it ships (revises invitation-only-beta).
