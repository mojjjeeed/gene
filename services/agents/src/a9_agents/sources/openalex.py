"""OpenAlex: breadth, open-access status and citation-chasing."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
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
    norm_arxiv_id,
    norm_doi,
    norm_pmcid,
    norm_pmid,
)
from a9_agents.sources.http import PolicedClient, Policy

BASE_URL = "https://api.openalex.org/works"
SELECT = (
    "id,doi,title,display_name,publication_year,abstract_inverted_index,authorships,"
    "primary_location,best_oa_location,open_access,ids,type"
)


def rebuild_abstract(inverted: dict[str, list[int]] | None) -> str | None:
    """OpenAlex ships abstracts as {word: [positions]}; put the words back in order."""
    if not inverted:
        return None
    slots: dict[int, str] = {pos: word for word, positions in inverted.items() for pos in positions}
    return " ".join(slots[i] for i in sorted(slots)) or None


class OpenAlex:
    name = "openalex"

    def __init__(self, client: PolicedClient | None = None, *, page_size: int = 100):
        self._client = client or PolicedClient(
            Policy("openalex", min_interval=0.15, max_concurrency=2)
        )
        self._page_size = page_size

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        return await collect(self.name, self._pages(plan, limit), limit)

    def _params(self, plan: SearchPlan, per_page: int, cursor: str) -> dict[str, Any]:
        filters = []
        if plan.date_from:
            filters.append(f"from_publication_date:{plan.date_from.isoformat()}")
        if plan.date_to:
            filters.append(f"to_publication_date:{plan.date_to.isoformat()}")
        params: dict[str, Any] = {
            "search": boolean_query(plan),
            "per-page": per_page,
            "cursor": cursor,
            "select": SELECT,
        }
        if filters:
            params["filter"] = ",".join(filters)
        if mailto := os.environ.get(
            "A9_CONTACT_EMAIL"
        ):  # only if the user opts in; never by default
            params["mailto"] = mailto
        return params

    async def _pages(
        self, plan: SearchPlan, limit: int
    ) -> AsyncIterator[list[LiteratureRecord | None]]:
        cursor: str | None = "*"
        fetched = 0
        while cursor and fetched < limit:
            response = await self._client.get(
                BASE_URL, self._params(plan, min(self._page_size, max(limit - fetched, 1)), cursor)
            )
            body = response.json()
            if "results" not in body:
                raise SourceError(self.name, f"unexpected response: {str(body)[:120]}")
            if not body["results"]:
                return
            fetched += len(body["results"])
            yield [self.to_record(w) for w in body["results"]]
            cursor = (body.get("meta") or {}).get("next_cursor")

    @staticmethod
    def to_record(w: dict[str, Any]) -> LiteratureRecord | None:
        title = clean_text(w.get("title") or w.get("display_name"))
        if not title:
            return None
        doi = norm_doi(w.get("doi"))
        ids = w.get("ids") or {}
        primary, best = w.get("primary_location") or {}, w.get("best_oa_location") or {}
        arxiv = next(
            (
                norm_arxiv_id(loc["landing_page_url"])
                for loc in (primary, best)
                if "arxiv.org/abs/" in (loc.get("landing_page_url") or "")
            ),
            None,
        )
        work_id = str(w["id"]).rsplit("/", 1)[-1]
        return LiteratureRecord.model_validate(
            {
                "source": "openalex",
                "source_id": work_id,
                "title": title,
                "abstract": rebuild_abstract(w.get("abstract_inverted_index")),
                "authors": [
                    a["author"]["display_name"]
                    for a in w.get("authorships") or []
                    if (a.get("author") or {}).get("display_name")
                ],
                "year": w.get("publication_year"),
                "journal": ((primary.get("source") or {}).get("display_name")),
                "doi": doi,
                "pmid": norm_pmid(ids.get("pmid")),
                "pmcid": norm_pmcid(ids.get("pmcid")),
                "arxiv_id": arxiv,
                "url": doi_url(doi) if doi else str(w["id"]),
                "licence": best.get("license") or primary.get("license"),
                "is_open_access": (w.get("open_access") or {}).get("is_oa"),
                "is_preprint": w.get("type") == "preprint",
                "publication_types": [w["type"]] if w.get("type") else [],
            }
        )
