"""Hybrid retrieval for one turn of a conversation.

  rewrite against history -> decompose -> per sub-question: dense arm, lexical arm, paper-level arm
  -> reciprocal-rank fusion (~50) -> cross-encoder rerank (8-12) -> neighbour expansion.

Rewrite and decomposition are rule-based here (no model access); the LLM versions plug in behind the
same function signatures. Everything is scoped to the conversation by ConversationIndex and by the
membership join in the lexical arm.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field

from a9_agents.db import Conn
from a9_agents.index.conversation_index import ConversationIndex
from a9_agents.index.embed import DenseEmbedder, Reranker
from a9_agents.index.lexical import lexical_search

RRF_K = 60


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    paper_id: uuid.UUID
    kind: str
    text: str
    section_path: list[str]
    page: int
    char_start: int
    char_end: int
    title: str
    doi: str | None
    year: int | None
    score: float = 0.0
    arms: dict[str, int] = field(
        default_factory=dict
    )  # arm -> rank (1-based), for explaining why it surfaced
    before: str = ""
    after: str = ""


@dataclass
class RetrievalResult:
    question: str
    rewritten: str
    subqueries: list[str]
    candidates: int
    chunks: list[RetrievedChunk]
    ms: dict[str, float]


_ANAPHORA = re.compile(
    r"^\s*(it|its|this|that|these|those|they|them|their|he|she|the same|and|also|what about|how about)\b",
    re.IGNORECASE,
)


def rewrite_query(question: str, history: list[str]) -> str:
    """Make a follow-up stand alone by anchoring it to the previous user question. (An LLM rewrite replaces this.)"""
    q = question.strip()
    if history and (_ANAPHORA.match(q) or len(q.split()) <= 4):
        return f"{history[-1].strip().rstrip('?')} ({q})"
    return q


def decompose(question: str, limit: int = 3) -> list[str]:
    """Split a multi-part question into independent ones. Conservative: only on explicit separators."""
    parts = [
        p.strip()
        for p in re.split(r"\?\s+(?=[A-Z])|;\s+|\s+and also\s+|\s+as well as\s+", question)
        if p.strip()
    ]
    parts = [
        p if p.endswith("?") or not question.rstrip().endswith("?") else p + "?" for p in parts
    ]
    return (parts or [question])[:limit]


def rrf(rankings: list[list[uuid.UUID]], k: int = RRF_K) -> list[tuple[uuid.UUID, float]]:
    """Reciprocal-rank fusion: robust to the arms' incomparable score scales."""
    score: dict[uuid.UUID, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            score[item] = score.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(score.items(), key=lambda kv: (-kv[1], str(kv[0])))


async def _fetch(conn: Conn, ids: list[uuid.UUID]) -> dict[uuid.UUID, RetrievedChunk]:
    cur = await conn.execute(
        """SELECT c.id, c.paper_id, c.kind, c.text, c.section_path, c.page, c.char_start, c.char_end,
                  p.title, p.doi, p.year
           FROM chunks c JOIN papers p ON p.id = c.paper_id WHERE c.id = ANY(%s)""",
        (ids,),
    )
    return {
        r["id"]: RetrievedChunk(
            r["id"],
            r["paper_id"],
            r["kind"],
            r["text"],
            list(r["section_path"]),
            r["page"],
            r["char_start"],
            r["char_end"],
            r["title"],
            r["doi"],
            r["year"],
        )
        for r in await cur.fetchall()
    }


async def _expand(conn: Conn, c: RetrievedChunk) -> None:
    """Parent/section expansion: the chunks either side within the same section, so the model sees context."""
    if c.kind not in ("body", "abstract"):
        return
    base = "SELECT text FROM chunks WHERE paper_id = %s AND kind = %s AND section_path = %s AND "
    cur = await conn.execute(
        base + "char_start < %s ORDER BY char_start DESC LIMIT 1",
        (c.paper_id, c.kind, c.section_path, c.char_start),
    )
    if prev := await cur.fetchone():
        c.before = prev["text"]
    cur = await conn.execute(
        base + "char_start > %s ORDER BY char_start LIMIT 1",
        (c.paper_id, c.kind, c.section_path, c.char_start),
    )
    if nxt := await cur.fetchone():
        c.after = nxt["text"]


async def retrieve(
    conn: Conn,
    index: ConversationIndex,
    conversation_id: uuid.UUID,
    embedder: DenseEmbedder,
    reranker: Reranker,
    question: str,
    history: list[str] | None = None,
    *,
    fuse_to: int = 50,
    final: int = 10,
    expand: bool = True,
) -> RetrievalResult:
    t0 = time.perf_counter()
    rewritten = rewrite_query(question, history or [])
    subqueries = decompose(rewritten)
    rankings: list[list[uuid.UUID]] = []
    arm_rank: dict[uuid.UUID, dict[str, int]] = {}

    def note(arm: str, ids: list[uuid.UUID]) -> None:
        rankings.append(ids)
        for rank, i in enumerate(ids, start=1):
            arm_rank.setdefault(i, {}).setdefault(arm, rank)

    for sub in subqueries:
        vector = await embedder.embed_query(sub)
        note("dense", [h.id for h in await index.search_chunks(vector, limit=50)])
        note(
            "lexical",
            [cid for cid, _ in await lexical_search(conn, conversation_id, sub, limit=50)],
        )
        papers = await index.search_papers(
            vector, limit=8
        )  # catches the right paper even if it never uses the user's words
        if papers:
            note(
                "paper",
                [
                    h.id
                    for h in await index.search_chunks(
                        vector, limit=30, paper_ids=[p.id for p in papers]
                    )
                ],
            )
    t_search = time.perf_counter()

    fused = rrf(rankings)[:fuse_to]
    rows = await _fetch(conn, [i for i, _ in fused])
    candidates = [rows[i] for i, _ in fused if i in rows]
    for c in candidates:
        c.arms = arm_rank.get(c.chunk_id, {})
    scores = await reranker.rerank(rewritten, [c.text for c in candidates])
    for c, s in zip(candidates, scores, strict=True):
        c.score = s
    top = sorted(candidates, key=lambda c: (-c.score, str(c.chunk_id)))[:final]
    t_rerank = time.perf_counter()
    if expand:
        for c in top:
            await _expand(conn, c)
    t_end = time.perf_counter()
    return RetrievalResult(
        question, rewritten, subqueries, len(candidates), top,
        {"search": (t_search - t0) * 1000, "rerank": (t_rerank - t_search) * 1000, "expand": (t_end - t_rerank) * 1000, "total": (t_end - t0) * 1000},
    )  # fmt: skip
