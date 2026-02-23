"""ETL オーケストレーター: 取得 → クリーニング → エンリッチ → 埋め込み → インデックス登録。"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from opensearchpy import AsyncOpenSearch
from opensearchpy._async.http_aiohttp import AIOHttpConnection

from connectors.watson_news.cleaner import clean_box_document, clean_news_article
from connectors.watson_news.enricher import enrich_article, enrich_box_chunk
from connectors.watson_news.gdelt_connector import GdeltConnector
from connectors.watson_news.ibm_crawl_connector import crawl_target, load_crawl_targets
from utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# OpenSearch 設定
# ---------------------------------------------------------------------------
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "")

# Watson News の OpenSearch インデックス名
IDX_NEWS_RAW = "watson_news_raw"
IDX_NEWS_CLEAN = "watson_news_clean"
IDX_NEWS_ENRICHED = "watson_news_enriched"
IDX_BOX_RAW = "watson_box_raw"
IDX_BOX_ENRICHED = "watson_box_enriched"


def _make_opensearch() -> AsyncOpenSearch:
    return AsyncOpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        connection_class=AIOHttpConnection,
        scheme="https",
        use_ssl=True,
        verify_certs=False,
        ssl_assert_fingerprint=None,
        http_auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
        http_compress=True,
    )


async def _get_known_urls(os_client: AsyncOpenSearch, index: str) -> set[str]:
    """*index* に既に格納されている URL のセットを返す。"""
    try:
        resp = await os_client.search(
            index=index,
            body={"query": {"match_all": {}}, "_source": ["url"], "size": 10000},
        )
        return {hit["_source"]["url"] for hit in resp["hits"]["hits"] if "url" in hit.get("_source", {})}
    except Exception as exc:
        logger.warning("Could not fetch known URLs", index=index, error=str(exc))
        return set()


async def _upsert_doc(os_client: AsyncOpenSearch, index: str, doc_id: str, body: dict) -> None:
    try:
        await os_client.index(index=index, id=doc_id, body=body)
    except Exception as exc:
        logger.warning("OpenSearch upsert failed", index=index, id=doc_id, error=str(exc))


# ---------------------------------------------------------------------------
# パイプライン処理ステップ
# ---------------------------------------------------------------------------

async def run_gdelt_pipeline() -> int:
    """GDELT 記事を取得し、生データとエンリッチ済みレコードを保存する。

    処理した記事数を返す。
    """
    logger.info("Starting GDELT pipeline")
    os_client = _make_opensearch()
    connector = GdeltConnector()

    try:
        docs = await connector.fetch_articles()
        known_urls = await _get_known_urls(os_client, IDX_NEWS_RAW)

        processed = 0
        for doc in docs:
            if doc.source_url in known_urls:
                continue

            # 生データレイヤー
            raw_body = {
                "id": doc.id,
                "url": doc.source_url,
                "title": doc.metadata.get("title", ""),
                "body": doc.content.decode(errors="replace"),
                "source_type": "gdelt",
                "crawled_at": datetime.now(tz=timezone.utc).isoformat(),
                **doc.metadata,
            }
            await _upsert_doc(os_client, IDX_NEWS_RAW, doc.id, raw_body)

            # クリーニング + エンリッチ
            clean = clean_news_article(doc)
            if not clean:
                continue

            await _upsert_doc(os_client, IDX_NEWS_CLEAN, doc.id, clean)

            enriched = await enrich_article(clean)
            await _upsert_doc(os_client, IDX_NEWS_ENRICHED, doc.id, enriched)
            processed += 1

        logger.info("GDELT pipeline complete", processed=processed)
        return processed
    finally:
        await connector.close()
        await os_client.close()


async def run_ibm_crawl_pipeline() -> int:
    """IBM 公式サイトをクロールし、生データとエンリッチ済みレコードを保存する。

    処理した記事数を返す。
    """
    logger.info("Starting IBM crawl pipeline")
    os_client = _make_opensearch()

    try:
        targets = load_crawl_targets()
        known_urls = await _get_known_urls(os_client, IDX_NEWS_RAW)

        total = 0
        for target in targets:
            docs = await crawl_target(target, known_urls)
            for doc in docs:
                raw_body = {
                    "id": doc.id,
                    "url": doc.source_url,
                    "title": doc.metadata.get("title", ""),
                    "body": doc.content.decode(errors="replace"),
                    "source_type": "ibm_crawl",
                    "crawled_at": datetime.now(tz=timezone.utc).isoformat(),
                    **doc.metadata,
                }
                await _upsert_doc(os_client, IDX_NEWS_RAW, doc.id, raw_body)

                clean = clean_news_article(doc)
                if not clean:
                    continue

                await _upsert_doc(os_client, IDX_NEWS_CLEAN, doc.id, clean)

                enriched = await enrich_article(clean)
                await _upsert_doc(os_client, IDX_NEWS_ENRICHED, doc.id, enriched)
                total += 1

            # 同一実行内での再処理を防ぐため、新たにクロールした URL を既知セットに追加
            known_urls.update(doc.source_url for doc in docs)

        logger.info("IBM crawl pipeline complete", processed=total)
        return total
    finally:
        await os_client.close()


async def run_box_pipeline(box_documents: list[Any]) -> int:
    """BoxConnector が取得した Box ドキュメントを処理する。

    Args:
        box_documents: Box から取得した :class:`ConnectorDocument` インスタンスのリスト。

    Returns:
        処理したチャンク数。
    """
    logger.info("Starting Box pipeline", doc_count=len(box_documents))
    os_client = _make_opensearch()

    try:
        total_chunks = 0
        for doc in box_documents:
            # 生データレイヤー
            raw_body = {
                "id": doc.id,
                "box_file_id": doc.metadata.get("box_file_id", doc.id),
                "filename": doc.filename,
                "mimetype": doc.mimetype,
                "updated_at": doc.modified_time.isoformat(),
                "source_type": "box",
            }
            await _upsert_doc(os_client, IDX_BOX_RAW, doc.id, raw_body)

            # クリーニング（チャンク分割）
            chunks = clean_box_document(doc)
            for chunk in chunks:
                enriched_chunk = await enrich_box_chunk(chunk)
                await _upsert_doc(
                    os_client, IDX_BOX_ENRICHED, enriched_chunk["id"], enriched_chunk
                )
                total_chunks += 1

        logger.info("Box pipeline complete", total_chunks=total_chunks)
        return total_chunks
    finally:
        await os_client.close()


async def run_full_pipeline() -> dict[str, int]:
    """全 ETL パイプラインを並列実行する（GDELT + IBM クロール）。

    Box パイプラインは認証済み Box ドキュメントが必要なため、個別に起動する。

    Returns:
        カウントを含む dict: ``{"gdelt": n, "ibm_crawl": n}``。
    """
    gdelt_task = asyncio.create_task(run_gdelt_pipeline())
    ibm_task = asyncio.create_task(run_ibm_crawl_pipeline())

    gdelt_count, ibm_count = await asyncio.gather(gdelt_task, ibm_task, return_exceptions=True)

    return {
        "gdelt": gdelt_count if isinstance(gdelt_count, int) else 0,
        "ibm_crawl": ibm_count if isinstance(ibm_count, int) else 0,
    }
