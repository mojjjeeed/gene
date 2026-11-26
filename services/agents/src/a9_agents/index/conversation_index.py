"""The ONLY module that talks to the vector store.

`ConversationIndex(conversation_id)` is the sole query path. The conversation id is a required
constructor argument and every search carries it as a mandatory filter, so a query without the filter
cannot be written: there is no method that takes a raw filter. A test (and a lint rule) fails the build
if `qdrant_client` is imported anywhere else.

Chunks are stored once, globally; a payload array `conversation_ids` is the membership. Paper-level
vectors live in a second collection (SPECTER2 is the intended model; this uses the chunk embedder as a
stand-in) and carry `conversation_ids` too, a small deviation from the PRD so the paper-level pass is
isolated by the same mandatory filter.
"""

from __future__ import annotations

import asyncio
import os
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

CHUNKS = "a9_chunks"
PAPERS = "a9_papers"


def make_client(*, memory: bool = False) -> QdrantClient:
    """A server if A9_QDRANT_URL is set; otherwise embedded storage on disk (one process at a time).
    `memory=True` is a throwaway in-process store for tests."""
    if memory:
        return QdrantClient(":memory:")
    if url := os.environ.get("A9_QDRANT_URL"):
        return QdrantClient(url=url)
    return QdrantClient(path=str(Path(os.environ.get("A9_QDRANT_PATH", ".qdrant")).resolve()))


def ensure_collections(client: QdrantClient, dims: int) -> None:
    for name in (CHUNKS, PAPERS):
        if not client.collection_exists(name):
            client.create_collection(
                name, vectors_config=models.VectorParams(size=dims, distance=models.Distance.COSINE)
            )
            # Payload indexes keep the mandatory conversation filter fast on a server; embedded mode ignores them.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                client.create_payload_index(
                    name, "conversation_ids", models.PayloadSchemaType.KEYWORD
                )
                client.create_payload_index(name, "paper_id", models.PayloadSchemaType.KEYWORD)


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: uuid.UUID
    paper_id: uuid.UUID
    section_path: list[str]
    year: int | None
    oa_status: str
    vector: list[float]


@dataclass(frozen=True)
class IndexedPaper:
    paper_id: uuid.UUID
    year: int | None
    vector: list[float]


@dataclass(frozen=True)
class Hit:
    id: uuid.UUID  # chunk id, or paper id for the paper-level collection
    paper_id: uuid.UUID
    score: float


