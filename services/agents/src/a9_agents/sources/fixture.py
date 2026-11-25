"""Sources that need no network, for development and tests. Their records are labelled sample data.

fixture          answers with three canned records
fixture_down     is down from the start (a named coverage note)
fixture_partial  returns two records, then fails (kept, with a named note)
"""

from __future__ import annotations

from a9_contracts.literature_record import LiteratureRecord
from a9_contracts.search_plan import SearchPlan

from a9_agents.sources.base import SearchOutcome, SourceError


def _record(source: str, n: int, topic: str) -> LiteratureRecord:
    return LiteratureRecord.model_validate(
        {
            "source": "fixture",
            "source_id": f"{source}-{n}",
            "title": f"Sample record {n} for {topic} (fixture data, not a real paper)",
            "abstract": "Sample abstract.",
            "authors": ["Sample Author"],
            "year": 2024,
            "journal": "Sample Journal",
            "doi": f"10.0000/fixture.{'retracted.' if n == 2 else ''}{source}.{n}",
            "related_dois": [],
            "pmid": None,
            "pmcid": None,
            "arxiv_id": None,
            "url": f"https://example.org/fixture/{source}/{n}",
            "licence": None,
            "is_open_access": None,
            "is_preprint": False,
            "publication_types": ["sample"],
        }
    )


class FixtureSource:
    def __init__(self, name: str = "fixture", count: int = 3):
        self.name, self._count = name, count

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        return SearchOutcome(
            self.name, [_record(self.name, i, plan.topic) for i in range(min(self._count, limit))]
        )


class DownSource:
    def __init__(self, name: str = "fixture_down"):
        self.name = name

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        raise SourceError(self.name, "unavailable after 4 attempts (HTTP 503)", transient=True)


class PartialSource:
    def __init__(self, name: str = "fixture_partial"):
        self.name = name

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        return SearchOutcome(
            self.name,
            [_record(self.name, i, plan.topic) for i in range(2)],
            "stopped early after 2 records: connection reset",
        )
