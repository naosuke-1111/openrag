"""Pydantic response schemas for Neural Feed API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ArticleItem(BaseModel):
    id: str
    title: str
    domain: str
    source_type: str
    sentiment_label: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]
    sentiment_score: float
    topic: str
    published: str


class EntityItem(BaseModel):
    text: str
    count: int


class CategoryCount(BaseModel):
    topic: str
    count: int


class KpiMetrics(BaseModel):
    throughput: float          # articles/min
    total_today: int
    active_sources: int
    connected: bool
    last_updated: str


class TopEntitiesResponse(BaseModel):
    entities: list[EntityItem]
    unique_count: int


class CategoriesResponse(BaseModel):
    categories: list[CategoryCount]
    total: int


class ToneResponse(BaseModel):
    average_score: float
    label: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]
    sample_size: int


class RecentArticlesResponse(BaseModel):
    articles: list[ArticleItem]
    total: int
