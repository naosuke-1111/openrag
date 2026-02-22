"""Unit tests for GdeltConnector."""

import pytest
import respx
import httpx

from connectors.watson_news.gdelt_connector import GdeltConnector


GDELT_SAMPLE_RESPONSE = {
    "articles": [
        {
            "url": "https://example.com/ibm-article-1",
            "title": "IBM Announces New AI Model",
            "domain": "example.com",
            "language": "English",
            "seendate": "20260221T120000Z",
            "socialimage": "",
        },
        {
            "url": "https://example.com/ibm-article-2",
            "title": "IBM Cloud Expansion",
            "domain": "example.com",
            "language": "English",
            "seendate": "20260221T130000Z",
            "socialimage": "",
        },
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_returns_connector_documents():
    """GdeltConnector.fetch_articles should return ConnectorDocument instances."""
    respx.get(url__startswith="https://api.gdeltproject.org").mock(
        return_value=httpx.Response(200, json=GDELT_SAMPLE_RESPONSE)
    )

    connector = GdeltConnector()
    docs = await connector.fetch_articles(query="IBM", max_records=10, timespan="15min")
    await connector.close()

    assert len(docs) == 2
    assert docs[0].metadata["source_type"] == "gdelt"
    assert docs[0].metadata["title"] == "IBM Announces New AI Model"
    assert docs[0].source_url == "https://example.com/ibm-article-1"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_handles_empty_response():
    """GdeltConnector should handle an empty articles list gracefully."""
    respx.get(url__startswith="https://api.gdeltproject.org").mock(
        return_value=httpx.Response(200, json={"articles": []})
    )

    connector = GdeltConnector()
    docs = await connector.fetch_articles()
    await connector.close()

    assert docs == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_retries_on_server_error():
    """GdeltConnector should retry up to 3 times on server errors."""
    call_count = 0

    def error_then_success(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=GDELT_SAMPLE_RESPONSE)

    respx.get(url__startswith="https://api.gdeltproject.org").mock(
        side_effect=error_then_success
    )

    connector = GdeltConnector()
    docs = await connector.fetch_articles()
    await connector.close()

    assert len(docs) == 2
    assert call_count == 3
