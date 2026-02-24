"""クロール倫理テスト: robots.txt 遵守とリクエストインターバルの検証。

IBM公式サイトクローラーが以下の倫理要件を満たすことを確認する:
1. robots.txt で禁止されている URL をスキップする
2. robots.txt で許可されている URL はクロールする
3. robots.txt の取得が失敗しても fail-open（許可）で動作する
4. respect_robots_txt=False のターゲットは robots.txt をチェックしない
5. リクエストインターバルを待機する（asyncio.sleep が呼ばれること）
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest
import respx

from connectors.watson_news.ibm_crawl_connector import (
    CrawlTarget,
    RobotsTxtCache,
    crawl_target,
)

# _robots_cache はモジュールレベルのグローバル（TTL キャッシュ）。
# テスト間でキャッシュが持続しないよう、各テストで新しいインスタンスに差し替える。
_FRESH_CACHE_PATCH = patch(
    "connectors.watson_news.ibm_crawl_connector._robots_cache",
    new_callable=RobotsTxtCache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _target(
    name: str = "test_site",
    index_url: str = "https://www.ibm.com/announcements",
    respect: bool = True,
    interval: int = 0,
    max_articles: int = 10,
    lang: str = "en",
    site_cat: str = "test",
    selector: str | None = None,
) -> CrawlTarget:
    return CrawlTarget(
        name=name,
        index_url=index_url,
        language=lang,
        site_category=site_cat,
        interval_hours=1,
        respect_robots_txt=respect,
        request_interval_seconds=interval,
        max_articles_per_run=max_articles,
        article_link_selector=selector,
    )


_INDEX_HTML = """
<html><body>
  <a href="/news/article-1">Article 1</a>
  <a href="/news/article-2">Article 2</a>
  <a href="https://external.com/page">External</a>
