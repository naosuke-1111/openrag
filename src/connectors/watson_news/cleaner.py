"""クリーニング処理: HTML 除去、重複排除、言語検出。"""

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
    """HTML をプレーンテキストに変換し、タグを除去してリンクを Markdown 形式にする。"""
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
    """生のニュース記事 ConnectorDocument をクリーニングする。

    ``watson_news_clean`` レコードを表す dict を返す。
    記事が重複している場合や対象外の言語の場合は ``None`` を返す。
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
    """Box ドキュメントをバイト列からプレーンテキストに変換してクリーニングする。

    重い処理（PDF / Office 抽出）は上流の docling で行われる。
    ここでは空白を正規化し、論理的なチャンクに分割する。
    """
    raw = doc.content.decode(errors="replace")
    body = _normalize_whitespace(raw)

    # 段落ベースのシンプルなチャンク分割
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
