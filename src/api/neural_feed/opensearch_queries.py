"""OpenSearch query definitions for Neural Feed API."""
from __future__ import annotations

# Index name (defined in watson_news ETL pipeline)
IDX_NEWS_ENRICHED = "watson_news_enriched"

RECENT_ARTICLES_QUERY: dict = {
    "size": 15,
    "sort": [{"published": {"order": "desc"}}],
    "_source": [
        "id", "title", "domain", "source_type",
        "sentiment_label", "sentiment_score", "topic", "published",
    ],
}

CATEGORY_AGGREGATION_QUERY: dict = {
    "size": 0,
    "query": {"range": {"published": {"gte": "now-1h"}}},
    "aggs": {
        "by_topic": {
            "terms": {"field": "topic", "size": 10}
        }
    },
}

GLOBAL_TONE_QUERY: dict = {
    "size": 0,
    "query": {"range": {"published": {"gte": "now-1h"}}},
    "aggs": {
        "avg_sentiment": {"avg": {"field": "sentiment_score"}},
        "count": {"value_count": {"field": "sentiment_score"}},
    },
}

TOP_ENTITIES_QUERY: dict = {
    "size": 0,
    "query": {"range": {"published": {"gte": "now-15m"}}},
    "aggs": {
        "entity_names": {
            "terms": {"field": "entities.text", "size": 20}
        }
    },
}

KPI_TODAY_QUERY: dict = {
    "size": 0,
    "query": {"range": {"published": {"gte": "now/d"}}},
    "aggs": {
        "total_today": {"value_count": {"field": "id.keyword"}},
        "by_source": {"terms": {"field": "source_type", "size": 10}},
    },
}


def new_articles_since_query(since_id: str | None, size: int = 5) -> dict:
    """Query for articles published after the given document (for SSE polling)."""
    base: dict = {
        "size": size,
        "sort": [{"published": {"order": "asc"}}],
        "_source": [
            "id", "title", "domain", "source_type",
            "sentiment_label", "sentiment_score", "topic", "published",
        ],
    }
    if since_id:
        base["search_after"] = [since_id]
    else:
        base["query"] = {"range": {"published": {"gte": "now-5m"}}}
    return base