</body></html>
"""

_ARTICLE_HTML = "<html><head><title>Test Article</title></head><body>Content</body></html>"


# ---------------------------------------------------------------------------
# RobotsTxtCache tests
# ---------------------------------------------------------------------------

class TestRobotsTxtCache:
    @pytest.mark.asyncio
    @respx.mock
    async def test_allows_url_when_robots_txt_permits(self):
        robots_txt = "User-agent: *\nDisallow: /blocked/\nAllow: /news/"
        respx.get("https://www.ibm.com/robots.txt").mock(
            return_value=httpx.Response(200, text=robots_txt)
        )

        cache = RobotsTxtCache()
        result = await cache.can_fetch(
            "https://www.ibm.com/news/article-1", "WatsonNewsBot/1.0"
        )

        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_blocks_url_when_robots_txt_disallows(self):
        robots_txt = "User-agent: *\nDisallow: /blocked/"
        respx.get("https://www.ibm.com/robots.txt").mock(
            return_value=httpx.Response(200, text=robots_txt)
        )

        cache = RobotsTxtCache()
        result = await cache.can_fetch(
            "https://www.ibm.com/blocked/secret-page", "WatsonNewsBot/1.0"
        )

        assert result is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_allows_all_when_robots_txt_returns_non_200(self):
        """robots.txt が 404 を返した場合はすべて許可（fail-open）。"""
        respx.get("https://www.ibm.com/robots.txt").mock(
            return_value=httpx.Response(404)
        )

        cache = RobotsTxtCache()
        result = await cache.can_fetch(
            "https://www.ibm.com/any-path", "WatsonNewsBot/1.0"
        )

        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_allows_all_when_robots_txt_fetch_fails(self):
        """robots.txt の取得がネットワークエラーで失敗した場合は fail-open。"""
        respx.get("https://www.ibm.com/robots.txt").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        cache = RobotsTxtCache()
        result = await cache.can_fetch(
            "https://www.ibm.com/news/article-1", "WatsonNewsBot/1.0"
        )

        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_caches_robots_txt_and_does_not_refetch(self):
        """同じドメインの robots.txt はキャッシュし、2回目以降は取得しない。"""
        robots_txt = "User-agent: *\nDisallow: /blocked/"
        route = respx.get("https://www.ibm.com/robots.txt").mock(
            return_value=httpx.Response(200, text=robots_txt)
        )

        cache = RobotsTxtCache()
        await cache.can_fetch("https://www.ibm.com/news/a", "bot")
        await cache.can_fetch("https://www.ibm.com/news/b", "bot")

        # robots.txt へのリクエストは 1 回のみであるべき
        assert route.call_count == 1


# ---------------------------------------------------------------------------
# crawl_target: robots.txt 遵守テスト
# ---------------------------------------------------------------------------

class TestCrawlTargetRobotsCompliance:
    @pytest.mark.asyncio
    @respx.mock
    @_FRESH_CACHE_PATCH
    async def test_skips_disallowed_urls(self, _mock_cache):
        """robots.txt で禁止された URL はクロールしない。"""
        robots_txt = "User-agent: *\nDisallow: /news/"
        target = _target(respect=True)

        respx.get("https://www.ibm.com/announcements").mock(
            return_value=httpx.Response(200, text=_INDEX_HTML)
        )
        respx.get("https://www.ibm.com/robots.txt").mock(
            return_value=httpx.Response(200, text=robots_txt)
        )
        # 記事ページ — 呼ばれないはずだが登録しておく（assert_all_called=False 相当）
        respx.get(url__regex=r"https://www\.ibm\.com/news/article-\d").mock(
            return_value=httpx.Response(200, text=_ARTICLE_HTML)
        )

        docs = await crawl_target(target, known_urls=set())

        # /news/ はすべて禁止 → 取得記事は 0 件
        assert docs == []

    @pytest.mark.asyncio
    @respx.mock
    @_FRESH_CACHE_PATCH
    async def test_crawls_allowed_urls(self, _mock_cache):
        """robots.txt で許可された URL はクロールする。"""
        robots_txt = "User-agent: *\nDisallow: /blocked/"
        target = _target(respect=True, interval=0)

        respx.get("https://www.ibm.com/announcements").mock(
            return_value=httpx.Response(200, text=_INDEX_HTML)
        )
        respx.get("https://www.ibm.com/robots.txt").mock(
            return_value=httpx.Response(200, text=robots_txt)
        )
        respx.get("https://www.ibm.com/news/article-1").mock(
            return_value=httpx.Response(200, text=_ARTICLE_HTML)
        )
        respx.get("https://www.ibm.com/news/article-2").mock(
            return_value=httpx.Response(200, text=_ARTICLE_HTML)
        )

        docs = await crawl_target(target, known_urls=set())

        assert len(docs) == 2

    @pytest.mark.asyncio
    @respx.mock
    @_FRESH_CACHE_PATCH
    async def test_skips_robots_check_when_disabled(self, _mock_cache):
        """respect_robots_txt=False のターゲットは robots.txt を確認しない。"""
        robots_txt = "User-agent: *\nDisallow: /news/"
        target = _target(respect=False, interval=0)

        respx.get("https://www.ibm.com/announcements").mock(
            return_value=httpx.Response(200, text=_INDEX_HTML)
        )
        # robots.txt が呼ばれないはずだが、念のため登録
        robots_route = respx.get("https://www.ibm.com/robots.txt").mock(
            return_value=httpx.Response(200, text=robots_txt)
        )
        respx.get("https://www.ibm.com/news/article-1").mock(
            return_value=httpx.Response(200, text=_ARTICLE_HTML)
        )
        respx.get("https://www.ibm.com/news/article-2").mock(
            return_value=httpx.Response(200, text=_ARTICLE_HTML)
        )

        docs = await crawl_target(target, known_urls=set())

        # respect_robots_txt=False → /news/ は禁止されていてもクロールされる
        assert len(docs) == 2
        # robots.txt へのリクエストは発生しない
        assert robots_route.call_count == 0

    @pytest.mark.asyncio
    @respx.mock
    @_FRESH_CACHE_PATCH
    async def test_respects_request_interval_between_articles(self, _mock_cache):
        """記事クロール間に asyncio.sleep が呼ばれること（インターバル遵守）。"""
        robots_txt = "User-agent: *\nAllow: /"
        target = _target(respect=True, interval=5)

        respx.get("https://www.ibm.com/announcements").mock(
            return_value=httpx.Response(200, text=_INDEX_HTML)
        )
        respx.get("https://www.ibm.com/robots.txt").mock(
            return_value=httpx.Response(200, text=robots_txt)
        )
        respx.get("https://www.ibm.com/news/article-1").mock(
            return_value=httpx.Response(200, text=_ARTICLE_HTML)
        )
        respx.get("https://www.ibm.com/news/article-2").mock(
            return_value=httpx.Response(200, text=_ARTICLE_HTML)
        )

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch(
            "connectors.watson_news.ibm_crawl_connector.asyncio.sleep",
            side_effect=mock_sleep,
        ):
            await crawl_target(target, known_urls=set())

        # 記事が 2 件 → sleep が 2 回、各 5 秒
        assert len(sleep_calls) == 2
        for s in sleep_calls:
            assert s == 5

    @pytest.mark.asyncio
    @respx.mock
    @_FRESH_CACHE_PATCH
    async def test_known_urls_are_skipped(self, _mock_cache):
        """既にインデックス済みの URL はクロールしない（差分検出）。"""
        robots_txt = "User-agent: *\nAllow: /"
        target = _target(respect=True, interval=0)
        known = {"https://www.ibm.com/news/article-1"}

        respx.get("https://www.ibm.com/announcements").mock(
            return_value=httpx.Response(200, text=_INDEX_HTML)
        )
        respx.get("https://www.ibm.com/robots.txt").mock(
            return_value=httpx.Response(200, text=robots_txt)
        )
        # article-1 はスキップ → article-2 のみ取得される
        respx.get("https://www.ibm.com/news/article-2").mock(
            return_value=httpx.Response(200, text=_ARTICLE_HTML)
        )

        docs = await crawl_target(target, known_urls=known)

        assert len(docs) == 1
        assert docs[0].source_url == "https://www.ibm.com/news/article-2"
