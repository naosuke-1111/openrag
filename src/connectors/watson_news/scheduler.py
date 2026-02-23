"""Watson News ETL ジョブ向け APScheduler ベースのスケジューラー。

登録されるジョブ:
- GDELT 取得ジョブ（15分ごと）
- IBM クロールジョブ（ibm_crawl_targets.yaml に定義された対象ごと、間隔はファイルに準拠）
- Box 差分取得 + クリーニング / エンリッチ / インデックス登録（1時間ごと）
"""

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from connectors.watson_news.etl_pipeline import run_gdelt_pipeline, run_ibm_crawl_pipeline
from connectors.watson_news.ibm_crawl_connector import load_crawl_targets, crawl_target
from utils.logging_config import get_logger

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


# ---------------------------------------------------------------------------
# ジョブラッパー（APScheduler に必要な sync → async ブリッジ）
# ---------------------------------------------------------------------------

def _run_gdelt() -> None:
    asyncio.get_event_loop().run_until_complete(run_gdelt_pipeline())


def _run_ibm_crawl() -> None:
    asyncio.get_event_loop().run_until_complete(run_ibm_crawl_pipeline())


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def register_jobs(scheduler: AsyncIOScheduler | None = None) -> AsyncIOScheduler:
    """全 Watson News ETL ジョブをスケジューラーに登録する。

    Args:
        scheduler: 既存の :class:`AsyncIOScheduler` インスタンス。
            指定しない場合は新規作成される。

    Returns:
        スケジューラー（開始済みまたは渡されたもの）。
    """
    sched = scheduler or _get_scheduler()

    # GDELT — 固定 15分間隔
    sched.add_job(
        run_gdelt_pipeline,
        trigger=IntervalTrigger(minutes=15),
        id="watson_news_gdelt",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    logger.info("Registered GDELT job", interval="15min")

    # IBM クロール — YAML 設定から動的にジョブを生成
    try:
        targets = load_crawl_targets()
    except Exception as exc:
        logger.warning("Could not load crawl targets, IBM crawl jobs not registered", error=str(exc))
        targets = []

    for target in targets:
        sched.add_job(
            run_ibm_crawl_pipeline,
            trigger=IntervalTrigger(hours=target.interval_hours),
            id=f"watson_news_ibm_crawl_{target.name}",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=600,
        )
        logger.info(
            "Registered IBM crawl job",
            target=target.name,
            interval_hours=target.interval_hours,
        )

    return sched


def start_scheduler() -> AsyncIOScheduler:
    """スケジューラーを作成、設定、起動する。"""
    sched = _get_scheduler()
    register_jobs(sched)
    if not sched.running:
        sched.start()
        logger.info("Watson News scheduler started")
    return sched


def stop_scheduler() -> None:
    """スケジューラーが実行中であれば停止する。"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Watson News scheduler stopped")
    _scheduler = None
