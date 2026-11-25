"""Retraction and expression-of-concern checks against Crossref (which carries Retraction Watch data).

A retracted paper is FLAGGED and KEPT: the user may well be asking about it. 'Not checked' is a
separate state from 'checked and clean', and the two are never conflated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote

from a9_agents.sources.base import SourceError
from a9_agents.sources.http import PolicedClient, Policy

BASE_URL = "https://api.crossref.org/works"

#: Crossref `updated-by` types -> our status. Corrections and errata are not retractions.
STATUS_BY_TYPE = {
    "retraction": "retracted",
    "withdrawal": "withdrawn",
    "removal": "withdrawn",
    "expression_of_concern": "expression_of_concern",
}
RANK = {"none": 0, "expression_of_concern": 1, "withdrawn": 2, "retracted": 3}


@dataclass(frozen=True)
class RetractionResult:
    #: False when the DOI is not in Crossref at all (e.g. DataCite DOIs): we could not check.
    checked: bool
    status: str = "none"
    notice_dois: list[str] = field(default_factory=list)


class RetractionChecker(Protocol):
    name: str

    async def check(self, doi: str) -> RetractionResult: ...


class CrossrefRetractionChecker:
    name = "crossref"

    def __init__(self, client: PolicedClient | None = None):
        self._client = client or PolicedClient(
            Policy("crossref", min_interval=0.1, max_concurrency=3)
        )

    async def check(self, doi: str) -> RetractionResult:
        try:
            response = await self._client.get(f"{BASE_URL}/{quote(doi, safe='/')}")
        except SourceError as exc:
            if exc.reason == "HTTP 404":
                return RetractionResult(checked=False)  # Crossref does not know this DOI
            raise
        updates = response.json()["message"].get("updated-by") or []
        status, notices = "none", []
        for update in updates:
            mapped = STATUS_BY_TYPE.get(str(update.get("type", "")).lower())
            if mapped:
                notices.append(str(update.get("DOI", "")).lower())
                if RANK[mapped] > RANK[status]:
                    status = mapped
        return RetractionResult(
            checked=True, status=status, notice_dois=sorted({n for n in notices if n})
        )


class FixtureRetractionChecker:
    """No network: a DOI containing 'retracted' is retracted, 'concern' is an expression of concern."""

    name = "fixture"

    async def check(self, doi: str) -> RetractionResult:
        if "retracted" in doi:
            return RetractionResult(True, "retracted", [f"{doi}.notice"])
        if "concern" in doi:
            return RetractionResult(True, "expression_of_concern", [f"{doi}.notice"])
        return RetractionResult(True)


def make_retraction_checker() -> RetractionChecker | None:
    import os

    kind = os.environ.get("A9_RETRACTION_CHECK", "crossref")
    if kind == "crossref":
        return CrossrefRetractionChecker()
    if kind == "fixture":
        return FixtureRetractionChecker()
    if kind == "off":
        return None
    raise ValueError(f"unknown A9_RETRACTION_CHECK {kind!r} (expected crossref, fixture or off)")
