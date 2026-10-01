from __future__ import annotations

import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .api import auth_routes, file_routes, judge_routes, organizer_routes
from .config import BACKEND_ROOT, get_settings
from .db import SessionLocal, init_db
from .ingestion.sources.future import REGISTRY as FUTURE_SOURCES
from .models import Organization

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("evidra")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings = get_settings()
    if settings.environment != "test" and settings.auto_seed:
        with SessionLocal() as db:
            empty = db.scalar(select(Organization.id).limit(1)) is None
        if empty:
            from .seed.seed import seed

            log.info("Empty database — seeding demo data (first start takes ~30-60s for OCR)…")
            seed()
    yield


app = FastAPI(title="Evidra API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(organizer_routes.router)
app.include_router(judge_routes.router)
app.include_router(file_routes.router)


@app.get("/api/health")
def health():
    from .services.processing import ingestion_pipeline

    settings = get_settings()
    pipe = ingestion_pipeline()
    return {
        "status": "ok",
        "ai_engine": settings.ai_engine,
        "ai_model": settings.anthropic_model if settings.ai_engine == "anthropic" else None,
        "ai_configured": settings.ai_engine != "anthropic" or bool(settings.anthropic_api_key),
        "ocr_engine": pipe.ocr.name if pipe.ocr.available() else None,
        "slide_rendering": {"pdf": True, "pptx": bool(shutil.which("soffice") or shutil.which("libreoffice")
                                                   or settings.libreoffice_path)},
        "future_sources": {k: v.planned_version for k, v in FUTURE_SOURCES.items()},
    }


# Serve the built frontend (single-process deployment) when present.
_dist = BACKEND_ROOT.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = (_dist / path).resolve()
        if path and candidate.is_file() and Path(_dist.resolve()) in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
