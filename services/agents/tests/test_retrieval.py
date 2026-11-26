"""Index, isolation and hybrid retrieval, with the real open embedding and rerank models."""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from typing import Any

import pytest
from a9_agents.db import owner, scoped
from a9_agents.fulltext.chunker import chunk_document
from a9_agents.fulltext.document import DocBuilder
from a9_agents.fulltext.ingest import _insert_chunks, add_memberships
from a9_agents.index.conversation_index import ConversationIndex, make_client
from a9_agents.index.lexical import lexical_search, or_query
from a9_agents.index.pipeline import index_conversation
from a9_agents.index.retrieval import decompose, retrieve, rewrite_query, rrf

PAPERS = {
    "kinase": (
        "Acquired resistance to osimertinib in EGFR mutant lung cancer",
        {
            "Results": "Patients who progressed on osimertinib frequently acquired the C797S mutation, which prevents covalent binding of the drug to the kinase. "
            "The median time to progression after first line osimertinib was 18.9 months in the cohort. Rare variant ZX4417 was found in two patients.",
            "Discussion": "Fourth generation inhibitors that bind outside the ATP pocket may overcome C797S mediated resistance and are in early trials.",
        },
    ),
    "climate": (
        "Ocean heat uptake and sea level rise projections",
        {
            "Results": "Global mean sea level is projected to rise by 0.4 metres by 2100 under a moderate emissions scenario, driven by thermal expansion and glacier melt. "
            "Ocean heat content increased steadily across the observational record.",
            "Discussion": "Uncertainty in ice sheet dynamics dominates the high end of the projections.",
        },
    ),
    "genomics": (
        "Long read sequencing resolves structural variants in tumour genomes",
        {
            "Results": "Nanopore sequencing detected structural variants missed by short reads, including a large inversion on chromosome 7 and several complex rearrangements.",
            "Discussion": "Long reads improve phasing of haplotypes and resolve repetitive regions of the genome.",
        },
    ),
}


async def add_paper(pool: Any, key: str, store: Any = None) -> uuid.UUID:
    title, sections = PAPERS[key]
    pid, run = uuid.uuid4(), uuid.uuid4()
    b = DocBuilder("test-v1")
    b.add("abstract", sections["Results"].split(".")[0] + ".", ["Abstract"])
    for name, text in sections.items():
        b.add("body", text, [name])
    doc, chunks = b.build(title=title), None
    chunks = chunk_document(doc)
    if store is not None:
        store.put(f"papers/{pid}/document.test-v1.json", doc.to_json())
    async with owner(pool) as c:
        await c.execute(
            "INSERT INTO papers (id, title, source, abstract, licence, full_text_allowed, year) VALUES (%s, %s, 's', %s, 'cc by', true, 2024)",
            (pid, title, doc.span(doc.blocks[0])),
        )
        await _insert_chunks(c, pid, run, "test-v1", chunks)
    return pid


async def make_conv(pool: Any) -> tuple[uuid.UUID, uuid.UUID]:
    user, project, conv = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with owner(pool) as c:
        await c.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user, f"{user}@x.org"))
        await c.execute(
            "INSERT INTO projects (id, user_id, name) VALUES (%s, %s, 'p')", (project, user)
        )
        await c.execute(
            "INSERT INTO conversations (id, user_id, project_id) VALUES (%s, %s, %s)",
            (conv, user, project),
        )
    return user, conv


async def extra_conv(pool: Any, user: uuid.UUID) -> uuid.UUID:
    project, conv = uuid.uuid4(), uuid.uuid4()
    async with owner(pool) as c:
        await c.execute(
            "INSERT INTO projects (id, user_id, name) VALUES (%s, %s, 'p2')", (project, user)
        )
        await c.execute(
            "INSERT INTO conversations (id, user_id, project_id) VALUES (%s, %s, %s)",
            (conv, user, project),
        )
    return conv


async def corpus(
    pool: Any, embedder: Any, qdrant: Any, keys: list[str], store: Any = None
) -> tuple[uuid.UUID, uuid.UUID, ConversationIndex, dict[str, uuid.UUID]]:
    user, conv = await make_conv(pool)
    ids = {k: await add_paper(pool, k, store) for k in keys}
    async with scoped(pool, role="a9_worker") as c:
        await add_memberships(c, user_id=user, conversation_id=conv, paper_ids=list(ids.values()))
        index = ConversationIndex(qdrant, conv)
        await index_conversation(c, index, embedder, conv)
    return user, conv, index, ids


