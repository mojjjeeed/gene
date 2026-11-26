"""Measured-value claims (IC50, Ki, Kd, EC50, GI50) from chunk text, with exact offsets.

This extractor is RULE-BASED, not a language model: it finds only values written as '<assay> ... <number> <unit>'
and says nothing about anything else. The schema-constrained LLM extractor (targets, pathways, cohorts,
endpoints, limitations) plugs in behind the same interface and is not built. Offsets are relative to the chunk
text, so the result can be cached by the text's hash and reused wherever that text appears.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from psycopg.types.json import Jsonb

from a9_agents.db import Conn

EXTRACTOR_VERSION = "regex-measurements-v1"
TO_NM = {"pm": 1e-3, "nm": 1.0, "um": 1e3, "µm": 1e3, "μm": 1e3, "mm": 1e6}
ASSAY = r"IC\s?50|IC₅₀|EC\s?50|EC₅₀|GI\s?50|GI₅₀|K\s?i|K\s?d|K\s?D"
_VALUE = re.compile(
    rf"\b(?P<assay>{ASSAY})\b(?:\s+values?)?(?:\s+(?:of|was|were|is|=|:|around|approximately|about))*\s*(?:=|:)?\s*"
    r"(?P<q>[<>≤≥~≈]|less than|greater than)?\s*(?P<num>\d+(?:\.\d+)?)\s*(?:±\s*\d+(?:\.\d+)?\s*)?(?P<unit>pM|nM|µM|μM|uM|mM)\b"
)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[\"'])")
_TARGET = re.compile(r"\b[A-Z][A-Z0-9]{2,7}(?:-[A-Z0-9]+)?\b")
_TARGET_SKIP = frozenset(
    {
        "IC50",
        "EC50",
        "GI50",
        "KD",
        "DNA",
        "RNA",
        "ATP",
        "PDF",
        "FDA",
        "NSCLC",
        "TKI",
        "SD",
        "SEM",
        "HPLC",
        "NMR",
    }
)


@dataclass(frozen=True)
class Claim:
    kind: str
    assay: str
    qualifier: str | None
    value: float
    unit: str
    value_nm: float
    entity_raw: str | None
    target_raw: str | None
    sentence: str
    start: int  # relative to the chunk text
    end: int


class ClaimExtractor(Protocol):
    version: str

    def extract(self, text: str) -> list[Claim]: ...


def _assay(raw: str) -> str:
    a = re.sub(r"\s", "", raw).replace("₅₀", "50")
    return {"Ki": "Ki", "Kd": "Kd", "KD": "Kd"}.get(a, a)


class RegexClaimExtractor:
    version = EXTRACTOR_VERSION

    def extract(self, text: str) -> list[Claim]:
        spans, pos = [], 0
        for part in _SENT.split(text):
            i = text.index(part, pos)
            pos = i + len(part)
            spans.append((i, i + len(part)))
        claims = []
        for m in _VALUE.finditer(text):
            s0, s1 = next((a, b) for a, b in spans if a <= m.start() < b or b > m.start())
            sentence = text[s0:s1]
            before = sentence[: m.start() - s0]
            targets = [t for t in _TARGET.findall(sentence) if t not in _TARGET_SKIP]
            subject = re.match(
                r"\s*((?:[A-Z][\w\-]*|\d+)(?:\s+(?:[A-Z]?[\w\-]*\d[\w\-]*|[A-Z][\w\-]*))?)", before
            )
            value = float(m.group("num"))
            unit = m.group("unit").replace("μ", "µ")  # Greek mu -> micro sign
            unit = "µM" if unit == "uM" else unit
            claims.append(
                Claim(
                    "measurement",
                    _assay(m.group("assay")),
                    m.group("q"),
                    value,
                    unit,
                    value * TO_NM[unit.lower()],
                    subject.group(1).strip() if subject else None,
                    targets[0] if targets else None,
                    sentence,
                    m.start(),
                    m.end(),
                )
            )
        return claims


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class ExtractStats:
    chunks: int = 0
    cache_hits: int = 0
    extractions: int = 0
    claims: int = 0


async def extract_corpus(
    conn: Conn, extractor: ClaimExtractor, paper_ids: list[uuid.UUID], run_id: uuid.UUID
) -> ExtractStats:
    """Extract claims from every text chunk of the papers. Cached by (chunk hash, extractor version)."""
    stats = ExtractStats()
    cur = await conn.execute(
        """SELECT id, paper_id, kind, text, text_hash, section_path, page, char_start, parser_version
           FROM chunks WHERE paper_id = ANY(%s) AND kind IN ('abstract', 'body', 'table', 'figure_caption') ORDER BY id""",
        (paper_ids,),
    )
    for ch in await cur.fetchall():
        stats.chunks += 1
        hit = await (
            await conn.execute(
                "SELECT claims FROM extractions WHERE chunk_hash = %s AND extractor_version = %s",
                (ch["text_hash"], extractor.version),
            )
        ).fetchone()
        if hit is not None:
            stats.cache_hits += 1
            found: list[dict[str, Any]] = hit["claims"]
        else:
            found = [asdict(c) for c in extractor.extract(ch["text"])]
            stats.extractions += 1
            await conn.execute(
                "INSERT INTO extractions (chunk_hash, extractor_version, claims) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (ch["text_hash"], extractor.version, Jsonb(found)),
            )
        for c in found:
            cur = await conn.execute(
                """INSERT INTO claims (chunk_id, kind, assay, qualifier, value, unit, value_nm, entity_raw, target_raw, sentence,
                                       paper_id, section_path, page, char_start, char_end, parser_version, extraction_model, prompt_version, run_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (ch["id"], c["kind"], c["assay"], c["qualifier"], c["value"], c["unit"], c["value_nm"], c["entity_raw"], c["target_raw"], c["sentence"],
                 ch["paper_id"], ch["section_path"], ch["page"], ch["char_start"] + c["start"], ch["char_start"] + c["end"], ch["parser_version"], extractor.version, "none", run_id),
            )  # fmt: skip
            stats.claims += cur.rowcount
    return stats
