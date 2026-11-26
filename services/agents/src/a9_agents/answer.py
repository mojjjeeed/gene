"""Answering a question from retrieved chunks, with every sentence cited and independently verified.

Generation is cite-as-you-write: each sentence carries the ids of the chunks it rests on. A separate
verifier then sees ONLY the sentence and the cited chunks (never the generator's reasoning or the other
chunks) and decides whether the citation supports it. Unsupported sentences are removed and REPORTED;
nothing is shipped quietly. Every cited chunk id is resolved against its exact source span.

STAND-INS (no model access): `ExtractiveGenerator` quotes the best sentences instead of writing prose,
and `OverlapVerifier` is a lexical check (numbers and content words), not an entailment model. The
interfaces are what an LLM generator and an LLM verifier plug into.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from a9_agents.db import Conn
from a9_agents.fulltext.ingest import resolve_chunk
from a9_agents.fulltext.store import ObjectStore
from a9_agents.index.embed import Reranker
from a9_agents.index.retrieval import RetrievalResult, RetrievedChunk

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[\"'])")
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_WORD = re.compile(r"[a-z][a-z0-9\-]{2,}")
_STOP = frozenset(
    "the and for with that this was were are from have has had not but which their than then also been into its these those can may such our about between".split()
)
MAX_QUOTE_WORDS = 60  # answers paraphrase by default; quotation is capped and always attributed


@dataclass(frozen=True)
class AnswerSentence:
    text: str
    cites: list[uuid.UUID]


@dataclass(frozen=True)
class Verdict:
    supported: bool
    reason: str


@dataclass
class VerifiedSentence:
    text: str
    cites: list[uuid.UUID]
    verdict: Verdict


@dataclass
class Answer:
    question: str
    kept: list[VerifiedSentence] = field(default_factory=list)
    #: Sentences the verifier rejected. Reported to the user, never silently discarded.
    removed: list[VerifiedSentence] = field(default_factory=list)
    unresolved_citations: list[uuid.UUID] = field(default_factory=list)

    @property
    def grounding_rate(self) -> float:
        total = len(self.kept) + len(self.removed)
        return len(self.kept) / total if total else 1.0

    @property
    def citations_resolve(self) -> bool:
        return not self.unresolved_citations


class Generator(Protocol):
    async def generate(
        self, question: str, chunks: list[RetrievedChunk]
    ) -> list[AnswerSentence]: ...


class Verifier(Protocol):
    async def verify(self, sentence: str, cited_texts: list[str]) -> Verdict:
        """Sees only the sentence and the chunks it cites."""
        ...


def sentences_of(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if len(s.split()) >= 6]


class ExtractiveGenerator:
    """Quote the sentences that best answer the question, each cited to its own chunk."""

    def __init__(self, reranker: Reranker, max_sentences: int = 4, min_score: float = -2.0):
        self._reranker, self._max, self._min = reranker, max_sentences, min_score

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> list[AnswerSentence]:
        pool = [
            (s, c.chunk_id)
            for c in chunks[:6]
            for s in sentences_of(c.text)
            if len(s.split()) <= MAX_QUOTE_WORDS
        ]
        if not pool:
            return []
        scores = await self._reranker.rerank(question, [s for s, _ in pool])
        best = sorted(zip(pool, scores, strict=True), key=lambda x: -x[1])[: self._max]
        return [AnswerSentence(s, [cid]) for (s, cid), score in best if score >= self._min]


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUM.findall(text)}


def _content(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


class OverlapVerifier:
    """Supported iff every number in the sentence appears in a cited chunk and most of its content words do."""

    def __init__(self, min_overlap: float = 0.7):
        self._min = min_overlap

    async def verify(self, sentence: str, cited_texts: list[str]) -> Verdict:
        if not cited_texts:
            return Verdict(False, "the sentence cites nothing")
        source = " ".join(cited_texts)
        missing = _numbers(sentence) - _numbers(source)
        if missing:
            return Verdict(False, f"number(s) not in the cited text: {', '.join(sorted(missing))}")
        words = _content(sentence)
        if not words:
            return Verdict(False, "nothing checkable in the sentence")
        overlap = len(words & _content(source)) / len(words)
        if overlap < self._min:
            return Verdict(False, f"only {overlap:.0%} of its content appears in the cited text")
        return Verdict(
            True, f"{overlap:.0%} of its content and all its numbers appear in the cited text"
        )


async def answer_question(
    conn: Conn,
    store: ObjectStore,
    retrieval: RetrievalResult,
    generator: Generator,
    verifier: Verifier,
) -> Answer:
    by_id = {c.chunk_id: c for c in retrieval.chunks}
    answer = Answer(retrieval.question)
    for s in await generator.generate(retrieval.rewritten, retrieval.chunks):
        # A citation to a chunk that was never retrieved cannot support anything.
        cited = [by_id[c].text for c in s.cites if c in by_id]
        verdict = (
            await verifier.verify(s.text, cited)
            if len(cited) == len(s.cites)
            else Verdict(False, "cites a chunk that was not retrieved")
        )
        (answer.kept if verdict.supported else answer.removed).append(
            VerifiedSentence(s.text, s.cites, verdict)
        )
    for cid in dict.fromkeys(c for v in answer.kept for c in v.cites):
        try:
            await resolve_chunk(
                conn, store, cid
            )  # raises if the chunk or its source span is gone or altered
        except (LookupError, ValueError, OSError):
            answer.unresolved_citations.append(cid)
    return answer
