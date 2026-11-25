"""The canonical parsed document.

One string (`text`) plus blocks that point into it by character offsets. Everything downstream (chunks,
claims, citations) refers to offsets in THIS string, so a citation always resolves to an exact span.
The same model is produced by every parser (JATS, PDF), which is what keeps provenance uniform.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Literal

BlockKind = Literal["abstract", "body", "table", "figure_caption", "references"]
SEPARATOR = "\n\n"


@dataclass
class Block:
    kind: BlockKind
    start: int
    end: int
    section_path: list[str]
    page: int = 1  # sources without pagination (JATS, HTML) are all "page 1"
    #: For tables: the cell grid, so the whole table can be stored structurally as well as linearised.
    rows: list[list[str]] | None = None


@dataclass
class ParsedDocument:
    text: str
    blocks: list[Block]
    parser: str
    title: str | None = None
    licence_raw: str | None = None
    ids: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def span(self, block: Block) -> str:
        return self.text[block.start : block.end]

    def to_json(self) -> bytes:
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":")).encode()

    @staticmethod
    def from_json(data: bytes) -> ParsedDocument:
        raw = json.loads(data)
        return ParsedDocument(**{**raw, "blocks": [Block(**b) for b in raw["blocks"]]})


class DocBuilder:
    """Append blocks one at a time; offsets are recorded exactly as the text is laid down."""

    def __init__(self, parser: str):
        self._parts: list[str] = []
        self._len = 0
        self.blocks: list[Block] = []
        self.parser = parser

    def add(
        self,
        kind: BlockKind,
        text: str,
        section_path: list[str],
        *,
        page: int = 1,
        rows: list[list[str]] | None = None,
    ) -> Block | None:
        text = text.strip()
        if not text:
            return None
        start = self._len + (len(SEPARATOR) if self._parts else 0)
        if self._parts:
            self._parts.append(SEPARATOR)
            self._len += len(SEPARATOR)
        self._parts.append(text)
        self._len += len(text)
        block = Block(kind, start, start + len(text), list(section_path), page, rows)
        self.blocks.append(block)
        return block

    def build(
        self,
        *,
        title: str | None = None,
        licence_raw: str | None = None,
        ids: dict[str, str] | None = None,
        warnings: list[str] | None = None,
    ) -> ParsedDocument:
        doc = ParsedDocument(
            text="".join(self._parts), blocks=self.blocks, parser=self.parser, title=title,
            licence_raw=licence_raw, ids=ids or {}, warnings=warnings or [],
        )  # fmt: skip
        problems = [b for b in doc.blocks if not (0 <= b.start < b.end <= len(doc.text))]
        assert not problems, f"block offsets outside the text: {problems[:3]}"
        return doc


_WS = re.compile(r"[ \t\r\f\v]+")


def collapse(text: str) -> str:
    """Collapse runs of whitespace (paragraph text); tables keep their own structure."""
    return re.sub(r"\s+", " ", text).strip()


def linearise_table(text: str) -> str:
    """Turn a table's tab/newline text into 'header: value; header: value' rows a retriever can match.

    Deterministic from the table text alone, so a linearised chunk can be re-derived from its span.
    """
    lines = [ln for ln in text.split("\n") if ln.strip()]
    rows = [[c.strip() for c in ln.split("\t")] for ln in lines]
    if len(rows) < 2:
        return "; ".join(c for r in rows for c in r if c)
    header, body = rows[0], rows[1:]
    out = []
    for row in body:
        pairs = [
            f"{header[i] if i < len(header) and header[i] else f'col{i + 1}'}: {c}"
            for i, c in enumerate(row)
            if c
        ]
        if pairs:
            out.append("; ".join(pairs))
    return "\n".join(out)
