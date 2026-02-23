"""Watson News service: search, article retrieval, trend analytics, and ETL triggers."""

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from opensearchpy import AsyncOpenSearch, NotFoundError
from opensearchpy._async.http_aiohttp import AIOHttpConnection

from connectors.watson_news.enricher import get_watsonx_client
from connectors.watson_news.etl_pipeline import (
    IDX_BOX_ENRICHED,
    IDX_BOX_RAW,
    IDX_NEWS_ENRICHED,
    IDX_NEWS_RAW,
    run_full_pipeline,
)
from models.watson_news import (
    ArticleListResponse,
    BoxFileListResponse,
    ETLStatusResponse,
    SearchResultItem,
    TrendDataPoint,
    TrendResponse,
    WatsonNewsSearchRequest,
    WatsonNewsSearchResponse,
)
from utils.logging_config import get_logger

logger = get_logger(__name__)

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "")

# Dimension of granite-embedding-107m-multilingual
_EMBED_DIM = 384

_etl_status: dict[str, Any] = {
    "gdelt_last_run": None,
    "ibm_crawl_last_run": None,
    "box_last_run": None,
    "scheduler_running": False,
}


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


# ---------------------------------------------------------------------------
# OpenSearch index management
# ---------------------------------------------------------------------------

_NEWS_ENRICHED_MAPPING = {
    "settings": {
        "index": {"knn": True},
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "vector": {
                "type": "knn_vector",
                "dimension": _EMBED_DIM,
                "method": {
                    "name": "disk_ann",
                    "engine": "jvector",
                    "space_type": "l2",
                    "parameters": {"ef_construction": 100, "m": 16},
                },
            },
            "source_type": {"type": "keyword"},
            "language": {"type": "keyword"},
            "published": {"type": "date"},
            "crawled_at": {"type": "date"},
            "sentiment_label": {"type": "keyword"},
            "topic": {"type": "keyword"},
            "entities": {"type": "nested"},
            "url": {"type": "keyword"},
            "title": {"type": "text"},
            "clean_body": {"type": "text"},
            "summary": {"type": "text"},
        }
    },
}

_BOX_ENRICHED_MAPPING = {
    "settings": {
        "index": {"knn": True},
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "vector": {
                "type": "knn_vector",
                "dimension": _EMBED_DIM,
                "method": {
                    "name": "disk_ann",
                    "engine": "jvector",
                    "space_type": "l2",
                    "parameters": {"ef_construction": 100, "m": 16},
                },
            },
            "source_type": {"type": "keyword"},
            "box_file_id": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "filename": {"type": "keyword"},
            "clean_text": {"type": "text"},
        }
    },
}

_SIMPLE_MAPPINGS = {
    IDX_NEWS_RAW: {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "url": {"type": "keyword"},
                "source_type": {"type": "keyword"},
                "crawled_at": {"type": "date"},
                "language": {"type": "keyword"},
            }
        },
    },
    IDX_BOX_RAW: {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "box_file_id": {"type": "keyword"},
                "source_type": {"type": "keyword"},
                "updated_at": {"type": "date"},
            }
        },
    },
}


async def ensure_indices() -> None:
    """Create Watson News OpenSearch indices if they don't exist."""
    os_client = _make_os()
    try:
        index_mappings = {
            **_SIMPLE_MAPPINGS,
            IDX_NEWS_ENRICHED: _NEWS_ENRICHED_MAPPING,
            IDX_BOX_ENRICHED: _BOX_ENRICHED_MAPPING,
            "watson_news_clean": {
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "url": {"type": "keyword"},
                        "source_type": {"type": "keyword"},
                        "language": {"type": "keyword"},
                        "published": {"type": "date"},
                    }
                },
            },
        }
        for idx, body in index_mappings.items():
            exists = await os_client.indices.exists(index=idx)
            if not exists:
                await os_client.indices.create(index=idx, body=body)
                logger.info("Created OpenSearch index", index=idx)
            else:
                logger.debug("OpenSearch index already exists", index=idx)
    except Exception as exc:
        logger.error("Failed to ensure Watson News indices", error=str(exc))
    finally:
        await os_client.close()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

