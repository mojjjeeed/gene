"""Identity resolution and de-duplication of records from many sources into papers.

The ladder, strongest evidence first. A pair merges at the first rung that fires:
  1. an identifier both carry: DOI, then PMID, then PMCID, then arXiv id
  2. a link a publisher asserts: a preprint's `published` DOI, Crossref's has-preprint/is-preprint-of
  3. the same normalised title and the same first-author surname, publication years within two
  4. embedding similarity, but only between a preprint and a non-preprint, with the same first-author
     surname and years within two (so similarity alone can never merge two unrelated papers)
Every merge records which rung caused it, so a user can be shown why two records became one.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from a9_contracts.literature_record import LiteratureRecord

from a9_agents.embedder import Embedder, cosine

RETRACTION_RANK = {"none": 0, "expression_of_concern": 1, "withdrawn": 2, "retracted": 3}


# ----------------------------------- normalisation -----------------------------------

_PREFIX = re.compile(
    r"^\s*(?:withdrawn|retracted|retraction|erratum|correction)\s*[:\-]\s*", re.IGNORECASE
)


def title_key(title: str) -> str:
    folded = (
        unicodedata.normalize("NFKD", _PREFIX.sub("", title)).encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def surname(author: str) -> str | None:
    """First author's surname across the formats sources use.

    'Margalit, S.' (bioRxiv) / 'Zhang Y' (Europe PMC) / 'Hannah A Blair' (PubMed) / 'Yong Du' (OpenAlex).
    """
    name = author.strip()
    if not name:
        return None
    if "," in name:
        last = name.split(",", 1)[0]
    else:
        tokens = name.replace(".", " ").split()
        if not tokens:
            return None
        trailing_initials = len(tokens) > 1 and tokens[-1].isupper() and len(tokens[-1]) <= 3
        last = " ".join(tokens[:-1]) if trailing_initials else tokens[-1]
    folded = unicodedata.normalize("NFKD", last).encode("ascii", "ignore").decode().lower()
    words = re.sub(r"[^a-z\s'-]", "", folded).split()
    return words[-1] if words else None  # 'van der Berg' -> 'berg'


def first_author(record: LiteratureRecord) -> str | None:
    return surname(record.authors[0]) if record.authors else None


def title_author_key(record: LiteratureRecord) -> str | None:
    words = title_key(record.title).split()
    author = first_author(record)
    # A short title ("Introduction", "Editorial") is not evidence of identity.
    return f"{' '.join(words)}|{author}" if len(words) >= 5 and author else None


def years_close(a: LiteratureRecord, b: LiteratureRecord, gap: int = 2) -> bool:
    return a.year is None or b.year is None or abs(a.year - b.year) <= gap


# ------------------------------------- clustering -------------------------------------


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[max(ra, rb)] = min(ra, rb)
        return True


@dataclass
class Cluster:
    records: list[LiteratureRecord]
    #: The rungs that merged members, strongest first, e.g. ["doi", "linked_doi"].
    reasons: list[str] = field(default_factory=list)


async def cluster_records(
    records: list[LiteratureRecord],
    *,
    embedder: Embedder | None = None,
    similarity_threshold: float = 0.80,
) -> list[Cluster]:
    uf = _UnionFind(len(records))
    reason_for_root: dict[int, set[str]] = defaultdict(set)
    merges: list[tuple[int, int, str]] = []

    def join(a: int, b: int, why: str) -> None:
        if uf.union(a, b):
            merges.append((a, b, why))

    # Rung 1: identifiers, in the order DOI, PMID, PMCID, arXiv id.
    id_rungs: list[tuple[str, Callable[[LiteratureRecord], str | None]]] = [
        ("doi", lambda r: r.doi),
        ("pmid", lambda r: r.pmid),
        ("pmcid", lambda r: r.pmcid),
        ("arxiv_id", lambda r: r.arxiv_id),
    ]
    for why, getter in id_rungs:
        seen: dict[str, int] = {}
        for i, rec in enumerate(records):
            if value := getter(rec):
                if value in seen:
                    join(seen[value], i, why)
                else:
                    seen[value] = i

    # Rung 2: links a publisher asserts. A record's own DOI can match another's related DOI, and
    # two records that name the same related DOI are versions of one work.
    by_doi = {r.doi: i for i, r in enumerate(records) if r.doi}
    related_owner: dict[str, int] = {}
    for i, rec in enumerate(records):
        for rel in rec.related_dois:
            if rel in by_doi:
                join(i, by_doi[rel], "linked_doi")
            if rel in related_owner:
                join(i, related_owner[rel], "linked_doi")
            else:
                related_owner[rel] = i

    # Rung 3: same title and first author.
    keyed: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        if key := title_author_key(rec):
            keyed[key].append(i)
    for members in keyed.values():
        for j in members[1:]:
            if years_close(records[members[0]], records[j]):
                join(members[0], j, "title_author")

    # Rung 4: similarity, only preprint <-> non-preprint pairs that agree on first author and year.
    if embedder is not None:
        texts = [f"{r.title}. {(r.abstract or '')[:600]}" for r in records]
        vectors = await embedder.embed(texts)
        for i, a in enumerate(records):
            for j in range(i + 1, len(records)):
                b = records[j]
                if uf.find(i) == uf.find(j) or a.is_preprint == b.is_preprint:
                    continue
                sa, sb = first_author(a), first_author(b)
                if (
                    sa
                    and sa == sb
                    and years_close(a, b)
                    and cosine(vectors[i], vectors[j]) >= similarity_threshold
                ):
                    join(i, j, "similarity")

    # Replay merges to attach each reason to the final cluster that contains it.
    final = _UnionFind(len(records))
    for x, y, _why in merges:
        final.union(x, y)
    for x, _y, why in merges:
        reason_for_root[final.find(x)].add(why)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(records)):
        groups[final.find(i)].append(i)
    order = ["doi", "pmid", "pmcid", "arxiv_id", "linked_doi", "title_author", "similarity"]
    return [
        Cluster([records[i] for i in idx], sorted(reason_for_root[root], key=order.index))
        for root, idx in sorted(groups.items())
    ]


# ------------------------------------ the paper ------------------------------------


@dataclass
class PaperDraft:
    title: str
    abstract: str | None
    authors: list[str]
    year: int | None
    journal: str | None
    doi: str | None
    alt_dois: list[str]
    pmid: str | None
    pmcid: str | None
    arxiv_id: str | None
    licence: str | None
    is_open_access: bool | None
    is_preprint: bool
    publication_types: list[str]
    source: str
    #: What the sources themselves assert about retraction (a title prefix or publication type).
    retraction_hint: str
    merged_from: int
    reasons: list[str]


def retraction_hint(record: LiteratureRecord) -> str:
    types = {t.lower() for t in record.publication_types}
    title = record.title.lstrip().lower()
    if "retracted publication" in types or title.startswith("retracted:"):
        return "retracted"
    if title.startswith("withdrawn:"):
        return "withdrawn"
    return "none"


def _first[T](
    recs: list[LiteratureRecord],
    primary: LiteratureRecord,
    get: Callable[[LiteratureRecord], T | None],
) -> T | None:
    """The primary record's value if it has one, else the first other record's."""
    return next((v for r in [primary, *recs] if (v := get(r)) is not None), None)


def to_draft(cluster: Cluster) -> PaperDraft:
    recs = cluster.records
    primary = max(
        recs,
        key=lambda r: (not r.is_preprint, bool(r.doi), bool(r.abstract), len(r.abstract or "")),
    )
    doi = (
        primary.doi
        or next((r.doi for r in recs if r.doi and not r.is_preprint), None)
        or _first(recs, primary, lambda r: r.doi)
    )
    all_dois = {d for r in recs for d in [r.doi, *r.related_dois] if d}
    return PaperDraft(
        title=_PREFIX.sub("", primary.title).strip() or primary.title,
        abstract=primary.abstract or max((r.abstract or "" for r in recs), key=len) or None,
        authors=primary.authors or next((r.authors for r in recs if r.authors), []),
        year=_first(recs, primary, lambda r: r.year),
        journal=_first(recs, primary, lambda r: r.journal),
        doi=doi,
        alt_dois=sorted(all_dois - {doi} if doi else all_dois),
        pmid=_first(recs, primary, lambda r: r.pmid),
        pmcid=_first(recs, primary, lambda r: r.pmcid),
        arxiv_id=_first(recs, primary, lambda r: r.arxiv_id),
        # The licence of the version we treat as canonical. A preprint's licence does not cover the
        # journal version, so it is never borrowed: unknown stays unknown.
        licence=primary.licence,
        is_open_access=_first(recs, primary, lambda r: r.is_open_access),
        is_preprint=all(r.is_preprint for r in recs),
        publication_types=sorted({t for r in recs for t in r.publication_types}),
        source=primary.source.value,
        retraction_hint=max((retraction_hint(r) for r in recs), key=lambda h: RETRACTION_RANK[h]),
        merged_from=len(recs),
        reasons=cluster.reasons,
    )
