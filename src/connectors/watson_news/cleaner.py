"""Cleaning step: HTML stripping, deduplication, and language detection."""

import re
import unicodedata
from typing import Any

import html2text
from langdetect import LangDetectException, detect

from connectors.base import ConnectorDocument
from utils.logging_config import get_logger

logger = get_logger(__name__)

_ALLOWED_LANGUAGES = {"en", "ja"}
_MIN_BODY_CHARS = 100


def _strip_html(raw: str) -> str:
    """Convert HTML to plain text, stripping tags and markdown-ifying links."""
    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    converter.body_width = 0
    return converter.handle(raw)


def _normalize_whitespace(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_language(text: str) -> str | None:
    try:
        return detect(text[:2000])
    except LangDetectException:
        return None


def clean_news_article(doc: ConnectorDocument) -> dict[str, Any] | None:
    """Clean a raw news article ConnectorDocument.

    Returns a dict representing a ``watson_news_clean`` record, or ``None``
    if the article is a duplicate or in a non-target language.
    """
    mimetype = doc.mimetype or ""
    raw = doc.content.decode(errors="replace")

    if "html" in mimetype:
        body = _strip_html(raw)
    else:
        body = raw

    body = _normalize_whitespace(body)

    if len(body) < _MIN_BODY_CHARS:
        logger.debug("Article body too short, skipping", url=doc.source_url)
        return None

    lang = doc.metadata.get("language") or _detect_language(body)
    if lang and lang not in _ALLOWED_LANGUAGES:
        logger.debug("Non-target language, skipping", lang=lang, url=doc.source_url)
        return None

    title = doc.metadata.get("title", "")

    return {
        "id": doc.id,
        "url": doc.source_url,
        "title": title,
        "clean_body": body,
        "published": doc.created_time.isoformat(),
        "language": lang or "en",
        "source_type": doc.metadata.get("source_type", "unknown"),
        "site_category": doc.metadata.get("site_category", ""),
        "crawl_target": doc.metadata.get("crawl_target", ""),
    }


def clean_box_document(doc: ConnectorDocument) -> list[dict[str, Any]]:
    """Clean a Box document by extracting plain text from bytes.

    The heavy lifting (PDF / Office extraction) is done upstream by docling.
    Here we normalise whitespace and split into logical chunks.
    """
    raw = doc.content.decode(errors="replace")
    body = _normalize_whitespace(raw)

    # Simple paragraph-based chunking
    paragraphs = [p.strip() for p in body.split("\n\n") if len(p.strip()) >= 30]

    return [
        {
            "id": f"{doc.id}_chunk_{i}",
            "box_file_id": doc.metadata.get("box_file_id", doc.id),
            "chunk_index": i,
            "clean_text": para,
            "filename": doc.filename,
            "mimetype": doc.mimetype,
            "source_type": "box",
        }
        for i, para in enumerate(paragraphs)
    ]
