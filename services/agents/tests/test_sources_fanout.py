"""Fan-out: sources run concurrently, and a source that is down, slow, partial or buggy becomes a
named coverage note while the others carry on."""

from __future__ import annotations

import asyncio

import pytest
from a9_agents.sources.base import SearchOutcome, SourceError
from a9_agents.sources.fanout import SourceReport, search_all
from a9_agents.sources.fixture import DownSource, FixtureSource, PartialSource
from a9_agents.sources.registry import build_sources
from a9_contracts.literature_record import LiteratureRecord
from sources_fixtures import EGFR_PLAN


class Slow:
    name = "slow"

    async def search(self, plan: object, *, limit: int = 100) -> SearchOutcome:
        await asyncio.sleep(30)
        raise AssertionError("should have been timed out")


class Buggy:
    name = "buggy"

    async def search(self, plan: object, *, limit: int = 100) -> SearchOutcome:
        raise KeyError("an adapter bug")


class DiesMidRun:
    """Answers after others have finished, then fails: 'killing one source mid-run'."""

    name = "mid_run"

    def __init__(self, gate: asyncio.Event):
        self.gate = gate

    async def search(self, plan: object, *, limit: int = 100) -> SearchOutcome:
        await self.gate.wait()
        raise SourceError(self.name, "connection reset by peer", transient=True)


async def test_healthy_sources_are_unaffected_by_a_dead_one() -> None:
    result = await search_all([FixtureSource(), DownSource()], EGFR_PLAN)
    assert len(result.records) == 3
    assert [r.source for r in result.reports] == ["fixture", "fixture_down"]
    assert result.coverage_notes == [
        {"source": "fixture_down", "reason": "unavailable after 4 attempts (HTTP 503)"}
    ]


async def test_a_partial_source_keeps_its_records_and_names_the_gap() -> None:
    result = await search_all([PartialSource()], EGFR_PLAN)
    assert len(result.records) == 2
    (note,) = result.coverage_notes
    assert note["source"] == "fixture_partial" and "stopped early after 2 records" in note["reason"]


async def test_a_slow_source_is_cut_off_and_named() -> None:
    result = await search_all([FixtureSource(), Slow()], EGFR_PLAN, per_source_timeout=0.05)
    assert len(result.records) == 3
    assert result.coverage_notes == [{"source": "slow", "reason": "no answer within 0.05s"}]


async def test_an_adapter_bug_degrades_to_a_note_and_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    result = await search_all([FixtureSource(), Buggy()], EGFR_PLAN)
    assert len(result.records) == 3
    assert result.coverage_notes == [{"source": "buggy", "reason": "internal error (KeyError)"}]
    assert "source buggy crashed" in caplog.text  # degraded for the user, loud for us


async def test_a_source_killed_mid_run_does_not_stop_the_others() -> None:
    gate = asyncio.Event()
    seen: list[str] = []

    async def on_done(report: SourceReport, records: list[LiteratureRecord]) -> None:
        seen.append(report.source)
        if report.source == "fixture":
            gate.set()  # only now does the doomed source fail: it dies while the run is under way

    result = await search_all(
        [DiesMidRun(gate), FixtureSource()], EGFR_PLAN, on_source_done=on_done
    )
    assert seen == ["fixture", "mid_run"]  # results are reported as they land, not in list order
    assert len(result.records) == 3
    assert result.coverage_notes == [{"source": "mid_run", "reason": "connection reset by peer"}]


async def test_cancellation_is_not_swallowed() -> None:
    task = asyncio.create_task(search_all([Slow()], EGFR_PLAN, per_source_timeout=60))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_every_source_failing_still_returns_a_result_with_every_name() -> None:
    result = await search_all([DownSource("a"), DownSource("b")], EGFR_PLAN)
    assert result.records == [] and sorted(n["source"] for n in result.coverage_notes) == ["a", "b"]


def test_registry_builds_named_sources_and_rejects_typos(monkeypatch: pytest.MonkeyPatch) -> None:
    assert [s.name for s in build_sources("fixture, europe_pmc,,pubmed")] == [
        "fixture",
        "europe_pmc",
        "pubmed",
    ]
    assert build_sources("") == []
    monkeypatch.setenv("A9_SOURCES", "arxiv")
    assert [s.name for s in build_sources()] == ["arxiv"]
    with pytest.raises(ValueError, match="unknown source 'europepmc'"):
        build_sources("europepmc")  # a typo must not silently mean 'no sources'
    monkeypatch.delenv("A9_SOURCES")
    assert [s.name for s in build_sources()] == [
        "europe_pmc",
        "pubmed",
        "openalex",
        "crossref",
        "arxiv",
        "biorxiv",
        "medrxiv",
    ]
