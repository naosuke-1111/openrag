"""IBM 関連ニュース向け GDELT v2 記事リストコネクター。"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import httpx

from connectors.base import ConnectorDocument, DocumentACL
from utils.logging_config import get_logger

logger = get_logger(__name__)

GDELT_API_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERY_KEYWORD = os.getenv("GDELT_QUERY_KEYWORD", "IBM")
GDELT_MAX_RECORDS = int(os.getenv("GDELT_MAX_RECORDS", "250"))
GDELT_TIMESPAN = os.getenv("GDELT_TIMESPAN", "15min")
GDELT_REQUEST_TIMEOUT = float(os.getenv("GDELT_REQUEST_TIMEOUT", "30"))


class GdeltConnector:
    """GDELT v2 Document API から IBM 関連記事を取得する。

    GDELT は公開 API のため OAuth 不要。
    """

    CONNECTOR_NAME = "gdelt_news"
    CONNECTOR_DESCRIPTION = "GDELT News Connector for IBM-related articles"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(GDELT_REQUEST_TIMEOUT),
                follow_redirects=True,
            )
        return self._http_client

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def fetch_articles(
        self,
        query: str | None = None,
        max_records: int | None = None,
        timespan: str | None = None,
    ) -> list[ConnectorDocument]:
        """*query* に一致する記事を GDELT から取得する。

        Args:
            query: 検索キーワード（デフォルト: 環境変数 GDELT_QUERY_KEYWORD）。
            max_records: 返却する記事の最大件数。
            timespan: GDELT タイムスパン文字列（例: ``"15min"``、``"1d"``）。

        Returns:
            :class:`ConnectorDocument` インスタンスのリスト（記事ごとに1件）。
        """
        q = query or GDELT_QUERY_KEYWORD
        n = max_records or GDELT_MAX_RECORDS
        ts = timespan or GDELT_TIMESPAN

        url = (
            f"{GDELT_API_BASE}"
            f"?query={quote_plus(q)}"
            f"&mode=ArtList"
            f"&maxrecords={n}"
            f"&format=json"
            f"&timespan={ts}"
        )
        logger.info("Fetching GDELT articles", query=q, max_records=n, timespan=ts)

        client = await self._get_client()
        for attempt in range(1, 4):
            try:
                response = await client.get(url)
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "GDELT HTTP error",
                    attempt=attempt,
                    status_code=exc.response.status_code,
                )
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)
            except httpx.RequestError as exc:
                logger.warning("GDELT request error", attempt=attempt, error=str(exc))
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)

        data = response.json()
        articles = data.get("articles", [])
        logger.info("GDELT articles fetched", count=len(articles))
        return [self._to_connector_document(a) for a in articles]

    def _to_connector_document(self, article: dict[str, Any]) -> ConnectorDocument:
        url = article.get("url", "")
        title = article.get("title", "")
        domain = article.get("domain", "")
        seendate = article.get("seendate", "")

        # GDELT seendate のフォーマット: 20260221T120000Z
        try:
            seen_dt = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, TypeError):
            seen_dt = datetime.now(tz=timezone.utc)

        content = f"# {title}\n\nURL: {url}\nDomain: {domain}\nSeen: {seendate}\n"
        return ConnectorDocument(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, url)),
            filename=f"{title[:80]}.txt",
            mimetype="text/plain",
            content=content.encode(),
            source_url=url,
            acl=DocumentACL(owner="gdelt"),
            modified_time=seen_dt,
            created_time=seen_dt,
            metadata={
                "source_type": "gdelt",
                "title": title,
                "domain": domain,
                "language": article.get("language", ""),
                "seendate": seendate,
                "socialimage": article.get("socialimage", ""),
            },
        )
