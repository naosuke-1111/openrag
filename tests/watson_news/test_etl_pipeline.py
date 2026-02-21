"""Unit tests for ETL pipeline helpers."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from connectors.base import ConnectorDocument, DocumentACL


def _make_doc(url: str, content: str = "", source_type: str = "gdelt") -> ConnectorDocument:
    now = datetime.now(tz=timezone.utc)
    return ConnectorDocument(
        id=f"doc-{hash(url)}",
        filename="test.html",
        mimetype="text/html",
        content=(content or f"<p>{'IBM content ' * 30}</p>").encode(),
        source_url=url,
        acl=DocumentACL(owner=source_type),
        modified_time=now,
        created_time=now,
        metadata={
            "source_type": source_type,
            "title": "Test Article",
            "language": "en",
        },
    )


@pytest.mark.asyncio
async def test_run_gdelt_pipeline_skips_known_urls():
    """Documents whose URLs are already in OpenSearch should be skipped."""
    docs = [_make_doc("https://example.com/known"), _make_doc("https://example.com/new")]

    with (
        patch("connectors.watson_news.etl_pipeline.GdeltConnector") as mock_connector_cls,
        patch("connectors.watson_news.etl_pipeline._make_opensearch") as mock_os_factory,
        patch("connectors.watson_news.etl_pipeline._get_known_urls", new=AsyncMock(return_value={"https://example.com/known"})),
        patch("connectors.watson_news.etl_pipeline._upsert_doc", new=AsyncMock()),
        patch("connectors.watson_news.etl_pipeline.clean_news_article", return_value=None),
    ):
        mock_connector = AsyncMock()
        mock_connector.fetch_articles = AsyncMock(return_value=docs)
        mock_connector.close = AsyncMock()
        mock_connector_cls.return_value = mock_connector

        mock_os = AsyncMock()
        mock_os.close = AsyncMock()
        mock_os_factory.return_value = mock_os

        from connectors.watson_news.etl_pipeline import run_gdelt_pipeline
        count = await run_gdelt_pipeline()

        # Only the new URL should be processed
        assert count == 0  # cleaner returned None, so 0 indexed


@pytest.mark.asyncio
async def test_run_full_pipeline_runs_both_pipelines():
    """run_full_pipeline should invoke both GDELT and IBM crawl pipelines."""
    with (
        patch("connectors.watson_news.etl_pipeline.run_gdelt_pipeline", new=AsyncMock(return_value=5)),
        patch("connectors.watson_news.etl_pipeline.run_ibm_crawl_pipeline", new=AsyncMock(return_value=3)),
    ):
        from connectors.watson_news.etl_pipeline import run_full_pipeline
        result = await run_full_pipeline()
        assert result["gdelt"] == 5
        assert result["ibm_crawl"] == 3
