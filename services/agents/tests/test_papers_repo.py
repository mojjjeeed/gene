"""Writing resolved papers to the shared table: add information, never destroy it."""

from __future__ import annotations

import uuid
from typing import Any

from a9_agents.db import scoped
from a9_agents.identity import cluster_records, to_draft
from a9_agents.papers import lock_papers, record_retraction, upsert_paper
from a9_contracts.literature_record import LiteratureRecord


def rec(doi: str | None, **kw: Any) -> LiteratureRecord:
    uid = uuid.uuid4().hex[:8]
    base: dict[str, Any] = {
        "source": "openalex", "source_id": uid, "title": f"Distinct title number {uid} about kinase signalling in tumours",
        "abstract": None, "authors": ["Ada Lovelace"], "year": 2023, "journal": None, "doi": doi, "related_dois": [],
        "pmid": None, "pmcid": None, "arxiv_id": None, "url": "https://example.org/x", "licence": None,
        "is_open_access": None, "is_preprint": False, "publication_types": [],
    }  # fmt: skip
    return LiteratureRecord.model_validate({**base, **kw})


async def put(pool: Any, *records: LiteratureRecord) -> tuple[uuid.UUID, str]:
    (cluster,) = await cluster_records(list(records))
    async with scoped(pool, role="a9_worker") as conn:
        await lock_papers(conn)
        return await upsert_paper(conn, to_draft(cluster))


async def row(pool: Any, paper_id: uuid.UUID) -> dict[str, Any]:
    async with scoped(pool, role="a9_worker") as conn:
        found = await (
            await conn.execute("SELECT * FROM papers WHERE id = %s", (paper_id,))
        ).fetchone()
    assert found is not None
    return dict(found)


def u() -> str:
    return uuid.uuid4().hex[:10]


async def test_the_same_paper_from_two_runs_is_one_row(pool: Any) -> None:
    doi = f"10.9/{u()}"
    first, outcome1 = await put(pool, rec(doi, abstract="original abstract"))
    second, outcome2 = await put(pool, rec(doi, abstract="a different abstract", pmid="777"))
    assert first == second and (outcome1, outcome2) == ("created", "updated")
    paper = await row(pool, first)
    assert paper["abstract"] == "original abstract"  # nothing already known is overwritten
    assert paper["pmid"] == "777"  # but empty fields are filled


async def test_promotion_keeps_one_paper_and_every_doi_findable(pool: Any) -> None:
    pre, jour = f"10.1101/{u()}", f"10.9/{u()}"
    preprint = rec(
        pre,
        is_preprint=True,
        related_dois=[jour],
        licence="cc_by",
        title="Preprint working title about tumour kinases here",
    )
    pid, _ = await put(pool, preprint)
    before = await row(pool, pid)
    assert (before["doi"], before["alt_dois"], before["is_preprint"], before["licence"]) == (
        pre,
        [jour],
        True,
        "cc_by",
    )

    journal = rec(
        jour,
        journal="J Real Science",
        licence=None,
        title="Final published title about tumour kinases in vivo",
    )
    pid2, outcome = await put(pool, journal)  # a later run sees only the journal version
    assert pid2 == pid and outcome == "updated"
    after = await row(pool, pid)
    assert after["doi"] == jour and after["alt_dois"] == [pre] and after["is_preprint"] is False
    assert after["journal"] == "J Real Science" and after["title"].startswith("Final published")
    assert after["licence"] is None, (
        "the preprint's licence must not carry over to the journal version"
    )
    assert after["full_text_allowed"] is False


async def test_a_new_identifier_never_steals_one_that_belongs_to_another_paper(pool: Any) -> None:
    a_doi, b_doi, pmid = f"10.9/{u()}", f"10.9/{u()}", str(uuid.uuid4().int)[:9]
    a, _ = await put(pool, rec(a_doi))
    b, _ = await put(pool, rec(b_doi, pmid=pmid))
    # A record that names A's DOI but carries B's PMID would need to merge two existing papers: refuse.
    attached, outcome = await put(pool, rec(a_doi, pmid=pmid))
    assert outcome == "ambiguous"
    assert (
        attached == a
    )  # attached to the oldest match; the other row is left for a person to merge
    assert (await row(pool, b))["pmid"] == pmid  # B still owns its PMID
    assert (await row(pool, a))["pmid"] is None  # and A did not take it


async def test_identifiers_found_later_are_added_without_duplicates(pool: Any) -> None:
    doi = f"10.9/{u()}"
    pid, _ = await put(pool, rec(doi, pmcid="PMC424242"))
    again, _ = await put(
        pool, rec(None, pmcid="PMC424242", title="A different title but the same PMCID is enough")
    )
    assert again == pid


async def test_retraction_status_only_ever_goes_up_and_the_paper_stays(pool: Any) -> None:
    pid, _ = await put(pool, rec(f"10.9/{u()}"))
    async with scoped(pool, role="a9_worker") as conn:
        await record_retraction(
            conn, pid, status="expression_of_concern", notice_dois=["10.9/n1"], checked=True
        )
        await record_retraction(
            conn, pid, status="retracted", notice_dois=["10.9/n2"], checked=True
        )
        await record_retraction(
            conn, pid, status="none", notice_dois=[], checked=True
        )  # a later clean check
    paper = await row(pool, pid)
    assert paper["retraction_status"] == "retracted"  # flagged, and the row is still here
    assert sorted(paper["retraction_notice_dois"]) == ["10.9/n1", "10.9/n2"]
    assert paper["retraction_checked_at"] is not None


async def test_an_unchecked_paper_has_no_check_time_so_it_cannot_look_cleared(pool: Any) -> None:
    pid, _ = await put(pool, rec(f"10.9/{u()}"))
    async with scoped(pool, role="a9_worker") as conn:
        await record_retraction(conn, pid, status="none", notice_dois=[], checked=False)
    paper = await row(pool, pid)
    assert paper["retraction_status"] == "none" and paper["retraction_checked_at"] is None


async def test_a_source_asserted_retraction_is_flagged_at_creation(pool: Any) -> None:
    pid, _ = await put(
        pool, rec(f"10.9/{u()}", title="RETRACTED: Kinase signalling in tumours and other things")
    )
    paper = await row(pool, pid)
    assert paper["retraction_status"] == "retracted" and paper["title"].startswith(
        "Kinase signalling"
    )
