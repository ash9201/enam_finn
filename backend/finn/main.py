from datetime import datetime, timezone
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finn import __version__
from finn.config import configuration_status, load_local_env


load_local_env()
app = FastAPI(title="FINN foundation", version=__version__)
origins = [origin.strip() for origin in os.getenv("FINN_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
if os.getenv("FINN_ENV", "development") == "development":
    origins = list(dict.fromkeys(origins + ["http://localhost:5173", "http://127.0.0.1:5173"]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)


@app.get("/health/live")
def live() -> dict:
    # Liveness must not depend on a third-party service or wake-up-time model call.
    return {"status": "ok", "service": "finn-api", "version": __version__, "milestone": 0}


@app.get("/health/ready")
def ready() -> dict:
    return {
        "status": "foundation_only",
        "configuration": configuration_status(),
        "dependencies_verified": False,
        "note": "Configuration is not verification. Run the private feasibility CLI; investor workflows are gated.",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
