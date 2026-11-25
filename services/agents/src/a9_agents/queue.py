"""Enqueue a job for the workers. Best effort: if Redis is down the row stays queued and the reaper
re-enqueues it, so a failure here costs latency, never the job."""

from __future__ import annotations

import logging

from arq.connections import ArqRedis

log = logging.getLogger(__name__)


async def enqueue(arq: ArqRedis | None, key: str) -> None:
    if arq is None:
        return
    try:
        await arq.enqueue_job("run_job", key, _job_id=key)
    except Exception:
        log.warning("enqueue failed for %s; the reaper will pick it up", key, exc_info=True)
