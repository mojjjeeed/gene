"""PDF -> ParsedDocument with PyMuPDF.

Heuristic by nature: headings come from font size and weight, running headers and footers from text that
repeats across pages, tables from PyMuPDF's table finder. It is the fallback when no structured source
(JATS) exists, and its failures are reported, not hidden: a document that yields too little text raises.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import pymupdf

from a9_agents.fulltext.document import BlockKind, DocBuilder, ParsedDocument, collapse

PARSER_VERSION = "pymupdf-v1"
MIN_CHARS_PER_PAGE = 200  # below this on average, treat it as a scan or a failed extraction

_KNOWN = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s*)?(abstract|introduction|background|methods?|materials and methods|results(?: and discussion)?|"
    r"discussion|conclusions?|references|bibliography|acknowledg(?:e)?ments?|supplementary(?: information)?)\s*$",
    re.IGNORECASE,
)
_NUMBERED = re.compile(r"^\d+(\.\d+)*\.?\s+\S")
_FIG = re.compile(r"^(figure|fig\.?)\s*\d+", re.IGNORECASE)
_TABLE = re.compile(r"^table\s*\d+", re.IGNORECASE)


def _join_lines(lines: list[str]) -> str:
    out = ""
    for line in lines:
        if out.endswith("-") and line[:1].islower():
            out = out[:-1] + line  # re-join a word hyphenated across a line break
        else:
            out = f"{out} {line}" if out else line
    return collapse(out)


def _within(inner: tuple[float, ...], outer: tuple[float, ...], tol: float = 2.0) -> bool:
    return (
        inner[0] >= outer[0] - tol
        and inner[1] >= outer[1] - tol
        and inner[2] <= outer[2] + tol
        and inner[3] <= outer[3] + tol
    )


def parse_pdf(data: bytes) -> ParsedDocument:
    try:
        pdf: Any = pymupdf.open(stream=data, filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception as exc:
        raise ValueError(f"unreadable PDF: {exc}") from exc
    if pdf.is_encrypted:
        raise ValueError("PDF is encrypted")
    if pdf.page_count == 0:
        raise ValueError("PDF has no pages")

    pages: list[
        tuple[float, list[dict[str, Any]], list[tuple[float, ...]], list[list[list[str]]]]
    ] = []
    sizes: Counter[float] = Counter()
    for page in pdf:
        raw = page.get_text("dict")
        blocks: list[dict[str, Any]] = []
        for blk in raw["blocks"]:
            if blk.get("type") != 0:
                continue
            lines = []
            for ln in blk["lines"]:
                text = "".join(s["text"] for s in ln["spans"]).strip()
                if not text:
                    continue
                size = round(max(s["size"] for s in ln["spans"]), 1)
                bold = any((s["flags"] & 16) or "bold" in s["font"].lower() for s in ln["spans"])
                sizes[size] += len(text)
                lines.append({"text": text, "size": size, "bold": bold})
            if lines:
                blocks.append({"lines": lines, "bbox": tuple(blk["bbox"])})
        table_boxes: list[tuple[float, ...]] = []
        table_rows: list[list[list[str]]] = []
        try:
            for t in page.find_tables().tables:
                rows = [[collapse(c or "") for c in r] for r in t.extract()]
                filled = sum(1 for r in rows for c in r if c)
                if (
                    len(rows) >= 2
                    and max(len(r) for r in rows) >= 2
                    and filled >= 0.6 * sum(len(r) for r in rows)
                ):
                    table_boxes.append(tuple(t.bbox))
                    table_rows.append(rows)
        except Exception:  # table finding is best-effort; the text is still parsed
            pass
        pages.append((page.rect.height, blocks, table_boxes, table_rows))

    body_size = sizes.most_common(1)[0][0] if sizes else 10.0

    # Running headers/footers: short text near the top or bottom that repeats on many pages.
    repeats: Counter[str] = Counter()
    for height, blocks, _, _ in pages:
        seen = set()
        for blk in blocks:
            y0, y1 = blk["bbox"][1], blk["bbox"][3]
            if y1 < height * 0.09 or y0 > height * 0.91:
                key = re.sub(r"\d+", "#", _join_lines([ln["text"] for ln in blk["lines"]])).lower()
                if key not in seen:
                    seen.add(key)
                    repeats[key] += 1
    threshold = max(3, int(0.4 * len(pages)))
    furniture = {k for k, n in repeats.items() if n >= threshold and len(k) < 140}

    b = DocBuilder(PARSER_VERSION)
    path: list[str] = []
    section_kind: BlockKind = "body"
    total_chars = 0
    for pno, (height, blocks, table_boxes, table_rows) in enumerate(pages, start=1):
        pending_tables = list(zip(table_boxes, table_rows, strict=True))
        emitted_tables = [False] * len(pending_tables)
        for blk in blocks:
            text = _join_lines([ln["text"] for ln in blk["lines"]])
            y0, y1 = blk["bbox"][1], blk["bbox"][3]
            near_edge = y1 < height * 0.09 or y0 > height * 0.91
            if not text:
                continue
            if near_edge and (
                re.sub(r"\d+", "#", text).lower() in furniture or re.fullmatch(r"\d{1,4}", text)
            ):
                continue
            inside = next(
                (i for i, (box, _) in enumerate(pending_tables) if _within(blk["bbox"], box)), None
            )
            if inside is not None:
                if not emitted_tables[inside]:
                    emitted_tables[inside] = True
                    rows = pending_tables[inside][1]
                    b.add(
                        "table",
                        "\n".join("\t".join(r) for r in rows),
                        list(path) or ["Body"],
                        page=pno,
                        rows=rows,
                    )
                    total_chars += sum(len(c) for r in rows for c in r)
                continue
            first = blk["lines"][0]
            heading_like = (
                len(blk["lines"]) <= 2
                and len(text) < 120
                and (
                    _KNOWN.match(text)
                    or (first["size"] >= body_size * 1.12 and not text.endswith("."))
                    or (
                        first["bold"]
                        and first["size"] >= body_size * 0.98
                        and len(text) < 80
                        and _NUMBERED.match(text)
                    )
                )
            )
            if heading_like:
                label = re.sub(r"^\d+(\.\d+)*\.?\s*", "", text).strip() or text
                if _NUMBERED.match(text) and "." in text.split()[0].rstrip(".") and path:
                    path = [
                        path[0],
                        text,
                    ]  # a numbered sub-heading sits under the current top-level one
                else:
                    path = [text]
                low = label.lower()
                section_kind = (
                    "references"
                    if re.match(r"(references|bibliography)", low)
                    else ("abstract" if low.startswith("abstract") else "body")
                )
                continue
            if _FIG.match(text):
                b.add("figure_caption", text, list(path) or ["Body"], page=pno)
            else:
                b.add(section_kind if path else "body", text, list(path) or ["Body"], page=pno)
            total_chars += len(text)

    if total_chars < MIN_CHARS_PER_PAGE * min(pdf.page_count, 3):
        raise ValueError(
            f"extracted only {total_chars} characters from {pdf.page_count} pages (scanned or image-only PDF?)"
        )
    meta_title = (pdf.metadata or {}).get("title") or None
    return b.build(
        title=meta_title, warnings=[] if len(b.blocks) > 3 else ["very little structure recovered"]
    )
