from datetime import datetime, timezone
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finn import __version__
from finn.config import configuration_status, load_local_env
from finn.api import router
from finn import embeddings


load_local_env()


@asynccontextmanager
async def lifespan(app):
    yield
    if embeddings.enabled():
        embeddings.stop_background()


app = FastAPI(title="FINN API", version=__version__, lifespan=lifespan)
origins = [
    origin.strip()
    for origin in os.getenv("FINN_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
if os.getenv("FINN_ENV", "development") == "development":
    origins = list(dict.fromkeys(origins + ["http://localhost:5173", "http://127.0.0.1:5173"]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)


@app.get("/health/live")
def live() -> dict:
    # Liveness must not depend on a third-party service or wake-up-time model call.
    return {
        "status": "ok",
        "service": "finn-api",
        "version": __version__,
        "milestone": 2,
        "revision": os.getenv("RENDER_GIT_COMMIT"),
    }


@app.get("/health/ready")
def ready() -> dict:
    return {
        "status": "configuration_only",
        "configuration": configuration_status(),
        "dependencies_verified": False,
        "note": "Configuration is not live dependency verification. Run the private feasibility CLI for detailed checks.",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
