"""Index a conversation's corpus: embed each chunk with its context header, once, ever.

Chunks are global, so a chunk already embedded for another conversation only gains this conversation's
membership: popular literature is embedded once, not once per user."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from a9_agents.db import Conn
from a9_agents.fulltext.chunker import Chunk, embedding_text, paper_summary
from a9_agents.index.conversation_index import ConversationIndex, IndexedChunk, IndexedPaper
from a9_agents.index.embed import DenseEmbedder

BATCH = 48


@dataclass(frozen=True)
class IndexResult:
    chunks_total: int
    chunks_embedded: int
    chunks_reused: int
    papers: int


async def index_conversation(
    conn: Conn, index: ConversationIndex, embedder: DenseEmbedder, conversation_id: uuid.UUID
) -> IndexResult:
    cur = await conn.execute(
        """SELECT c.id, c.paper_id, c.kind, c.text, c.section_path, c.page, c.char_start, c.char_end, c.tokens,
                  p.title, p.abstract, p.year, p.full_text_allowed
           FROM chunk_memberships m JOIN chunks c ON c.id = m.chunk_id JOIN papers p ON p.id = c.paper_id
           WHERE m.conversation_id = %s ORDER BY c.id""",
        (conversation_id,),
    )
    rows = await cur.fetchall()
    known = await index.known([r["id"] for r in rows])
    reused = [r["id"] for r in rows if r["id"] in known]
    await index.join(chunk_ids=reused)

    fresh = [r for r in rows if r["id"] not in known]
    for start in range(0, len(fresh), BATCH):
        batch = fresh[start : start + BATCH]
        texts = [
            embedding_text(Chunk(r["kind"], r["text"], r["char_start"], r["char_end"], list(r["section_path"]), r["page"], r["tokens"]), r["title"], paper_summary(r["abstract"]))
            for r in batch
        ]  # fmt: skip
        vectors = await embedder.embed(texts)
        await index.add_chunks(
            [
                IndexedChunk(
                    r["id"],
                    r["paper_id"],
                    list(r["section_path"]),
                    r["year"],
                    "open" if r["full_text_allowed"] else "abstract_only",
                    v,
                )
                for r, v in zip(batch, vectors, strict=True)
            ]
        )

    papers = {r["paper_id"]: r for r in rows}
    known_papers = {p for p in papers}  # paper vectors are cheap (one per paper): refresh them
    ordered = sorted(known_papers)
    for start in range(0, len(ordered), BATCH):
        part = ordered[start : start + BATCH]
        vecs = await embedder.embed(
            [f"{papers[p]['title']}. {(papers[p]['abstract'] or '')[:1200]}" for p in part]
        )
        await index.add_papers(
            [IndexedPaper(p, papers[p]["year"], v) for p, v in zip(part, vecs, strict=True)]
        )
    return IndexResult(len(rows), len(fresh), len(reused), len(papers))
