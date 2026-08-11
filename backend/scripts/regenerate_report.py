"""ORPHEUS-112/113/117: regenerate a delivered report in place.

Re-runs deterministic scoring (stage 3) and narrative generation (stage 4)
against a job's **already-stored** `ingested_data`, then overwrites that job's
`scores` and `narratives` rows. The point is to correct a report a client has
already read without minting a second job — a normal re-run through the product
creates a new job row, so the client ends up looking at a corrected report next
to the wrong one it replaced.

Written for the metric-accuracy batch (ORPHEUS-117 raw units, ORPHEUS-112
impressions denominator, ORPHEUS-113 invented milestones), all three of which
change `forward_brief_data` and narrative text but never a scored input. The
script asserts that: if the composite moves, it aborts unless you say
otherwise, because a moving composite means something outside this batch's
blast radius changed and the run needs a human look.

What it deliberately does NOT touch: the job row (status, `data_limited`,
`config_snapshot`), `reports`, and the report-ready email path. Stage 1
(ingestion) and stage 2 (rubric scoring) are not re-run either — parsing is
unchanged by this batch, and the stored Dim 1 / Dim 4 rubric scores are reused
so the composite is guaranteed identical and no Claude rubric calls are spent.
One narrative call runs per job (~$0.10).

Run from the repo root on a machine with backend deps + env (NOT the Claude
sandbox — PyPI and API egress are blocked there):

    # inspect only; writes nothing
    python -m backend.scripts.regenerate_report 301ba109

    # write it
    python -m backend.scripts.regenerate_report 301ba109 --apply

    # put it back
    python -m backend.scripts.regenerate_report --restore snapshot_301ba109_....json

Requires SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY — read from the
environment, falling back to backend/.env then .env.

A snapshot of the pre-existing `scores` + `narratives` rows is written before
any write, and `--restore` puts them back verbatim, so the overwrite is
reversible. Snapshots are untracked by default (repo root, timestamped).
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from anthropic import Anthropic  # noqa: E402
from supabase import create_client  # noqa: E402

from backend.agents.narrative import (  # noqa: E402
    build_milestone_targets,
    generate_narratives,
)
from backend.ingestion.types import XlsxData, ZipData  # noqa: E402
from backend.models.quality import DataQualityReport  # noqa: E402
from backend.scoring.engine import resolve_ref_date, run_scoring  # noqa: E402
from backend.scoring.reconciliation import check_reconciliation  # noqa: E402
from backend.workers.processor import (  # noqa: E402
    _merge_dim_summaries,
    _merge_sub_dim_narratives,
)

REQUIRED_ENV = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "ANTHROPIC_API_KEY")

# Rubric-scored dimensions: their sub-dim scores are reused from the stored
# row rather than re-derived, so no Claude rubric call is made and the
# composite cannot drift.
RUBRIC_DIMENSIONS = ("Profile Signal Clarity", "Profile-Behavior Alignment")

# Phrasings that must not survive into client-facing text (ORPHEUS-117's
# acceptance criterion, plus ORPHEUS-112's stale value).
BANNED_SUBSTRINGS = (
    "raw value",
    "raw archive value",
    "activity units",
    "activity unit",
)


def _load_env() -> None:
    """Fill missing env vars from backend/.env or .env (KEY=VALUE lines)."""
    for env_path in (REPO_ROOT / "backend" / ".env", REPO_ROOT / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing required env vars: {', '.join(missing)} "
                 f"(checked environment, backend/.env, .env)")


# ============================================================
# Fetch
# ============================================================

def _resolve_job_id(supabase, prefix: str) -> str:
    """Accept an id prefix the way the Plane tickets and handoffs quote them."""
    if len(prefix) >= 36:
        return prefix
    rows = (
        supabase.table("jobs").select("id,created_at").order(
            "created_at", desc=True
        ).execute()
    ).data or []
    matches = [r["id"] for r in rows if r["id"].startswith(prefix)]
    if not matches:
        sys.exit(f"No job id starts with {prefix!r}.")
    if len(matches) > 1:
        sys.exit(f"Ambiguous prefix {prefix!r}: {', '.join(matches)}")
    return matches[0]


def _fetch_context(supabase, job_id: str) -> dict:
    job = (
        supabase.table("jobs").select("*").eq("id", job_id).single().execute()
    ).data
    if job["status"] != "complete":
        sys.exit(
            f"Job {job_id} is {job['status']!r}, not 'complete'. This script "
            f"corrects delivered reports; let the worker finish the job first."
        )

    client_row = (
        supabase.table("clients")
        .select("*, advisors!inner(is_individual, narrative_config)")
        .eq("id", job["client_id"])
        .single()
        .execute()
    ).data

    q_row = (
        supabase.table("questionnaire_responses")
        .select("answers")
        .eq("client_id", job["client_id"])
        .single()
        .execute()
    ).data

    ingested = (
        supabase.table("ingested_data")
        .select("zip_data,xlsx_data,quality_report")
        .eq("job_id", job_id)
        .single()
        .execute()
    ).data

    scores = (
        supabase.table("scores").select("*").eq("job_id", job_id).single().execute()
    ).data

    narratives = (
        supabase.table("narratives").select("*").eq("job_id", job_id).execute()
    ).data or []

    return {
        "job": job,
        "client_row": client_row,
        "questionnaire": (q_row or {}).get("answers") or {},
        "ingested": ingested,
        "scores": scores,
        "narratives": narratives,
    }


def _extract_rubric_scores(scores_row: dict) -> tuple[dict, dict]:
    """Pull stored Dim 1 / Dim 4 sub-dim scores back out of scores.dimensions."""
    by_dim: dict[str, dict[str, int]] = {}
    for dim in (scores_row.get("dimensions") or {}).get("dimensions", []):
        if dim.get("name") not in RUBRIC_DIMENSIONS:
            continue
        by_dim[dim["name"]] = {
            sub["name"]: int(round(float(sub["score"])))
            for sub in dim.get("sub_dimensions", [])
        }
    missing = [d for d in RUBRIC_DIMENSIONS if not by_dim.get(d)]
    if missing:
        sys.exit(
            f"Stored scores row has no sub-dimensions for {missing} — cannot "
            f"reuse rubric scores. Re-run the job through the worker instead."
        )
    return by_dim[RUBRIC_DIMENSIONS[0]], by_dim[RUBRIC_DIMENSIONS[1]]


def _stored_ref_date(job: dict, zip_data: ZipData) -> date:
    """Prefer the ref_date the original run recorded (ORPHEUS-91).

    Re-resolving would give the same answer today — the anchor is the export's
    latest dated activity, not the wall clock — but reusing the recorded value
    removes the question entirely.
    """
    recorded = (job.get("config_snapshot") or {}).get("ref_date")
    if recorded:
        return date.fromisoformat(recorded)
    return resolve_ref_date(zip_data)


# ============================================================
# Snapshot / restore
# ============================================================

def _write_snapshot(ctx: dict, out_dir: Path) -> Path:
    job_id = ctx["job"]["id"]
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    path = out_dir / f"snapshot_{job_id[:8]}_{stamp}.json"
    path.write_text(json.dumps({
        "job_id": job_id,
        "taken_at": stamp,
        "scores": ctx["scores"],
        "narratives": ctx["narratives"],
    }, indent=2, default=str))
    return path


def restore(supabase, snapshot_path: Path) -> None:
    data = json.loads(snapshot_path.read_text())
    job_id = data["job_id"]
    scores = data["scores"]
    narratives = data["narratives"]

    print(f"Restoring job {job_id} from {snapshot_path.name}")
    supabase.table("scores").update({
        "total_score": scores["total_score"],
        "band": scores["band"],
        "dimensions": scores["dimensions"],
        "forward_brief_data": scores["forward_brief_data"],
    }).eq("job_id", job_id).execute()

    supabase.table("narratives").delete().eq("job_id", job_id).execute()
    for row in narratives:
        payload = {k: v for k, v in row.items() if k not in ("id",)}
        supabase.table("narratives").insert(payload).execute()

    print(f"  scores row restored, {len(narratives)} narrative rows reinserted.")


# ============================================================
# Verification
# ============================================================

def _client_facing_strings(scoring_output, narrative_result) -> list[tuple[str, str]]:
    """Every string the client can read, tagged with where it came from."""
    out: list[tuple[str, str]] = []
    for name, text in narrative_result.sections.items():
        out.append((f"section:{name}", text))
    for name, text in narrative_result.summaries.items():
        out.append((f"summary:{name}", text))
    for dim in scoring_output.scored_dimensions.dimensions:
        for sub in dim.sub_dimensions:
            for slot in ("summary", "best_practices"):
                value = getattr(sub, slot, None)
                if value:
                    out.append((f"{dim.name}/{sub.name}.{slot}", value))
            for i, bullet in enumerate(sub.improvements or []):
                out.append((f"{dim.name}/{sub.name}.improvements[{i}]", bullet))
    cs = narrative_result.cheat_sheet or {}
    for i, p in enumerate(cs.get("priorities", [])):
        out.append((f"cheat_sheet.priorities[{i}]", f"{p['title']} {p['action']}"))
    for section in cs.get("rhythm", []):
        for i, item in enumerate(section.get("items", [])):
            out.append((f"cheat_sheet.rhythm[{section['cadence']}][{i}]", item))
    for i, m in enumerate(cs.get("milestones", [])):
        out.append((f"cheat_sheet.milestones[{i}]", f"{m['value']} {m['label']}"))
    return out


def _contains_number(text: str, number: str) -> bool:
    """True when `number` appears in `text` as a standalone figure."""
    return re.search(
        rf"(?<![\d.,]){re.escape(number)}(?![\d.,]*\d)", text
    ) is not None


def verify(scoring_output, narrative_result, milestone_targets, stale_values) -> list[str]:
    """Return a list of failures; empty means the acceptance test passed."""
    failures: list[str] = []
    strings = _client_facing_strings(scoring_output, narrative_result)

    # ORPHEUS-114: an in-place regeneration is held to the same
    # reconciliation identities the worker enforces pre-persist.
    for r in check_reconciliation(scoring_output.forward_brief_data):
        if not r.ok:
            failures.append(f"reconciliation {r.name}: {r.detail}")

    # ORPHEUS-117: no internal scoring unit reaches the client.
    for where, text in strings:
        lowered = text.lower()
        for banned in BANNED_SUBSTRINGS:
            if banned in lowered:
                failures.append(f"{where}: contains {banned!r}")

    # ORPHEUS-112: the superseded figure must not survive anywhere. Matched on
    # digit boundaries so a legitimate figure that merely contains the stale
    # digits (18,750 vs 875) doesn't trip the gate.
    for where, text in strings:
        for stale in stale_values:
            if stale and _contains_number(text, stale):
                failures.append(f"{where}: still quotes the stale value {stale!r}")

    # ORPHEUS-113: milestone values are ours, and no label carries a digit.
    got = [m["value"] for m in (narrative_result.cheat_sheet or {}).get("milestones", [])]
    want = [t.value for t in milestone_targets]
    if got != want:
        failures.append(f"milestone values {got} != computed {want}")
    for i, m in enumerate((narrative_result.cheat_sheet or {}).get("milestones", [])):
        if any(ch.isdigit() for ch in m["label"]):
            failures.append(f"cheat_sheet.milestones[{i}].label carries a digit: {m['label']!r}")

    return failures


# ============================================================
# Main
# ============================================================

async def regenerate(args) -> int:
    supabase = create_client(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
    )
    anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    job_id = _resolve_job_id(supabase, args.job_id)
    ctx = _fetch_context(supabase, job_id)
    job, scores_row = ctx["job"], ctx["scores"]

    zip_data = ZipData.model_validate(ctx["ingested"]["zip_data"])
    xlsx_data = (
        XlsxData.model_validate(ctx["ingested"]["xlsx_data"])
        if ctx["ingested"].get("xlsx_data") else None
    )
    quality_report = DataQualityReport.model_validate(
        ctx["ingested"].get("quality_report") or {}
    )

    old_composite = float(scores_row["total_score"])
    old_band = scores_row["band"]
    old_q = (scores_row.get("forward_brief_data") or {}).get("quantitative") or {}
    old_per_post = old_q.get("avg_impressions_per_post")
    old_milestones = _old_milestones(ctx["narratives"])

    print(f"Job {job_id}")
    print(f"  client        {job['client_id']} "
          f"({ctx['client_row'].get('display_name')})")
    print(f"  created       {job['created_at']}")
    print(f"  stored        {old_composite} / {old_band}")
    print(f"  narratives    {len(ctx['narratives'])} rows "
          f"({', '.join(sorted(r['section'] for r in ctx['narratives']))})")
    print()

    # --- Stage 3, with the stored rubric scores -----------------------
    dim1_scores, dim4_scores = _extract_rubric_scores(scores_row)
    ref_date = _stored_ref_date(job, zip_data)
    print(f"Re-scoring with ref_date {ref_date.isoformat()} "
          f"(rubric scores reused, no rubric call)")

    scoring_output = run_scoring(
        zip_data=zip_data,
        xlsx_data=xlsx_data,
        dim1_rubric_scores=dim1_scores,
        dim4_rubric_scores=dim4_scores,
        ref_date=ref_date,
        photo_present_override=job.get("oidc_photo_present"),
    )
    new_composite = round(scoring_output.scored_dimensions.composite, 2)
    new_per_post = scoring_output.forward_brief_data.quantitative.avg_impressions_per_post

    print(f"  composite     {old_composite} -> {new_composite}")
    print(f"  per-post      {old_per_post} -> {new_per_post}")

    if abs(new_composite - old_composite) > 0.01 and not args.allow_composite_change:
        print()
        print("ABORT: the composite moved. This batch (ORPHEUS-112/113/117) only "
              "touches forward_brief_data and narrative text, so a change here "
              "means something else did too. Investigate, or pass "
              "--allow-composite-change if you know why.")
        return 2

    # --- Stage 4 ------------------------------------------------------
    milestone_targets = build_milestone_targets(scoring_output)
    print()
    print("Computed milestone targets:")
    for t in milestone_targets:
        base = f" (from {t.baseline_display})" if t.baseline_display else ""
        print(f"  {t.value:>10}  {t.label}{base}")
    if old_milestones:
        print("Superseding:")
        for value, label in old_milestones:
            print(f"  {value:>10}  {label}")

    if not args.apply:
        print()
        print("Dry run — nothing written. Re-run with --apply to regenerate "
              "narratives and overwrite the stored rows.")
        return 0

    snapshot_path = _write_snapshot(ctx, Path(args.snapshot_dir))
    print()
    print(f"Snapshot written: {snapshot_path}")
    print("Generating narratives (1 Claude call)...")

    narrative_result = await generate_narratives(
        client=anthropic_client,
        scoring_output=scoring_output,
        questionnaire=ctx["questionnaire"],
        zip_data=zip_data,
        narrative_config=ctx["client_row"]["advisors"].get("narrative_config"),
        quality_report=quality_report,
    )

    _merge_sub_dim_narratives(scoring_output, narrative_result.sub_dimensions)
    _merge_dim_summaries(scoring_output, narrative_result.summaries)
    if narrative_result.cta_present is not None:
        scoring_output.forward_brief_data.qualitative_flags \
            .engagement_invitation.cta_in_about = narrative_result.cta_present

    # --- Verify before writing ---------------------------------------
    stale = [str(old_per_post), f"{float(old_per_post):,.0f}"] if old_per_post else []
    failures = verify(scoring_output, narrative_result, milestone_targets, stale)
    print()
    if failures:
        print(f"VERIFICATION FAILED ({len(failures)} issue(s)) — nothing written:")
        for f in failures:
            print(f"  - {f}")
        print()
        print("The snapshot above is untouched; the stored report is unchanged. "
              "Re-run to get a fresh generation, or investigate the prompt.")
        return 3
    print("Verification passed: no internal units, no stale value, milestone "
          "values match the computed targets, no digits in labels.")

    # --- Write --------------------------------------------------------
    _write_rows(supabase, job_id, scoring_output, narrative_result, ctx["narratives"])
    print()
    print(f"Wrote scores + {len(narrative_result.sections) + 1} narrative rows "
          f"for {job_id}.")
    print(f"Roll back with: python -m backend.scripts.regenerate_report "
          f"--restore {snapshot_path}")
    return 0


def _old_milestones(narratives: list[dict]) -> list[tuple[str, str]]:
    for row in narratives:
        if row.get("section") != "cheat_sheet":
            continue
        try:
            payload = json.loads(row.get("generated_text") or "{}")
        except json.JSONDecodeError:
            return []
        return [
            (m.get("value", ""), m.get("label", ""))
            for m in payload.get("milestones", [])
        ]
    return []


def _write_rows(supabase, job_id, scoring_output, narrative_result, old_rows) -> None:
    """Overwrite scores + narratives, preserving each section's publish state.

    Status and published_at are carried over per section rather than recomputed
    from the advisor's is_individual flag: this job's rows already went through
    whichever path applies, and a regeneration must not silently publish a
    draft under review or unpublish something the client is reading.
    """
    supabase.table("scores").update({
        "dimensions": json.loads(scoring_output.scored_dimensions.model_dump_json()),
        "forward_brief_data": json.loads(
            scoring_output.forward_brief_data.model_dump_json()
        ),
        "scored_at": datetime.utcnow().isoformat(),
    }).eq("job_id", job_id).execute()

    prior = {r["section"]: r for r in old_rows}
    # Fall back to the publish state of whatever the job already had, so a new
    # section (cheat_sheet on a pre-ORPHEUS-60 job) doesn't default to draft
    # on a published report or vice versa.
    default_status = next(
        (r.get("status") for r in old_rows if r.get("status")), "published"
    )
    default_published = next(
        (r.get("published_at") for r in old_rows if r.get("published_at")), None
    )
    now = datetime.utcnow().isoformat()

    supabase.table("narratives").delete().eq("job_id", job_id).execute()

    payloads = dict(narrative_result.sections)
    if narrative_result.cheat_sheet is not None:
        payloads["cheat_sheet"] = json.dumps(narrative_result.cheat_sheet)

    for section, text in payloads.items():
        old = prior.get(section, {})
        row = {
            "job_id": job_id,
            "section": section,
            "generated_text": text,
            "status": old.get("status") or default_status,
            "generated_at": now,
        }
        published_at = old.get("published_at") or (
            default_published if not prior.get(section) else None
        )
        if published_at:
            row["published_at"] = published_at
        # An admin edit is preserved — regenerating the machine text should not
        # silently discard a human's rewrite (ORPHEUS-31's surface).
        if old.get("edited_text"):
            row["edited_text"] = old["edited_text"]
        supabase.table("narratives").insert(row).execute()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate a delivered report in place (ORPHEUS-112/113/117)."
    )
    parser.add_argument("job_id", nargs="?", help="Job id or unique id prefix.")
    parser.add_argument("--apply", action="store_true",
                        help="Write the results. Without this, inspect only.")
    parser.add_argument("--restore", metavar="SNAPSHOT",
                        help="Roll a job back from a snapshot file.")
    parser.add_argument("--snapshot-dir", default=str(REPO_ROOT),
                        help="Where to write the pre-write snapshot.")
    parser.add_argument("--allow-composite-change", action="store_true",
                        help="Proceed even if the composite moves (it should not).")
    args = parser.parse_args()

    _load_env()

    if args.restore:
        supabase = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
        )
        restore(supabase, Path(args.restore))
        return 0

    if not args.job_id:
        parser.error("job_id is required unless --restore is given.")

    return asyncio.run(regenerate(args))


if __name__ == "__main__":
    sys.exit(main())
