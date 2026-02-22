"""APScheduler-based scheduler for Watson News ETL jobs.

Registers:
- GDELT fetch job (every 15 minutes)
- IBM crawl jobs (one per target, interval from ibm_crawl_targets.yaml)
- Box diff-fetch + clean/enrich/index (every 1 hour)
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
# Job wrappers (sync → async bridge required by APScheduler)
# ---------------------------------------------------------------------------

def _run_gdelt() -> None:
    asyncio.get_event_loop().run_until_complete(run_gdelt_pipeline())


def _run_ibm_crawl() -> None:
    asyncio.get_event_loop().run_until_complete(run_ibm_crawl_pipeline())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_jobs(scheduler: AsyncIOScheduler | None = None) -> AsyncIOScheduler:
    """Register all Watson News ETL jobs with the scheduler.

    Args:
        scheduler: Existing :class:`AsyncIOScheduler` instance.  A new one is
            created if not provided.

    Returns:
        The scheduler (started or passed in).
    """
    sched = scheduler or _get_scheduler()

    # GDELT — fixed 15-minute interval
    sched.add_job(
        run_gdelt_pipeline,
        trigger=IntervalTrigger(minutes=15),
        id="watson_news_gdelt",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    logger.info("Registered GDELT job", interval="15min")

    # IBM Crawl — dynamic jobs from YAML config
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
    """Create, configure, and start the scheduler."""
    sched = _get_scheduler()
    register_jobs(sched)
    if not sched.running:
        sched.start()
        logger.info("Watson News scheduler started")
    return sched


def stop_scheduler() -> None:
    """Stop the scheduler if running."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Watson News scheduler stopped")
    _scheduler = None
