"""Arq worker: runs jobs by kind, and reaps jobs whose worker died.

Run with:  arq a9_workers.worker.WorkerSettings
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from a9_agents.db import Pool, open_pool, scoped
from a9_agents.plan_graph import build_plan_graph
from a9_agents.planner import make_planner
from a9_agents.settings import database_dsn, job_lease_seconds, queue_name, redis_url
from a9_agents.sources.registry import build_sources
from arq import cron
from arq.connections import RedisSettings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from redis.asyncio import Redis

from a9_workers.handlers import dummy, plan
from a9_workers.leases import (
    Job,
    LeaseLostError,
    claim,
    fail_exhausted,
    heartbeat,
    release_after_error,
)

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any], Job], Awaitable[None]]
HANDLERS: dict[str, Handler] = {
    "dummy_pipeline": dummy.run,
    "plan_pipeline": plan.start,
    "resume_plan": plan.resume,
}


async def startup(ctx: dict[str, Any]) -> None:
    ctx["pool"] = await open_pool()
    ctx["pubsub_redis"] = Redis.from_url(redis_url())
    # LangGraph's checkpointer needs autocommit connections; it manages its own tables.
    ctx["checkpoint_pool"] = AsyncConnectionPool(
        database_dsn(),
        min_size=1,
        max_size=4,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await ctx["checkpoint_pool"].open(wait=True, timeout=10)
    saver = AsyncPostgresSaver(ctx["checkpoint_pool"])
    await saver.setup()
    ctx["plan_graph"] = build_plan_graph(
        pool=ctx["pool"],
        redis=ctx["pubsub_redis"],
        planner=make_planner(),
        sources=build_sources(),
        source_limit=int(os.environ.get("A9_SOURCE_LIMIT", "100")),
    ).compile(checkpointer=saver)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["checkpoint_pool"].close()
    await ctx["pubsub_redis"].aclose()
    await ctx["pool"].close()


async def run_job(ctx: dict[str, Any], key: str) -> str:
    """Claim the job by its deterministic key and run it. Safe to call any number of times."""
    pool: Pool = ctx["pool"]
    job = await claim(pool, key)
    if job is None:
        return "skipped"  # done already, or someone else holds a live lease
    handler = HANDLERS.get(job.kind)
    if handler is None:
        await release_after_error(pool, job, f"no handler for job kind {job.kind!r}")
        return "no_handler"
    try:
        async with heartbeat(pool, job):
            await handler(ctx, job)
    except LeaseLostError:
        log.warning("lost lease on %s; stopping", key)
        return "lease_lost"
    except Exception as exc:
        log.exception("job %s failed on attempt %s", key, job.attempt)
        await release_after_error(pool, job, f"{type(exc).__name__}: {exc}")
        return "error"
    return "ok"


async def reap_stale_jobs(ctx: dict[str, Any]) -> int:
    """Re-enqueue jobs that are queued but idle, or running with an expired lease."""
    pool: Pool = ctx["pool"]
    lease = job_lease_seconds()
    async with scoped(pool, role="a9_worker") as conn:
        cur = await conn.execute(
            """SELECT job_key, attempts FROM jobs
               WHERE (status = 'running' AND heartbeat_at < now() - make_interval(secs => %(lease)s))
                  OR (status = 'queued' AND updated_at < now() - make_interval(secs => %(lease)s))""",
            {"lease": lease},
        )
        stale = await cur.fetchall()
    requeued = 0
    for row in stale:
        # A distinct arq id per attempt; the claim, not arq, is what makes this idempotent.
        queued = await ctx["redis"].enqueue_job(
            "run_job",
            row["job_key"],
            _job_id=f"{row['job_key']}#{row['attempts']}",
            _queue_name=queue_name(),
        )
        requeued += queued is not None
        await fail_exhausted(pool, row["job_key"])
    return requeued


_REAP_EVERY = max(int(os.environ.get("A9_REAP_INTERVAL_SECONDS", "5")), 1)


class WorkerSettings:
    functions = [run_job]
    cron_jobs = [cron(reap_stale_jobs, second=set(range(0, 60, _REAP_EVERY)), run_at_startup=True)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(redis_url())
    queue_name = queue_name()
    max_tries = 1  # retries are ours (lease + reaper), not arq's
    keep_result = 0
    job_timeout = 3600
    allow_abort_jobs = False
