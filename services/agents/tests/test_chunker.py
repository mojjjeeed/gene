"""Chunking invariants, on synthetic documents so each rule can be broken on purpose."""

from __future__ import annotations

import random
import re

from a9_agents.fulltext.chunker import (
    Chunk,
    chunk_document,
    count_tokens,
    embedding_text,
    paper_summary,
    verify_chunks,
)
from a9_agents.fulltext.document import DocBuilder, ParsedDocument, linearise_table


def sentence(i: int, words: int = 14) -> str:
    rng = random.Random(i)
    vocab = [
        "kinase",
        "binding",
        "assay",
        "resistance",
        "mutation",
        "inhibitor",
        "cells",
        "signalling",
        "dose",
        "tumour",
        "response",
        "cohort",
    ]
    return f"Finding {i} " + " ".join(rng.choice(vocab) for _ in range(words)) + "."


def paragraph(start: int, sentences: int) -> str:
    return " ".join(sentence(start + k) for k in range(sentences))


def build(sections: dict[str, int], *, extras: bool = True) -> ParsedDocument:
    b = DocBuilder("test-v1")
    b.add("abstract", paragraph(9000, 5), ["Abstract"])
    n = 0
    for name, paragraphs in sections.items():
        for _ in range(paragraphs):
            b.add("body", paragraph(n, 8), [name])
            n += 8
    if extras:
        b.add(
            "table",
            "Drug\tIC50 (nM)\nOsimertinib\t12\nGefitinib\t480",
            ["Results"],
            rows=[["Drug", "IC50 (nM)"], ["Osimertinib", "12"], ["Gefitinib", "480"]],
        )
        b.add("figure_caption", "Figure 2. Dose response of mutant cells.", ["Results"])
        b.add("references", "1. Somebody et al. A reference.", ["References"])
    return b.build(title="A test paper")


def test_every_chunk_is_an_exact_span_and_nothing_crosses_a_section() -> None:
    doc = build({"Introduction": 6, "Methods": 9, "Results": 4})
    chunks = chunk_document(doc)
    assert verify_chunks(doc, chunks) == []
    for c in chunks:
        if c.kind in ("body", "abstract"):
            assert doc.text[c.start : c.end] == c.text
            assert len(c.section_path) == 1


def test_body_chunks_respect_the_size_target_and_overlap_about_fifteen_percent() -> None:
    doc = build({"Methods": 40}, extras=False)
    body = [c for c in chunk_document(doc) if c.kind == "body"]
    assert len(body) >= 3
    assert all(c.tokens <= 800 for c in body)
    assert all(c.tokens >= 400 for c in body[:-1]), [c.tokens for c in body]
    ratios = [
        count_tokens(doc.text[b.start : a.end]) / a.tokens
        for a, b in zip(body, body[1:], strict=False)
        if b.start < a.end
    ]
    assert ratios and 0.08 <= sum(ratios) / len(ratios) <= 0.30, ratios
    assert all(
        b.start > a.start for a, b in zip(body, body[1:], strict=False)
    )  # always moves forward


def test_a_short_section_is_one_chunk_and_is_never_merged_across_the_boundary() -> None:
    doc = build({"Introduction": 1, "Methods": 1})
    body = [c for c in chunk_document(doc) if c.kind == "body"]
    assert [c.section_path for c in body] == [["Introduction"], ["Methods"]]
    assert all(c.tokens < 400 for c in body)


def test_tables_are_whole_and_also_linearised_and_captions_are_their_own_chunks() -> None:
    doc = build({"Results": 2})
    chunks = chunk_document(doc)
    (table,) = [c for c in chunks if c.kind == "table"]
    (lin,) = [c for c in chunks if c.kind == "table_linearised"]
    assert table.text == "Drug\tIC50 (nM)\nOsimertinib\t12\nGefitinib\t480"
    assert lin.text == "Drug: Osimertinib; IC50 (nM): 12\nDrug: Gefitinib; IC50 (nM): 480"
    assert (lin.start, lin.end) == (table.start, table.end), (
        "the linearised form points at the same source span"
    )
    (cap,) = [c for c in chunks if c.kind == "figure_caption"]
    assert cap.text.startswith("Figure 2.")


def test_references_are_not_chunked() -> None:
    assert not any("Somebody" in c.text for c in chunk_document(build({"Methods": 2})))


def test_a_single_enormous_sentence_is_split_at_word_boundaries_not_dropped() -> None:
    b = DocBuilder("t")
    giant = " ".join(f"word{i}" for i in range(3000)) + "."
    b.add("body", giant, ["Methods"])
    doc = b.build()
    chunks = chunk_document(doc)
    assert len(chunks) >= 4 and all(c.tokens <= 800 for c in chunks)
    assert verify_chunks(doc, chunks) == []
    covered: set[int] = set()
    for c in chunks:
        covered.update(range(c.start, c.end))
    assert covered >= set(range(len(giant)))  # nothing in the text is left out of every chunk


def test_chunking_is_deterministic() -> None:
    doc = build({"Methods": 20, "Results": 9})
    assert [(c.kind, c.start, c.end) for c in chunk_document(doc)] == [
        (c.kind, c.start, c.end) for c in chunk_document(doc)
    ]


def test_verification_catches_every_kind_of_corruption() -> None:
    doc = build({"Introduction": 3, "Methods": 3})
    good = chunk_document(doc)
    body = next(c for c in good if c.kind == "body")
    tampered = [Chunk(**{**body.__dict__, "text": body.text.replace("Finding", "Finding!", 1)})]
    assert any("differs" in p for p in verify_chunks(doc, tampered))
    outside = [Chunk(**{**body.__dict__, "end": len(doc.text) + 50})]
    assert any("outside" in p for p in verify_chunks(doc, outside))
    other = next(c for c in good if c.kind == "body" and c.section_path != body.section_path)
    straddling_text = doc.text[body.start : other.end]
    straddle = [
        Chunk(
            "body",
            straddling_text,
            body.start,
            other.end,
            body.section_path,
            1,
            count_tokens(straddling_text),
        )
    ]
    assert any("crosses a section" in p for p in verify_chunks(doc, straddle))
    lin = next(c for c in chunk_document(build({"Results": 1})) if c.kind == "table_linearised")
    assert any(
        "re-derivable" in p
        for p in verify_chunks(
            build({"Results": 1}), [Chunk(**{**lin.__dict__, "text": "made up"})]
        )
    )


def test_linearise_handles_ragged_and_single_row_tables() -> None:
    assert linearise_table("a\tb\n1\t2\t3") == "a: 1; b: 2; col3: 3"
    assert linearise_table("only\tone row") == "only; one row"
    assert linearise_table("") == ""


def test_the_context_header_is_prepended_for_embedding_but_never_stored_in_the_chunk() -> None:
    doc = build({"Methods": 2}, extras=False)
    chunk = next(c for c in chunk_document(doc) if c.kind == "body")
    summary = paper_summary("Kinase inhibitors work. Another sentence follows here.")
    assert summary == "Kinase inhibitors work."
    text = embedding_text(chunk, "A test paper", summary)
    assert text.startswith("A test paper\nMethods\nKinase inhibitors work.\n\n")
    assert text.endswith(chunk.text) and "A test paper" not in chunk.text
    assert paper_summary(None) == "" and len(paper_summary("x" * 500)) <= 200
    assert re.search(r"…$", paper_summary("y" * 500))
