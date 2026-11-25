"""arXiv: preprints with full text. The API asks for no more than one request every three seconds."""

from __future__ import annotations

from collections.abc import AsyncIterator
from xml.etree.ElementTree import Element

from a9_contracts.literature_record import LiteratureRecord
from a9_contracts.search_plan import SearchPlan
from defusedxml import ElementTree

from a9_agents.sources.base import (
    SearchOutcome,
    SourceError,
    boolean_query,
    clean_text,
    collect,
    norm_arxiv_id,
    norm_doi,
    year_of,
)
from a9_agents.sources.http import PolicedClient, Policy

BASE_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def _t(el: Element | None) -> str | None:
    return clean_text(el.text) if el is not None and el.text else None


class Arxiv:
    name = "arxiv"

    def __init__(self, client: PolicedClient | None = None, *, page_size: int = 50):
        self._client = client or PolicedClient(Policy("arxiv", min_interval=3.1, max_concurrency=1))
        self._page_size = page_size

    @staticmethod
    def build_query(plan: SearchPlan) -> str:
        query = f"({boolean_query(plan, field_prefix='all:')})"
        if plan.date_from or plan.date_to:
            start = plan.date_from.strftime("%Y%m%d") if plan.date_from else "19000101"
            end = plan.date_to.strftime("%Y%m%d") if plan.date_to else "30001231"
            query += f" AND submittedDate:[{start}0000 TO {end}2359]"
        return query

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        return await collect(self.name, self._pages(plan, limit), limit)

    async def _pages(
        self, plan: SearchPlan, limit: int
    ) -> AsyncIterator[list[LiteratureRecord | None]]:
        start = 0
        while start < limit:
            response = await self._client.get(
                BASE_URL,
                {
                    "search_query": self.build_query(plan),
                    "start": start,
                    "max_results": min(self._page_size, limit - start),
                    "sortBy": "relevance",
                    "sortOrder": "descending",
                },
            )
            root = ElementTree.fromstring(response.content)
            if root.tag != f"{ATOM}feed":
                raise SourceError(self.name, f"unexpected response root <{root.tag}>")
            entries = root.findall(f"{ATOM}entry")
            # arXiv reports API errors as a single entry whose id is an arxiv.org/api/errors URL.
            if entries and "/api/errors" in (_t(entries[0].find(f"{ATOM}id")) or ""):
                raise SourceError(
                    self.name, f"search rejected: {_t(entries[0].find(f'{ATOM}summary'))}"
                )
            if not entries:
                return
            yield [self.to_record(e) for e in entries]
            start += len(entries)

    @staticmethod
    def to_record(entry: Element) -> LiteratureRecord | None:
        ident = norm_arxiv_id(_t(entry.find(f"{ATOM}id")))
        title = _t(entry.find(f"{ATOM}title"))
        if not ident or not title:
            return None
        doi = norm_doi(_t(entry.find(f"{ARXIV}doi")))
        return LiteratureRecord.model_validate(
            {
                "source": "arxiv",
                "source_id": ident,
                "title": title,
                "abstract": _t(entry.find(f"{ATOM}summary")),
                "authors": [
                    n for a in entry.findall(f"{ATOM}author") if (n := _t(a.find(f"{ATOM}name")))
                ],
                "year": year_of(_t(entry.find(f"{ATOM}published"))),
                "journal": _t(entry.find(f"{ARXIV}journal_ref")),
                "doi": doi,
                "pmid": None,
                "pmcid": None,
                "arxiv_id": ident,
                "url": f"https://arxiv.org/abs/{ident}",
                "licence": None,  # arXiv's per-paper licence is not in the API response: unknown, not assumed
                "is_open_access": True,
                "is_preprint": True,
                "publication_types": ["preprint"],
            }
        )
