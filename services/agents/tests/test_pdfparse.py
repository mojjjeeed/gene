"""PDF parsing on generated PDFs, so layout features can be controlled and each heuristic checked."""

from __future__ import annotations

import pymupdf
import pytest
from a9_agents.fulltext.chunker import chunk_document, verify_chunks
from a9_agents.fulltext.pdfparse import parse_pdf

BODY = (
    "We measured the response of mutant cell lines to a panel of kinase inhibitors across seven doses and three replicates, "
    "and fitted dose response curves to estimate potency in every line under identical conditions."
)


def make_pdf(*, encrypt: bool = False, empty: bool = False, pages: int = 4) -> bytes:
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        page = doc.new_page()
        page.insert_text((72, 30), "Journal of Tests 2026 Vol 3", fontsize=8)  # running header
        page.insert_text((300, 825), str(n), fontsize=9)  # page number
        if empty:
            continue
        if n == 1:
            page.insert_text((72, 75), "A Study of Kinase Resistance", fontsize=20)
            page.insert_text((72, 110), "Abstract", fontsize=14)
            page.insert_textbox(
                pymupdf.Rect(72, 120, 520, 220),
                "Resistance to targeted therapy limits outcomes. " + BODY,
                fontsize=10,
            )
            page.insert_text((72, 250), "1. Introduction", fontsize=14)
            page.insert_text((72, 275), "The inhib-", fontsize=10)
            page.insert_text(
                (72, 288),
                "itor binds the hinge region of the kinase domain and blocks signalling in tumour cells.",
                fontsize=10,
            )
            page.insert_textbox(pymupdf.Rect(72, 300, 520, 420), BODY * 2, fontsize=10)
        if n == 2:
            page.insert_text((72, 80), "2. Methods", fontsize=14)
            page.insert_textbox(pymupdf.Rect(72, 95, 520, 260), BODY * 3, fontsize=10)
            page.insert_text(
                (72, 300), "Figure 1. Overview of the dose response assay.", fontsize=9
            )
        if n == 3:
            page.insert_text((72, 80), "3. Results", fontsize=14)
            page.insert_textbox(pymupdf.Rect(72, 95, 520, 260), BODY * 3, fontsize=10)
        if n == 4:
            page.insert_text((72, 80), "References", fontsize=14)
            page.insert_textbox(
                pymupdf.Rect(72, 95, 520, 200),
                "1. Someone A. A reference list entry that must never be chunked. 2. Other B. Another entry.",
                fontsize=9,
            )
    out: bytes = (
        doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
        if encrypt
        else doc.tobytes()
    )
    return out


def test_headings_sections_and_pages_are_recovered() -> None:
    doc = parse_pdf(make_pdf())
    paths = {tuple(b.section_path) for b in doc.blocks}
    assert (
        ("Abstract",) in paths
        and ("1. Introduction",) in paths
        and ("2. Methods",) in paths
        and ("3. Results",) in paths
    )
    methods = [b for b in doc.blocks if b.section_path == ["2. Methods"] and b.kind == "body"]
    assert methods and all(b.page == 2 for b in methods)
    assert any(b.kind == "abstract" for b in doc.blocks)


def test_running_headers_and_page_numbers_are_removed() -> None:
    doc = parse_pdf(make_pdf())
    assert "Journal of Tests" not in doc.text
    assert not any(line.strip().isdigit() for line in doc.text.split("\n"))


def test_a_word_hyphenated_across_a_line_break_is_rejoined() -> None:
    doc = parse_pdf(make_pdf())
    assert "inhibitor binds the hinge region" in doc.text and "inhib- itor" not in doc.text


def test_figure_captions_are_their_own_blocks_and_references_are_marked_and_never_chunked() -> None:
    doc = parse_pdf(make_pdf())
    caption = next(b for b in doc.blocks if b.kind == "figure_caption")
    assert doc.span(caption).startswith("Figure 1.")
    refs = [b for b in doc.blocks if b.kind == "references"]
    assert refs and any("reference list entry" in doc.span(b) for b in refs)
    assert not any("reference list entry" in c.text for c in chunk_document(doc))


def test_the_chunks_of_a_parsed_pdf_round_trip() -> None:
    doc = parse_pdf(make_pdf())
    chunks = chunk_document(doc)
    assert chunks and verify_chunks(doc, chunks) == []


def test_a_pdf_with_no_extractable_text_is_an_error_not_an_empty_document() -> None:
    with pytest.raises(ValueError, match="only .* characters"):
        parse_pdf(make_pdf(empty=True))


def test_unreadable_and_encrypted_pdfs_are_errors() -> None:
    with pytest.raises(ValueError, match="unreadable PDF"):
        parse_pdf(b"%PDF-1.4 this is not a real pdf")
    with pytest.raises(ValueError, match="encrypted"):
        parse_pdf(make_pdf(encrypt=True))


def test_document_json_round_trips_exactly() -> None:
    from a9_agents.fulltext.document import ParsedDocument

    doc = parse_pdf(make_pdf())
    again = ParsedDocument.from_json(doc.to_json())
    assert again.text == doc.text and again.blocks == doc.blocks and again.parser == doc.parser
