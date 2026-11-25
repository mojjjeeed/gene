"""Section-aware chunking with offsets.

Invariants (all checked by `verify_chunks`, across a whole corpus):
  * every chunk's text is an exact contiguous span of the document text (derived chunks, i.e. linearised
    tables, are re-derivable from their span);
  * no chunk crosses a section boundary;
  * body chunks target 400-800 tokens with about 15% overlap; a section shorter than the target is one chunk;
  * tables are stored whole AND linearised; figure captions are their own chunks;
  * references are not chunked.
The context header that precedes embedding is built separately and never stored as chunk text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from a9_agents.fulltext.document import Block, ParsedDocument, linearise_table

CHUNKER_VERSION = "chunker-v1"
TARGET_MIN, TARGET_MAX, OVERLAP = 400, 800, 0.15

_TOKEN = re.compile(r"\w+|[^\w\s]")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[\"'])")


def count_tokens(text: str) -> int:
    """A word-piece-like estimate: words and punctuation. It is not the embedding model's tokenizer."""
    return len(_TOKEN.findall(text))


@dataclass
class Chunk:
    kind: str  # abstract | body | table | table_linearised | figure_caption
    text: str
    start: int
    end: int
    section_path: list[str]
    page: int
    tokens: int


@dataclass
class _Unit:
    start: int
    end: int
    tokens: int
    page: int


def _units(doc: ParsedDocument, block: Block, max_tokens: int) -> list[_Unit]:
    """Sentences of a block as spans; a sentence longer than max_tokens is cut at word boundaries."""
    text = doc.text[block.start : block.end]
    units: list[_Unit] = []
    pos = 0
    for part in _SENT.split(text):
        idx = text.index(part, pos)
        pos = idx + len(part)
        start, end = block.start + idx, block.start + idx + len(part)
        n = count_tokens(part)
        if n <= max_tokens:
            units.append(_Unit(start, end, n, block.page))
            continue
        words = list(re.finditer(r"\S+", part))
        step_start = 0
        while step_start < len(words):
            window = words[step_start : step_start + max_tokens // 2]
            s, e = start + window[0].start(), start + window[-1].end()
            units.append(_Unit(s, e, count_tokens(doc.text[s:e]), block.page))
            step_start += len(window)
    return units


def _chunk_units(
    doc: ParsedDocument,
    units: list[_Unit],
    kind: str,
    path: list[str],
    lo: int,
    hi: int,
    overlap: float,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    i = 0
    while i < len(units):
        j, total = i, 0
        while j < len(units) and (total + units[j].tokens <= hi or j == i):
            total += units[j].tokens
            j += 1
        # A small tail that would become its own tiny chunk is folded into this one if it still fits.
        tail = sum(u.tokens for u in units[j:])
        if j < len(units) and tail < lo // 4 and total + tail <= hi + lo // 4:
            j, total = len(units), total + tail
        s, e = units[i].start, units[j - 1].end
        chunks.append(
            Chunk(kind, doc.text[s:e], s, e, path, units[i].page, count_tokens(doc.text[s:e]))
        )
        if j >= len(units):
            break
        # Next chunk starts far enough back to repeat about `overlap` of this one, but always moves forward.
        back, repeat = j, 0
        while back - 1 > i and repeat < overlap * total:
            back -= 1
            repeat += units[back].tokens
        i = max(back, i + 1)
    return chunks


def chunk_document(
    doc: ParsedDocument, *, lo: int = TARGET_MIN, hi: int = TARGET_MAX, overlap: float = OVERLAP
) -> list[Chunk]:
    out: list[Chunk] = []
    group: list[Block] = []

    def flush() -> None:
        if not group:
            return
        units = [u for blk in group for u in _units(doc, blk, hi)]
        if units:
            out.extend(
                _chunk_units(doc, units, group[0].kind, group[0].section_path, lo, hi, overlap)
            )
        group.clear()

    for block in doc.blocks:
        if block.kind in ("abstract", "body"):
            if group and (
                group[0].kind != block.kind or group[0].section_path != block.section_path
            ):
                flush()
            group.append(block)
            continue
        flush()
        if block.kind == "references":
            continue
        text = doc.text[block.start : block.end]
        n = count_tokens(text)
        if block.kind == "table":
            out.append(
                Chunk("table", text, block.start, block.end, block.section_path, block.page, n)
            )
            lin = linearise_table(text)
            if lin.strip():
                out.append(
                    Chunk(
                        "table_linearised",
                        lin,
                        block.start,
                        block.end,
                        block.section_path,
                        block.page,
                        count_tokens(lin),
                    )
                )
        elif block.kind == "figure_caption":
            out.append(
                Chunk(
                    "figure_caption",
                    text,
                    block.start,
                    block.end,
                    block.section_path,
                    block.page,
                    n,
                )
            )
    flush()
    return out


def verify_chunks(doc: ParsedDocument, chunks: list[Chunk]) -> list[str]:
    """Every way a chunk can fail to round-trip to its source. Empty means every chunk is exact."""
    problems: list[str] = []
    by_section = [(b.start, b.end, b.section_path, b.kind) for b in doc.blocks]
    for n, c in enumerate(chunks):
        tag = f"chunk {n} ({c.kind} {c.start}-{c.end})"
        if not (0 <= c.start < c.end <= len(doc.text)):
            problems.append(f"{tag}: span outside the document")
            continue
        source = doc.text[c.start : c.end]
        if c.kind == "table_linearised":
            if linearise_table(source) != c.text:
                problems.append(f"{tag}: not re-derivable from its table span")
        elif source != c.text:
            problems.append(f"{tag}: text differs from the source span")
        if c.kind in ("abstract", "body"):
            paths = {
                tuple(p)
                for s, e, p, k in by_section
                if s < c.end and e > c.start and k in ("abstract", "body")
            }
            if len(paths) != 1 or list(next(iter(paths))) != c.section_path:
                problems.append(f"{tag}: crosses a section boundary or has the wrong section path")
    return problems


def paper_summary(abstract: str | None, limit: int = 200) -> str:
    """One line on what the paper is about: the abstract's first sentence. (An LLM summary comes later.)"""
    if not abstract:
        return ""
    first = _SENT.split(abstract.strip())[0]
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def embedding_text(chunk: Chunk, title: str, summary: str) -> str:
    """What is embedded: title, section path, and a one-line summary, then the chunk. Never stored as the chunk."""
    header = [title, " > ".join(chunk.section_path)]
    if summary:
        header.append(summary)
    return "\n".join(h for h in header if h) + "\n\n" + chunk.text
