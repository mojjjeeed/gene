"""A ten-step dummy pipeline used to prove the event stream, resume and replay end to end.

Each step writes its event and its checkpoint in ONE transaction, fenced on the lease. So after a
kill the successor resumes at the first unrecorded step, and no event is lost or duplicated.
"""

from __future__ import annotations

import asyncio
from typing import Any

from a9_agents.db import Pool, scoped
from a9_agents.events import emit_event
from a9_agents.pubsub import notify
from redis.asyncio import Redis

from a9_workers.leases import Job, fence, finish

STAGE = "dummy"


async def run(pool: Pool, redis: Redis | None, job: Job) -> None:
    steps = int(job.payload.get("steps", 10))
    delay = float(job.payload.get("step_delay", 0.5))
    checkpoint: dict[str, Any] = dict(job.checkpoint)

    if checkpoint.get("done"):
        return

    if not checkpoint.get("started"):
        checkpoint = {"started": True, "next_step": 0}
        async with scoped(pool, role="a9_worker") as conn:
            await fence(conn, job, checkpoint)
            event = await emit_event(conn, job.run_id, {"type": "stage_started", "stage": STAGE})
        await notify(redis, job.run_id, event["seq"])

    for i in range(int(checkpoint["next_step"]), steps):
        await asyncio.sleep(delay)  # stands in for real work
        checkpoint = {"started": True, "next_step": i + 1}
        async with scoped(pool, role="a9_worker") as conn:
            await fence(conn, job, checkpoint)
            event = await emit_event(
                conn,
                job.run_id,
                {"type": "progress", "stage": STAGE, "done": i + 1, "total": steps},
            )
        await notify(redis, job.run_id, event["seq"])

    async with scoped(pool, role="a9_worker") as conn:
        checkpoint = {"started": True, "next_step": steps, "done": True}
        await finish(conn, job, checkpoint)
        await emit_event(conn, job.run_id, {"type": "stage_finished", "stage": STAGE})
        cur = await conn.execute("SELECT coverage_notes FROM runs WHERE id = %s", (job.run_id,))
        row = await cur.fetchone()
        assert row is not None
        last = await emit_event(
            conn, job.run_id, {"type": "run_finished", "coverage_notes": row["coverage_notes"]}
        )
    await notify(redis, job.run_id, last["seq"])
