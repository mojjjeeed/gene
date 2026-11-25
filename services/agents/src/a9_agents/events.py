"""Writing run events.

An event is inserted in the same transaction as the state change it reports. seq comes from
runs.last_seq (bumped atomically), so it is gapless and monotonic per run. A closed run refuses
further events, which keeps a zombie worker from writing after the run has finished.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from a9_contracts.run_event import RunEvent
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from a9_agents.db import Conn

_ADAPTER: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)

_RUN_STATUS_AFTER = {
    "needs_input": "needs_input",
    "run_failed": "failed",
    "run_finished": "finished",
}


class RunClosedError(Exception):
    """The run is already finished or failed; no more events can be written."""


async def emit_event(conn: Conn, run_id: uuid.UUID, body: dict[str, Any]) -> dict[str, Any]:
    """Append one event. `body` has `type` and the type's own fields; the envelope is added here."""
    event_type = str(body["type"])
    cur = await conn.execute(
        """
        UPDATE runs SET
          last_seq = last_seq + 1,
          updated_at = now(),
          status = CASE WHEN %(new)s::text IS NOT NULL THEN %(new)s::text ELSE 'running' END
        WHERE id = %(id)s AND status NOT IN ('failed', 'finished')
        RETURNING last_seq, user_id, trace_id
        """,
        {"new": _RUN_STATUS_AFTER.get(event_type), "id": run_id},
    )
    row = await cur.fetchone()
    if row is None:
        raise RunClosedError(f"run {run_id} is closed or does not exist")

    envelope: dict[str, Any] = {
        "run_id": str(run_id),
        "seq": row["last_seq"],
        "ts": datetime.now(UTC).isoformat(),
        **body,
    }
    if row["trace_id"]:
        envelope["trace_id"] = row["trace_id"]
    event = _ADAPTER.validate_python(envelope)  # the contract is enforced at the write
    data: dict[str, Any] = event.model_dump(mode="json", exclude_none=True)
    await conn.execute(
        "INSERT INTO run_events (run_id, seq, user_id, type, data) VALUES (%s, %s, %s, %s, %s)",
        (run_id, data["seq"], row["user_id"], data["type"], Jsonb(data)),
    )
    return data


async def events_since(
    conn: Conn, run_id: uuid.UUID, last_seq: int, limit: int = 500
) -> list[dict[str, Any]]:
    cur = await conn.execute(
        "SELECT data FROM run_events WHERE run_id = %s AND seq > %s ORDER BY seq LIMIT %s",
        (run_id, last_seq, limit),
    )
    return [r["data"] for r in await cur.fetchall()]
