"""Ingest one paper's full text: licence first, then fetch, parse, store, chunk, verify, insert.

Invariants enforced here and again by the database:
  * the licence is evaluated BEFORE anything is stored; unknown or unrecognised means metadata only;
  * a parse failure marks the paper abstract-only and ingest continues;
  * every chunk is verified to round-trip to its source span before it is written.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from a9_agents.db import Conn
from a9_agents.fulltext.chunker import CHUNKER_VERSION, Chunk, chunk_document, verify_chunks
from a9_agents.fulltext.document import ParsedDocument
from a9_agents.fulltext.fetch import ArxivPdf, FullTextRoute, NoFullText
from a9_agents.fulltext.jats import parse_jats
from a9_agents.fulltext.licence import evaluate_licence
from a9_agents.fulltext.pdfparse import parse_pdf
from a9_agents.fulltext.store import ObjectStore

log = logging.getLogger(__name__)
ABSTRACT_PARSER = "abstract-v1"


@dataclass(frozen=True)
class IngestResult:
    paper_id: uuid.UUID
    status: str  # parsed | abstract_only | not_permitted | failed
    note: str
    chunks: int


async def _insert_chunks(
    conn: Conn, paper_id: uuid.UUID, run_id: uuid.UUID, parser: str, chunks: list[Chunk]
) -> int:
    n = 0
    import hashlib

    async with conn.cursor() as cur:
        for c in chunks:
            await cur.execute(
                """INSERT INTO chunks (paper_id, kind, text, text_hash, section_path, page, char_start, char_end,
                                       parser_version, extraction_model, prompt_version, run_id, tokens)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (paper_id, kind, parser_version, char_start, char_end) DO NOTHING""",
                (paper_id, c.kind, c.text, hashlib.sha256(c.text.encode()).hexdigest(), c.section_path, c.page,
                 c.start, c.end, parser, CHUNKER_VERSION, "none", run_id, c.tokens),
            )  # fmt: skip
            n += cur.rowcount
    return n


async def _set_status(conn: Conn, paper_id: uuid.UUID, status: str, note: str) -> None:
    await conn.execute(
        "UPDATE papers SET fulltext_status = %s, fulltext_note = %s WHERE id = %s",
        (status, note[:500], paper_id),
    )


async def _abstract_chunk(conn: Conn, paper: dict[str, Any], run_id: uuid.UUID) -> int:
    text = (paper.get("abstract") or "").strip()
    if not text:
        return 0
    chunk = Chunk("abstract", text, 0, len(text), ["Abstract"], 1, len(text.split()))
    return await _insert_chunks(conn, paper["id"], run_id, ABSTRACT_PARSER, [chunk])


async def ingest_paper(
    conn: Conn,
    store: ObjectStore,
    paper: dict[str, Any],
    run_id: uuid.UUID,
    *,
    routes: list[FullTextRoute],
    arxiv: ArxivPdf | None = None,
) -> IngestResult:
    """`paper` is a papers row (id, abstract, pmcid, arxiv_id, licence, ...)."""
    pid: uuid.UUID = paper["id"]

    async def finish(status: str, note: str, chunks: int = 0) -> IngestResult:
        # Without parsed full text the abstract is all there is; it becomes the paper's one chunk.
        if status != "parsed":
            chunks += await _abstract_chunk(conn, paper, run_id)
        await _set_status(conn, pid, status, note)
        return IngestResult(pid, status, note, chunks)

    # 1. Find a route and the licence its source states. Nothing is stored yet.
    full = None
    pdf_bytes: bytes | None = None
    licence_raw: str | None = paper.get("licence")
    reasons: list[str] = []
    for route in routes:
        try:
            full = await route.fetch(paper)
            break
        except NoFullText as exc:
            reasons.append(f"{route.name}: {exc}")
        except Exception as exc:
            reasons.append(f"{route.name}: {type(exc).__name__}: {exc}")
    if full is not None:
        licence_raw = full.licence_raw or licence_raw
    elif arxiv is not None and paper.get("arxiv_id"):
        try:
            licence_raw = await arxiv.licence_of(str(paper["arxiv_id"])) or licence_raw
        except Exception as exc:
            reasons.append(f"arxiv_pdf: licence lookup failed ({type(exc).__name__})")
            licence_raw = licence_raw
    else:
        licence_raw = licence_raw

    # 2. The licence decides whether we may keep anything. Unknown is not open.
    decision = evaluate_licence(licence_raw)
    await conn.execute(
        "UPDATE papers SET licence = COALESCE(%s, licence) WHERE id = %s", (licence_raw, pid)
    )
    if full is None and not (arxiv is not None and paper.get("arxiv_id") and decision.permitted):
        note = "; ".join(reasons) or "no open full-text route for this paper"
        status = "not_permitted" if licence_raw and not decision.permitted else "abstract_only"
        return await finish(status, decision.reason if status == "not_permitted" else note)
    if not decision.permitted:
        return await finish("not_permitted", decision.reason)

    # 3. Permitted: fetch (if not already), parse, store, chunk, verify.
    await conn.execute("UPDATE papers SET full_text_allowed = true WHERE id = %s", (pid,))
    try:
        if full is not None:
            raw, fmt, route_name = full.data, full.format, full.route
        else:
            assert arxiv is not None
            pdf_bytes = await arxiv.fetch_pdf(str(paper["arxiv_id"]))
            raw, fmt, route_name = pdf_bytes, "pdf", "arxiv_pdf"
        doc: ParsedDocument = parse_jats(raw) if fmt == "jats" else parse_pdf(raw)
        chunks = chunk_document(doc)
        problems = verify_chunks(doc, chunks)
        if problems:
            raise ValueError(f"chunks do not round-trip: {problems[0]}")
        if not chunks:
            raise ValueError("parsed document produced no chunks")
    except Exception as exc:
        log.warning(
            "full text for %s failed (%s: %s); keeping the abstract", pid, type(exc).__name__, exc
        )
        await conn.execute("UPDATE papers SET full_text_allowed = false WHERE id = %s", (pid,))
        return await finish("failed", f"{type(exc).__name__}: {exc}")

    base = f"papers/{pid}"
    original_key = f"{base}/original.pdf" if fmt == "pdf" else f"{base}/fulltext.jats.xml"
    doc_key = f"{base}/document.{doc.parser}.json"
    for key, kind, data in (
        (original_key, "original_pdf" if fmt == "pdf" else "jats_xml", raw),
        (doc_key, "document_json", doc.to_json()),
    ):
        digest = store.put(key, data)
        await conn.execute(
            """INSERT INTO paper_assets (paper_id, kind, object_key, sha256) VALUES (%s, %s, %s, %s)
               ON CONFLICT (paper_id, kind, object_key) DO NOTHING""",
            (pid, kind, key, digest),
        )
    inserted = await _insert_chunks(conn, pid, run_id, doc.parser, chunks)
    if not any(c.kind == "abstract" for c in chunks):
        inserted += await _abstract_chunk(
            conn, paper, run_id
        )  # the parse found no abstract; keep the record's
    await conn.execute("UPDATE papers SET abstract_only = false WHERE id = %s", (pid,))
    return await finish("parsed", f"{route_name}: {len(chunks)} chunks, {licence_raw}", inserted)


async def add_memberships(
    conn: Conn, *, user_id: uuid.UUID, conversation_id: uuid.UUID, paper_ids: list[uuid.UUID]
) -> int:
    """Put the papers' chunks in the conversation's corpus. New rows get an ingestion timestamp, so the UI
    can show what arrived since the last turn."""
    if not paper_ids:
        return 0
    cur = await conn.execute(
        """INSERT INTO chunk_memberships (user_id, conversation_id, chunk_id)
           SELECT %s, %s, c.id FROM chunks c WHERE c.paper_id = ANY(%s)
           ON CONFLICT DO NOTHING""",
        (user_id, conversation_id, paper_ids),
    )
    return cur.rowcount


async def resolve_chunk(conn: Conn, store: ObjectStore, chunk_id: uuid.UUID) -> dict[str, Any]:
    """A citation is a lookup: chunk id -> the exact source text, page and section, verified on the way.

    Fails loudly if the stored span no longer matches the chunk, because a citation that cannot resolve
    is a bug, never a plausible-looking link."""
    from a9_agents.fulltext.document import linearise_table

    cur = await conn.execute(
        """SELECT c.id, c.paper_id, c.kind, c.text, c.section_path, c.page, c.char_start, c.char_end, c.parser_version,
                  p.title, p.doi, p.abstract FROM chunks c JOIN papers p ON p.id = c.paper_id WHERE c.id = %s""",
        (chunk_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise LookupError(f"chunk {chunk_id} does not exist")
    if row["parser_version"] == ABSTRACT_PARSER:
        source = (row["abstract"] or "")[row["char_start"] : row["char_end"]]
    else:
        doc = ParsedDocument.from_json(
            store.get(f"papers/{row['paper_id']}/document.{row['parser_version']}.json")
        )
        source = doc.text[row["char_start"] : row["char_end"]]
    expected = linearise_table(source) if row["kind"] == "table_linearised" else source
    if expected != row["text"]:
        raise ValueError(f"chunk {chunk_id} no longer matches its source span")
    return {
        "chunk_id": str(row["id"]), "paper_id": str(row["paper_id"]), "kind": row["kind"], "text": row["text"],
        "source_span": source, "section_path": list(row["section_path"]), "page": row["page"],
        "char_start": row["char_start"], "char_end": row["char_end"], "title": row["title"], "doi": row["doi"],
    }  # fmt: skip
