"""The plans and adapter factories shared by the cassette recorder and the contract tests.

Dates are fixed so a recording stays valid forever. Re-record with:
    A9_RECORD_CASSETTES=1 .venv-a9/bin/python services/agents/tests/record_cassettes.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from a9_agents.sources.arxiv import Arxiv
from a9_agents.sources.base import LiteratureSource
from a9_agents.sources.biorxiv import BioRxiv
from a9_agents.sources.crossref import Crossref
from a9_agents.sources.europepmc import EuropePmc
from a9_agents.sources.http import PolicedClient, Policy
from a9_agents.sources.openalex import OpenAlex
from a9_agents.sources.pubmed import PubMed
from a9_contracts.search_plan import SearchPlan

CASSETTES = Path(__file__).parent / "cassettes"
LIMIT = 5

EGFR_PLAN = SearchPlan.model_validate(
    {
        "topic": "EGFR T790M resistance",
        "concepts": [
            {"label": "EGFR", "synonyms": ["ERBB1"], "mesh_terms": ["ErbB Receptors"]},
            {"label": "T790M", "synonyms": [], "mesh_terms": []},
        ],
        "include_criteria": [],
        "exclude_criteria": [],
        "date_from": "2020-01-01",
        "date_to": "2024-12-31",
        "generated_by": "stub",
        "model": None,
    }
)

# arXiv: a plan that has results there (EGFR AND T790M legitimately has none, see arxiv_empty).
ARXIV_PLAN = SearchPlan.model_validate(
    {**EGFR_PLAN.model_dump(mode="json"), "topic": "kinase inhibitor docking",
     "concepts": [{"label": "kinase", "synonyms": [], "mesh_terms": []},
                  {"label": "docking", "synonyms": [], "mesh_terms": []}]}
)  # fmt: skip

# bioRxiv has no keyword search: one broad concept in a short fixed window gives matches to assert on.
PREPRINT_PLAN = SearchPlan.model_validate(
    {**EGFR_PLAN.model_dump(mode="json"), "concepts": [{"label": "cancer", "synonyms": [], "mesh_terms": []}],
     "date_from": None, "date_to": "2024-06-30", "topic": "cancer"}
)  # fmt: skip


def fast_client(source: str, transport: Any) -> PolicedClient:
    """No pacing and no real sleeping: recorded responses replay instantly."""

    async def no_sleep(_: float) -> None:
        return None

    return PolicedClient(
        Policy(source, min_interval=0.0, max_concurrency=4), transport=transport, sleep=no_sleep
    )


def adapters(transport_for: Any) -> dict[str, tuple[LiteratureSource, SearchPlan]]:
    # (typed as the protocol, so callers cannot lean on adapter-specific attributes)
    """name -> (adapter, plan). `transport_for(name)` supplies each adapter's transport."""
    return {
        "europe_pmc": (
            EuropePmc(fast_client("europe_pmc", transport_for("europe_pmc"))),
            EGFR_PLAN,
        ),
        "pubmed": (PubMed(fast_client("pubmed", transport_for("pubmed"))), EGFR_PLAN),
        "openalex": (OpenAlex(fast_client("openalex", transport_for("openalex"))), EGFR_PLAN),
        "crossref": (Crossref(fast_client("crossref", transport_for("crossref"))), EGFR_PLAN),
        "arxiv": (Arxiv(fast_client("arxiv", transport_for("arxiv"))), ARXIV_PLAN),
        "arxiv_empty": (Arxiv(fast_client("arxiv", transport_for("arxiv_empty"))), EGFR_PLAN),
        "biorxiv": (
            BioRxiv(
                "biorxiv",
                fast_client("biorxiv", transport_for("biorxiv")),
                max_pages=3,
                today=date(2024, 6, 30),
            ),
            PREPRINT_PLAN,
        ),
        "medrxiv": (
            BioRxiv(
                "medrxiv",
                fast_client("medrxiv", transport_for("medrxiv")),
                max_pages=3,
                today=date(2024, 6, 30),
            ),
            PREPRINT_PLAN,
        ),
    }
