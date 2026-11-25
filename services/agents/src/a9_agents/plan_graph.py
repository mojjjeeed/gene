"""The ingest graph so far: plan -> request approval -> (interrupt) -> finish plan -> search -> conclude.

State lives in LangGraph's Postgres checkpointer, keyed by the run's thread id, so the run parks at
the interrupt and any later request, from any device, can resume the same thread. Nodes are idempotent
per run (checked against run_events), so a worker that dies mid-node and is replaced cannot emit
duplicate events or create a second plan.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from redis.asyncio import Redis

from a9_agents.db import Conn, Pool, scoped
from a9_agents.events import emit_event
from a9_agents.planner import Planner
from a9_agents.plans import create_next_version, get_plan
from a9_agents.pubsub import notify
from a9_agents.sources.base import LiteratureSource
from a9_agents.sources.fanout import SourceReport, search_all

STAGE = "plan"
SEARCH = "search"


class PlanState(TypedDict, total=False):
    run_id: str
    user_id: str
    conversation_id: str
    topic: str
    plan_id: str
    version: int
    approved_plan_id: str
    approved_version: int


async def _marker(conn: Conn, run_id: uuid.UUID, contains: dict[str, Any]) -> dict[str, Any] | None:
    from psycopg.types.json import Jsonb

    cur = await conn.execute(
        "SELECT data FROM run_events WHERE run_id = %s AND data @> %s ORDER BY seq LIMIT 1",
        (run_id, Jsonb(contains)),
    )
    row = await cur.fetchone()
    return None if row is None else dict(row["data"])


async def _source_events(conn: Conn, run_id: uuid.UUID) -> list[dict[str, Any]]:
    from psycopg.types.json import Jsonb

    cur = await conn.execute(
        "SELECT data FROM run_events WHERE run_id = %s AND data @> %s ORDER BY seq",
        (run_id, Jsonb({"type": "partial_result", "payload": {"event": "source_done"}})),
    )
    return [dict(r["data"]) for r in await cur.fetchall()]


def build_plan_graph(
    *,
    pool: Pool,
    redis: Redis | None,
    planner: Planner,
    sources: Sequence[LiteratureSource] = (),
    source_limit: int = 100,
    source_timeout: float = 120.0,
) -> StateGraph[PlanState]:
    async def plan(state: PlanState) -> PlanState:
        run_id, user_id = uuid.UUID(state["run_id"]), uuid.UUID(state["user_id"])
        conversation_id = uuid.UUID(state["conversation_id"])
        async with scoped(pool, role="a9_worker") as conn:
            done = await _marker(
                conn, run_id, {"type": "partial_result", "payload": {"event": "plan_created"}}
            )
        if done is not None:  # this run already created its plan; never call the model twice
            return {"plan_id": done["payload"]["plan_id"], "version": done["payload"]["version"]}

        proposed = await planner.plan(state["topic"])
        async with scoped(pool, role="a9_worker") as conn:
            record = await create_next_version(
                conn, user_id=user_id, conversation_id=conversation_id, plan=proposed
            )
            await emit_event(conn, run_id, {"type": "stage_started", "stage": STAGE})
            last = await emit_event(
                conn,
                run_id,
                {
                    "type": "partial_result",
                    "stage": STAGE,
                    "payload": {
                        "event": "plan_created",
                        "plan_id": str(record.id),
                        "version": record.version,
                        "generated_by": proposed.generated_by.value,
                    },
                },
            )
        await notify(redis, run_id, last["seq"])
        return {"plan_id": str(record.id), "version": record.version}

    async def request_approval(state: PlanState) -> PlanState:
        run_id = uuid.UUID(state["run_id"])
        question = {
            "kind": "approve_plan",
            "plan_id": state["plan_id"],
            "version": state["version"],
        }
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(
                conn, run_id, {"type": "needs_input", "question": {"plan_id": state["plan_id"]}}
            ):
                return {}
            event = await emit_event(
                conn, run_id, {"type": "needs_input", "stage": STAGE, "question": question}
            )
        await notify(redis, run_id, event["seq"])
        return {}

    async def wait_for_approval(state: PlanState) -> PlanState:
        # Parks the run. The resume value is whatever the approval job passes back in.
        answer = interrupt({"kind": "approve_plan", "plan_id": state["plan_id"]})
        return {"approved_plan_id": answer["plan_id"], "approved_version": answer["version"]}

    async def finish_plan(state: PlanState) -> PlanState:
        run_id = uuid.UUID(state["run_id"])
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": STAGE}):
                return {}
            await emit_event(
                conn,
                run_id,
                {
                    "type": "partial_result",
                    "stage": STAGE,
                    "payload": {
                        "event": "plan_approved",
                        "plan_id": state["approved_plan_id"],
                        "version": state["approved_version"],
                    },
                },
            )
            event = await emit_event(conn, run_id, {"type": "stage_finished", "stage": STAGE})
        await notify(redis, run_id, event["seq"])
        return {}

    async def search(state: PlanState) -> PlanState:
        """Query every source at once; each result is staged and reported as it lands."""
        from psycopg.types.json import Jsonb

        run_id, user_id = uuid.UUID(state["run_id"]), uuid.UUID(state["user_id"])
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": SEARCH}):
                return {}
            record = await get_plan(conn, uuid.UUID(state["approved_plan_id"]))
            assert record is not None, "the approved plan disappeared"
            if not await _marker(conn, run_id, {"type": "stage_started", "stage": SEARCH}):
                event = await emit_event(conn, run_id, {"type": "stage_started", "stage": SEARCH})
                await notify(redis, run_id, event["seq"])
            done = {e["payload"]["source"] for e in await _source_events(conn, run_id)}

        pending = [s for s in sources if s.name not in done]
        finished = len(done)

        async def on_source_done(report: SourceReport, records: list[Any]) -> None:
            nonlocal finished
            async with scoped(pool, role="a9_worker") as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """INSERT INTO source_records (run_id, user_id, source, source_id, record)
                           VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                        [
                            (
                                run_id,
                                user_id,
                                r.source.value,
                                r.source_id,
                                Jsonb(r.model_dump(mode="json")),
                            )
                            for r in records
                        ],
                    )
                finished += 1
                await emit_event(
                    conn,
                    run_id,
                    {"type": "progress", "stage": SEARCH, "done": finished, "total": len(sources)},
                )
                event = await emit_event(
                    conn,
                    run_id,
                    {
                        "type": "partial_result",
                        "stage": SEARCH,
                        "payload": {
                            "event": "source_done",
                            "source": report.source,
                            "count": report.count,
                            "partial_reason": report.partial_reason,
                            "error": report.error,
                        },
                    },
                )
            await notify(redis, run_id, event["seq"])

        if pending:
            await search_all(
                pending, record.plan, limit=source_limit, per_source_timeout=source_timeout,
                on_source_done=on_source_done,
            )  # fmt: skip

        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": SEARCH}):
                return {}
            notes = [
                {
                    "source": e["payload"]["source"],
                    "reason": e["payload"]["error"] or e["payload"]["partial_reason"],
                }
                for e in await _source_events(conn, run_id)
                if e["payload"]["error"] or e["payload"]["partial_reason"]
            ]
            if not sources:
                notes.append(
                    {"source": "all sources", "reason": "no literature sources are configured"}
                )
            await conn.execute(
                "UPDATE runs SET coverage_notes = %s WHERE id = %s", (Jsonb(notes), run_id)
            )
            event = await emit_event(conn, run_id, {"type": "stage_finished", "stage": SEARCH})
        await notify(redis, run_id, event["seq"])
        return {}

    async def conclude(state: PlanState) -> PlanState:
        run_id = uuid.UUID(state["run_id"])
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "run_finished"}):
                return {}
            cur = await conn.execute("SELECT coverage_notes FROM runs WHERE id = %s", (run_id,))
            row = await cur.fetchone()
            assert row is not None
            event = await emit_event(
                conn, run_id, {"type": "run_finished", "coverage_notes": row["coverage_notes"]}
            )
        await notify(redis, run_id, event["seq"])
        return {}

    builder: StateGraph[PlanState] = StateGraph(PlanState)
    builder.add_node("plan", plan)
    builder.add_node("request_approval", request_approval)
    builder.add_node("wait_for_approval", wait_for_approval)
    builder.add_node("finish_plan", finish_plan)
    builder.add_node("search", search)
    builder.add_node("conclude", conclude)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "request_approval")
    builder.add_edge("request_approval", "wait_for_approval")
    builder.add_edge("wait_for_approval", "finish_plan")
    builder.add_edge("finish_plan", "search")
    builder.add_edge("search", "conclude")
    builder.add_edge("conclude", END)
    return builder
