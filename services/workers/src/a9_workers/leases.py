"""Job leases.

A worker holds a job by leasing it. `attempts` is the fencing token: every write the holder makes is
conditional on it, so a worker that lost its lease (killed, paused, partitioned) cannot write after a
successor has taken over.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from a9_agents.db import Conn, Pool, scoped
from a9_agents.events import RunClosedError, emit_event
from a9_agents.settings import job_lease_seconds, max_job_attempts
from psycopg.types.json import Jsonb

log = logging.getLogger(__name__)


class LeaseLostError(Exception):
    """Another worker took this job over; stop without writing anything."""


@dataclass(frozen=True)
class Job:
    key: str
    user_id: uuid.UUID
    run_id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    checkpoint: dict[str, Any]
    attempt: int  # the fencing token


async def claim(pool: Pool, key: str) -> Job | None:
    """Take the job if it is queued, or running with a stale heartbeat. None means: not yours."""
    async with scoped(pool, role="a9_worker") as conn:
        cur = await conn.execute(
            """
            UPDATE jobs SET status = 'running', attempts = attempts + 1,
                            heartbeat_at = now(), updated_at = now(), error = NULL
            WHERE job_key = %(key)s AND attempts < %(max)s AND (
                    status = 'queued'
                 OR (status = 'running' AND heartbeat_at < now() - make_interval(secs => %(lease)s)))
            RETURNING user_id, run_id, kind, payload, checkpoint, attempts
            """,
            {"key": key, "max": max_job_attempts(), "lease": job_lease_seconds()},
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return Job(
        key,
        row["user_id"],
        row["run_id"],
        row["kind"],
        row["payload"],
        row["checkpoint"],
        row["attempts"],
    )


async def fence(conn: Conn, job: Job, checkpoint: dict[str, Any] | None = None) -> None:
    """Prove we still hold the lease (and optionally save progress) inside the caller's transaction."""
    cur = await conn.execute(
        """UPDATE jobs SET heartbeat_at = now(), updated_at = now(),
                           checkpoint = COALESCE(%s, checkpoint)
           WHERE job_key = %s AND status = 'running' AND attempts = %s""",
        (Jsonb(checkpoint) if checkpoint is not None else None, job.key, job.attempt),
    )
    if cur.rowcount != 1:
        raise LeaseLostError(job.key)


async def finish(conn: Conn, job: Job, checkpoint: dict[str, Any]) -> None:
    cur = await conn.execute(
        """UPDATE jobs SET status = 'succeeded', checkpoint = %s, updated_at = now()
           WHERE job_key = %s AND status = 'running' AND attempts = %s""",
        (Jsonb(checkpoint), job.key, job.attempt),
    )
    if cur.rowcount != 1:
        raise LeaseLostError(job.key)


async def release_after_error(pool: Pool, job: Job, error: str) -> None:
    """A handler raised: requeue for the reaper to retry (still fenced)."""
    async with scoped(pool, role="a9_worker") as conn:
        await conn.execute(
            """UPDATE jobs SET status = 'queued', error = %s, updated_at = now()
               WHERE job_key = %s AND status = 'running' AND attempts = %s""",
            (error[:2000], job.key, job.attempt),
        )


@contextlib.asynccontextmanager
async def heartbeat(pool: Pool, job: Job) -> AsyncIterator[None]:
    """Keep the lease fresh while a long step runs."""
    interval = max(job_lease_seconds() / 3, 0.2)

    async def beat() -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                async with scoped(pool, role="a9_worker") as conn:
                    await fence(conn, job)
            except LeaseLostError:
                return
            except Exception:
                log.warning("heartbeat failed for %s", job.key, exc_info=True)

    task = asyncio.create_task(beat())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def fail_exhausted(pool: Pool, key: str) -> None:
    """Out of attempts: fail the job and the run, visibly. Never leave it parked forever."""
    async with scoped(pool, role="a9_worker") as conn:
        cur = await conn.execute(
            """UPDATE jobs SET status = 'failed', error = COALESCE(error, 'attempts exhausted'),
                              updated_at = now()
               WHERE job_key = %s AND status IN ('queued', 'running') AND attempts >= %s
               RETURNING run_id, error""",
            (key, max_job_attempts()),
        )
        row = await cur.fetchone()
        if row is not None:
            with contextlib.suppress(RunClosedError):
                await emit_event(conn, row["run_id"], {"type": "run_failed", "error": row["error"]})