async def search_watson_news(req: WatsonNewsSearchRequest) -> WatsonNewsSearchResponse:
    """Perform hybrid KNN + keyword search across Watson News and Box indices."""
    os_client = _make_os()
    client = get_watsonx_client()

    try:
        # Embed the query
        vectors = await client.embed([req.query])
        query_vector = vectors[0] if vectors else []

        # Determine which indices to search
        indices = []
        if any(st in req.source_types for st in ("gdelt", "ibm_crawl")):
            indices.append(IDX_NEWS_ENRICHED)
        if "box" in req.source_types:
            indices.append(IDX_BOX_ENRICHED)

        if not indices:
            return WatsonNewsSearchResponse(query=req.query, total=0, results=[])

        # Build filters
        filter_clauses: list[dict] = []
        if req.source_types:
            filter_clauses.append({"terms": {"source_type": req.source_types}})
        if req.language:
            filter_clauses.append({"term": {"language": req.language}})
        if req.sentiment:
            filter_clauses.append({"term": {"sentiment_label": req.sentiment}})
        if req.topic:
            filter_clauses.append({"term": {"topic": req.topic}})
        if req.date_from or req.date_to:
            date_range: dict = {}
            if req.date_from:
                date_range["gte"] = req.date_from
            if req.date_to:
                date_range["lte"] = req.date_to
            filter_clauses.append({"range": {"published": date_range}})

        knn_query: dict[str, Any] = {
            "knn": {
                "vector": {
                    "vector": query_vector,
                    "k": req.top_k,
                }
            }
        }

        if filter_clauses:
            knn_query["knn"]["vector"]["filter"] = {"bool": {"must": filter_clauses}}

        os_body: dict = {
            "query": knn_query,
            "size": req.top_k,
        }

        resp = await os_client.search(
            index=",".join(indices),
            body=os_body,
        )

        hits = resp["hits"]["hits"]
        total = resp["hits"]["total"]["value"]

        results = [
            SearchResultItem(
                id=hit["_id"],
                source_type=hit["_source"].get("source_type", ""),
                score=hit["_score"] or 0.0,
                url=hit["_source"].get("url", ""),
                title=hit["_source"].get("title", ""),
                summary=hit["_source"].get("summary", ""),
                sentiment_label=hit["_source"].get("sentiment_label", ""),
                topic=hit["_source"].get("topic", ""),
                language=hit["_source"].get("language", ""),
                published=hit["_source"].get("published", ""),
                filename=hit["_source"].get("filename", ""),
            )
            for hit in hits
        ]

        return WatsonNewsSearchResponse(query=req.query, total=total, results=results)
    finally:
        await os_client.close()


# ---------------------------------------------------------------------------
# Article list / detail
# ---------------------------------------------------------------------------

async def list_articles(
    page: int = 1,
    page_size: int = 20,
    source_type: str | None = None,
    language: str | None = None,
) -> ArticleListResponse:
    os_client = _make_os()
    try:
        filters: list[dict] = []
        if source_type:
            filters.append({"term": {"source_type": source_type}})
        if language:
            filters.append({"term": {"language": language}})

        query = {"bool": {"must": filters}} if filters else {"match_all": {}}
        from_ = (page - 1) * page_size

        resp = await os_client.search(
            index=IDX_NEWS_ENRICHED,
            body={
                "query": query,
                "from": from_,
                "size": page_size,
                "sort": [{"published": {"order": "desc"}}],
                "_source": {
                    "excludes": ["vector", "clean_body"]
                },
            },
        )
        hits = resp["hits"]["hits"]
        total = resp["hits"]["total"]["value"]
        return ArticleListResponse(
            total=total,
            page=page,
            page_size=page_size,
            articles=[{"id": h["_id"], **h["_source"]} for h in hits],
        )
    finally:
        await os_client.close()


