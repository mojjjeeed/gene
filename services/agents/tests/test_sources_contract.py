"""Contract tests: every adapter against real responses recorded once (tests/cassettes).

The same invariants apply to all sources; the golden values below were read off the real recordings.
Re-record deliberately with tests/record_cassettes.py. Replay is strict: a request the cassette does
not contain fails the test, so a query change cannot slip past unnoticed.
"""

from __future__ import annotations

import re

import pytest
from a9_agents.sources.base import LiteratureSource, SearchOutcome
from a9_contracts.literature_record import LiteratureRecord
from cassette import CassetteTransport
from sources_fixtures import CASSETTES, LIMIT, adapters

NAMES = ["europe_pmc", "pubmed", "openalex", "crossref", "arxiv", "biorxiv", "medrxiv"]


async def run(name: str) -> tuple[SearchOutcome, CassetteTransport]:
    transports: dict[str, CassetteTransport] = {}

    def transport_for(n: str) -> CassetteTransport:
        transports[n] = CassetteTransport(CASSETTES / f"{n}.json")
        return transports[n]

    adapter, plan = adapters(transport_for)[name]
    return await adapter.search(plan, limit=LIMIT), transports[name]


@pytest.mark.parametrize("name", NAMES)
async def test_records_satisfy_the_contract(name: str) -> None:
    outcome, _ = await run(name)
    assert outcome.source == name or name in {"biorxiv", "medrxiv"}
    assert len(outcome.records) == LIMIT
    assert len({r.source_id for r in outcome.records}) == LIMIT, "source ids must be unique"
    for r in outcome.records:
        assert isinstance(r, LiteratureRecord)
        assert r.source.value == name
        assert r.title.strip() == r.title and not re.search(r"<[a-z/][^>]*>", r.title), (
            "markup leaked into title"
        )
        assert r.abstract is None or not re.search(r"</?[a-z][^>]*>", r.abstract), (
            "markup leaked into abstract"
        )
        assert r.url.startswith("https://"), "every record links somewhere that can resolve"
        assert r.doi is None or re.fullmatch(r"10\.\S+", r.doi) and r.doi == r.doi.lower()
        assert r.pmid is None or r.pmid.isdigit()
        assert r.pmcid is None or re.fullmatch(r"PMC\d+", r.pmcid)
        assert r.arxiv_id is None or not re.search(r"v\d+$", r.arxiv_id)
        assert r.year is None or 1900 <= r.year <= 2100
        assert any([r.doi, r.pmid, r.pmcid, r.arxiv_id, r.source_id]), "needs some identifier"
        # An unknown licence stays unknown: never invented, never defaulted to open.
        assert r.licence is None or r.licence.strip()


@pytest.mark.parametrize("name", [*NAMES, "arxiv_empty"])
async def test_cassette_matches_the_code_exactly(name: str) -> None:
    """Every recorded response is used and nothing is requested that was not recorded."""
    _, transport = await run(name) if name != "arxiv_empty" else await _run_empty()
    assert set(transport.served) == set(transport.entries)


async def _run_empty() -> tuple[SearchOutcome, CassetteTransport]:
    transports: dict[str, CassetteTransport] = {}

    def transport_for(n: str) -> CassetteTransport:
        transports[n] = CassetteTransport(CASSETTES / f"{n}.json")
        return transports[n]

    adapter, plan = adapters(transport_for)["arxiv_empty"]
    return await adapter.search(plan, limit=LIMIT), transports["arxiv_empty"]


async def test_a_search_with_no_hits_is_an_empty_success_not_a_failure() -> None:
    outcome, _ = await _run_empty()
    assert outcome.records == [] and outcome.partial_reason is None


# --- the plan reaches each source in its own dialect ------------------------------------------

DIALECT = {
    "europe_pmc": [
        "((EGFR OR ERBB1) AND (T790M))",
        "FIRST_PDATE:[2020-01-01 TO 2024-12-31]",
        "resultType=core",
    ],
    "pubmed": [
        "EGFR[Title/Abstract]",
        '"ErbB Receptors"[MeSH Terms]',
        "mindate=2020/01/01",
        "maxdate=2024/12/31",
        "datetype=pdat",
    ],
    "openalex": [
        "search=(EGFR OR ERBB1) AND (T790M)",
        "from_publication_date:2020-01-01",
        "to_publication_date:2024-12-31",
    ],
    "crossref": [
        "query.bibliographic=EGFR T790M",
        "from-pub-date:2020-01-01",
        "until-pub-date:2024-12-31",
    ],
    "arxiv": ["all:kinase", "all:docking", "submittedDate:[202001010000 TO 202412312359]"],
    "biorxiv": ["/details/biorxiv/2024-04-01/2024-06-30/0/json"],
    "medrxiv": ["/details/medrxiv/2024-04-01/2024-06-30/0/json"],
}