class ConversationIndex:
    def __init__(self, client: QdrantClient, conversation_id: uuid.UUID):
        if not isinstance(conversation_id, uuid.UUID):
            raise TypeError("conversation_id must be a UUID")
        self._client, self._cid = client, str(conversation_id)

    def _scope(self, paper_ids: list[uuid.UUID] | None = None) -> models.Filter:
        must: list[models.Condition] = [
            models.FieldCondition(key="conversation_ids", match=models.MatchValue(value=self._cid))
        ]
        if paper_ids is not None:
            must.append(
                models.FieldCondition(
                    key="paper_id", match=models.MatchAny(any=[str(p) for p in paper_ids])
                )
            )
        return models.Filter(must=must)

    def _members(self, collection: str, ids: list[str]) -> dict[str, list[str]]:
        found = self._client.retrieve(
            collection, ids=ids, with_payload=["conversation_ids"], with_vectors=False
        )
        return {str(p.id): list((p.payload or {}).get("conversation_ids", [])) for p in found}

    def _upsert(self, collection: str, rows: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        existing = self._members(collection, [r[0] for r in rows])
        points = []
        for pid, vector, payload in rows:
            members = sorted(
                {*existing.get(pid, []), self._cid}
            )  # add this conversation, keep the others
            points.append(
                models.PointStruct(
                    id=pid, vector=vector, payload={**payload, "conversation_ids": members}
                )
            )
        self._client.upsert(collection, points=points)

    async def add_chunks(self, items: list[IndexedChunk]) -> None:
        rows = [
            (str(c.chunk_id), c.vector, {"chunk_id": str(c.chunk_id), "paper_id": str(c.paper_id), "section_path": c.section_path, "year": c.year, "oa_status": c.oa_status})
            for c in items
        ]  # fmt: skip
        await asyncio.to_thread(self._upsert, CHUNKS, rows)

    async def add_papers(self, items: list[IndexedPaper]) -> None:
        rows = [
            (str(p.paper_id), p.vector, {"paper_id": str(p.paper_id), "year": p.year})
            for p in items
        ]
        await asyncio.to_thread(self._upsert, PAPERS, rows)

    def _search(
        self, collection: str, vector: list[float], limit: int, paper_ids: list[uuid.UUID] | None
    ) -> list[Hit]:
        res = self._client.query_points(
            collection,
            query=vector,
            query_filter=self._scope(paper_ids),
            limit=limit,
            with_payload=["paper_id"],
        )
        return [
            Hit(uuid.UUID(str(p.id)), uuid.UUID(str((p.payload or {})["paper_id"])), float(p.score))
            for p in res.points
        ]

    async def search_chunks(
        self, vector: list[float], limit: int = 50, paper_ids: list[uuid.UUID] | None = None
    ) -> list[Hit]:
        return await asyncio.to_thread(self._search, CHUNKS, vector, limit, paper_ids)

    async def search_papers(self, vector: list[float], limit: int = 10) -> list[Hit]:
        return await asyncio.to_thread(self._search, PAPERS, vector, limit, None)

    def _known(self, ids: list[str]) -> set[str]:
        return {
            str(p.id)
            for p in self._client.retrieve(CHUNKS, ids=ids, with_payload=False, with_vectors=False)
        }

    async def known(self, chunk_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        """Which chunks already have a vector (embedded for ANY conversation): those are never re-embedded."""
        return (
            {
                uuid.UUID(i)
                for i in await asyncio.to_thread(self._known, [str(c) for c in chunk_ids])
            }
            if chunk_ids
            else set()
        )

    def _join(self, collection: str, ids: list[str]) -> None:
        for pid, members in self._members(collection, ids).items():
            if self._cid not in members:
                self._client.set_payload(
                    collection,
                    payload={"conversation_ids": sorted({*members, self._cid})},
                    points=[pid],
                )

    async def join(self, chunk_ids: list[uuid.UUID] = (), paper_ids: list[uuid.UUID] = ()) -> None:  # type: ignore[assignment]
        """Add this conversation to vectors that already exist."""
        if chunk_ids:
            await asyncio.to_thread(self._join, CHUNKS, [str(c) for c in chunk_ids])
        if paper_ids:
            await asyncio.to_thread(self._join, PAPERS, [str(p) for p in paper_ids])

    async def count(self) -> int:
        return (
            await asyncio.to_thread(
                self._client.count, CHUNKS, count_filter=self._scope(), exact=True
            )
        ).count

    def _remove(self) -> None:
        for collection in (CHUNKS, PAPERS):
            offset = None
            while True:
                points, offset = self._client.scroll(
                    collection,
                    scroll_filter=self._scope(),
                    limit=256,
                    offset=offset,
                    with_payload=["conversation_ids"],
                )
                for p in points:
                    rest = [
                        c for c in (p.payload or {}).get("conversation_ids", []) if c != self._cid
                    ]
                    if rest:
                        self._client.set_payload(
                            collection, payload={"conversation_ids": rest}, points=[p.id]
                        )
                    else:
                        self._client.delete(
                            collection, points_selector=models.PointIdsList(points=[p.id])
                        )  # nobody else uses it
                if offset is None:
                    break

    async def remove_conversation(self) -> None:
        """Deletion on request: take this conversation out of the index; vectors no other conversation uses go too."""
        await asyncio.to_thread(self._remove)
