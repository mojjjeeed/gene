"""Europe PMC: the primary full-text path for biomedical work. Metadata, abstracts, OA flag, licence."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from typing import Any

from a9_contracts.literature_record import LiteratureRecord
from a9_contracts.search_plan import SearchPlan

from a9_agents.sources.base import (
    SearchOutcome,
    SourceError,
    boolean_query,
    clean_text,
    collect,
    doi_url,
    norm_doi,
    norm_pmcid,
    norm_pmid,
    year_of,
)
from a9_agents.sources.http import PolicedClient, Policy

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePmc:
    name = "europe_pmc"

    def __init__(self, client: PolicedClient | None = None, *, page_size: int = 100):
        self._client = client or PolicedClient(
            Policy("europe_pmc", min_interval=0.2, max_concurrency=2)
        )
        self._page_size = page_size

    @staticmethod
    def build_query(plan: SearchPlan) -> str:
        start = plan.date_from.isoformat() if plan.date_from else "1900-01-01"
        end = plan.date_to.isoformat() if plan.date_to else date.today().isoformat()
        return f"({boolean_query(plan)}) AND (FIRST_PDATE:[{start} TO {end}])"

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        return await collect(self.name, self._pages(plan, limit), limit)

    async def _pages(
        self, plan: SearchPlan, limit: int
    ) -> AsyncIterator[list[LiteratureRecord | None]]:
        cursor = "*"
        fetched = 0
        while fetched < limit:
            response = await self._client.get(
                BASE_URL,
                {
                    "query": self.build_query(plan),
                    "format": "json",
                    "resultType": "core",
                    "pageSize": min(self._page_size, max(limit - fetched, 1)),
                    "cursorMark": cursor,
                },
            )
            body = response.json()
            if "resultList" not in body:
                raise SourceError(self.name, f"unexpected response: {str(body)[:120]}")
            results: list[dict[str, Any]] = body["resultList"]["result"]
            if not results:
                return
            fetched += len(results)
            yield [self.to_record(r) for r in results]
            next_cursor = body.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor:
                return
            cursor = next_cursor

    @staticmethod
    def to_record(r: dict[str, Any]) -> LiteratureRecord | None:
        title = clean_text(r.get("title"))
        if not title:
            return None
        doi = norm_doi(r.get("doi"))
        authors = [
            a["fullName"]
            for a in (r.get("authorList") or {}).get("author", [])
            if a.get("fullName")
        ]
        if not authors and r.get("authorString"):
            authors = [a.strip().rstrip(".") for a in r["authorString"].split(",") if a.strip()]
        journal = ((r.get("journalInfo") or {}).get("journal") or {}).get("title") or r.get(
            "journalTitle"
        )
        src, rid = r.get("source", "MED"), str(r.get("id", ""))
        return LiteratureRecord.model_validate(
            {
                "source": "europe_pmc",
                "source_id": f"{src}:{rid}",
                "title": title,
                "abstract": clean_text(r.get("abstractText")),
                "authors": authors,
                "year": year_of(r.get("pubYear")),
                "journal": journal,
                "doi": doi,
                "pmid": norm_pmid(r.get("pmid")),
                "pmcid": norm_pmcid(r.get("pmcid")),
                "arxiv_id": None,
                "url": doi_url(doi) if doi else f"https://europepmc.org/article/{src}/{rid}",
                "licence": r.get("license"),
                "is_open_access": {"Y": True, "N": False}.get(r.get("isOpenAccess", "")),
                "is_preprint": src == "PPR",
                "publication_types": list((r.get("pubTypeList") or {}).get("pubType", [])),
            }
        )
