"""Neural Feed REST + SSE route handlers.

Endpoints:
  GET /api/neural-feed/articles/stream   SSE: push new articles in real-time
  GET /api/neural-feed/articles/recent   Recent articles list
  GET /api/neural-feed/kpi               KPI metrics
  GET /api/neural-feed/categories        Topic category counts
  GET /api/neural-feed/tone              Global Tone Index
  GET /api/neural-feed/entities/top      Top entities
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

from opensearchpy import AsyncOpenSearch, NotFoundError
from opensearchpy._async.http_aiohttp import AIOHttpConnection
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

from api.neural_feed.opensearch_queries import (
    CATEGORY_AGGREGATION_QUERY,
    GLOBAL_TONE_QUERY,
    IDX_NEWS_ENRICHED,
    KPI_TODAY_QUERY,
    RECENT_ARTICLES_QUERY,
    TOP_ENTITIES_QUERY,
)
from api.neural_feed.schemas import (
    ArticleItem,
    CategoriesResponse,
    CategoryCount,
    EntityItem,
    KpiMetrics,
    RecentArticlesResponse,
    ToneResponse,
    TopEntitiesResponse,
)
from utils.logging_config import get_logger

logger = get_logger(__name__)

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "")
SSE_POLL_INTERVAL = int(os.getenv("NEURAL_FEED_SSE_INTERVAL", "5"))


def _make_os() -> AsyncOpenSearch:
    return AsyncOpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        connection_class=AIOHttpConnection,
        scheme="https",
        use_ssl=True,
        verify_certs=False,
        ssl_assert_fingerprint=None,
        http_auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
        http_compress=True,
    )


def _hit_to_article(hit: dict) -> ArticleItem:
    src = hit.get("_source", {})
    label = src.get("sentiment_label", "NEUTRAL")
    if label not in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
        label = "NEUTRAL"
    return ArticleItem(
        id=hit.get("_id", src.get("id", "")),
        title=src.get("title", ""),
        domain=src.get("domain", ""),
        source_type=src.get("source_type", "gdelt"),
        sentiment_label=label,
        sentiment_score=float(src.get("sentiment_score", 0.0)),
        topic=src.get("topic", "Other"),
        published=src.get("published", datetime.now(timezone.utc).isoformat()),
    )


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------

async def stream_articles(request: Request) -> StreamingResponse:
    """GET /api/neural-feed/articles/stream — SSE endpoint."""

    async def event_generator():
        os_client = _make_os()
        last_published: str | None = None
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    query: dict = {
                        "size": 5,
                        "sort": [{"published": {"order": "desc"}}],
                        "_source": [
                            "id", "title", "domain", "source_type",
                            "sentiment_label", "sentiment_score", "topic", "published",
                        ],
                    }
                    if last_published:
                        query["query"] = {
                            "range": {"published": {"gt": last_published}}
                        }
                    else:
                        query["query"] = {
                            "range": {"published": {"gte": "now-2m"}}
                        }

                    resp = await os_client.search(
                        index=IDX_NEWS_ENRICHED, body=query
                    )
                    hits = resp.get("hits", {}).get("hits", [])
                    for hit in reversed(hits):
                        article = _hit_to_article(hit)
                        last_published = article.published
                        data = json.dumps(article.model_dump())
                        yield f"event: new_article\ndata: {data}\n\n"

                except Exception as exc:
                    logger.warning("neural-feed SSE query error", error=str(exc))
                    yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

                # heartbeat to keep connection alive
                yield ": heartbeat\n\n"
                await asyncio.sleep(SSE_POLL_INTERVAL)
        finally:
            await os_client.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

async def get_recent_articles(request: Request) -> JSONResponse:
    """GET /api/neural-feed/articles/recent"""
    os_client = _make_os()
    try:
        resp = await os_client.search(
            index=IDX_NEWS_ENRICHED, body=RECENT_ARTICLES_QUERY
        )
        hits = resp.get("hits", {}).get("hits", [])
        articles = [_hit_to_article(h) for h in hits]
        total = resp.get("hits", {}).get("total", {}).get("value", len(articles))
        result = RecentArticlesResponse(articles=articles, total=total)
        return JSONResponse(result.model_dump())
    except Exception as exc:
        logger.warning("neural-feed recent articles error", error=str(exc))
        return JSONResponse({"articles": [], "total": 0})
    finally:
        await os_client.close()


async def get_kpi(request: Request) -> JSONResponse:
    """GET /api/neural-feed/kpi"""
    os_client = _make_os()
    try:
        resp = await os_client.search(
            index=IDX_NEWS_ENRICHED, body=KPI_TODAY_QUERY
        )
        aggs = resp.get("aggregations", {})
        total_today = int(
            aggs.get("total_today", {}).get("value", 0)
        )
        sources = aggs.get("by_source", {}).get("buckets", [])
        active_sources = len([s for s in sources if s.get("doc_count", 0) > 0])

        # Approx throughput: total_today / minutes_since_midnight
        now = datetime.now(timezone.utc)
        minutes_today = now.hour * 60 + now.minute or 1
        throughput = round(total_today / minutes_today, 1)

        metrics = KpiMetrics(
            throughput=throughput,
            total_today=total_today,
            active_sources=max(active_sources, 1),
            connected=True,
            last_updated=now.isoformat(),
        )
        return JSONResponse(metrics.model_dump())
    except Exception as exc:
        logger.warning("neural-feed kpi error", error=str(exc))
        metrics = KpiMetrics(
            throughput=0.0,
            total_today=0,
            active_sources=0,
            connected=False,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )
        return JSONResponse(metrics.model_dump())
    finally:
        await os_client.close()


async def get_categories(request: Request) -> JSONResponse:
    """GET /api/neural-feed/categories"""
    os_client = _make_os()
    try:
        resp = await os_client.search(
            index=IDX_NEWS_ENRICHED, body=CATEGORY_AGGREGATION_QUERY
        )
        buckets = (
            resp.get("aggregations", {}).get("by_topic", {}).get("buckets", [])
        )
        cats = [
            CategoryCount(topic=b["key"], count=b["doc_count"])
            for b in buckets
        ]
        total = sum(c.count for c in cats)
        result = CategoriesResponse(categories=cats, total=total)
        return JSONResponse(result.model_dump())
    except Exception as exc:
        logger.warning("neural-feed categories error", error=str(exc))
        return JSONResponse({"categories": [], "total": 0})
    finally:
        await os_client.close()


async def get_tone(request: Request) -> JSONResponse:
    """GET /api/neural-feed/tone"""
    os_client = _make_os()
    try:
        resp = await os_client.search(
            index=IDX_NEWS_ENRICHED, body=GLOBAL_TONE_QUERY
        )
        aggs = resp.get("aggregations", {})
        avg = aggs.get("avg_sentiment", {}).get("value") or 0.0
        count = int(aggs.get("count", {}).get("value", 0))
        if avg >= 0.3:
            label = "POSITIVE"
        elif avg <= -0.3:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"
        result = ToneResponse(
            average_score=round(float(avg), 3),
            label=label,
            sample_size=count,
        )
        return JSONResponse(result.model_dump())
    except Exception as exc:
        logger.warning("neural-feed tone error", error=str(exc))
        return JSONResponse(
            {"average_score": 0.0, "label": "NEUTRAL", "sample_size": 0}
        )
    finally:
        await os_client.close()


async def get_top_entities(request: Request) -> JSONResponse:
    """GET /api/neural-feed/entities/top"""
    os_client = _make_os()
    try:
        resp = await os_client.search(
            index=IDX_NEWS_ENRICHED, body=TOP_ENTITIES_QUERY
        )
        buckets = (
            resp.get("aggregations", {})
            .get("entity_names", {})
            .get("buckets", [])
        )
        entities = [
            EntityItem(text=b["key"], count=b["doc_count"])
            for b in buckets[:10]
        ]
        result = TopEntitiesResponse(
            entities=entities,
            unique_count=len(buckets),
        )
        return JSONResponse(result.model_dump())
    except Exception as exc:
        logger.warning("neural-feed entities error", error=str(exc))
        return JSONResponse({"entities": [], "unique_count": 0})
    finally:
        await os_client.close()
