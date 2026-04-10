"""Entry point for: python -m backend.workers"""

import asyncio
import logging

from backend.workers.processor import run_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

if __name__ == "__main__":
    asyncio.run(run_loop())