@pytest.mark.parametrize("name", NAMES)
async def test_the_plan_is_translated_into_the_sources_own_syntax(name: str) -> None:
    _, transport = await run(name)
    first = transport.served[0]
    for fragment in DIALECT[name]:
        assert fragment in first.replace("%3A", ":"), f"{fragment!r} missing from {first}"


# --- golden values read off the real recordings -----------------------------------------------


async def test_europe_pmc_golden() -> None:
    outcome, _ = await run("europe_pmc")
    first = outcome.records[0]
    assert (first.doi, first.pmid, first.pmcid) == ("10.1111/cas.16437", "39741120", "PMC11875782")
    assert first.licence == "cc by" and first.is_open_access is True and not first.is_preprint
    assert first.journal == "Cancer science" and first.authors[:2] == ["Zhang Y", "Xu Y"]
    assert first.url == "https://doi.org/10.1111/cas.16437"


async def test_pubmed_golden() -> None:
    outcome, _ = await run("pubmed")
    first, second = outcome.records[0], outcome.records[1]
    assert (first.pmid, first.doi, first.journal) == (
        "37751131",
        "10.1007/s40265-023-01946-w",
        "Drugs",
    )
    assert "Review" in first.publication_types and first.pmcid is None
    assert second.pmcid == "PMC8562388" and second.pmid == "34558640"
    assert first.licence is None and first.is_open_access is None  # PubMed does not say: unknown
    assert first.url == "https://pubmed.ncbi.nlm.nih.gov/37751131/"
    assert first.authors[0] == "Hannah A Blair"


async def test_openalex_golden() -> None:
    outcome, _ = await run("openalex")
    first = outcome.records[0]
    assert (first.source_id, first.doi, first.pmid) == (
        "W3087185067",
        "10.1158/1535-7163.mct-20-0229",
        "32943545",
    )
    assert first.abstract and first.abstract.startswith(
        "Osimertinib is the only EGFR-tyrosine kinase inhibitor"
    )
    assert first.is_open_access is False
    assert any(r.is_open_access for r in outcome.records)
    assert (
        sum(1 for r in outcome.records if r.abstract is None) == 2
    )  # OpenAlex lacks them; we do not invent


async def test_crossref_golden() -> None:
    outcome, _ = await run("crossref")
    first = outcome.records[0]
    assert first.doi == "10.18231/2394-6377.2018.0026" and first.year == 2020
    assert first.publication_types == ["journal-article"] and first.is_open_access is None
    assert first.pmid is None  # Crossref has no PubMed ids


async def test_arxiv_golden() -> None:
    outcome, _ = await run("arxiv")
    first, second = outcome.records[0], outcome.records[1]
    assert (first.arxiv_id, first.source_id, first.url) == (
        "2410.08938",
        "2410.08938",
        "https://arxiv.org/abs/2410.08938",
    )
    assert all(r.is_preprint and r.arxiv_id for r in outcome.records)
    assert second.doi == "10.7554/elife.99702.1"
    assert all(r.licence is None for r in outcome.records)


@pytest.mark.parametrize("name", ["biorxiv", "medrxiv"])
async def test_preprint_servers_report_what_they_could_not_do(name: str) -> None:
    outcome, _ = await run(name)
    assert all(r.is_preprint and r.is_open_access for r in outcome.records)
    reason = outcome.partial_reason or ""
    assert "no keyword search" in reason and re.search(r"scanned \d+ of \d+", reason), reason
    assert all(r.licence != "unknown" for r in outcome.records)


async def test_biorxiv_golden_and_keyword_filter() -> None:
    outcome, _ = await run("biorxiv")
    first = outcome.records[0]
    assert first.doi == "10.1101/2024.03.31.587463" and first.licence == "cc_by_nc_nd"
    assert first.url == "https://www.biorxiv.org/content/10.1101/2024.03.31.587463v2"
    # The plan's one concept is "cancer": every kept record must mention it.
    assert all("cancer" in f"{r.title} {r.abstract}".lower() for r in outcome.records)
    assert "scanned 60 of 14726" in (outcome.partial_reason or "")


def test_adapters_satisfy_the_source_protocol() -> None:
    def transport_for(n: str) -> CassetteTransport:
        return CassetteTransport(CASSETTES / f"{n}.json")

    for adapter, _ in adapters(transport_for).values():
        source: LiteratureSource = adapter
        assert source.name