# --- pure functions ------------------------------------------------------------------------------


def test_rrf_rewards_agreement_over_a_single_arms_top_rank() -> None:
    a, b, c = (uuid.uuid4() for _ in range(3))
    fused = [i for i, _ in rrf([[a, b, c], [c, b, a], [b, c, a]])]
    assert fused[0] == b  # second in two arms and first in none still beats an isolated first place
    assert rrf([]) == []
    assert rrf([[a]])[0][0] == a and rrf([[a]])[0][1] == pytest.approx(1 / 61)
    assert [i for i, _ in rrf([[a, b], [b, a]])] == sorted(
        [a, b], key=str
    )  # ties break deterministically


def test_rewrite_anchors_follow_ups_and_leaves_standalone_questions_alone() -> None:
    history = ["What mutations cause osimertinib resistance?"]
    assert (
        rewrite_query(
            "What mutations cause osimertinib resistance in lung cancer patients?", history
        )
        == "What mutations cause osimertinib resistance in lung cancer patients?"
    )
    assert rewrite_query("And what about its prevalence?", history).startswith(
        "What mutations cause osimertinib resistance (And what about"
    )
    assert rewrite_query("how common?", history).startswith("What mutations")
    assert rewrite_query("Does it matter?", []) == "Does it matter?"


def test_decompose_splits_only_on_explicit_separators() -> None:
    assert decompose("What is C797S? How is it treated?") == [
        "What is C797S?",
        "How is it treated?",
    ]
    assert decompose("Define resistance; list the mutations") == [
        "Define resistance",
        "list the mutations",
    ]
    assert decompose("How does osimertinib bind and why does C797S block it?") == [
        "How does osimertinib bind and why does C797S block it?"
    ]
    assert len(decompose("a? B? C? D?")) <= 3


def test_the_lexical_query_cannot_carry_tsquery_syntax() -> None:
    assert or_query("What is EGFR T790M resistance?") == "egfr | t790m | resistance"
    assert or_query("'; DROP TABLE chunks; --") == "drop | table | chunks"
    assert or_query("a & ! | ( ) :*") is None and or_query("") is None


# --- structure: the vector client has exactly one importer -----------------------------------------


def test_nothing_but_the_conversation_index_imports_the_vector_client() -> None:
    root = Path(__file__).resolve().parents[3]
    allowed = root / "services/agents/src/a9_agents/index/conversation_index.py"
    offenders = []
    for path in [*(root / "services").rglob("*.py"), *(root / "packages").rglob("*.py")]:
        if ".venv" in path.parts or path == allowed:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(n == "qdrant_client" or n.startswith("qdrant_client.") for n in names):
                offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"only ConversationIndex may import the vector client: {offenders}"


def test_the_index_has_no_way_to_pass_a_raw_filter() -> None:
    import inspect

    for name, fn in inspect.getmembers(ConversationIndex, inspect.isfunction):
        if not name.startswith("_"):
            assert not {"query_filter", "filter", "scroll_filter"} & set(
                inspect.signature(fn).parameters
            ), name
    with pytest.raises(TypeError):
        ConversationIndex(make_client(memory=True), "not-a-uuid")  # type: ignore[arg-type]


# --- retrieval, with real models --------------------------------------------------------------------


async def test_hybrid_retrieval_finds_the_right_chunk_and_explains_how(
    pool: Any, embedder: Any, reranker: Any, qdrant: Any
) -> None:
    user, conv, index, ids = await corpus(pool, embedder, qdrant, ["kinase", "climate", "genomics"])
    async with scoped(pool, role="a9_app", user_id=user) as c:
        res = await retrieve(
            c,
            index,
            conv,
            embedder,
            reranker,
            "Why does the C797S mutation cause resistance to osimertinib?",
        )
        top = res.chunks[0]
        assert top.paper_id == ids["kinase"] and "C797S" in top.text
        assert {"dense", "lexical"} <= set(top.arms)  # surfaced by more than one arm
        assert res.candidates <= 50 and len(res.chunks) <= 10 and res.ms["total"] > 0

        sea = await retrieve(
            c, index, conv, embedder, reranker, "How much will sea level rise by 2100?"
        )
        assert sea.chunks[0].paper_id == ids["climate"]


