"""Which sources a deployment uses: A9_SOURCES, a comma-separated list of names."""

from __future__ import annotations

import os
from collections.abc import Callable

from a9_agents.sources.arxiv import Arxiv
from a9_agents.sources.base import LiteratureSource
from a9_agents.sources.biorxiv import BioRxiv
from a9_agents.sources.crossref import Crossref
from a9_agents.sources.europepmc import EuropePmc
from a9_agents.sources.fixture import DownSource, FixtureSource, PartialSource
from a9_agents.sources.openalex import OpenAlex
from a9_agents.sources.pubmed import PubMed

FACTORIES: dict[str, Callable[[], LiteratureSource]] = {
    "europe_pmc": EuropePmc,
    "pubmed": PubMed,
    "openalex": OpenAlex,
    "crossref": Crossref,
    "arxiv": Arxiv,
    "biorxiv": lambda: BioRxiv("biorxiv"),
    "medrxiv": lambda: BioRxiv("medrxiv"),
    "fixture": FixtureSource,
    "fixture_down": DownSource,
    "fixture_partial": PartialSource,
}
DEFAULT = "europe_pmc,pubmed,openalex,crossref,arxiv,biorxiv,medrxiv"


def build_sources(names: str | None = None) -> list[LiteratureSource]:
    raw = os.environ.get("A9_SOURCES", DEFAULT) if names is None else names
    out: list[LiteratureSource] = []
    for name in (n.strip() for n in raw.split(",")):
        if not name:
            continue
        if name not in FACTORIES:
            raise ValueError(
                f"unknown source {name!r} in A9_SOURCES (known: {', '.join(sorted(FACTORIES))})"
            )
        out.append(FACTORIES[name]())
    return out
