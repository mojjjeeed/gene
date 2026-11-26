"""Lexical arm: Postgres full-text over the conversation's chunks (BM25-like ranking via ts_rank_cd).

Scoped by joining chunk_memberships for the conversation; row-level security scopes memberships to the
caller as well, so both layers must agree before a chunk is returned."""

from __future__ import annotations

import re
import uuid

from a9_agents.db import Conn

_STOP = frozenset(
    "a an and are as at be by for from how in is it of on or that the this to was were what which who with does did do about".split()
)


def or_query(text: str) -> str | None:
    """'EGFR T790M resistance?' -> 'egfr | t790m | resistance' (OR, so a long question still matches).
    Only alphanumerics survive, so no input can inject tsquery syntax."""
    terms = [t for t in dict.fromkeys(re.findall(r"[a-z0-9]{2,}", text.lower())) if t not in _STOP]
    return " | ".join(terms) or None


async def lexical_search(
    conn: Conn, conversation_id: uuid.UUID, query: str, limit: int = 50
) -> list[tuple[uuid.UUID, float]]:
    q = or_query(query)
    if q is None:
        return []
    cur = await conn.execute(
        """SELECT c.id, ts_rank_cd(c.tsv, to_tsquery('english', %(q)s), 32) AS score
           FROM chunks c JOIN chunk_memberships m ON m.chunk_id = c.id AND m.conversation_id = %(c)s
           WHERE c.tsv @@ to_tsquery('english', %(q)s)
           ORDER BY score DESC, c.id LIMIT %(n)s""",
        {"q": q, "c": conversation_id, "n": limit},
    )
    return [(r["id"], float(r["score"])) for r in await cur.fetchall()]
