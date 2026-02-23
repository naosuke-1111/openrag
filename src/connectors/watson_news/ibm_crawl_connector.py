"""差分 URL 検出機能を備えた IBM 公式サイトクローラー。

watson-news/ibm_crawl_targets.yaml からクロール対象を読み込み、
OpenSearch に既にインデックスされた URL と比較して新しい記事 URL を検出する。
"""

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import yaml
from bs4 import BeautifulSoup

from connectors.base import ConnectorDocument, DocumentACL
from utils.logging_config import get_logger

logger = get_logger(__name__)

IBM_CRAWL_USER_AGENT = os.getenv("IBM_CRAWL_USER_AGENT", "WatsonNewsBot/1.0")
_DEFAULT_CONFIG_PATH = (
    Path(__file__).parents[3] / "watson-news" / "ibm_crawl_targets.yaml"
)


@dataclass
class CrawlTarget:
    name: str
    index_url: str
    language: str
    site_category: str
    interval_hours: int
    display_name: str = ""
    enabled: bool = True
    respect_robots_txt: bool = True
    request_interval_seconds: int = 5
    max_articles_per_run: int = 100
    request_timeout_seconds: int = 30
    max_retries: int = 3
    article_link_selector: str | None = None


def load_crawl_targets(config_path: str | None = None) -> list[CrawlTarget]:
    """YAML 設定ファイルからクロール対象を読み込む。

    Args:
        config_path: YAML ファイルのパス。デフォルトは環境変数 ``WATSON_NEWS_CRAWL_CONFIG``、
            次に ``watson-news/ibm_crawl_targets.yaml`` を参照する。

    Returns:
        有効な :class:`CrawlTarget` インスタンスのリスト。
    """
    if config_path is None:
        config_path = os.getenv(
            "WATSON_NEWS_CRAWL_CONFIG",
            str(_DEFAULT_CONFIG_PATH),
        )
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    defaults: dict = raw.get("defaults", {})
    targets: list[CrawlTarget] = []
    valid_fields = set(CrawlTarget.__dataclass_fields__.keys())  # type: ignore[attr-defined]
    for item in raw.get("targets", []):
        merged = {**defaults, **item}
        kwargs = {k: v for k, v in merged.items() if k in valid_fields}
        target = CrawlTarget(**kwargs)
        if target.enabled:
            targets.append(target)
    return targets


class RobotsTxtCache:
    """robots.txt ファイルのシンプルなインプロセスキャッシュ（TTL: 1時間）。"""

    _TTL_SECONDS = 3600

    def __init__(self) -> None:
        self._cache: dict[str, tuple[RobotFileParser, float]] = {}

    async def can_fetch(self, url: str, user_agent: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        now = asyncio.get_event_loop().time()

        if robots_url in self._cache:
            parser, ts = self._cache[robots_url]
            if now - ts < self._TTL_SECONDS:
                return parser.can_fetch(user_agent, url)

        parser = RobotFileParser(robots_url)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(robots_url, headers={"User-Agent": user_agent})
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    parser.allow_all = True
        except Exception:
            parser.allow_all = True  # type: ignore[attr-defined]

        self._cache[robots_url] = (parser, now)
        return parser.can_fetch(user_agent, url)


_robots_cache = RobotsTxtCache()


async def _fetch_html(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 3,
    timeout: float = 30.0,
) -> str | None:
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.get(
                url,
                headers={"User-Agent": IBM_CRAWL_USER_AGENT},
                timeout=timeout,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.text
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning(
                "Fetch error", url=url, attempt=attempt, error=str(exc)
            )
            if attempt < max_retries:
                await asyncio.sleep(2**attempt)
    return None


def _extract_article_urls(
    html: str,
    base_url: str,
    selector: str | None,
) -> list[str]:
    """インデックスページの HTML 文字列から記事 URL を抽出する。"""
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc

    if selector:
        elements = soup.select(selector)
        hrefs = [el.get("href") for el in elements if el.get("href")]
    else:
        hrefs = [a.get("href") for a in soup.find_all("a", href=True)]

    urls: list[str] = []
    for href in hrefs:
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc.endswith(base_domain) and parsed.scheme in {"http", "https"}:
            # クエリパラメーターとフラグメントを除去して正規化
            clean = parsed._replace(query="", fragment="").geturl()
            if clean not in urls:
                urls.append(clean)
    return urls


async def crawl_target(
    target: CrawlTarget,
    known_urls: set[str],
) -> list[ConnectorDocument]:
    """単一の IBM サイト対象をクロールし、新しい記事を返す。

    Args:
        target: クロール対象の設定。
        known_urls: 既にインデックスされた URL のセット（差分検出用）。

    Returns:
        新しい :class:`ConnectorDocument` インスタンスのリスト。
    """
    async with httpx.AsyncClient() as client:
        # 1. インデックスページを取得
        html = await _fetch_html(
            client,
            target.index_url,
            max_retries=target.max_retries,
            timeout=float(target.request_timeout_seconds),
        )
        if not html:
            logger.warning("Failed to fetch index page", target=target.name)
            return []

        # 2. 記事 URL を抽出
        all_urls = _extract_article_urls(html, target.index_url, target.article_link_selector)

        # 3. 差分: 新しい URL のみを残す
        new_urls = [u for u in all_urls if u not in known_urls]
        if target.max_articles_per_run > 0:
            new_urls = new_urls[: target.max_articles_per_run]

        logger.info(
            "IBM crawl differential",
            target=target.name,
            total=len(all_urls),
            new=len(new_urls),
        )

        # 4. 各新規記事をクロール
        documents: list[ConnectorDocument] = []
        for url in new_urls:
            if target.respect_robots_txt:
                if not await _robots_cache.can_fetch(url, IBM_CRAWL_USER_AGENT):
                    logger.info("robots.txt disallows", url=url)
                    continue

            await asyncio.sleep(target.request_interval_seconds)

            article_html = await _fetch_html(
                client,
                url,
                max_retries=target.max_retries,
                timeout=float(target.request_timeout_seconds),
            )
            if not article_html:
                continue

            doc = _html_to_connector_document(
                article_html, url, target
            )
            documents.append(doc)

        return documents


def _html_to_connector_document(
    html: str,
    url: str,
    target: CrawlTarget,
) -> ConnectorDocument:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    now = datetime.now(tz=timezone.utc)
    return ConnectorDocument(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, url)),
        filename=f"{title[:80]}.html",
        mimetype="text/html",
        content=html.encode(),
        source_url=url,
        acl=DocumentACL(owner="ibm_crawl"),
        modified_time=now,
        created_time=now,
        metadata={
            "source_type": "ibm_crawl",
            "title": title,
            "language": target.language,
            "site_category": target.site_category,
            "crawl_target": target.name,
            "display_name": target.display_name,
        },
    )
