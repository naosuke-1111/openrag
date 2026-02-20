"""
Box RAG Service — main application entry point.

Standalone FastAPI service (no direct dependency on OpenRAG source).
Loosely coupled: communicates with OpenSearch directly for Box-specific indexes.

Endpoints:
  POST /shared-link/resolve   → Resolve Box shared link
  POST /ingest/selection      → Start ingestion job
  GET  /ingest/jobs/{job_id}  → Poll job status
  GET  /documents             → List ingested documents
  DELETE /documents/{id}      → Delete document
  POST /search                → RAG search
  GET  /health                → Health check
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config as cfg
import opensearch_store as os_store
from api.shared_link import router as shared_link_router
from api.ingest import router as ingest_router
from api.search import router as search_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("Box RAG service starting up")
    logger.info("LLM model:       %s", cfg.WATSONX_LLM_MODEL)
    logger.info("Embedding model: %s (dim=%d)", cfg.WATSONX_EMBED_MODEL, cfg.EMBED_DIM)
    logger.info("OpenSearch:      %s:%d", cfg.OPENSEARCH_HOST, cfg.OPENSEARCH_PORT)
    logger.info("Docling serve:   %s", cfg.DOCLING_SERVE_URL or "(library mode)")

    # Ensure OpenSearch indexes exist
    try:
        await os_store.store.ensure_indexes()
        logger.info("OpenSearch indexes ready")
    except Exception as exc:
        logger.warning("Could not ensure OpenSearch indexes on startup: %s", exc)

    yield

    logger.info("Box RAG service shutting down")
    await os_store.store.close()


app = FastAPI(
    title="Box RAG Service",
    description=(
        "RAG pipeline for Box shared links using OpenSearch + watsonx.ai.\n\n"
        "Loosely coupled with OpenRAG — uses OpenSearch directly for Box-specific indexes."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (allow all origins for internal network use; restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ──────────────────────────────────────────────────────────────
app.include_router(shared_link_router, tags=["Box"])
app.include_router(ingest_router, tags=["Ingestion"])
app.include_router(search_router, tags=["Search"])


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint."""
    checks = {}

    # Check OpenSearch
    try:
        cl = os_store.store.client
        info = await cl.info()
        checks["opensearch"] = "ok"
    except Exception as exc:
        checks["opensearch"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


# ── Static Frontend ───────────────────────────────────────────────────────────
_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend_dir / "static")), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(str(_frontend_dir / "index.html"))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=cfg.BOX_RAG_PORT,
        reload=False,
        log_level=cfg.LOG_LEVEL.lower(),
    )
