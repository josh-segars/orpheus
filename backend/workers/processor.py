# Background job processor
# Claims pending jobs from Supabase using SELECT ... FOR UPDATE SKIP LOCKED
# Runs the full pipeline: ingestion → scoring → narrative generation
# Updates job state: pending → running → complete (or failed, max 3 retries)

# TODO: implement
