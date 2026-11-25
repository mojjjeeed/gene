"""Query building: the plan's AND-of-ORs structure and its safety against odd input."""

from __future__ import annotations

import pytest
from a9_agents.sources.base import (
    boolean_query,
    clean_text,
    norm_arxiv_id,
    norm_doi,
    norm_pmcid,
    norm_pmid,
    plain_terms,
)
from a9_contracts.search_plan import SearchPlan


def plan(*concepts: tuple[str, list[str], list[str]]) -> SearchPlan:
    return SearchPlan.model_validate(
        {
            "topic": "t",
            "concepts": [{"label": a, "synonyms": b, "mesh_terms": c} for a, b, c in concepts],
            "include_criteria": [], "exclude_criteria": [], "date_from": None, "date_to": None,
            "generated_by": "stub", "model": None,
        }
    )  # fmt: skip


def test_or_within_a_concept_and_across_concepts() -> None:
    p = plan(("EGFR", ["ERBB1", "HER1"], []), ("T790M", [], []))
    assert boolean_query(p) == "(EGFR OR ERBB1 OR HER1) AND (T790M)"


def test_multiword_terms_are_quoted_and_duplicates_dropped() -> None:
    p = plan(("lung cancer", ["Lung Cancer", "NSCLC"], []))
    assert boolean_query(p) == '("lung cancer" OR NSCLC)'


def test_field_wrappers_and_mesh() -> None:
    p = plan(("EGFR", [], ["ErbB Receptors"]))
    q = boolean_query(p, field_suffix="[Title/Abstract]", mesh_format='"{}"[MeSH Terms]')
    assert q == '(EGFR[Title/Abstract] OR "ErbB Receptors"[MeSH Terms])'
    assert boolean_query(plan(("kinase", [], [])), field_prefix="all:") == "(all:kinase)"


@pytest.mark.parametrize(
    "hostile", ['a" OR 1=1 --', "x) OR (y", "[Title]", "back\\slash", "{curly}"]
)
def test_syntax_characters_in_terms_cannot_break_out_of_the_query(hostile: str) -> None:
    q = boolean_query(plan((hostile, [], [])))
    assert q.count("(") == 1 and q.count(")") == 1  # no injected groups
    assert q.count('"') in (0, 2)  # quotes balanced
    assert "[" not in q and "\\" not in q


def test_a_plan_with_no_usable_concept_is_an_error_not_an_empty_query() -> None:
    with pytest.raises(ValueError, match="no usable concepts"):
        boolean_query(plan(('"()"', [], [])))


def test_plain_terms_for_sources_without_boolean_syntax() -> None:
    assert plain_terms(plan(("EGFR", ["ERBB1"], []), ("lung cancer", [], []))) == "EGFR lung cancer"


@pytest.mark.parametrize(
    ("raw", "doi"),
    [("https://doi.org/10.1000/ABC.1", "10.1000/abc.1"), ("doi:10.1000/x", "10.1000/x"), (" 10.1/Y ", "10.1/y"),
     ("not-a-doi", None), ("", None), (None, None)],
)  # fmt: skip
def test_doi_normalisation(raw: str | None, doi: str | None) -> None:
    assert norm_doi(raw) == doi


def test_other_identifier_normalisation() -> None:
    assert (
        norm_pmcid("pmc123") == "PMC123"
        and norm_pmcid("123") == "PMC123"
        and norm_pmcid("") is None
    )
    assert norm_pmid("https://pubmed.ncbi.nlm.nih.gov/12345/") == "12345" and norm_pmid("x") is None
    assert norm_arxiv_id("http://arxiv.org/abs/2101.00001v3") == "2101.00001"
    assert norm_arxiv_id("arXiv:hep-th/9901001v1") == "hep-th/9901001"


def test_clean_text_strips_markup_entities_and_whitespace() -> None:
    assert (
        clean_text("<jats:p>Effect of <i>EGFR</i>&nbsp;loss\n in  cells &amp; tissue</jats:p>")
        == "Effect of EGFR loss in cells & tissue"
    )
    assert clean_text("   ") is None and clean_text(None) is None