async def test_the_lexical_arm_finds_a_rare_token_that_meaning_alone_would_not(
    pool: Any, embedder: Any, reranker: Any, qdrant: Any
) -> None:
    user, conv, index, ids = await corpus(pool, embedder, qdrant, ["kinase", "climate", "genomics"])
    async with scoped(pool, role="a9_app", user_id=user) as c:
        lex = await lexical_search(c, conv, "ZX4417")
        assert len(lex) == 1
        res = await retrieve(c, index, conv, embedder, reranker, "What was found about ZX4417?")
        assert any("ZX4417" in x.text and x.arms.get("lexical") == 1 for x in res.chunks[:3])


async def test_expansion_adds_the_neighbouring_context_within_a_section(
    pool: Any, embedder: Any, reranker: Any, qdrant: Any
) -> None:
    user, conv, index, ids = await corpus(pool, embedder, qdrant, ["kinase"])
    async with scoped(pool, role="a9_app", user_id=user) as c:
        res = await retrieve(
            c, index, conv, embedder, reranker, "C797S fourth generation inhibitors", final=5
        )
    assert all(x.kind in ("abstract", "body") for x in res.chunks)
    assert all(isinstance(x.before, str) and isinstance(x.after, str) for x in res.chunks)


async def test_a_conversation_never_sees_another_conversations_chunks(
    pool: Any, embedder: Any, reranker: Any, qdrant: Any
) -> None:
    user_a, conv_a, index_a, _ = await corpus(pool, embedder, qdrant, ["kinase"])
    user_b, conv_b, index_b, ids_b = await corpus(pool, embedder, qdrant, ["climate"])
    assert await index_a.count() > 0 and await index_b.count() > 0
    vec = await embedder.embed_query("sea level rise")
    assert {h.paper_id for h in await index_b.search_chunks(vec)} == {ids_b["climate"]}
    assert all(
        h.paper_id != ids_b["climate"] for h in await index_a.search_chunks(vec)
    )  # A cannot reach B's paper
    async with scoped(pool, role="a9_app", user_id=user_a) as c:
        assert (
            await lexical_search(c, conv_a, "sea level rise ocean") == []
        )  # lexical arm is scoped too
        res = await retrieve(
            c, index_a, conv_a, embedder, reranker, "How much will sea level rise?"
        )
        assert all(x.paper_id != ids_b["climate"] for x in res.chunks)


async def test_a_chunk_is_embedded_once_however_many_conversations_use_it(
    pool: Any, embedder: Any, qdrant: Any
) -> None:
    calls = {"n": 0}

    class Counting:
        name, dims = embedder.name, embedder.dims

        async def embed(self, texts: list[str]) -> list[list[float]]:
            calls["n"] += len(texts)
            return list(await embedder.embed(texts))

        async def embed_query(self, text: str) -> list[float]:
            return list(await embedder.embed_query(text))

    user, conv1 = await make_conv(pool)
    pid = await add_paper(pool, "kinase")
    conv2 = await extra_conv(pool, user)
    async with scoped(pool, role="a9_worker") as c:
        await add_memberships(c, user_id=user, conversation_id=conv1, paper_ids=[pid])
        first = await index_conversation(c, ConversationIndex(qdrant, conv1), Counting(), conv1)
        spent = calls["n"]
        await add_memberships(c, user_id=user, conversation_id=conv2, paper_ids=[pid])
        second = await index_conversation(c, ConversationIndex(qdrant, conv2), Counting(), conv2)
    assert first.chunks_embedded == first.chunks_total > 0 and first.chunks_reused == 0
    assert (second.chunks_embedded, second.chunks_reused) == (0, first.chunks_total)
    assert (
        calls["n"] - spent == 1
    )  # only the one paper-level vector for the second conversation, no chunks
    assert await ConversationIndex(qdrant, conv2).count() == first.chunks_total


async def test_removing_a_conversation_deletes_what_only_it_used_and_keeps_shared_vectors(
    pool: Any, embedder: Any, qdrant: Any
) -> None:
    user, conv1, index1, ids = await corpus(pool, embedder, qdrant, ["kinase"])
    conv2 = await extra_conv(pool, user)
    async with scoped(pool, role="a9_worker") as c:
        await add_memberships(c, user_id=user, conversation_id=conv2, paper_ids=[ids["kinase"]])
        index2 = ConversationIndex(qdrant, conv2)
        await index_conversation(c, index2, embedder, conv2)
    shared = await index1.count()
    await index1.remove_conversation()
    assert (
        await index1.count() == 0 and await index2.count() == shared
    )  # the other conversation still has them
    await index2.remove_conversation()
    assert (
        await index2.count() == 0 and qdrant.count("a9_chunks").count == 0
    )  # nobody left: the vectors are gone
