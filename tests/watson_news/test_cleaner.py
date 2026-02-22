"""Unit tests for the cleaner module."""

import pytest
from datetime import datetime, timezone

from connectors.base import ConnectorDocument, DocumentACL
from connectors.watson_news.cleaner import (
    clean_news_article,
    clean_box_document,
    _normalize_whitespace,
    _strip_html,
)


def _make_doc(content: str, mimetype: str = "text/html", source_type: str = "gdelt", lang: str = "en") -> ConnectorDocument:
    now = datetime.now(tz=timezone.utc)
    return ConnectorDocument(
        id="test-id",
        filename="test.html",
        mimetype=mimetype,
        content=content.encode(),
        source_url="https://example.com/article",
        acl=DocumentACL(owner="test"),
        modified_time=now,
        created_time=now,
        metadata={
            "source_type": source_type,
            "title": "Test Title",
            "language": lang,
        },
    )


def test_strip_html_removes_tags():
    html = "<h1>Title</h1><p>Some <b>bold</b> text.</p>"
    result = _strip_html(html)
    assert "<h1>" not in result
    assert "Title" in result
    assert "bold" in result


def test_normalize_whitespace_collapses_spaces():
    text = "Hello    world\n\n\nNew paragraph"
    result = _normalize_whitespace(text)
    assert "    " not in result
    assert "\n\n\n" not in result


def test_clean_news_article_returns_dict_for_valid_html():
    html = "<h1>IBM AI News</h1>" + "<p>IBM has announced a major breakthrough in artificial intelligence. " * 5 + "</p>"
    doc = _make_doc(html, mimetype="text/html", source_type="gdelt", lang="en")
    result = clean_news_article(doc)
    assert result is not None
    assert result["source_type"] == "gdelt"
    assert "clean_body" in result
    assert len(result["clean_body"]) >= 100


def test_clean_news_article_filters_short_body():
    doc = _make_doc("<p>Too short</p>", mimetype="text/html", lang="en")
    result = clean_news_article(doc)
    assert result is None


def test_clean_box_document_splits_into_chunks():
    text = "\n\n".join([f"Paragraph number {i} with some meaningful content that exceeds thirty characters." for i in range(5)])
    doc = _make_doc(text, mimetype="text/plain", source_type="box")
    chunks = clean_box_document(doc)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert "chunk_index" in chunk
        assert "clean_text" in chunk
        assert chunk["source_type"] == "box"
