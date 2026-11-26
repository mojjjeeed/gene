"""Answers: cited sentence by sentence, verified independently, unsupported ones removed and reported."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from a9_agents.answer import AnswerSentence, ExtractiveGenerator, OverlapVerifier, answer_question
from a9_agents.db import scoped
from a9_agents.fulltext.store import LocalObjectStore
from a9_agents.index.retrieval import retrieve
from test_retrieval import PAPERS, corpus

TRUE = "Patients who progressed on osimertinib frequently acquired the C797S mutation, which prevents covalent binding of the drug to the kinase."
SOURCE = PAPERS["kinase"][1]["Results"]


async def test_the_verifier_accepts_a_true_quote_and_rejects_each_kind_of_fabrication() -> None:
    v = OverlapVerifier()
    assert (await v.verify(TRUE, [SOURCE])).supported
    altered = TRUE.replace("frequently", "in 73% of cases")
    assert "73" in (await v.verify(altered, [SOURCE])).reason
    off_topic = (
        "Global mean sea level is projected to rise by 2 metres under every scenario considered."
    )
    assert not (await v.verify(off_topic, [SOURCE])).supported
    assert (await v.verify(TRUE, [])).reason == "the sentence cites nothing"
    assert not (
        await v.verify(TRUE, [PAPERS["climate"][1]["Results"]])
    ).supported  # right sentence, wrong citation


async def test_verifier_catches_constructed_fabrications_and_does_not_reject_true_quotes() -> None:
    """A floor, not a claim: number-changing fabrications are the easy case. Subtle misreadings need an entailment model."""
    v = OverlapVerifier()
    sources = [" ".join(p[1].values()) for p in PAPERS.values()]
    quotes = [
        (s.rstrip(".") + ".", src)
        for src in sources
        for s in src.split(". ")
        if len(s.split()) >= 8
    ]
    assert all([(await v.verify(q, [src])).supported for q, src in quotes]), (
        "a verbatim quote of its own source was rejected"
    )
    swaps = {"18.9": "31.4", "0.4": "1.9", "7": "12"}
    fakes = [
        (q.replace(old, new), src)
        for q, src in quotes
        for old, new in swaps.items()
        if f" {old} " in q or f" {old}." in q
    ]
    assert len(fakes) >= 3
    rejected = [not (await v.verify(f, [src])).supported for f, src in fakes]
    assert sum(rejected) / len(rejected) == 1.0


class Scripted:
    def __init__(self, sentences: list[AnswerSentence]):
        self._s = sentences

    async def generate(self, question: str, chunks: list[Any]) -> list[AnswerSentence]:
        return self._s


async def setup(
    pool: Any, embedder: Any, reranker: Any, qdrant: Any, tmp: Path
) -> tuple[Any, Any, Any, Any, Any]:
    store = LocalObjectStore(tmp)
    user, conv, index, ids = await corpus(pool, embedder, qdrant, ["kinase", "climate"], store)
    return store, user, conv, index, ids


async def test_the_extractive_pipeline_answers_with_resolving_citations(
    pool: Any, embedder: Any, reranker: Any, qdrant: Any, tmp_path: Path
) -> None:
    store, user, conv, index, ids = await setup(pool, embedder, reranker, qdrant, tmp_path)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        res = await retrieve(
            c,
            index,
            conv,
            embedder,
            reranker,
            "Why does the C797S mutation cause resistance to osimertinib?",
        )
        answer = await answer_question(
            c, store, res, ExtractiveGenerator(reranker), OverlapVerifier()
        )
    assert answer.kept and answer.grounding_rate == 1.0 and answer.citations_resolve
    assert any("C797S" in s.text for s in answer.kept)
    assert all(s.cites for s in answer.kept)


async def test_unsupported_sentences_are_removed_and_reported_never_shipped(
    pool: Any, embedder: Any, reranker: Any, qdrant: Any, tmp_path: Path
) -> None:
    store, user, conv, index, ids = await setup(pool, embedder, reranker, qdrant, tmp_path)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        res = await retrieve(
            c,
            index,
            conv,
            embedder,
            reranker,
            "Why does the C797S mutation cause resistance to osimertinib?",
        )
        top = res.chunks[0].chunk_id
        stranger = uuid.uuid4()
        gen = Scripted(
            [
                AnswerSentence(TRUE, [top]),  # supported
                AnswerSentence(
                    TRUE.replace("frequently", "in 73% of cases"), [top]
                ),  # invented number
                AnswerSentence(
                    "Ocean heat content decreased sharply during the observational record.", [top]
                ),  # off topic
                AnswerSentence(TRUE, [stranger]),  # cites a chunk that was never retrieved
                AnswerSentence("An uncited claim about the kinase domain and resistance.", []),
            ]
        )
        answer = await answer_question(c, store, res, gen, OverlapVerifier())
    assert [s.text for s in answer.kept] == [TRUE]
    assert len(answer.removed) == 4 and all(s.verdict.reason for s in answer.removed)
    assert any("73" in s.verdict.reason for s in answer.removed)
    assert any("was not retrieved" in s.verdict.reason for s in answer.removed)
    assert answer.grounding_rate == pytest.approx(0.2)  # reported honestly, not hidden


async def test_a_citation_whose_source_changed_is_flagged_unresolved(
    pool: Any, embedder: Any, reranker: Any, qdrant: Any, tmp_path: Path
) -> None:
    store, user, conv, index, ids = await setup(pool, embedder, reranker, qdrant, tmp_path)
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
        key = f"papers/{top.paper_id}/document.test-v1.json"
        store.put(key, store.get(key).replace(top.text[:25].encode(), b"X" * 25, 1))
        answer = await answer_question(
            c, store, res, Scripted([AnswerSentence(TRUE, [top.chunk_id])]), OverlapVerifier()
        )
    assert (
        answer.kept
        and not answer.citations_resolve
        and answer.unresolved_citations == [top.chunk_id]
    )
