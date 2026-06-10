"""ORPHEUS-75: rubric scoring inter-rater consistency experiment.

Measures run-to-run variance of the Dim 1 / Dim 4 Claude rubric calls on
fixed inputs (the preserved demo jobs' ingested data), and whether
temperature=0 eliminates it. Dims 2/3 are deterministic, so all composite
spread observed here is attributable to the rubric calls.

Run from the repo root on a machine with backend deps + env (NOT the
Claude sandbox — PyPI and API egress are blocked there):

    python -m backend.scripts.rubric_consistency

Requires SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY — read from
the environment, falling back to backend/.env then .env.

Output: a printed report plus a full raw-results JSON file
(rubric_consistency_results_<timestamp>.json, untracked) for the
Plane writeup.

Default design (locked with Josh 2026-06-10): N=10 runs per profile per
arm, two arms (production default temperature vs. temperature=0), the two
preserved post-68 profiles. ~80 Claude calls, a few minutes, ~$1-2.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from anthropic import Anthropic  # noqa: E402
from supabase import create_client  # noqa: E402

from backend.agents.rubric import score_dimension_1, score_dimension_4  # noqa: E402
from backend.ingestion.types import XlsxData, ZipData  # noqa: E402
from backend.scoring.engine import run_scoring  # noqa: E402

# The two preserved post-ORPHEUS-68 demo jobs (cloud Supabase).
DEFAULT_JOBS = {
    "josh-27-untuned": "e11eff50-29bf-4655-8c13-85c502943d07",
    "andrew-75.75-tuned": "710b14be-c1f4-4d97-8542-c512a031a54f",
}

PRODUCTION_MODEL = "claude-sonnet-4-20250514"

REQUIRED_ENV = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "ANTHROPIC_API_KEY")


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


def _fetch_ingested(supabase, job_id: str) -> tuple[ZipData, XlsxData | None]:
    res = (
        supabase.table("ingested_data")
        .select("zip_data,xlsx_data")
        .eq("job_id", job_id)
        .single()
        .execute()
    )
    row = res.data
    zip_data = ZipData.model_validate(row["zip_data"])
    xlsx_data = XlsxData.model_validate(row["xlsx_data"]) if row.get("xlsx_data") else None
    return zip_data, xlsx_data


async def _score_with_retry(fn, client, zip_data, model, temperature, attempts=3):
    last_err = None
    for _ in range(attempts):
        try:
            return await fn(client, zip_data, model, temperature)
        except (ValueError, json.JSONDecodeError) as err:  # parse failures only
            last_err = err
    raise RuntimeError(f"Rubric call failed after {attempts} attempts: {last_err}")


async def run_experiment(args) -> dict:
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    anthropic = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    ref_date = date.today()

    # "api-default" (temperature param omitted) was production behavior
    # before ORPHEUS-75 shipped temperature=0 as the rubric default.
    arms: list[tuple[str, float | None]] = [("api-default", None)]
    if not args.skip_temp0:
        arms.append(("temperature-0", 0.0))

    results = {
        "experiment": "ORPHEUS-75 rubric consistency",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "runs_per_arm": args.runs,
        "ref_date": ref_date.isoformat(),
        "profiles": {},
    }

    total = len(DEFAULT_JOBS) * len(arms) * args.runs
    done = 0

    for label, job_id in DEFAULT_JOBS.items():
        print(f"\nFetching ingested data for {label} (job {job_id[:8]})...")
        zip_data, xlsx_data = _fetch_ingested(supabase, job_id)
        profile_block = {"job_id": job_id, "arms": {}}

        for arm_name, temperature in arms:
            runs = []
            for i in range(args.runs):
                dim1 = await _score_with_retry(
                    score_dimension_1, anthropic, zip_data, args.model, temperature)
                dim4 = await _score_with_retry(
                    score_dimension_4, anthropic, zip_data, args.model, temperature)
                out = run_scoring(zip_data, xlsx_data, dim1, dim4, ref_date=ref_date)
                sd = out.scored_dimensions
                runs.append({
                    "dim1_scores": dim1,
                    "dim4_scores": dim4,
                    "composite": sd.composite,
                    "band": sd.band.value if hasattr(sd.band, "value") else str(sd.band),
                })
                done += 1
                print(f"  [{done}/{total}] {label} / {arm_name} run {i + 1}: "
                      f"composite {sd.composite} ({runs[-1]['band']})")
            profile_block["arms"][arm_name] = {"temperature": temperature, "runs": runs}

        results["profiles"][label] = profile_block

    results["finished_at"] = datetime.now().isoformat(timespec="seconds")
    return results


def _summarize(results: dict) -> str:
    lines = ["", "=" * 72, "ORPHEUS-75 RUBRIC CONSISTENCY — SUMMARY", "=" * 72]
    lines.append(f"Model: {results['model']}   Runs/arm: {results['runs_per_arm']}   "
                 f"Ref date: {results['ref_date']}")

    for label, profile in results["profiles"].items():
        lines.append(f"\n--- Profile: {label} (job {profile['job_id'][:8]}) ---")
        for arm_name, arm in profile["arms"].items():
            runs = arm["runs"]
            composites = [r["composite"] for r in runs]
            bands = Counter(r["band"] for r in runs)
            lines.append(f"\n  Arm: {arm_name} (temperature="
                         f"{'API default' if arm['temperature'] is None else arm['temperature']})")
            lines.append(f"    Composite: min {min(composites)}  max {max(composites)}  "
                         f"mean {statistics.mean(composites):.2f}  "
                         f"stdev {statistics.pstdev(composites):.2f}  "
                         f"range {max(composites) - min(composites):.2f}")
            lines.append(f"    Bands: {dict(bands)}"
                         + ("   << BAND-CROSSING" if len(bands) > 1 else ""))
            # Per-sub-dimension spread
            for dim_key in ("dim1_scores", "dim4_scores"):
                for sub in runs[0][dim_key]:
                    vals = [r[dim_key][sub] for r in runs]
                    spread = Counter(vals)
                    flag = "" if len(spread) == 1 else "  << VARIES"
                    lines.append(f"    {sub}: {dict(sorted(spread.items()))}{flag}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", type=int, default=10, help="runs per profile per arm")
    parser.add_argument("--model", default=PRODUCTION_MODEL)
    parser.add_argument("--skip-temp0", action="store_true",
                        help="baseline arm only (skip the temperature=0 arm)")
    parser.add_argument("--out", default=None, help="results JSON path")
    args = parser.parse_args()

    _load_env()
    results = asyncio.run(run_experiment(args))

    out_path = Path(args.out) if args.out else REPO_ROOT / (
        f"rubric_consistency_results_{datetime.now():%Y-%m-%d_%H%M%S}.json")
    out_path.write_text(json.dumps(results, indent=2))

    print(_summarize(results))
    print(f"Full raw results: {out_path}")


if __name__ == "__main__":
    main()
