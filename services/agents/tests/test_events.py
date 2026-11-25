"""Event writing and job keys: gapless seq, contract enforced at the write, closed runs stay closed."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import psycopg
import pytest
from a9_agents.db import Conn
from a9_agents.events import RunClosedError, emit_event, events_since
from a9_agents.jobkeys import job_key
from a9_agents.runs import create_job, create_run
from psycopg.rows import dict_row
from pydantic import ValidationError


@pytest.fixture()
async def conn(migrated_url: str) -> AsyncIterator[Conn]:
    async with await psycopg.AsyncConnection.connect(migrated_url, row_factory=dict_row) as c:
        yield c
        await c.rollback()


async def _id(conn: Conn, sql: str, *params: object) -> uuid.UUID:
    row = await (await conn.execute(sql, params)).fetchone()
    assert row is not None
    return uuid.UUID(str(row["id"]))


async def new_run(conn: Conn) -> tuple[uuid.UUID, uuid.UUID]:
    user = await _id(
        conn, "INSERT INTO users (email) VALUES (%s) RETURNING id", f"{uuid.uuid4()}@x.org"
    )
    project = await _id(
        conn, "INSERT INTO projects (user_id, name) VALUES (%s, 'p') RETURNING id", user
    )
    conversation = await _id(
        conn,
        "INSERT INTO conversations (user_id, project_id) VALUES (%s, %s) RETURNING id",
        user,
        project,
    )
    run = await create_run(conn, user_id=user, conversation_id=conversation, kind="ingest")
    return user, run


async def test_seq_is_gapless_and_monotonic(conn: Conn) -> None:
    _, run = await new_run(conn)
    events = [
        await emit_event(conn, run, {"type": "stage_started", "stage": "s"}),
        await emit_event(conn, run, {"type": "progress", "stage": "s", "done": 1, "total": 2}),
        await emit_event(
            conn, run, {"type": "partial_result", "stage": "s", "payload": {"kept": 3}}
        ),
    ]
    assert [e["seq"] for e in events] == [1, 2, 3]
    stored = await events_since(conn, run, 1)
    assert [e["seq"] for e in stored] == [2, 3]  # replay is strictly after the given seq


async def test_status_follows_events_and_a_closed_run_refuses_more(
    conn: Conn,
) -> None:
    _, run = await new_run(conn)

    async def status() -> str:
        row = await (await conn.execute("SELECT status FROM runs WHERE id = %s", (run,))).fetchone()
        assert row is not None
        return str(row["status"])

    assert await status() == "queued"
    await emit_event(conn, run, {"type": "stage_started", "stage": "plan"})
    assert await status() == "running"
    await emit_event(
        conn, run, {"type": "needs_input", "stage": "plan", "question": {"kind": "approve_plan"}}
    )
    assert await status() == "needs_input"
    await emit_event(conn, run, {"type": "progress", "stage": "search", "done": 0, "total": None})
    assert await status() == "running"  # the answer resumed the same run
    await emit_event(
        conn,
        run,
        {"type": "run_finished", "coverage_notes": [{"source": "arxiv", "reason": "timeout"}]},
    )
    assert await status() == "finished"
    with pytest.raises(RunClosedError):
        await emit_event(conn, run, {"type": "progress", "stage": "x", "done": 1, "total": 1})


async def test_invalid_event_is_rejected_before_it_consumes_a_seq(
    conn: Conn,
) -> None:
    _, run = await new_run(conn)
    with pytest.raises(ValidationError):
        async with conn.transaction():
            await emit_event(conn, run, {"type": "progress", "stage": "s"})  # missing done/total
    ok = await emit_event(conn, run, {"type": "stage_started", "stage": "s"})
    assert ok["seq"] == 1


async def test_run_failed_carries_the_error(conn: Conn) -> None:
    _, run = await new_run(conn)
    event = await emit_event(conn, run, {"type": "run_failed", "error": "database lost"})
    assert event["error"] == "database lost"


def test_job_key_is_deterministic_and_input_sensitive() -> None:
    a = job_key("search", source="europe_pmc", plan="p1", page=1)
    assert a == job_key("search", page=1, plan="p1", source="europe_pmc")  # order never matters
    assert a != job_key("search", source="europe_pmc", plan="p1", page=2)
    assert a != job_key("fetch", source="europe_pmc", plan="p1", page=1)
    assert a.startswith("search:")


async def test_creating_the_same_job_twice_is_a_no_op(conn: Conn) -> None:
    user, run = await new_run(conn)
    k1, created1 = await create_job(
        conn, user_id=user, run_id=run, kind="dummy_pipeline", payload={"steps": 10}
    )
    k2, created2 = await create_job(
        conn, user_id=user, run_id=run, kind="dummy_pipeline", payload={"steps": 10}
    )
    assert (k1 == k2, created1, created2) == (True, True, False)
