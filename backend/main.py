"""FastAPI entry point. Wires middleware, routers, and the /health probe."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import jobs as jobs_router

load_dotenv()

app = FastAPI(title="Orpheus Social API")

# CORS. Full allowlist + env validation lands in ORPHEUS-32; for now we read
# a comma-separated FRONTEND_ORIGINS and fall back to the Vite dev default.
_raw_origins = os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173")
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