async def get_article(article_id: str) -> dict[str, Any] | None:
    os_client = _make_os()
    try:
        resp = await os_client.get(index=IDX_NEWS_ENRICHED, id=article_id)
        doc = resp["_source"]
        doc["id"] = resp["_id"]
        # Strip large vector from API response
        doc.pop("vector", None)
        return doc
    except NotFoundError:
        return None
    finally:
        await os_client.close()


# ---------------------------------------------------------------------------
# Box files
# ---------------------------------------------------------------------------

async def list_box_files(page: int = 1, page_size: int = 20) -> BoxFileListResponse:
    os_client = _make_os()
    try:
        from_ = (page - 1) * page_size
        resp = await os_client.search(
            index=IDX_BOX_RAW,
            body={
                "query": {"match_all": {}},
                "from": from_,
                "size": page_size,
                "sort": [{"updated_at": {"order": "desc"}}],
            },
        )
        hits = resp["hits"]["hits"]
        total = resp["hits"]["total"]["value"]
        return BoxFileListResponse(
            total=total,
            files=[{"id": h["_id"], **h["_source"]} for h in hits],
        )
    finally:
        await os_client.close()


async def get_box_file(file_id: str) -> dict[str, Any] | None:
    os_client = _make_os()
    try:
        # File metadata
        file_resp = await os_client.get(index=IDX_BOX_RAW, id=file_id)
        file_data: dict = {"id": file_resp["_id"], **file_resp["_source"]}

        # Chunks
        chunks_resp = await os_client.search(
            index=IDX_BOX_ENRICHED,
            body={
                "query": {"term": {"box_file_id": file_data.get("box_file_id", file_id)}},
                "sort": [{"chunk_index": {"order": "asc"}}],
                "size": 200,
                "_source": {"excludes": ["vector"]},
            },
        )
        file_data["chunks"] = [
            {"id": h["_id"], **h["_source"]}
            for h in chunks_resp["hits"]["hits"]
        ]
        return file_data
    except NotFoundError:
        return None
    finally:
        await os_client.close()


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

async def get_trends(period: str = "7d") -> TrendResponse:
    """Return daily article counts and average sentiment for the last *period*."""
    os_client = _make_os()
    try:
        resp = await os_client.search(
            index=IDX_NEWS_ENRICHED,
            body={
                "size": 0,
                "aggs": {
                    "by_day": {
                        "date_histogram": {
                            "field": "published",
                            "calendar_interval": "day",
                        },
                        "aggs": {
                            "avg_sentiment": {"avg": {"field": "sentiment_score"}}
                        },
                    }
                },
            },
        )
        buckets = resp["aggregations"]["by_day"]["buckets"]
        data = [
            TrendDataPoint(
                date=b["key_as_string"],
                count=b["doc_count"],
                sentiment_avg=round(b["avg_sentiment"]["value"] or 0.0, 3),
            )
            for b in buckets
        ]
        return TrendResponse(period=period, data=data)
    finally:
        await os_client.close()


# ---------------------------------------------------------------------------
# ETL trigger
# ---------------------------------------------------------------------------

async def trigger_etl() -> dict[str, Any]:
    """Manually trigger the full ETL pipeline and return counts."""
    result = await run_full_pipeline()
    now = datetime.now(tz=timezone.utc).isoformat()
    _etl_status["gdelt_last_run"] = now
    _etl_status["ibm_crawl_last_run"] = now
    return result


def get_etl_status() -> ETLStatusResponse:
    from connectors.watson_news.scheduler import _scheduler

    running = bool(_scheduler and _scheduler.running)
    return ETLStatusResponse(
        gdelt_last_run=_etl_status.get("gdelt_last_run"),
        ibm_crawl_last_run=_etl_status.get("ibm_crawl_last_run"),
        box_last_run=_etl_status.get("box_last_run"),
        scheduler_running=running,
    )
