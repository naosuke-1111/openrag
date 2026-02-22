"""Watson News REST API route handlers.

Endpoints:
  GET  /api/watson-news/articles                  - article list (paginated)
  GET  /api/watson-news/articles/{id}             - article detail
  POST /api/watson-news/search                    - RAG search (news + Box)
  GET  /api/watson-news/box/files                 - Box file list
  GET  /api/watson-news/box/files/{file_id}       - Box file detail + chunks
  GET  /api/watson-news/trends                    - trend analytics
  GET  /api/watson-news/etl/status                - ETL / scheduler status
  POST /api/watson-news/etl/trigger               - manually trigger ETL
"""

import json

from starlette.requests import Request
from starlette.responses import JSONResponse

from models.watson_news import WatsonNewsSearchRequest
from services.watson_news_service import (
    get_article,
    get_box_file,
    get_etl_status,
    get_trends,
    list_articles,
    list_box_files,
    search_watson_news,
    trigger_etl,
)
from utils.logging_config import get_logger

logger = get_logger(__name__)


def _json(data, status: int = 200) -> JSONResponse:
    return JSONResponse(content=data, status_code=status)


def _error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(content={"error": message}, status_code=status)


# ---------------------------------------------------------------------------
# Article endpoints
# ---------------------------------------------------------------------------

async def get_articles(request: Request) -> JSONResponse:
    """GET /api/watson-news/articles"""
    try:
        params = request.query_params
        page = int(params.get("page", "1"))
        page_size = min(int(params.get("page_size", "20")), 100)
        source_type = params.get("source_type")
        language = params.get("language")

        result = await list_articles(
            page=page,
            page_size=page_size,
            source_type=source_type,
            language=language,
        )
        return _json(result.model_dump())
    except Exception as exc:
        logger.error("Error listing articles", error=str(exc))
        return _error(str(exc), 500)


async def get_article_detail(request: Request) -> JSONResponse:
    """GET /api/watson-news/articles/{id}"""
    try:
        article_id = request.path_params.get("id", "")
        doc = await get_article(article_id)
        if doc is None:
            return _error("Article not found", 404)
        return _json(doc)
    except Exception as exc:
        logger.error("Error fetching article", error=str(exc))
        return _error(str(exc), 500)


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

async def search_articles(request: Request) -> JSONResponse:
    """POST /api/watson-news/search"""
    try:
        body = await request.json()
        search_req = WatsonNewsSearchRequest(**body)
        result = await search_watson_news(search_req)
        return _json(result.model_dump())
    except json.JSONDecodeError:
        return _error("Invalid JSON body", 400)
    except Exception as exc:
        logger.error("Error searching articles", error=str(exc))
        return _error(str(exc), 500)


# ---------------------------------------------------------------------------
# Box file endpoints
# ---------------------------------------------------------------------------

async def get_box_files(request: Request) -> JSONResponse:
    """GET /api/watson-news/box/files"""
    try:
        params = request.query_params
        page = int(params.get("page", "1"))
        page_size = min(int(params.get("page_size", "20")), 100)
        result = await list_box_files(page=page, page_size=page_size)
        return _json(result.model_dump())
    except Exception as exc:
        logger.error("Error listing Box files", error=str(exc))
        return _error(str(exc), 500)


async def get_box_file_detail(request: Request) -> JSONResponse:
    """GET /api/watson-news/box/files/{file_id}"""
    try:
        file_id = request.path_params.get("file_id", "")
        doc = await get_box_file(file_id)
        if doc is None:
            return _error("Box file not found", 404)
        return _json(doc)
    except Exception as exc:
        logger.error("Error fetching Box file", error=str(exc))
        return _error(str(exc), 500)


# ---------------------------------------------------------------------------
# Trends endpoint
# ---------------------------------------------------------------------------

async def get_trend_data(request: Request) -> JSONResponse:
    """GET /api/watson-news/trends"""
    try:
        period = request.query_params.get("period", "7d")
        result = await get_trends(period=period)
        return _json(result.model_dump())
    except Exception as exc:
        logger.error("Error fetching trends", error=str(exc))
        return _error(str(exc), 500)


# ---------------------------------------------------------------------------
# ETL management endpoints
# ---------------------------------------------------------------------------

async def etl_status(request: Request) -> JSONResponse:
    """GET /api/watson-news/etl/status"""
    try:
        status = get_etl_status()
        return _json(status.model_dump())
    except Exception as exc:
        logger.error("Error getting ETL status", error=str(exc))
        return _error(str(exc), 500)


async def etl_trigger(request: Request) -> JSONResponse:
    """POST /api/watson-news/etl/trigger"""
    try:
        result = await trigger_etl()
        return _json({"status": "triggered", "counts": result})
    except Exception as exc:
        logger.error("Error triggering ETL", error=str(exc))
        return _error(str(exc), 500)
