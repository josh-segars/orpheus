"""Prose-number reconciliation — ORPHEUS-121 (rides the ORPHEUS-114 registry).

The narrative agent fabricates aggregate counts: on job 301ba109 it wrote
"2,394 total comments" (matches nothing — 2,437 parsed / 2,365 usable /
1,815 in-window) and "331 posts in the archive" (actual: 341). The
diagnostic pattern from reconciling every figure in those narratives: every
number supplied as an explicitly labelled input was correct; every number
the agent derived or recalled from surrounding context was garbled. Prompt
constraints are the weakest lever against this class (the ORPHEUS-117
fix-in-code reasoning), so the gate is code: every numeric token in
client-facing prose must match a whitelisted measured value or a
structural allowance, or generation is rejected and retried.

Design notes:

  * The whitelist is built from the same values the prompt renders — the
    forward-brief metrics (at their registry display precisions, plus
    formatting variants), the coverage counts, sub-dim raw values, and the
    computed milestone targets. If the agent quotes a figure it was handed,
    it passes; if it mints one, it fails.
  * DELIBERATELY EXCLUDED: the composite, per-dimension contributions and
    normalized scores (clients see bands, ORPHEUS-128 — the agent quoting
    the composite is a rejection we WANT), and the band thresholds (prose
    should never quote them).
  * Structural allowances are metric-independent: years, small integers
    (≤12 — ordinals, list counts, "3–5 posts"), and a fixed set of
    duration/scale numbers (90 days, 365 days, the top-50 cap...). Word
    numbers ("three to five posts a week") never tokenize — digits only.
  * Kill switch: env PROSE_NUMBER_GATE ∈ {block (default), log, off}. A
    deterministic false positive would otherwise fail every job with no
    recourse short of a deploy. Rejected tokens are always logged.

Consumed by `generate_narratives` (blocking, with the violation fed back
into the retry prompt) and by `scripts/regenerate_report.py`'s verify step.
"""

from __future__ import annotations

import logging
import os
import re

from backend.models.scoring import ScoringStageOutput
from backend.scoring import registry

logger = logging.getLogger(__name__)


# One numeric token: digits, optional comma grouping, optional decimal tail.
_NUMBER_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Structural numbers that legitimately appear in guidance prose regardless
# of the client's metrics: durations (hours/days/weeks), the analytics
# top-50 cap, per-cent phrasing, and the substantive-comment word threshold.
_STRUCTURAL_ALLOWANCES: frozenset[str] = frozenset({
    "20", "24", "30", "45", "48", "50", "52", "60", "90", "100", "180", "365",
})

# Small integers pass unconditionally: ordinals, list counts, sub-dim scores
# ("4 of 5"), cadence phrasing ("3-5 posts a week").
_SMALL_INT_MAX = 12

_YEAR_RANGE = range(1900, 2100)


def prose_gate_mode() -> str:
    """Resolve the kill switch at call time: block (default) | log | off."""
    mode = os.environ.get("PROSE_NUMBER_GATE", "block").strip().lower()
    return mode if mode in ("block", "log", "off") else "block"


# --------------------------------------------------------------------------- #
# Client-facing string enumeration
# --------------------------------------------------------------------------- #

def client_facing_strings(narrative_result) -> list[tuple[str, str]]:
    """Every string the client can read, tagged with where it came from.

    Reads from the NarrativeResult directly (pre-merge), so it works both at
    generation time in `generate_narratives` and post-merge in
    `regenerate_report.py` — the sub-dim slot contents are identical in both
    places by construction (`_merge_sub_dim_narratives` copies them).
    """
    out: list[tuple[str, str]] = []
    for name, text in narrative_result.sections.items():
        out.append((f"section:{name}", text))
    for name, text in narrative_result.summaries.items():
        out.append((f"summary:{name}", text))
    for (dim_name, sub_name), payload in narrative_result.sub_dimensions.items():
        for slot in ("summary", "best_practices"):
            value = payload.get(slot)
            if value:
                out.append((f"{dim_name}/{sub_name}.{slot}", value))
        for i, bullet in enumerate(payload.get("improvements") or []):
            out.append((f"{dim_name}/{sub_name}.improvements[{i}]", bullet))
    cs = narrative_result.cheat_sheet or {}
    for i, p in enumerate(cs.get("priorities", [])):
        out.append((f"cheat_sheet.priorities[{i}]", f"{p['title']} {p['action']}"))
    for section in cs.get("rhythm", []):
        for i, item in enumerate(section.get("items", [])):
            out.append((f"cheat_sheet.rhythm[{section['cadence']}][{i}]", item))
    for i, m in enumerate(cs.get("milestones", [])):
        out.append((f"cheat_sheet.milestones[{i}]", f"{m['value']} {m['label']}"))
    return out


