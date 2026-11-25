"""Identity resolution, the dedup ladder, and retraction checks.

Real recorded data is used for the headline cases: a bioRxiv preprint and its published journal
version, and the 1998 Wakefield paper that was retracted in 2010."""

from __future__ import annotations

import json
from typing import Any

import pytest
from a9_agents.embedder import HashingEmbedder, make_embedder
from a9_agents.identity import (
    cluster_records,
    retraction_hint,
    surname,
    title_key,
    to_draft,
)
from a9_agents.retractions import (
    CrossrefRetractionChecker,
    FixtureRetractionChecker,
    make_retraction_checker,
)
from a9_agents.sources.base import SourceError
from a9_agents.sources.biorxiv import BioRxiv
from a9_agents.sources.europepmc import EuropePmc
from a9_contracts.literature_record import LiteratureRecord
from cassette import CassetteTransport
from sources_fixtures import CASSETTES, fast_client

PREPRINT_DOI, JOURNAL_DOI = "10.1101/2024.03.31.587463", "10.1093/nargab/lqae190"


def rec(**kw: Any) -> LiteratureRecord:
    base: dict[str, Any] = {
        "source": "openalex", "source_id": kw.pop("source_id", "x"), "title": "A long enough title for the matcher to trust",
        "abstract": None, "authors": ["Ada Lovelace"], "year": 2022, "journal": None, "doi": None,
        "related_dois": [], "pmid": None, "pmcid": None, "arxiv_id": None, "url": "https://example.org/x",
        "licence": None, "is_open_access": None, "is_preprint": False, "publication_types": [],
    }  # fmt: skip
    return LiteratureRecord.model_validate({**base, **kw})


def real_pair() -> tuple[LiteratureRecord, LiteratureRecord]:
    epmc = json.loads(
        next(iter(json.loads((CASSETTES / "identity_europepmc.json").read_text()).values()))["body"]
    )
    journal = EuropePmc.to_record(epmc["resultList"]["result"][0])
    bio = json.loads((CASSETTES / "biorxiv.json").read_text())
    item = next(
        i
        for v in bio.values()
        for i in json.loads(v["body"])["collection"]
        if i["doi"] == PREPRINT_DOI
    )
    preprint = BioRxiv.to_record(item)
    assert journal and preprint
    return preprint, journal


# --- normalisation ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("author", "expected"),
    [("Margalit, S.", "margalit"), ("Margalit S", "margalit"), ("Hannah A Blair", "blair"), ("Yong Du", "du"),
     ("Tulpová Z", "tulpova"), ("van der Berg AB", "berg"), ("de la Cruz, Maria", "cruz"), ("", None)],
)  # fmt: skip
def test_first_author_surname_across_source_formats(author: str, expected: str | None) -> None:
    assert surname(author) == expected


def test_title_key_ignores_case_punctuation_diacritics_and_withdrawal_prefixes() -> None:
    assert title_key("WITHDRAWN: Mitochondrial genome — a Study!") == title_key(
        "mitochondrial genome: a study"
    )
    assert title_key("Tulpová's Naïve  Result") == "tulpova s naive result"


# --- the ladder: each rung, and what must NOT merge ---------------------------------------------


async def test_identifiers_merge_in_every_form() -> None:
    cases = [
        ("doi", {"doi": "10.1/a"}),
        ("pmid", {"pmid": "12"}),
        ("pmcid", {"pmcid": "PMC9"}),
        ("arxiv_id", {"arxiv_id": "2101.00001"}),
    ]
    for why, ids in cases:
        clusters = await cluster_records(
            [
                rec(source_id="1", title="First distinct title here today", **ids),
                rec(
                    source_id="2",
                    title="Totally other words appear in this one",
                    authors=["Z Q"],
                    **ids,
                ),
            ]
        )
        assert [(len(c.records), c.reasons) for c in clusters] == [(2, [why])], why


