"""Crossref: canonical DOIs and versions. Relevance ranking is fuzzy, so it is used for identity and
breadth; retraction checks are a separate step (M0.7)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from a9_contracts.literature_record import LiteratureRecord
from a9_contracts.search_plan import SearchPlan

from a9_agents.sources.base import (
    SearchOutcome,
    SourceError,
    clean_text,
    collect,
    doi_url,
    norm_doi,
    plain_terms,
)
from a9_agents.sources.http import PolicedClient, Policy

BASE_URL = "https://api.crossref.org/works"
SELECT = "DOI,title,abstract,author,container-title,issued,type,license,URL"


class Crossref:
    name = "crossref"

    def __init__(self, client: PolicedClient | None = None, *, page_size: int = 100):
        self._client = client or PolicedClient(
            Policy("crossref", min_interval=0.1, max_concurrency=2)
        )
        self._page_size = page_size

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        return await collect(self.name, self._pages(plan, limit), limit)

    def _params(self, plan: SearchPlan, rows: int, cursor: str) -> dict[str, Any]:
        filters: list[str] = []  # no type filter: journal articles and preprints are both wanted
        if plan.date_from:
            filters.append(f"from-pub-date:{plan.date_from.isoformat()}")
        if plan.date_to:
            filters.append(f"until-pub-date:{plan.date_to.isoformat()}")
        params: dict[str, Any] = {
            "query.bibliographic": plain_terms(plan),
            "rows": rows,
            "cursor": cursor,
            "select": SELECT,
        }
        if filters:
            params["filter"] = ",".join(filters)
        if mailto := os.environ.get("A9_CONTACT_EMAIL"):  # opt-in only
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
            if "message" not in body:
                raise SourceError(self.name, f"unexpected response: {str(body)[:120]}")
            message = body["message"]
            items: list[dict[str, Any]] = message["items"]
            if not items:
                return
            fetched += len(items)
            yield [self.to_record(i) for i in items]
            cursor = message.get("next-cursor")

    @staticmethod
    def to_record(item: dict[str, Any]) -> LiteratureRecord | None:
        titles = item.get("title") or []
        title = clean_text(titles[0]) if titles else None
        doi = norm_doi(item.get("DOI"))
        if not title or not doi:
            return None
        parts = (item.get("issued") or {}).get("date-parts") or [[None]]
        licences = item.get("license") or []
        journals = item.get("container-title") or []
        kind = item.get("type")
        return LiteratureRecord.model_validate(
            {
                "source": "crossref",
                "source_id": doi,
                "title": title,
                "abstract": clean_text(item.get("abstract")),
                "authors": [
                    " ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get("name", "")
                    for a in item.get("author") or []
                    if a.get("family") or a.get("name")
                ],
                "year": parts[0][0],
                "journal": journals[0] if journals else None,
                "doi": doi,
                "pmid": None,
                "pmcid": None,
                "arxiv_id": None,
                "url": item.get("URL") or doi_url(doi),
                "licence": licences[0].get("URL") if licences else None,
                "is_open_access": None,
                "is_preprint": kind == "posted-content",
                "publication_types": [kind] if kind else [],
            }
        )
