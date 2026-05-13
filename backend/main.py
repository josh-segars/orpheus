"""FastAPI entry point. Wires middleware, routers, and the /health probe.

Importing `backend.config` at module load triggers Settings validation,
so the app refuses to start when required env vars are missing
(ORPHEUS-32). Pydantic raises a ValidationError listing exactly which
vars failed — far easier to debug than the previous KeyError-on-first-
request behavior.
"""

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routers import clients as clients_router
from backend.routers import jobs as jobs_router

load_dotenv()

# Resolve settings up front. Any missing required env var raises here,
# at import time, so uvicorn fails to start with a clear message rather
# than silently starting a broken app.
settings = get_settings()

app = FastAPI(title="Orpheus Social API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router.router)
app.include_router(clients_router.router)
app.include_router(clients_router.accept_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
