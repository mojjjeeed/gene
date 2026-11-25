"""bioRxiv and medRxiv. Their API lists preprints by date window and cannot search by keyword, so
this adapter scans a recent window and filters client-side. That limit is reported, not hidden."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from a9_contracts.literature_record import LiteratureRecord
from a9_contracts.search_plan import SearchPlan

from a9_agents.sources.base import (
    SearchOutcome,
    SourceError,
    clean_text,
    collect,
    concept_terms,
    norm_doi,
    year_of,
)
from a9_agents.sources.http import PolicedClient, Policy

BASE_URL = "https://api.biorxiv.org/details"


@dataclass
class _Scan:
    start: date
    end: date
    scanned: int = 0
    total: int = 0


def matches(plan: SearchPlan, text: str) -> bool:
    """Every concept must appear (label or a synonym) in the text: the plan's AND-of-ORs."""
    haystack = text.lower()
    return all(
        any(t.strip('"').lower() in haystack for t in concept_terms(c)) for c in plan.concepts
    )


class BioRxiv:
    def __init__(
        self,
        server: Literal["biorxiv", "medrxiv"] = "biorxiv",
        client: PolicedClient | None = None,
        *,
        window_days: int = 90,
        max_pages: int = 10,
        today: date | None = None,
    ):
        self.name: str = server
        self._server = server
        self._client = client or PolicedClient(Policy(server, min_interval=1.0, max_concurrency=1))
        self._window_days, self._max_pages, self._today = window_days, max_pages, today

    def window(self, plan: SearchPlan) -> tuple[date, date]:
        end = plan.date_to or self._today or date.today()
        start = end - timedelta(days=self._window_days)
        if plan.date_from and plan.date_from > start:
            start = plan.date_from
        return start, end

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        start, end = self.window(plan)
        scan = _Scan(start, end)
        outcome = await collect(self.name, self._pages(plan, limit, scan), limit)
        reasons: list[str] = []
        if scan.scanned < scan.total:
            reasons.append(
                f"scanned {scan.scanned} of {scan.total} {self._server} preprints from {start} to {end}"
            )
        if plan.date_from is None or plan.date_from < start:
            reasons.append(
                f"{self._server} has no keyword search, so only {start} to {end} was scanned "
                "and filtered by keyword here"
            )
        if outcome.partial_reason:
            reasons.append(outcome.partial_reason)
        outcome.partial_reason = "; ".join(reasons) or None
        return outcome

    async def _pages(
        self, plan: SearchPlan, limit: int, scan: _Scan
    ) -> AsyncIterator[list[LiteratureRecord | None]]:
        cursor = 0
        matched = 0
        for _ in range(self._max_pages):
            response = await self._client.get(
                f"{BASE_URL}/{self._server}/{scan.start}/{scan.end}/{cursor}/json"
            )
            body = response.json()
            message = body["messages"][0]
            collection: list[dict[str, Any]] = body.get("collection", [])
            if message.get("status") != "ok" and not collection:
                raise SourceError(self.name, f"API said: {message.get('status')}")
            scan.total = int(message.get("total", 0) or 0)
            if not collection:
                return
            scan.scanned += len(collection)
            kept = [
                r for r in (self.to_record(item) for item in collection)
                if r is not None and matches(plan, f"{r.title} {r.abstract or ''}")
            ]  # fmt: skip
            matched += len(kept)
            yield list(kept)
            # The cursor is an offset. Pages are NOT a fixed size (observed 30, documented up to 100),
            # so advance by what was actually returned or records are silently skipped.
            cursor += len(collection)
            if cursor >= scan.total or matched >= limit:
                return

    @staticmethod
    def to_record(item: dict[str, Any]) -> LiteratureRecord | None:
        doi = norm_doi(item.get("doi"))
        title = clean_text(item.get("title"))
        if not doi or not title:
            return None
        server = str(item.get("server", "")).lower()
        source = "medrxiv" if "med" in server else "biorxiv"
        licence = item.get("license")
        return LiteratureRecord.model_validate(
            {
                "source": source,
                "source_id": doi,
                "title": title,
                "abstract": clean_text(item.get("abstract")),
                "authors": [
                    a.strip() for a in str(item.get("authors", "")).split(";") if a.strip()
                ],
                "year": year_of(item.get("date")),
                "journal": "medRxiv" if source == "medrxiv" else "bioRxiv",
                "doi": doi,
                "pmid": None,
                "pmcid": None,
                "arxiv_id": None,
                "url": f"https://www.{source}.org/content/{doi}v{item.get('version', 1)}",
                "licence": licence if licence and licence != "unknown" else None,
                "is_open_access": True,
                "is_preprint": True,
                "publication_types": ["preprint"],
            }
        )
