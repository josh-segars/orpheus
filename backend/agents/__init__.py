"""Claude-backed pipeline agents (rubric scoring + narrative generation).

The default Anthropic model lives here so the two pipeline calls (rubric
scoring in `rubric.py`, narrative generation in `narrative.py`) and the
consistency harness (`scripts/rubric_consistency.py`) all resolve the same
value. Override per-deploy with the `ANTHROPIC_MODEL` env var without a code
change. Read at import time (function-default-friendly) — the worker reads
its env via os.environ directly (see config.py), so this matches that path.

ORPHEUS-90 (2026-06-15): bumped from `claude-sonnet-4-20250514` (the original
May 2025 Sonnet 4 snapshot) to `claude-sonnet-4-6`. Any model swap invalidates
the ORPHEUS-75 temperature-0 determinism result — re-run the consistency
harness and review band placement with Andrew before trusting new scores.
"""

import os

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
