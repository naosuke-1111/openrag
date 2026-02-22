"""Request / response schemas for Watson News API endpoints."""

from models.watson_news import (  # re-export for convenience
    ArticleListResponse,
    BoxFileListResponse,
    ETLStatusResponse,
    TrendResponse,
    WatsonNewsSearchRequest,
    WatsonNewsSearchResponse,
)

__all__ = [
    "WatsonNewsSearchRequest",
    "WatsonNewsSearchResponse",
    "ArticleListResponse",
    "BoxFileListResponse",
    "TrendResponse",
    "ETLStatusResponse",
]
