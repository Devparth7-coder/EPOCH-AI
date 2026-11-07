"""EPOCH AI — application entrypoint.

Serves the versioned REST API and (when built) the React SPA from the same
origin, so a single free-tier web service hosts the whole product.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import analytics, benchmark, claims, history, research, system
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, log, new_request_id, request_id_ctx
from app.db.session import init_db

configure_logging("DEBUG" if settings.debug else "INFO")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    log.info("startup", extra={"event": "startup", "extra_data": {"mode": settings.runtime_mode}})
    yield


app = FastAPI(
    lifespan=lifespan,
    title="EPOCH AI",
    version="1.0.0",
    description=(
        "Temporal intelligence and evidence verification engine. "
        "Information has a lifespan. EPOCH measures it."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id"],
)

install_error_handlers(app)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or new_request_id()
    token = request_id_ctx.set(request_id)
    started = time.perf_counter()
    content_length = int(request.headers.get("content-length") or 0)
    if content_length > settings.max_input_chars * 4:
        request_id_ctx.reset(token)
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "payload_too_large",
                    "message": f"Request body exceeds the {settings.max_input_chars * 4}-byte limit.",
                    "details": {"content_length": content_length},
                    "request_id": request_id,
                }
            },
        )
    try:
        response = await call_next(request)
    finally:
        duration = round((time.perf_counter() - started) * 1000, 2)
        request_id_ctx.reset(token)
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time-ms"] = str(duration)
    if request.url.path.startswith("/api"):
        log.info(
            "request",
            extra={
                "event": "http_request",
                "duration_ms": duration,
                "extra_data": {"method": request.method, "path": request.url.path, "status": response.status_code},
            },
        )
    return response


for router in (
    claims.router, research.router, history.router,
    analytics.router, system.router, benchmark.router,
):
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/api/v1/meta", tags=["system"])
def meta():
    return {
        "name": "EPOCH AI",
        "tagline": "Information has a lifespan. EPOCH measures it.",
        "version": "1.0.0",
        "runtime_mode": settings.runtime_mode,
        "verdicts": ["VERIFIED", "PARTIALLY_OUTDATED", "OUTDATED", "CONTRADICTED", "UNVERIFIED", "CONFLICTING"],
        "pipeline": [
            "extracting_claims",
            "planning_research",
            "retrieving_evidence",
            "analyzing_temporal",
            "detecting_contradictions",
            "generating_verdicts",
        ],
    }


# --------------------------------------------------------------------------- #
# Static SPA (built frontend). Mounted last so /api always wins.
# --------------------------------------------------------------------------- #
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Not found"}})
else:  # pragma: no cover - dev convenience
    @app.get("/", include_in_schema=False)
    def root():
        return {
            "service": "EPOCH AI API",
            "docs": "/api/docs",
            "note": "Frontend not built. Run `npm run build` in /frontend to serve the SPA.",
        }
