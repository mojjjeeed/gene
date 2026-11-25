"""Literature source adapters. Each queries a documented API (never publisher pages) and returns
LiteratureRecord objects; failures degrade to named coverage notes rather than failing a run."""

from a9_agents.sources.base import (
    LiteratureSource,
    SearchOutcome,
    SourceError,
)

__all__ = ["LiteratureSource", "SearchOutcome", "SourceError"]
