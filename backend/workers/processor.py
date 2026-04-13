"""Background job processor — runs the full analysis pipeline.

Claims pending jobs from Supabase using SELECT ... FOR UPDATE SKIP LOCKED,
then runs the 4-stage pipeline:

  1. Ingestion    — parse LinkedIn ZIP + XLSX into structured data
  2. Rubric       — Claude applies Dim 1 + Dim 4 rubrics → integer scores
  3. Scoring      — deterministic computation of all dimensions + Forward Brief
  4. Narrative    — Claude generates dimension narratives + Forward Brief text

Updates job state: pending → running → complete (or failed, max 3 retries).

Run as: python -m backend.workers
"""

import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, date

from anthropic import Anthropic

from backend.ingestion.types import ZipData, XlsxData
from backend.ingestion.zip_parser import parse_zip
from backend.ingestion.xlsx_parser import parse_xlsx
from backend.scoring.engine import run_scoring
from backend.scoring.config import build_config_snapshot
from backend.agents.rubric import score_rubrics
from backend.agents.narrative import generate_narratives
from backend.models.scoring import ScoringStageOutput
from backend.models.quality import DataQualityReport

logger = logging.getLogger("orpheus.worker")


# ============================================================
# Supabase helpers
# ============================================================

def _get_supabase_client():
    """Create a Supabase client using the service role key.

    The worker uses the service role (not user-scoped) because it runs
    outside of any user's auth context. RLS is bypassed.
    """
    try:
        from supabase import create_client
    except ImportError:
        raise RuntimeError(
            "supabase-py is required for the worker. "
            "Install with: pip install supabase"
        )

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _get_anthropic_client():
    """Create an Anthropic client from environment."""
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# ============================================================
# Job claiming — optimistic locking
# ============================================================

async def claim_job(supabase) -> dict | None:
    """Claim the next pending job using optimistic locking.

    Uses SELECT ... FOR UPDATE SKIP LOCKED to prevent duplicate claims
    when multiple workers are running. Returns the job row or None.
    """
    # Supabase doesn't support FOR UPDATE SKIP LOCKED via the REST API,
    # so we use an RPC call to a PostgreSQL function.
    result = supabase.rpc("claim_next_job").execute()

    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


async def update_job_status(
    supabase,
    job_id: str,
    status: str,
    error_message: str | None = None,
):
    """Update a job's status in the database."""
    update = {"status": status}
    if status == "running":
        update["started_at"] = datetime.utcnow().isoformat()
    elif status == "complete":
        update["completed_at"] = datetime.utcnow().isoformat()
    elif status == "failed":
        update["error_message"] = error_message
        update["completed_at"] = datetime.utcnow().isoformat()

    supabase.table("jobs").update(update).eq("id", job_id).execute()


# ============================================================
# Pipeline stages
# ============================================================

async def stage_ingestion(
    supabase,
    job_id: str,
    client_id: str,
) -> tuple[ZipData, XlsxData | None, DataQualityReport]:
    """Stage 1: Parse LinkedIn data files into structured types.

    Reads raw file data from storage, parses ZIP and XLSX,
    saves parsed data and quality report to the ingested_data table.

    Returns (zip_data, xlsx_data, quality_report). xlsx_data may be None
    if the client didn't upload an analytics export.
    """
    logger.info(f"[{job_id}] Stage 1: Ingestion")

    # Fetch uploaded files from Supabase storage
    # The upload path convention is: {client_id}/{job_id}/archive.zip
    # and optionally: {client_id}/{job_id}/analytics.xlsx
    zip_bytes = supabase.storage.from_("uploads").download(
        f"{client_id}/{job_id}/archive.zip"
    )
    zip_data, quality_report = parse_zip(zip_bytes)

    xlsx_data = None
    try:
        xlsx_bytes = supabase.storage.from_("uploads").download(
            f"{client_id}/{job_id}/analytics.xlsx"
        )
        xlsx_data = parse_xlsx(xlsx_bytes)
        logger.info(
            f"[{job_id}] XLSX parsed — {len(xlsx_data.engagement)} engagement days, "
            f"{xlsx_data.followers.total_followers} followers"
        )
    except Exception as e:
        if "not found" in str(e).lower() or "400" in str(e):
            logger.info(f"[{job_id}] No analytics XLSX uploaded — Forward Brief will be partial")
        else:
            logger.warning(f"[{job_id}] XLSX parse failed: {e} — Forward Brief will be partial")

    # Log quality report summary
    summary = quality_report.summary()
    if quality_report.has_critical:
        logger.warning(f"[{job_id}] Quality report: {summary}")
    elif quality_report.has_warnings:
        logger.info(f"[{job_id}] Quality report: {summary}")
    else:
        logger.info(f"[{job_id}] Quality report: {summary}")

    # Save parsed data + quality report to ingested_data table
    # Use upsert so retries don't crash on duplicate job_id
    supabase.table("ingested_data").upsert({
        "job_id": job_id,
        "zip_data": zip_data.model_dump(),
        "xlsx_data": xlsx_data.model_dump() if xlsx_data else None,
        "quality_report": quality_report.model_dump(),
        "ingested_at": datetime.utcnow().isoformat(),
    }, on_conflict="job_id").execute()

    return zip_data, xlsx_data, quality_report


