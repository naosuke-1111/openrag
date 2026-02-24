"""Integration tests for Watson News REST API route handlers.

各テストはサービス層の関数を unittest.mock でモックし、
Starlette TestClient 経由でルートハンドラーのリクエスト/レスポンスを検証する。
外部サービス（OpenSearch / watsonx.ai）への接続は不要。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from api.watson_news import routes
from models.watson_news import (
    ArticleListResponse,
    BoxFileListResponse,
    ETLStatusResponse,
    SearchResultItem,
    TrendDataPoint,
    TrendResponse,
    WatsonNewsSearchResponse,
)

# ---------------------------------------------------------------------------
# Minimal test app
# ---------------------------------------------------------------------------

_APP = Starlette(
    routes=[
        Route("/articles", routes.get_articles),
        Route("/articles/{id}", routes.get_article_detail),
        Route("/search", routes.search_articles, methods=["POST"]),
        Route("/box/files", routes.get_box_files),
        Route("/box/files/{file_id}", routes.get_box_file_detail),
        Route("/trends", routes.get_trend_data),
        Route("/etl/status", routes.etl_status),
        Route("/etl/trigger", routes.etl_trigger, methods=["POST"]),
    ]
)

_CLIENT = TestClient(_APP, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_ARTICLE_LIST = ArticleListResponse(
    total=2,
    page=1,
    page_size=20,
    articles=[
        {"id": "a1", "title": "IBM News", "source_type": "ibm_crawl"},
        {"id": "a2", "title": "GDELT Article", "source_type": "gdelt"},
    ],
)

_ARTICLE_DETAIL = {
    "id": "a1",
    "title": "IBM News",
    "source_type": "ibm_crawl",
    "sentiment_label": "positive",
}

_SEARCH_RESPONSE = WatsonNewsSearchResponse(
    query="IBM AI",
    total=1,
    results=[
        SearchResultItem(
            id="a1",
            source_type="ibm_crawl",
            score=0.95,
            title="IBM AI Strategy",
        )
    ],
)

_BOX_LIST = BoxFileListResponse(
    total=1,
    files=[{"id": "f1", "filename": "report.pdf", "box_file_id": "box_f1"}],
)

_BOX_DETAIL = {
    "id": "f1",
    "filename": "report.pdf",
    "box_file_id": "box_f1",
    "chunks": [{"id": "c1", "chunk_index": 0, "clean_text": "Hello world"}],
}

_TREND_RESPONSE = TrendResponse(
    period="7d",
    data=[TrendDataPoint(date="2026-02-20", count=5, sentiment_avg=0.4)],
)

_ETL_STATUS = ETLStatusResponse(
    gdelt_last_run="2026-02-24T00:00:00+00:00",
    scheduler_running=True,
)


# ---------------------------------------------------------------------------
# GET /articles
# ---------------------------------------------------------------------------

class TestGetArticles:
    def test_returns_200_with_articles(self):
        with patch("api.watson_news.routes.list_articles", new=AsyncMock(return_value=_ARTICLE_LIST)):
            r = _CLIENT.get("/articles")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert len(body["articles"]) == 2

    def test_passes_page_and_page_size_params(self):
        with patch("api.watson_news.routes.list_articles", new=AsyncMock(return_value=_ARTICLE_LIST)) as m:
            _CLIENT.get("/articles?page=2&page_size=5")
        m.assert_called_once()
        _, kwargs = m.call_args
        assert kwargs["page"] == 2
        assert kwargs["page_size"] == 5

    def test_passes_source_type_filter(self):
        with patch("api.watson_news.routes.list_articles", new=AsyncMock(return_value=_ARTICLE_LIST)) as m:
            _CLIENT.get("/articles?source_type=ibm_crawl")
        m.assert_called_once()
        _, kwargs = m.call_args
        assert kwargs["source_type"] == "ibm_crawl"

    def test_returns_500_on_service_error(self):
        with patch("api.watson_news.routes.list_articles", new=AsyncMock(side_effect=Exception("OS down"))):
            r = _CLIENT.get("/articles")
        assert r.status_code == 500
        assert "error" in r.json()


# ---------------------------------------------------------------------------
# GET /articles/{id}
# ---------------------------------------------------------------------------

class TestGetArticleDetail:
    def test_returns_200_when_found(self):
        with patch("api.watson_news.routes.get_article", new=AsyncMock(return_value=_ARTICLE_DETAIL)):
            r = _CLIENT.get("/articles/a1")
        assert r.status_code == 200
        assert r.json()["id"] == "a1"
        assert r.json()["title"] == "IBM News"

    def test_returns_404_when_not_found(self):
        with patch("api.watson_news.routes.get_article", new=AsyncMock(return_value=None)):
            r = _CLIENT.get("/articles/not-exist")
        assert r.status_code == 404
        assert "error" in r.json()

    def test_returns_500_on_service_error(self):
        with patch("api.watson_news.routes.get_article", new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = _CLIENT.get("/articles/a1")
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------

class TestSearchArticles:
    def test_returns_200_with_results(self):
        with patch("api.watson_news.routes.search_watson_news", new=AsyncMock(return_value=_SEARCH_RESPONSE)):
            r = _CLIENT.post("/search", json={"query": "IBM AI"})
        assert r.status_code == 200
        body = r.json()
        assert body["query"] == "IBM AI"
        assert body["total"] == 1
        assert len(body["results"]) == 1
        assert body["results"][0]["score"] == pytest.approx(0.95)

    def test_returns_400_on_invalid_json(self):
        r = _CLIENT.post("/search", content=b"not-json", headers={"content-type": "application/json"})
        assert r.status_code == 400

    def test_returns_500_on_service_error(self):
        with patch("api.watson_news.routes.search_watson_news", new=AsyncMock(side_effect=Exception("OS error"))):
            r = _CLIENT.post("/search", json={"query": "test"})
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# GET /box/files
# ---------------------------------------------------------------------------

class TestGetBoxFiles:
    def test_returns_200_with_files(self):
        with patch("api.watson_news.routes.list_box_files", new=AsyncMock(return_value=_BOX_LIST)):
            r = _CLIENT.get("/box/files")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["files"][0]["filename"] == "report.pdf"

    def test_passes_pagination_params(self):
        with patch("api.watson_news.routes.list_box_files", new=AsyncMock(return_value=_BOX_LIST)) as m:
            _CLIENT.get("/box/files?page=3&page_size=10")
        m.assert_called_once()
        _, kwargs = m.call_args
        assert kwargs["page"] == 3
        assert kwargs["page_size"] == 10


# ---------------------------------------------------------------------------
# GET /box/files/{file_id}
# ---------------------------------------------------------------------------

class TestGetBoxFileDetail:
    def test_returns_200_when_found(self):
        with patch("api.watson_news.routes.get_box_file", new=AsyncMock(return_value=_BOX_DETAIL)):
            r = _CLIENT.get("/box/files/f1")
        assert r.status_code == 200
        body = r.json()
        assert body["filename"] == "report.pdf"
        assert len(body["chunks"]) == 1

    def test_returns_404_when_not_found(self):
        with patch("api.watson_news.routes.get_box_file", new=AsyncMock(return_value=None)):
            r = _CLIENT.get("/box/files/no-exist")
        assert r.status_code == 404

    def test_returns_500_on_service_error(self):
        with patch("api.watson_news.routes.get_box_file", new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = _CLIENT.get("/box/files/f1")
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# GET /trends
# ---------------------------------------------------------------------------

class TestGetTrendData:
    def test_returns_200_with_trend_data(self):
        with patch("api.watson_news.routes.get_trends", new=AsyncMock(return_value=_TREND_RESPONSE)):
            r = _CLIENT.get("/trends")
        assert r.status_code == 200
        body = r.json()
        assert body["period"] == "7d"
        assert len(body["data"]) == 1
        assert body["data"][0]["count"] == 5

    def test_passes_period_param(self):
        with patch("api.watson_news.routes.get_trends", new=AsyncMock(return_value=_TREND_RESPONSE)) as m:
            _CLIENT.get("/trends?period=30d")
        m.assert_called_once()
        _, kwargs = m.call_args
        assert kwargs["period"] == "30d"


# ---------------------------------------------------------------------------
# GET /etl/status
# ---------------------------------------------------------------------------

class TestEtlStatus:
    def test_returns_200_with_status(self):
        with patch("api.watson_news.routes.get_etl_status", return_value=_ETL_STATUS):
            r = _CLIENT.get("/etl/status")
        assert r.status_code == 200
        body = r.json()
        assert body["scheduler_running"] is True
        assert body["gdelt_last_run"] == "2026-02-24T00:00:00+00:00"


# ---------------------------------------------------------------------------
# POST /etl/trigger
# ---------------------------------------------------------------------------

class TestEtlTrigger:
    def test_returns_200_with_triggered_status(self):
        mock_counts = {"gdelt": 5, "ibm_crawl": 3, "box": 1}
        with patch("api.watson_news.routes.trigger_etl", new=AsyncMock(return_value=mock_counts)):
            r = _CLIENT.post("/etl/trigger")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "triggered"
        assert body["counts"]["gdelt"] == 5