# --------------------------------------------------------------------------- #
# Whitelist construction
# --------------------------------------------------------------------------- #

def _normalize(token: str) -> str:
    """Canonical comparison form: commas stripped, trailing '.0' dropped."""
    t = token.replace(",", "")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t


def _value_variants(value: float | int, decimals: int = 0) -> set[str]:
    """Every display form a metric value legitimately appears in."""
    variants: set[str] = set()
    for d in {0, 1, decimals}:
        variants.add(_normalize(f"{value:.{d}f}"))
    variants.add(_normalize(str(value)))
    return variants


def _rate_variants(value: float) -> set[str]:
    """Percentage renderings of a stored 0–1 rate: 2.71 / 2.7 / 3."""
    pct = value * 100
    return {
        _normalize(f"{pct:.{d}f}") for d in (0, 1, 2)
    }


def build_number_whitelist(
    scoring_output: ScoringStageOutput,
    milestone_targets=None,
) -> set[str]:
    """Normalized tokens the prose is allowed to quote."""
    allowed: set[str] = set()
    q = scoring_output.forward_brief_data.quantitative

    # Forward-brief metrics at their registry precisions + variants.
    for key, spec in registry.FORWARD_BRIEF_METRICS.items():
        value = getattr(q, key, None)
        if value is None:
            continue
        if spec.percent:
            allowed |= _rate_variants(float(value))
        else:
            allowed |= _value_variants(value, spec.decimals)

    # Coverage counts and totals — the "72 of 2,437" class.
    cov = scoring_output.forward_brief_data.coverage
    if cov is not None:
        allowed |= _value_variants(cov.posts_in_window)
        allowed |= _value_variants(cov.top_posts_covered)
        for exc in (cov.shares, cov.comments, cov.reactions):
            allowed |= _value_variants(exc.total_rows)
            allowed |= _value_variants(exc.unparseable)
            allowed |= _value_variants(exc.empty)
            allowed |= _value_variants(exc.unparseable + exc.empty)

    # Sub-dim raw values (the labelled measured signals) — registered,
    # non-suppressed only, matching what the prompt actually renders.
    for dim in scoring_output.scored_dimensions.dimensions:
        for sub in dim.sub_dimensions:
            if sub.raw_value is None:
                continue
            if sub.name in registry.SUPPRESSED_SUB_DIMS:
                continue
            spec = registry.SUB_DIM_METRICS.get(sub.name)
            decimals = spec.decimals if spec else 0
            allowed |= _value_variants(sub.raw_value, decimals)

    # Computed milestone targets (and their baselines) — display strings
    # like "3,550" or "2.9%"; harvest their digit tokens.
    for target in milestone_targets or []:
        for text in (target.value, target.baseline_display or ""):
            for tok in _NUMBER_TOKEN.findall(text):
                allowed.add(_normalize(tok))

    # NOT whitelisted, deliberately: composite, contributions, normalized
    # scores (ORPHEUS-128 — bands are the client display; the agent quoting
    # the composite SHOULD reject) and band thresholds.
    allowed.discard("")
    return allowed


# --------------------------------------------------------------------------- #
# Scan
# --------------------------------------------------------------------------- #

def find_unwhitelisted_numbers(
    strings: list[tuple[str, str]],
    whitelist: set[str],
) -> list[tuple[str, str]]:
    """Return (where, token) for every numeric token no rule allows."""
    violations: list[tuple[str, str]] = []
    for where, text in strings:
        for raw in _NUMBER_TOKEN.findall(text):
            token = _normalize(raw)
            if not token or token in whitelist:
                continue
            if token in _STRUCTURAL_ALLOWANCES:
                continue
            if "." not in token:
                as_int = int(token)
                if as_int <= _SMALL_INT_MAX:
                    continue
                if as_int in _YEAR_RANGE:
                    continue
            violations.append((where, raw))
    return violations


def describe_violations(violations: list[tuple[str, str]]) -> str:
    """Human-readable summary for error messages and logs."""
    return "; ".join(f"{where}: {token!r}" for where, token in violations)
