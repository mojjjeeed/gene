"""Asking questions of a conversation's corpus, and resolving a citation to its exact source span."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from a9_agents.answer import ExtractiveGenerator, OverlapVerifier, answer_question
from a9_agents.auth import User
from a9_agents.db import Pool, scoped
from a9_agents.fulltext.ingest import resolve_chunk
from a9_agents.fulltext.store import LocalObjectStore
from a9_agents.index.conversation_index import ConversationIndex, ensure_collections, make_client
from a9_agents.index.embed import FastEmbedDense, FastEmbedReranker
from a9_agents.index.pipeline import index_conversation
from a9_agents.index.retrieval import retrieve

router = APIRouter()


class _Rag:
    """Models, vector client and object store, built once per process on first use (model load is slow)."""

    def __init__(self) -> None:
        self.embedder = FastEmbedDense()
        self.reranker = FastEmbedReranker()
        self.client = make_client()
        ensure_collections(self.client, self.embedder.dims)
        self.store = LocalObjectStore()


def _rag(request: Request) -> _Rag:
    if getattr(request.app.state, "rag", None) is None:
        request.app.state.rag = _Rag()
    rag: _Rag = request.app.state.rag
    return rag


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _line(event: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n".encode()


@router.get("/chunks/{chunk_id}")
async def get_chunk(chunk_id: uuid.UUID, request: Request, user: User) -> dict[str, Any]:
    """Resolve a citation: the chunk, its exact source span, page and section. 404 if it is not in the
    caller's corpus; 500 (loudly) if the stored span no longer matches."""
    rag, pool = _rag(request), request.app.state.pool
    async with scoped(pool, role="a9_app", user_id=user) as conn:
        try:
            return await resolve_chunk(conn, rag.store, chunk_id)
        except LookupError:
            raise HTTPException(404, "chunk not found") from None


@router.post("/conversations/{conversation_id}/messages")
async def ask(
    conversation_id: uuid.UUID, body: MessageIn, request: Request, user: User
) -> StreamingResponse:
    pool: Pool = request.app.state.pool
    rag = _rag(request)
    async with scoped(pool, role="a9_app", user_id=user) as conn:
        cur = await conn.execute("SELECT 1 FROM conversations WHERE id = %s", (conversation_id,))
        if await cur.fetchone() is None:
            raise HTTPException(404, "conversation not found")
        cur = await conn.execute(
            "SELECT content FROM messages WHERE conversation_id = %s AND role = 'user' ORDER BY created_at DESC LIMIT 4",
            (conversation_id,),
        )
        history = [r["content"] for r in reversed(await cur.fetchall())]
        await conn.execute(
            "INSERT INTO messages (user_id, conversation_id, role, content) VALUES (%s, %s, 'user', %s)",
            (user, conversation_id, body.content),
        )

    async def stream() -> AsyncIterator[bytes]:
        index = ConversationIndex(rag.client, conversation_id)
        async with scoped(pool, role="a9_app", user_id=user) as conn:
            stats = await index_conversation(conn, index, rag.embedder, conversation_id)
            if stats.chunks_total == 0:
                text = "There is nothing in this conversation's corpus to answer from yet."
                await conn.execute(
                    "INSERT INTO messages (user_id, conversation_id, role, content) VALUES (%s, %s, 'assistant', %s)",
                    (user, conversation_id, text),
                )
                yield _line({"type": "no_evidence", "text": text})
                yield _line(
                    {
                        "type": "done",
                        "grounding_rate": 1.0,
                        "citations_resolve": True,
                        "corpus_chunks": 0,
                    }
                )
                return
            res = await retrieve(
                conn, index, conversation_id, rag.embedder, rag.reranker, body.content, history
            )
            yield _line(
                {
                    "type": "retrieval",
                    "chunks": len(res.chunks),
                    "candidates": res.candidates,
                    "ms": round(res.ms["total"]),
                    "rewritten": res.rewritten,
                }
            )
            answer = await answer_question(
                conn, rag.store, res, ExtractiveGenerator(rag.reranker), OverlapVerifier()
            )
            for s in answer.kept:
                yield _line(
                    {
                        "type": "sentence",
                        "text": s.text,
                        "cites": [str(c) for c in s.cites],
                        "check": s.verdict.reason,
                    }
                )
            for s in answer.removed:  # reported, never silently dropped
                yield _line({"type": "removed", "text": s.text, "reason": s.verdict.reason})
            if not answer.kept:
                yield _line(
                    {
                        "type": "no_evidence",
                        "text": "None of the retrieved passages supported an answer, so none is given.",
                    }
                )
            content = " ".join(
                f"{s.text} " + "".join(f"[c:{c}]" for c in s.cites) for s in answer.kept
            )
            await conn.execute(
                "INSERT INTO messages (user_id, conversation_id, role, content) VALUES (%s, %s, 'assistant', %s)",
                (user, conversation_id, content or "No supported answer."),
            )
            yield _line(
                {
                    "type": "done",
                    "grounding_rate": answer.grounding_rate,
                    "citations_resolve": answer.citations_resolve,
                    "unresolved": [str(c) for c in answer.unresolved_citations],
                    "corpus_chunks": stats.chunks_total,
                }
            )

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@router.get("/conversations/{conversation_id}/corpus")
async def corpus_summary(
    conversation_id: uuid.UUID,
    request: Request,
    user: User,
    since: datetime | None = None,
) -> dict[str, Any]:
    """The corpus size, and what was added since `since` (the previous turn), so widening the evidence
    base mid-conversation is visible instead of silent."""
    pool: Pool = request.app.state.pool
    async with scoped(pool, role="a9_app", user_id=user) as conn:
        cur = await conn.execute("SELECT 1 FROM conversations WHERE id = %s", (conversation_id,))
        if await cur.fetchone() is None:
            raise HTTPException(404, "conversation not found")
        cur = await conn.execute(
            """SELECT count(*) AS chunks, count(DISTINCT c.paper_id) AS papers,
                      count(*) FILTER (WHERE m.ingested_at > %(since)s) AS new_chunks,
                      count(DISTINCT c.paper_id) FILTER (WHERE m.ingested_at > %(since)s) AS new_papers,
                      max(m.ingested_at) AS latest
               FROM chunk_memberships m JOIN chunks c ON c.id = m.chunk_id WHERE m.conversation_id = %(c)s""",
            {"c": conversation_id, "since": since},
        )
        row = await cur.fetchone()
    assert row is not None
    return {
        "chunks": row["chunks"], "papers": row["papers"], "new_chunks": row["new_chunks"] if since else None,
        "new_papers": row["new_papers"] if since else None, "latest": row["latest"].isoformat() if row["latest"] else None,
    }  # fmt: skip