async def test_a_publisher_asserted_link_merges_versions_with_different_dois_and_titles() -> None:
    preprint = rec(
        source_id="p",
        doi="10.1101/x",
        is_preprint=True,
        related_dois=["10.1/journal"],
        title="Totally different working title for a preprint",
        authors=["A B"],
    )
    journal = rec(
        source_id="j",
        doi="10.1/journal",
        title="The final published title looks nothing like it",
        authors=["C D"],
    )
    (cluster,) = await cluster_records([preprint, journal])
    assert cluster.reasons == ["linked_doi"] and len(cluster.records) == 2


async def test_two_records_naming_the_same_other_version_are_the_same_work() -> None:
    a = rec(
        source_id="a",
        doi="10.1/a",
        related_dois=["10.1/shared"],
        title="Alpha beta gamma delta epsilon zeta eta",
        authors=["P Q"],
    )
    b = rec(
        source_id="b",
        doi="10.1/b",
        related_dois=["10.1/shared"],
        title="Completely unrelated heading words appear here",
        authors=["R S"],
    )
    assert [c.reasons for c in await cluster_records([a, b])] == [["linked_doi"]]


async def test_title_and_first_author_merge_but_year_gap_and_short_titles_do_not() -> None:
    a = rec(
        source_id="a",
        title="Mechanisms of acquired resistance to osimertinib in lung cancer",
        year=2022,
    )
    assert [
        c.reasons
        for c in await cluster_records([a, a.model_copy(update={"source_id": "b", "year": 2023})])
    ] == [["title_author"]]
    assert (
        len(await cluster_records([a, a.model_copy(update={"source_id": "b", "year": 2030})])) == 2
    )  # a different paper
    short = rec(source_id="s", title="Introduction")
    assert (
        len(await cluster_records([short, short.model_copy(update={"source_id": "t"})])) == 2
    )  # too generic to be evidence
    other_author = a.model_copy(update={"source_id": "c", "authors": ["Grace Hopper"]})
    assert len(await cluster_records([a, other_author])) == 2  # same title, different first author


async def test_similarity_merges_only_a_retitled_preprint_with_its_journal_version() -> None:
    text = "We profile kidney tumours with nanopore sequencing and optical genome mapping to find structural variants and epigenetic changes"
    preprint = rec(
        source_id="p",
        is_preprint=True,
        title="Nanopore profiling of kidney tumours",
        abstract=text,
        authors=["Ada Lovelace"],
    )
    journal = rec(
        source_id="j",
        title="Long-read structural and epigenetic landscape of renal tumours",
        abstract=text,
        authors=["Lovelace A"],
    )
    (cluster,) = await cluster_records(
        [preprint, journal], embedder=HashingEmbedder(), similarity_threshold=0.8
    )
    assert cluster.reasons == ["similarity"]
    assert (
        len(await cluster_records([preprint, journal])) == 2
    )  # without an embedder the rung does not exist


@pytest.mark.parametrize(
    "journal_update",
    [
        {"authors": ["Grace Hopper"]},  # different first author
        {"year": 2030},  # years too far apart
        {"is_preprint": True},  # two preprints are not a preprint/journal pair
    ],
    ids=["other-author", "far-year", "both-preprints"],
)
async def test_similarity_alone_can_never_merge_unrelated_papers(
    journal_update: dict[str, Any],
) -> None:
    text = "identical abstract text about kidney tumours and sequencing methods used"
    preprint = rec(
        source_id="p", is_preprint=True, title="First working title of the preprint", abstract=text
    )
    other = rec(
        source_id="j",
        title="Second quite different published title text",
        abstract=text,
        **journal_update,
    )
    assert (
        len(
            await cluster_records(
                [preprint, other], embedder=HashingEmbedder(), similarity_threshold=0.5
            )
        )
        == 2
    )


async def test_clusters_report_every_rung_that_contributed() -> None:
    a = rec(source_id="a", doi="10.1/a", related_dois=["10.1/c"], pmid="1")
    b = rec(
        source_id="b",
        doi="10.1/b",
        pmid="1",
        title="Another title that has nothing in common here",
        authors=["Q R"],
    )
    c = rec(
        source_id="c",
        doi="10.1/c",
        title="Yet another unrelated heading for the third record",
        authors=["S T"],
    )
    (cluster,) = await cluster_records([a, b, c])
    assert cluster.reasons == ["pmid", "linked_doi"] and len(cluster.records) == 3


