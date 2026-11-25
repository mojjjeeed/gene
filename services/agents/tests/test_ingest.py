"""Full-text ingest against the real schema: licence first, abstract-only fallback, exact provenance."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from a9_agents.db import owner, scoped
from a9_agents.fulltext.fetch import ArxivPdf, PmcJats
from a9_agents.fulltext.ingest import ABSTRACT_PARSER, add_memberships, ingest_paper, resolve_chunk
from a9_agents.fulltext.store import LocalObjectStore
from a9_agents.sources.http import PolicedClient, Policy
from test_pdfparse import make_pdf

FIX = Path(__file__).parent / "fixtures"
CCBY = (FIX / "PMC11875782_ccby.xml").read_bytes()
NCND = (FIX / "PMC8562388_ccbyncnd.xml").read_bytes()


async def no_sleep(_: float) -> None:
    return None


def client(handler: Any) -> PolicedClient:
    return PolicedClient(
        Policy("t", min_interval=0.0, max_attempts=2),
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )


def _pmc() -> str:
    return f"PMC{uuid.uuid4().int % 10**9}"


def jats_route(body: bytes | None) -> PmcJats:
    """Serves one document for whatever PMCID is asked for (or 404 if None)."""

    def handler(r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body) if body is not None else httpx.Response(404)

    return PmcJats(ncbi=client(handler), epmc=client(lambda r: httpx.Response(500)))


async def make_paper(pool: Any, **cols: Any) -> dict[str, Any]:
    pid = uuid.uuid4()
    values = {
        "title": "A paper",
        "source": "europe_pmc",
        "abstract": "An abstract about kinases and resistance.",
        **cols,
    }
    async with owner(pool) as c:
        await c.execute(
            f"INSERT INTO papers (id, {', '.join(values)}) VALUES (%s, {', '.join(['%s'] * len(values))})",
            [pid, *values.values()],
        )
        row = await (await c.execute("SELECT * FROM papers WHERE id = %s", (pid,))).fetchone()
    assert row is not None
    return dict(row)


async def make_run(pool: Any) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user, project, conv, run = (uuid.uuid4() for _ in range(4))
    async with owner(pool) as c:
        await c.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user, f"{user}@x.org"))
        await c.execute(
            "INSERT INTO projects (id, user_id, name) VALUES (%s, %s, 'p')", (project, user)
        )
        await c.execute(
            "INSERT INTO conversations (id, user_id, project_id) VALUES (%s, %s, %s)",
            (conv, user, project),
        )
    return user, conv, run


async def state(
    pool: Any, pid: uuid.UUID
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    async with owner(pool) as c:
        paper = dict(
            await (await c.execute("SELECT * FROM papers WHERE id = %s", (pid,))).fetchone()
        )  # type: ignore[arg-type]
        chunks = [
            dict(r)
            for r in await (
                await c.execute(
                    "SELECT * FROM chunks WHERE paper_id = %s ORDER BY char_start", (pid,)
                )
            ).fetchall()
        ]
        assets = [
            r["kind"]
            for r in await (
                await c.execute("SELECT kind FROM paper_assets WHERE paper_id = %s", (pid,))
            ).fetchall()
        ]
    return paper, chunks, assets


async def run_ingest(pool: Any, store: Any, paper: dict[str, Any], **kw: Any) -> Any:
    async with scoped(pool, role="a9_worker") as conn:
        return await ingest_paper(conn, store, paper, uuid.uuid4(), **kw)


async def test_an_open_licence_is_parsed_stored_chunked_and_every_chunk_resolves(
    pool: Any, tmp_path: Path
) -> None:
    store = LocalObjectStore(tmp_path)
    paper = await make_paper(pool, pmcid=_pmc())
    result = await run_ingest(pool, store, paper, routes=[jats_route(CCBY)])
    assert result.status == "parsed" and result.chunks >= 20
    row, chunks, assets = await state(pool, paper["id"])
    assert (row["fulltext_status"], row["full_text_allowed"], row["abstract_only"]) == (
        "parsed",
        True,
        False,
    )
    assert row["licence"] == "https://creativecommons.org/licenses/by/4.0/"
    assert sorted(assets) == ["document_json", "jats_xml"]
    assert {c["kind"] for c in chunks} >= {
        "abstract",
        "body",
        "table",
        "table_linearised",
        "figure_caption",
    }
    assert all(
        c["page"] >= 1
        and c["section_path"]
        and c["parser_version"] == "jats-v1"
        and c["tokens"] > 0
        for c in chunks
    )
    async with scoped(pool, role="a9_worker") as conn:
        for c in chunks:  # every chunk, not a sample
            resolved = await resolve_chunk(conn, store, c["id"])
            assert resolved["source_span"] == c["text"] or c["kind"] == "table_linearised"
            assert resolved["title"] == paper["title"]


async def test_a_restrictive_licence_stores_metadata_and_the_abstract_only(
    pool: Any, tmp_path: Path
) -> None:
    store = LocalObjectStore(tmp_path)
    paper = await make_paper(pool, pmcid=_pmc())
    result = await run_ingest(pool, store, paper, routes=[jats_route(NCND)])
    assert result.status == "not_permitted" and "cc-by-nc-nd" in result.note
    row, chunks, assets = await state(pool, paper["id"])
    assert (row["full_text_allowed"], row["fulltext_status"]) == (False, "not_permitted")
    assert (
        row["licence"] == "https://creativecommons.org/licenses/by-nc-nd/4.0/"
    )  # recorded, so the reason is visible
    assert assets == [] and not list(tmp_path.rglob("*")), "nothing was written to object storage"
    assert [(c["kind"], c["parser_version"]) for c in chunks] == [("abstract", ABSTRACT_PARSER)]


async def test_a_null_licence_stores_metadata_only(pool: Any, tmp_path: Path) -> None:
    paper = await make_paper(pool)  # no pmcid, no arxiv id, no licence
    result = await run_ingest(pool, LocalObjectStore(tmp_path), paper, routes=[jats_route(None)])
    assert result.status == "abstract_only"
    row, chunks, assets = await state(pool, paper["id"])
    assert (row["full_text_allowed"], row["licence"], assets) == (False, None, [])
    assert [c["kind"] for c in chunks] == ["abstract"]


async def test_a_licence_on_the_record_alone_does_not_conjure_full_text(
    pool: Any, tmp_path: Path
) -> None:
    paper = await make_paper(pool, licence="cc by")  # open licence, but no route to any text
    result = await run_ingest(pool, LocalObjectStore(tmp_path), paper, routes=[jats_route(None)])
    assert (
        result.status == "abstract_only"
        and (await state(pool, paper["id"]))[1][0]["kind"] == "abstract"
    )


async def test_a_parse_failure_keeps_the_abstract_and_does_not_leave_full_text_allowed(
    pool: Any, tmp_path: Path
) -> None:
    broken = b"<article><body><sec><title>Empty</title></sec></body></article>"
    paper = await make_paper(pool, pmcid=_pmc())
    result = await run_ingest(pool, LocalObjectStore(tmp_path), paper, routes=[jats_route(broken)])
    assert result.status == "failed" and "no chunks" in result.note
    row, chunks, assets = await state(pool, paper["id"])
    assert (row["fulltext_status"], row["full_text_allowed"], assets) == ("failed", False, [])
    assert [c["kind"] for c in chunks] == ["abstract"]


async def test_reingesting_adds_nothing_new(pool: Any, tmp_path: Path) -> None:
    store, paper = LocalObjectStore(tmp_path), await make_paper(pool, pmcid=_pmc())
    first = await run_ingest(pool, store, paper, routes=[jats_route(CCBY)])
    second = await run_ingest(pool, store, paper, routes=[jats_route(CCBY)])
    assert first.chunks > 0 and second.chunks == 0
    assert (
        len((await state(pool, paper["id"]))[1]) == first.chunks
    )  # + the abstract-v1 chunk written separately


def arxiv_route(licence_link: str | None, pdf: bytes, calls: list[str]) -> ArxivPdf:
    def handler(r: httpx.Request) -> httpx.Response:
        calls.append(r.url.path)
        if "/abs/" in r.url.path:
            link = f'<a href="{licence_link}">license</a>' if licence_link else ""
            return httpx.Response(200, text=f"<html><body>{link}</body></html>")
        return httpx.Response(200, content=pdf)

    return ArxivPdf(client(handler))


async def test_arxiv_with_a_cc_by_licence_is_downloaded_and_parsed(
    pool: Any, tmp_path: Path
) -> None:
    calls: list[str] = []
    paper = await make_paper(pool, arxiv_id="2401.00001")
    arxiv = arxiv_route("https://creativecommons.org/licenses/by/4.0/", make_pdf(), calls)
    result = await run_ingest(pool, LocalObjectStore(tmp_path), paper, routes=[], arxiv=arxiv)
    assert result.status == "parsed" and calls == ["/abs/2401.00001", "/pdf/2401.00001"]
    row, chunks, assets = await state(pool, paper["id"])
    assert sorted(assets) == ["document_json", "original_pdf"] and row["full_text_allowed"] is True
    assert "pymupdf-v1" in {c["parser_version"] for c in chunks}
    assert max(c["page"] for c in chunks) >= 2


async def test_arxiv_default_licence_means_the_pdf_is_never_even_downloaded(
    pool: Any, tmp_path: Path
) -> None:
    calls: list[str] = []
    paper = await make_paper(pool, arxiv_id="2401.00002")
    arxiv = arxiv_route("https://arxiv.org/licenses/nonexclusive-distrib/1.0/", make_pdf(), calls)
    result = await run_ingest(pool, LocalObjectStore(tmp_path), paper, routes=[], arxiv=arxiv)
    assert result.status == "not_permitted" and calls == ["/abs/2401.00002"]
    assert (await state(pool, paper["id"]))[2] == []


async def test_arxiv_with_no_licence_on_the_page_is_abstract_only(
    pool: Any, tmp_path: Path
) -> None:
    calls: list[str] = []
    paper = await make_paper(pool, arxiv_id="2401.00003")
    result = await run_ingest(
        pool,
        LocalObjectStore(tmp_path),
        paper,
        routes=[],
        arxiv=arxiv_route(None, make_pdf(), calls),
    )
    assert result.status == "abstract_only" and "/pdf/2401.00003" not in calls


async def test_a_citation_that_no_longer_matches_its_source_fails_loudly(
    pool: Any, tmp_path: Path
) -> None:
    store, paper = LocalObjectStore(tmp_path), await make_paper(pool, pmcid=_pmc())
    await run_ingest(pool, store, paper, routes=[jats_route(CCBY)])
    _, chunks, _ = await state(pool, paper["id"])
    body = next(c for c in chunks if c["kind"] == "body")
    key = f"papers/{paper['id']}/document.jats-v1.json"
    store.put(
        key,
        store.get(key).replace(
            body["text"][:30].encode(), b"TAMPERED TEXT HERE ABOUT" + b"x" * 6, 1
        ),
    )
    async with scoped(pool, role="a9_worker") as conn:
        with pytest.raises(ValueError, match="no longer matches"):
            await resolve_chunk(conn, store, body["id"])
        with pytest.raises(LookupError):
            await resolve_chunk(conn, store, uuid.uuid4())


async def test_the_abstract_and_linearised_table_chunks_resolve_too(
    pool: Any, tmp_path: Path
) -> None:
    store, paper = LocalObjectStore(tmp_path), await make_paper(pool, pmcid=_pmc())
    await run_ingest(pool, store, paper, routes=[jats_route(CCBY)])
    _, chunks, _ = await state(pool, paper["id"])
    async with scoped(pool, role="a9_worker") as conn:
        lin = await resolve_chunk(
            conn, store, next(c["id"] for c in chunks if c["kind"] == "table_linearised")
        )
        assert (
            lin["source_span"].startswith("TABLE 1.")
            and "\t" in lin["source_span"]
            and "\t" not in lin["text"]
        )
    abstract_only = await make_paper(pool)
    await run_ingest(pool, store, abstract_only, routes=[jats_route(None)])
    _, a_chunks, _ = await state(pool, abstract_only["id"])
    async with scoped(pool, role="a9_worker") as conn:
        assert (await resolve_chunk(conn, store, a_chunks[0]["id"]))["text"] == abstract_only[
            "abstract"
        ]


async def test_memberships_put_chunks_in_a_conversation_once_and_only_for_that_user(
    pool: Any, tmp_path: Path
) -> None:
    store, paper = LocalObjectStore(tmp_path), await make_paper(pool, pmcid=_pmc())
    user, conv, _ = await make_run(pool)
    other, other_conv, _ = await make_run(pool)
    await run_ingest(pool, store, paper, routes=[jats_route(CCBY)])
    async with scoped(pool, role="a9_worker") as conn:
        first = await add_memberships(
            conn, user_id=user, conversation_id=conv, paper_ids=[paper["id"]]
        )
        again = await add_memberships(
            conn, user_id=user, conversation_id=conv, paper_ids=[paper["id"]]
        )
        assert await add_memberships(conn, user_id=user, conversation_id=conv, paper_ids=[]) == 0
    assert first > 20 and again == 0
    async with scoped(pool, role="a9_app", user_id=user) as conn:
        assert (await (await conn.execute("SELECT count(*) AS n FROM chunks")).fetchone())[
            "n"
        ] == first  # type: ignore[index]
        assert (
            await (
                await conn.execute(
                    "SELECT count(*) AS n FROM chunk_memberships WHERE ingested_at IS NOT NULL"
                )
            ).fetchone()
        )["n"] == first  # type: ignore[index]
    async with scoped(pool, role="a9_app", user_id=other) as conn:
        assert (await (await conn.execute("SELECT count(*) AS n FROM chunks")).fetchone())["n"] == 0  # type: ignore[index]
    _ = other_conv