async def stage_rubric_scoring(
    anthropic_client: Anthropic,
    zip_data: ZipData,
    job_id: str,
) -> tuple[dict[str, int], dict[str, int]]:
    """Stage 2: Apply Claude rubric scoring for Dimensions 1 and 4.

    Returns (dim1_scores, dim4_scores) — each a dict mapping
    sub-dimension names to integer scores (1-5).
    """
    logger.info(f"[{job_id}] Stage 2: Rubric scoring (Dim 1 + Dim 4)")

    dim1_scores, dim4_scores = await score_rubrics(anthropic_client, zip_data)

    logger.info(f"[{job_id}] Rubric scores — Dim 1: {dim1_scores}, Dim 4: {dim4_scores}")
    return dim1_scores, dim4_scores


async def stage_scoring(
    zip_data: ZipData,
    xlsx_data: XlsxData | None,
    dim1_scores: dict[str, int],
    dim4_scores: dict[str, int],
    job_id: str,
    supabase,
) -> ScoringStageOutput:
    """Stage 3: Deterministic scoring — compute all dimensions + Forward Brief.

    Combines rubric scores (Dim 1, 4) with quantitative band lookups (Dim 2, 3).
    Computes composite score, band assignment, and Forward Brief data.
    Saves results to the scores table and config_snapshot to the jobs table.
    """
    logger.info(f"[{job_id}] Stage 3: Deterministic scoring")

    result = run_scoring(
        zip_data=zip_data,
        xlsx_data=xlsx_data,
        dim1_rubric_scores=dim1_scores,
        dim4_rubric_scores=dim4_scores,
    )

    sd = result.scored_dimensions
    logger.info(
        f"[{job_id}] Score: {sd.composite:.1f} / 100 — {sd.band.value}"
    )

    # Save scores to database (upsert for retry safety)
    supabase.table("scores").upsert({
        "job_id": job_id,
        "total_score": sd.composite,
        "band": sd.band.value,
        "dimensions": json.loads(sd.model_dump_json()),
        "forward_brief_data": json.loads(result.forward_brief_data.model_dump_json()),
        "scored_at": datetime.utcnow().isoformat(),
    }, on_conflict="job_id").execute()

    # Save config snapshot to the job for reproducibility
    snapshot = build_config_snapshot()
    supabase.table("jobs").update({
        "config_snapshot": snapshot,
    }).eq("id", job_id).execute()

    return result


async def stage_narrative_generation(
    anthropic_client: Anthropic,
    scoring_output: ScoringStageOutput,
    questionnaire: dict,
    narrative_config: dict | None,
    quality_report: DataQualityReport,
    job_id: str,
    supabase,
    is_advisory: bool = True,
) -> dict[str, str]:
    """Stage 4: Claude generates dimension narratives and Forward Brief.

    Saves each section as a row in the narratives table.
    Advisory clients get status='draft'; self-serve get status='published'.
    Quality report is passed so Claude can acknowledge data limitations.
    """
    logger.info(f"[{job_id}] Stage 4: Narrative generation")

    sections = await generate_narratives(
        client=anthropic_client,
        scoring_output=scoring_output,
        questionnaire=questionnaire,
        narrative_config=narrative_config,
        quality_report=quality_report,
    )

    status = "draft" if is_advisory else "published"
    now = datetime.utcnow().isoformat()

    # Clear any narratives from a previous attempt before inserting
    supabase.table("narratives").delete().eq("job_id", job_id).execute()

    for section_name, narrative_text in sections.items():
        row = {
            "job_id": job_id,
            "section": section_name,
            "generated_text": narrative_text,
            "status": status,
            "generated_at": now,
        }
        if status == "published":
            row["published_at"] = now

        supabase.table("narratives").insert(row).execute()

    logger.info(
        f"[{job_id}] Generated {len(sections)} narrative sections (status={status})"
    )
    return sections


