"""Screening verdicts. A user's override is a SECOND row beside the model's, never an overwrite,
so the model's call stays visible and an override can be undone."""

from __future__ import annotations

import uuid
from typing import Any

from a9_contracts.screening_verdict import ScreeningVerdict

from a9_agents.db import Conn

COUNT_KEYS = ("include", "exclude", "unsure", "unscreened")


async def save_model_verdict(
    conn: Conn,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    paper_id: uuid.UUID,
    verdict: ScreeningVerdict,
) -> None:
    await conn.execute(
        """INSERT INTO screening_verdicts (user_id, conversation_id, paper_id, verdict, reason, decided_by, model)
           VALUES (%s, %s, %s, %s, %s, 'model', %s)
           ON CONFLICT (conversation_id, paper_id, decided_by) DO NOTHING""",
        (user_id, conversation_id, paper_id, verdict.verdict.value, verdict.reason, verdict.model),
    )


async def set_user_verdict(
    conn: Conn,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    paper_id: uuid.UUID,
    verdict: str,
    reason: str,
) -> None:
    await conn.execute(
        """INSERT INTO screening_verdicts (user_id, conversation_id, paper_id, verdict, reason, decided_by)
           VALUES (%s, %s, %s, %s, %s, 'user')
           ON CONFLICT (conversation_id, paper_id, decided_by)
           DO UPDATE SET verdict = EXCLUDED.verdict, reason = EXCLUDED.reason, created_at = now()""",
        (user_id, conversation_id, paper_id, verdict, reason),
    )


async def clear_user_verdict(
    conn: Conn, *, conversation_id: uuid.UUID, paper_id: uuid.UUID
) -> bool:
    cur = await conn.execute(
        "DELETE FROM screening_verdicts WHERE conversation_id = %s AND paper_id = %s AND decided_by = 'user'",
        (conversation_id, paper_id),
    )
    return cur.rowcount == 1


async def paper_verdicts(
    conn: Conn, conversation_id: uuid.UUID, paper_id: uuid.UUID
) -> dict[str, Any]:
    cur = await conn.execute(
        "SELECT decided_by, verdict, reason, model FROM screening_verdicts WHERE conversation_id = %s AND paper_id = %s",
        (conversation_id, paper_id),
    )
    by = {r["decided_by"]: dict(r) for r in await cur.fetchall()}
    effective = by.get("user") or by.get("model")
    return {
        "paper_id": str(paper_id),
        "effective": effective["verdict"] if effective else "unscreened",
        "user": by.get("user"),
        "model": by.get("model"),
    }


async def run_counts(conn: Conn, run_id: uuid.UUID, conversation_id: uuid.UUID) -> dict[str, int]:
    """What was kept and what was cut, for the papers this run found. A user's verdict wins."""
    cur = await conn.execute(
        """SELECT COALESCE(u.verdict, m.verdict, 'unscreened') AS v, count(*) AS n
           FROM (SELECT DISTINCT paper_id FROM source_records WHERE run_id = %(run)s AND paper_id IS NOT NULL) rp
           LEFT JOIN screening_verdicts m ON m.conversation_id = %(conv)s AND m.paper_id = rp.paper_id AND m.decided_by = 'model'
           LEFT JOIN screening_verdicts u ON u.conversation_id = %(conv)s AND u.paper_id = rp.paper_id AND u.decided_by = 'user'
           GROUP BY 1""",
        {"run": run_id, "conv": conversation_id},
    )
    counts = dict.fromkeys(COUNT_KEYS, 0)
    for row in await cur.fetchall():
        counts[row["v"]] = row["n"]
    return counts
