"""Pydantic data models for Watson News domain objects."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class Entity(BaseModel):
    name: str
    type: str  # org | person | location | product | technology


# ---------------------------------------------------------------------------
# News article models
# ---------------------------------------------------------------------------

class NewsRaw(BaseModel):
    id: str
    url: str
    title: str = ""
    body: str = ""
    source_type: str  # gdelt | ibm_crawl
    crawled_at: str
    language: str = ""
    site_category: str = ""
    crawl_target: str = ""


class NewsClean(BaseModel):
    id: str
    url: str
    title: str = ""
    clean_body: str = ""
    published: str = ""
    language: str = "en"
    source_type: str
    site_category: str = ""
    crawl_target: str = ""


class NewsEnriched(BaseModel):
    id: str
    url: str
    title: str = ""
    clean_body: str = ""
    summary: str = ""
    sentiment_label: str = "neutral"
    sentiment_score: float = 0.0
    entities: list[Entity] = Field(default_factory=list)
    topic: str = "other"
    language: str = "en"
    source_type: str
    site_category: str = ""
    published: str = ""
    vector: list[float] = Field(default_factory=list)
    enrich_model: str = ""
    embed_model: str = ""


# ---------------------------------------------------------------------------
# Box document models
# ---------------------------------------------------------------------------

class BoxRaw(BaseModel):
    id: str
    box_file_id: str
    filename: str
    mimetype: str
    updated_at: str
    source_type: str = "box"


class BoxChunk(BaseModel):
    id: str
    box_file_id: str
    chunk_index: int
    clean_text: str
    filename: str = ""
    mimetype: str = ""
    source_type: str = "box"
    vector: list[float] = Field(default_factory=list)
    embed_model: str = ""


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class WatsonNewsSearchRequest(BaseModel):
    query: str
    source_types: list[str] = Field(
        default_factory=lambda: ["gdelt", "ibm_crawl", "box"]
    )
    date_from: str | None = None
    date_to: str | None = None
    language: str | None = None
    sentiment: str | None = None  # positive | neutral | negative
    topic: str | None = None
    top_k: int = 10


class SearchResultItem(BaseModel):
    id: str
    source_type: str
    score: float
    url: str = ""
    title: str = ""
    summary: str = ""
    sentiment_label: str = ""
    topic: str = ""
    language: str = ""
    published: str = ""
    filename: str = ""  # Box files


class WatsonNewsSearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]


# ---------------------------------------------------------------------------
# API list / detail responses
# ---------------------------------------------------------------------------

class ArticleListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    articles: list[dict[str, Any]]


class BoxFileListResponse(BaseModel):
    total: int
    files: list[dict[str, Any]]


class TrendDataPoint(BaseModel):
    date: str
    count: int
    sentiment_avg: float = 0.0
    topic: str = ""


class TrendResponse(BaseModel):
    period: str
    data: list[TrendDataPoint]


class ETLStatusResponse(BaseModel):
    gdelt_last_run: str | None = None
    ibm_crawl_last_run: str | None = None
    box_last_run: str | None = None
    scheduler_running: bool = False
