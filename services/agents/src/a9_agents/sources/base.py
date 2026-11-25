"""The adapter contract, normalisers shared by every adapter, and the query builder."""

from __future__ import annotations

import html
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from a9_contracts.literature_record import LiteratureRecord
from a9_contracts.search_plan import Concept, SearchPlan


class SourceError(Exception):
    """A source could not answer. `reason` is shown to the user as a named coverage note."""

    def __init__(self, source: str, reason: str, *, transient: bool = False):
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason
        self.transient = transient


@dataclass
class SearchOutcome:
    source: str
    records: list[LiteratureRecord] = field(default_factory=list)
    #: Set when the source returned something but not everything (stopped early, or capped).
    partial_reason: str | None = None


class LiteratureSource(Protocol):
    name: str

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        """Return up to `limit` records for the plan. Raise SourceError if nothing could be fetched;
        return a partial outcome (with `partial_reason`) if it failed after fetching some."""
        ...


# ----------------------------------- normalisers -----------------------------------

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


def clean_text(value: str | None) -> str | None:
    """Strip markup and entities and collapse whitespace. Empty becomes None."""
    if value is None:
        return None
    text = _WS.sub(" ", html.unescape(_TAG.sub(" ", value))).strip()
    return text or None


def norm_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = _DOI_PREFIX.sub("", value.strip()).strip().lower()
    return doi if doi.startswith("10.") else None


def norm_pmcid(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return f"PMC{digits}" if digits else None


def norm_pmid(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value.rstrip("/").rsplit("/", 1)[-1])
    return digits or None


def norm_arxiv_id(value: str | None) -> str | None:
    """`http://arxiv.org/abs/2101.00001v2` -> `2101.00001`; also old-style `hep-th/9901001v1`."""
    if not value:
        return None
    ident = re.sub(
        r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:)", "", value.strip(), flags=re.IGNORECASE
    )
    ident = re.sub(r"v\d+$", "", ident)
    return ident or None


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi}"


def year_of(value: object) -> int | None:
    match = re.search(r"\b(1[89]\d\d|20\d\d)\b", str(value)) if value is not None else None
    return int(match.group(1)) if match else None


# --------------------------------- query building ---------------------------------

_UNSAFE = re.compile(r'["()\[\]{}\\]')


def _term(term: str) -> str | None:
    term = _WS.sub(" ", _UNSAFE.sub(" ", term)).strip()
    if not term:
        return None
    return term if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]*", term) else f'"{term}"'


def concept_terms(concept: Concept) -> list[str]:
    """Label and synonyms, quoted where needed, de-duplicated case-insensitively, order kept."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in [concept.label, *concept.synonyms]:
        term = _term(raw)
        if term and term.lower() not in seen:
            seen.add(term.lower())
            out.append(term)
    return out


def boolean_query(
    plan: SearchPlan,
    *,
    field_suffix: str = "",
    field_prefix: str = "",
    mesh_format: str | None = None,
) -> str:
    """`(a OR b) AND (c OR d)`: OR within a concept, AND across concepts.

    `field_prefix`/`field_suffix` wrap each term (e.g. `[Title/Abstract]`, `all:`);
    `mesh_format` (with one `{}`) adds the concept's MeSH terms as extra OR members.
    """
    groups: list[str] = []
    for concept in plan.concepts:
        members = [f"{field_prefix}{t}{field_suffix}" for t in concept_terms(concept)]
        if mesh_format:
            members += [
                mesh_format.format(m.replace('"', "")) for m in concept.mesh_terms if m.strip()
            ]
        if members:
            groups.append("(" + " OR ".join(members) + ")")
    if not groups:
        raise ValueError("search plan has no usable concepts")
    return " AND ".join(groups)


def plain_terms(plan: SearchPlan) -> str:
    """Concept labels only, space separated, for sources without boolean syntax."""
    return " ".join(t.strip('"') for c in plan.concepts if (t := _term(c.label)))


# ------------------------------------- pagination -------------------------------------


async def collect(
    source: str,
    pages: AsyncIterator[list[LiteratureRecord | None]],
    limit: int,
) -> SearchOutcome:
    """Gather pages up to `limit`, turning every way a source can go wrong into an honest outcome.

    - Failing before any record arrives raises SourceError (the caller records named reduced coverage).
    - Failing after some records returns those records with a `partial_reason`: kept, not discarded.
    - A response we cannot read is a SourceError too, never an empty success.
    - `None` entries are records the adapter had to skip (no title); they are counted and reported.
    """
    records: list[LiteratureRecord] = []
    skipped = 0
    failure: str | None = None
    try:
        async for page in pages:
            for item in page:
                if item is None:
                    skipped += 1
                elif len(records) < limit:
                    records.append(item)
            if len(records) >= limit:
                break
    except SourceError as exc:
        if not records:
            raise
        failure = f"stopped early after {len(records)} records: {exc.reason}"
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        reason = f"unreadable response ({type(exc).__name__}: {exc})"
        if not records:
            raise SourceError(source, reason) from exc
        failure = f"stopped early after {len(records)} records: {reason}"
    notes = [
        n for n in (failure, f"skipped {skipped} records without a title" if skipped else None) if n
    ]
    return SearchOutcome(source, records, "; ".join(notes) or None)
