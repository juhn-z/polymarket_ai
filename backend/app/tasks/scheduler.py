"""APScheduler job registration (PRD §6).

Jobs run inside the single FastAPI process via ``AsyncIOScheduler``.
Each job callable is a thin wrapper that opens its own DB session and
constructs the required services — this keeps the scheduler independent
of the FastAPI dependency graph.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger("scheduler")

JobFn = Callable[[], Awaitable[None]]


def register_jobs(
    scheduler: AsyncIOScheduler,
    *,
    scan: JobFn,
    aggregate: JobFn,
    predict: JobFn,
    generate: JobFn,
    execute: JobFn,
    snapshot: JobFn,
    health: JobFn,
) -> None:
    scheduler.add_job(scan, CronTrigger(hour=0, minute=0), id="market_scan")
    scheduler.add_job(aggregate, CronTrigger(hour=1, minute=0), id="data_aggregate")
    scheduler.add_job(predict, CronTrigger(hour=2, minute=0), id="ai_predict")
    scheduler.add_job(generate, CronTrigger(hour=2, minute=30), id="strategy_gen")
    scheduler.add_job(execute, CronTrigger(hour=3, minute=0), id="trade_execute")
    scheduler.add_job(snapshot, CronTrigger(minute=0), id="vault_snapshot")
    scheduler.add_job(health, CronTrigger(minute="*/5"), id="health_check")


async def safe(fn: JobFn, name: str) -> None:
    """Wrap a job to catch and log errors instead of killing the scheduler."""
    try:
        await fn()
    except Exception as exc:  # pragma: no cover
        log.exception("job %s failed: %s", name, exc)