# --- the M0.7 gate, on real data ----------------------------------------------------------------


async def test_a_real_preprint_and_its_published_version_collapse_to_one_paper() -> None:
    preprint, journal = real_pair()
    assert (
        preprint.doi == PREPRINT_DOI and journal.doi == JOURNAL_DOI and preprint.doi != journal.doi
    )
    (cluster,) = await cluster_records([preprint, journal])
    assert cluster.reasons == ["linked_doi"]
    paper = to_draft(cluster)
    assert paper.merged_from == 2 and not paper.is_preprint
    assert paper.doi == JOURNAL_DOI and paper.alt_dois == [
        PREPRINT_DOI
    ]  # nothing is lost: the other DOI stays findable
    assert paper.journal == "NAR genomics and bioinformatics"
    assert (
        paper.licence == "cc by-nc" and paper.licence != preprint.licence
    )  # never borrowed from the preprint


async def test_the_same_pair_collapses_even_when_no_source_asserts_the_link() -> None:
    preprint, journal = real_pair()
    clusters = await cluster_records(
        [preprint.model_copy(update={"related_dois": []}), journal], embedder=make_embedder()
    )
    assert [(len(c.records), c.reasons) for c in clusters] == [(2, ["title_author"])]


# --- retraction ---------------------------------------------------------------------------------


def crossref_checker() -> CrossrefRetractionChecker:
    return CrossrefRetractionChecker(
        fast_client("crossref", CassetteTransport(CASSETTES / "crossref_retractions.json"))
    )


async def test_a_known_retracted_doi_is_reported_retracted_with_its_notice() -> None:
    result = await crossref_checker().check("10.1016/s0140-6736(97)11096-0")
    assert result.checked and result.status == "retracted"
    assert result.notice_dois == [
        "10.1016/s0140-6736(10)60175-4"
    ]  # the 2010 retraction; the 2004 correction is not one


async def test_ordinary_papers_check_clean_and_unknown_dois_are_unchecked_not_clean() -> None:
    clean = await crossref_checker().check(JOURNAL_DOI)
    assert (clean.checked, clean.status, clean.notice_dois) == (True, "none", [])
    unknown = await crossref_checker().check("10.5555/a9-no-such-doi")
    assert (
        unknown.checked is False
    )  # Crossref does not know it: that is "could not check", not "fine"


async def test_a_crossref_outage_raises_so_the_paper_stays_unchecked() -> None:
    import httpx

    transport = httpx.MockTransport(lambda r: httpx.Response(503))
    with pytest.raises(SourceError):
        await CrossrefRetractionChecker(fast_client("crossref", transport)).check("10.1/x")


def test_source_asserted_retraction_hints() -> None:
    assert (
        retraction_hint(rec(title="RETRACTED: Something about kidneys and tumours")) == "retracted"
    )
    assert (
        retraction_hint(rec(publication_types=["Journal Article", "Retracted Publication"]))
        == "retracted"
    )
    assert (
        retraction_hint(rec(title="WITHDRAWN: Mitochondrial genome variation affects things"))
        == "withdrawn"
    )
    assert (
        retraction_hint(rec(publication_types=["Retraction of Publication"])) == "none"
    )  # a notice, not the paper
    assert retraction_hint(rec()) == "none"


async def test_fixture_checker_and_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = FixtureRetractionChecker()
    assert (await fx.check("10.0000/fixture.retracted.x")).status == "retracted"
    assert (await fx.check("10.0000/plain")).status == "none"
    monkeypatch.setenv("A9_RETRACTION_CHECK", "off")
    assert make_retraction_checker() is None
    monkeypatch.setenv("A9_RETRACTION_CHECK", "bogus")
    with pytest.raises(ValueError):
        make_retraction_checker()
