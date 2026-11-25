"""Planning jobs: start the graph, and resume it after the user approves.

The graph's state is in the Postgres checkpointer under the run's thread id. Both handlers look at
that state first, so a retry after a crash, or a duplicate resume, does the minimum and nothing twice.
"""

from __future__ import annotations

from typing import Any

from a9_agents.db import Pool, scoped
from langgraph.types import Command

from a9_workers.leases import Job, finish


def _config(job: Job) -> dict[str, Any]:
    return {"configurable": {"thread_id": job.payload["thread_id"]}}


async def _done(ctx: dict[str, Any], job: Job) -> None:
    pool: Pool = ctx["pool"]
    async with scoped(pool, role="a9_worker") as conn:
        await finish(conn, job, {"done": True})


async def start(ctx: dict[str, Any], job: Job) -> None:
    graph = ctx["plan_graph"]
    config = _config(job)
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        await graph.ainvoke(
            {
                "run_id": str(job.run_id),
                "user_id": str(job.user_id),
                "conversation_id": job.payload["conversation_id"],
                "topic": job.payload["topic"],
            },
            config,
        )
    elif snapshot.next and not any(t.interrupts for t in snapshot.tasks):
        await graph.ainvoke(
            None, config
        )  # a previous attempt died part-way: continue from its checkpoint
    await _done(ctx, job)


async def resume(ctx: dict[str, Any], job: Job) -> None:
    graph = ctx["plan_graph"]
    config = _config(job)
    snapshot = await graph.aget_state(config)
    answer = {"plan_id": job.payload["plan_id"], "version": job.payload["version"]}
    if any(t.interrupts for t in snapshot.tasks):
        await graph.ainvoke(Command(resume=answer), config)
    elif snapshot.next:
        await graph.ainvoke(
            None, config
        )  # already past the interrupt; a previous attempt died after it
    await _done(ctx, job)
