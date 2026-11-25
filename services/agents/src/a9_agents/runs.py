"""Creating runs and jobs."""

from __future__ import annotations

import uuid
from typing import Any

from psycopg.types.json import Jsonb

from a9_agents.db import Conn
from a9_agents.jobkeys import job_key


async def create_run(
    conn: Conn,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    kind: str,
    trace_id: str | None = None,
) -> uuid.UUID:
    cur = await conn.execute(
        "INSERT INTO runs (user_id, conversation_id, kind, trace_id) VALUES (%s, %s, %s, %s) RETURNING id",
        (user_id, conversation_id, kind, trace_id),
    )
    row = await cur.fetchone()
    assert row is not None
    return uuid.UUID(str(row["id"]))


async def create_job(
    conn: Conn,
    *,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
    kind: str,
    payload: dict[str, Any],
) -> tuple[str, bool]:
    """Insert a job under its deterministic key. Returns (job_key, created); a repeat is a no-op."""
    key = job_key(kind, run_id=str(run_id), **payload)
    cur = await conn.execute(
        """INSERT INTO jobs (user_id, run_id, job_key, kind, payload) VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (job_key) DO NOTHING""",
        (user_id, run_id, key, kind, Jsonb(payload)),
    )
    return key, cur.rowcount == 1