# ============================================================
# Full pipeline orchestrator
# ============================================================

async def run_pipeline(supabase, anthropic_client: Anthropic, job: dict):
    """Run the complete 4-stage analysis pipeline for a single job.

    Args:
        supabase: Supabase service-role client.
        anthropic_client: Anthropic API client.
        job: The claimed job row from the database.
    """
    job_id = job["id"]
    client_id = job["client_id"]

    logger.info(f"[{job_id}] Pipeline started for client {client_id}")

    # Fetch client info (needed for advisor config and advisory/self-serve distinction)
    client_row = (
        supabase.table("clients")
        .select("*, advisors!inner(is_individual, narrative_config)")
        .eq("id", client_id)
        .single()
        .execute()
    ).data

    is_advisory = not client_row["advisors"]["is_individual"]
    narrative_config = client_row["advisors"].get("narrative_config")

    # Fetch questionnaire answers
    q_row = (
        supabase.table("questionnaire_responses")
        .select("responses")
        .eq("client_id", client_id)
        .single()
        .execute()
    ).data
    questionnaire = q_row["responses"] if q_row else {}

    # Stage 1: Ingestion
    zip_data, xlsx_data, quality_report = await stage_ingestion(
        supabase, job_id, client_id
    )

    # Stage 2: Rubric scoring (Claude)
    dim1_scores, dim4_scores = await stage_rubric_scoring(
        anthropic_client, zip_data, job_id
    )

    # Stage 3: Deterministic scoring
    scoring_output = await stage_scoring(
        zip_data, xlsx_data, dim1_scores, dim4_scores, job_id, supabase
    )

    # Stage 4: Narrative generation (Claude)
    await stage_narrative_generation(
        anthropic_client, scoring_output, questionnaire,
        narrative_config, quality_report, job_id, supabase, is_advisory
    )

    # Mark job complete
    await update_job_status(supabase, job_id, "complete")

    # Create the report record
    branding = {
        "practice_name": client_row["advisors"].get("practice_name"),
        "logo_url": client_row["advisors"].get("logo_url"),
        "color_primary": client_row["advisors"].get("color_primary"),
        "color_accent": client_row["advisors"].get("color_accent"),
    }
    supabase.table("reports").upsert({
        "job_id": job_id,
        "client_id": client_id,
        "report_type": "advisory" if is_advisory else "self_serve",
        "branding_snapshot": branding,
        "published_at": datetime.utcnow().isoformat() if not is_advisory else None,
    }, on_conflict="job_id").execute()

    sd = scoring_output.scored_dimensions
    logger.info(
        f"[{job_id}] Pipeline complete — {sd.composite:.1f} ({sd.band.value})"
    )


# ============================================================
# Job processing loop
# ============================================================

MAX_RETRIES = 3
POLL_INTERVAL_SECONDS = 5


async def process_one(supabase, anthropic_client: Anthropic) -> bool:
    """Claim and process a single job. Returns True if a job was processed."""
    job = await claim_job(supabase)
    if not job:
        return False

    job_id = job["id"]
    attempt = job.get("attempt_count", 0) + 1

    try:
        # claim_job() already set status='running' and started_at via RPC.
        # Just update the attempt counter.
        supabase.table("jobs").update(
            {"attempt_count": attempt}
        ).eq("id", job_id).execute()

        await run_pipeline(supabase, anthropic_client, job)
        return True

    except Exception as e:
        error_msg = f"Attempt {attempt}/{MAX_RETRIES}: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"[{job_id}] {error_msg}")

        if attempt >= MAX_RETRIES:
            await update_job_status(supabase, job_id, "failed", error_msg)
            logger.error(f"[{job_id}] Max retries reached — marking as failed")
        else:
            # Reset to pending for retry
            supabase.table("jobs").update({
                "status": "pending",
                "error_message": error_msg,
            }).eq("id", job_id).execute()
            logger.info(f"[{job_id}] Reset to pending for retry ({attempt}/{MAX_RETRIES})")

        return True


async def run_loop():
    """Main worker loop — poll for jobs and process them."""
    logger.info("Worker starting — polling for jobs")

    supabase = _get_supabase_client()
    anthropic_client = _get_anthropic_client()

    while True:
        try:
            processed = await process_one(supabase, anthropic_client)
            if not processed:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Worker shutting down")
            break
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
