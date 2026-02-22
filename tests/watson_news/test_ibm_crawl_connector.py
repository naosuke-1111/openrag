"""Unit tests for IbmCrawlConnector helpers."""

import pytest

from connectors.watson_news.ibm_crawl_connector import (
    CrawlTarget,
    _extract_article_urls,
)


SAMPLE_HTML = """
<html>
<head><title>IBM Announcements</title></head>
<body>
  <a href="/new/announcements/2026/ibm-ai-launch">IBM AI Launch</a>
  <a href="/new/announcements/2026/ibm-cloud">IBM Cloud</a>
  <a href="https://external.com/other">External link</a>
  <a href="/new/announcements/2026/ibm-ai-launch">IBM AI Launch duplicate</a>
</body>
</html>
"""


def test_extract_article_urls_filters_external_and_deduplicates():
    base_url = "https://www.ibm.com/new/announcements"
    urls = _extract_article_urls(SAMPLE_HTML, base_url, selector=None)

    # External URL should be excluded
    assert not any("external.com" in u for u in urls)
    # Duplicates should be removed
    ibm_ai_urls = [u for u in urls if "ibm-ai-launch" in u]
    assert len(ibm_ai_urls) == 1
    # Internal IBM URLs should be present
    assert any("ibm-cloud" in u for u in urls)


def test_extract_article_urls_with_custom_selector():
    html = """
    <html><body>
      <a class="article-link" href="/announcements/a">Article A</a>
      <a href="/announcements/b">Not matched</a>
    </body></html>
    """
    base_url = "https://www.ibm.com"
    urls = _extract_article_urls(html, base_url, selector="a.article-link")
    assert len(urls) == 1
    assert "/announcements/a" in urls[0]


def _make_target(**kwargs) -> CrawlTarget:
    defaults = dict(
        name="test",
        index_url="https://www.ibm.com/new/announcements",
        language="en",
        site_category="announcements",
        interval_hours=2,
    )
    defaults.update(kwargs)
    return CrawlTarget(**defaults)


def test_crawl_target_defaults():
    t = _make_target()
    assert t.enabled is True
    assert t.respect_robots_txt is True
    assert t.max_articles_per_run == 100
    assert t.request_interval_seconds == 5
