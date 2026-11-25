"""Run every source at once and fold the results into one outcome, degrading instead of failing.

A source that is down, slow, partial or broken contributes a named coverage note, never an exception
that takes the run with it. The only things that propagate are cancellation and our own database
errors from the callback, because losing the database is the one hard failure.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from a9_contracts.literature_record import LiteratureRecord
from a9_contracts.search_plan import SearchPlan

from a9_agents.sources.base import LiteratureSource, SourceError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceReport:
    source: str
    count: int
    #: Set when the source answered but not completely.
    partial_reason: str | None = None
    #: Set when the source gave nothing at all.
    error: str | None = None

    @property
    def coverage_note(self) -> dict[str, str] | None:
        reason = self.error or self.partial_reason
        return {"source": self.source, "reason": reason} if reason else None


@dataclass
class FanoutResult:
    records: list[LiteratureRecord]
    reports: list[SourceReport]

    @property
    def coverage_notes(self) -> list[dict[str, str]]:
        return [n for r in self.reports if (n := r.coverage_note)]


SourceDone = Callable[[SourceReport, list[LiteratureRecord]], Awaitable[None]]


async def search_all(
    sources: Sequence[LiteratureSource],
    plan: SearchPlan,
    *,
    limit: int = 100,
    per_source_timeout: float = 120.0,
    on_source_done: SourceDone | None = None,
) -> FanoutResult:
    async def one(source: LiteratureSource) -> tuple[SourceReport, list[LiteratureRecord]]:
        records: list[LiteratureRecord] = []
        try:
            outcome = await asyncio.wait_for(source.search(plan, limit=limit), per_source_timeout)
            records = outcome.records
            report = SourceReport(source.name, len(records), outcome.partial_reason)
        except TimeoutError:
            report = SourceReport(source.name, 0, error=f"no answer within {per_source_timeout:g}s")
        except SourceError as exc:
            report = SourceReport(source.name, 0, error=exc.reason)
        except (
            Exception
        ) as exc:  # a bug in one adapter must not take the run down; it is logged loudly
            log.exception("source %s crashed", source.name)
            report = SourceReport(source.name, 0, error=f"internal error ({type(exc).__name__})")
        if on_source_done is not None:
            await on_source_done(report, records)
        return report, records

    results = await asyncio.gather(*(one(s) for s in sources))
    return FanoutResult(
        records=[r for _, recs in results for r in recs],
        reports=[rep for rep, _ in results],
    )
