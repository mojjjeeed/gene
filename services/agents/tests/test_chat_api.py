"""The chat endpoint and citation resolution, in-process (real models, real DB, in-memory vector store)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from a9_agents.app import app
from a9_agents.db import owner, scoped
from a9_agents.fulltext.ingest import add_memberships
from a9_agents.fulltext.store import LocalObjectStore
from test_retrieval import add_paper, make_conv

KEY = "k"


@pytest.fixture()
async def client(pool: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("A9_INTERNAL_KEY", KEY)
    monkeypatch.setenv("A9_QDRANT_PATH", ":memory:")
    monkeypatch.setenv("A9_OBJECT_ROOT", str(tmp_path))
    async with app.router.lifespan_context(app):
        app.state.rag = None
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=120
        ) as c:
            yield c
        app.state.rag = None


def hdr(user: uuid.UUID) -> dict[str, str]:
    return {"X-A9-Internal-Key": KEY, "X-A9-User-Id": str(user)}


async def events(client: Any, conv: uuid.UUID, user: uuid.UUID, text: str) -> list[dict[str, Any]]:
    r = await client.post(
        f"/conversations/{conv}/messages", json={"content": text}, headers=hdr(user)
    )
    assert r.status_code == 200, r.text
    return [json.loads(line[6:]) for line in r.text.split("\n\n") if line.startswith("data: ")]


async def seeded(pool: Any, tmp_path: Path) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    store = LocalObjectStore(tmp_path)
    user, conv = await make_conv(pool)
    pid = await add_paper(pool, "kinase", store)
    async with scoped(pool, role="a9_worker") as c:
        await add_memberships(c, user_id=user, conversation_id=conv, paper_ids=[pid])
    return user, conv, pid


async def test_a_question_gets_cited_verified_sentences_and_every_citation_resolves(
    client: Any, pool: Any, tmp_path: Path
) -> None:
    user, conv, pid = await seeded(pool, tmp_path)
    evs = await events(
        client, conv, user, "Why does the C797S mutation cause resistance to osimertinib?"
    )
    kinds = [e["type"] for e in evs]
    assert kinds[0] == "retrieval" and kinds[-1] == "done" and "sentence" in kinds
    done = evs[-1]
    assert done["grounding_rate"] == 1.0 and done["citations_resolve"] is True
    cites = {c for e in evs if e["type"] == "sentence" for c in e["cites"]}
    assert cites
    for chunk_id in cites:  # a citation is a lookup, and every one of them resolves
        r = await client.get(f"/chunks/{chunk_id}", headers=hdr(user))
        assert r.status_code == 200
        body = r.json()
        assert (
            body["paper_id"] == str(pid)
            and body["source_span"]
            and body["section_path"]
            and body["page"] >= 1
        )
    async with owner(pool) as c:
        rows = await (
            await c.execute(
                "SELECT role, content FROM messages WHERE conversation_id = %s ORDER BY created_at",
                (conv,),
            )
        ).fetchall()
    assert [r["role"] for r in rows] == ["user", "assistant"] and "[c:" in rows[1]["content"]


async def test_an_empty_corpus_says_so_instead_of_answering(client: Any, pool: Any) -> None:
    user, conv = await make_conv(pool)
    evs = await events(client, conv, user, "What is known about anything?")
    assert [e["type"] for e in evs] == [
        "no_evidence",
        "done",
    ] and "nothing in this conversation" in evs[0]["text"]


async def test_other_users_cannot_ask_or_resolve(client: Any, pool: Any, tmp_path: Path) -> None:
    user, conv, pid = await seeded(pool, tmp_path)
    evs = await events(
        client, conv, user, "Why does the C797S mutation cause resistance to osimertinib?"
    )
    chunk = next(c for e in evs if e["type"] == "sentence" for c in e["cites"])
    stranger, _ = await make_conv(pool)
    assert (
        await client.post(
            f"/conversations/{conv}/messages", json={"content": "hi"}, headers=hdr(stranger)
        )
    ).status_code == 404
    assert (await client.get(f"/chunks/{chunk}", headers=hdr(stranger))).status_code == 404
    assert (await client.get(f"/chunks/{uuid.uuid4()}", headers=hdr(user))).status_code == 404
    assert (
        await client.post(
            f"/conversations/{conv}/messages", json={"content": ""}, headers=hdr(user)
        )
    ).status_code == 422
    assert (await client.get(f"/chunks/{chunk}")).status_code == 401


async def test_the_corpus_summary_shows_what_arrived_since_the_last_turn(
    client: Any, pool: Any, tmp_path: Path
) -> None:
    user, conv, first = await seeded(pool, tmp_path)
    store = LocalObjectStore(tmp_path)
    before = (await client.get(f"/conversations/{conv}/corpus", headers=hdr(user))).json()
    assert before["papers"] == 1 and before["new_chunks"] is None and before["latest"]
    cutoff = before["latest"]
    second = await add_paper(pool, "climate", store)  # the user widens the search mid-conversation
    async with scoped(pool, role="a9_worker") as c:
        await add_memberships(c, user_id=user, conversation_id=conv, paper_ids=[second])
    after = (
        await client.get(
            f"/conversations/{conv}/corpus", params={"since": cutoff}, headers=hdr(user)
        )
    ).json()
    assert (
        after["papers"] == 2
        and after["new_papers"] == 1
        and 0 < after["new_chunks"] < after["chunks"]
    )
    assert first != second
    assert (
        await client.get(f"/conversations/{uuid.uuid4()}/corpus", headers=hdr(user))
    ).status_code == 404
