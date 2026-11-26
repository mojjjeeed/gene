"""Claim extraction with exact offsets, the cache, and entity normalisation (real recorded responses)."""

from __future__ import annotations

import uuid
from typing import Any

import psycopg.errors
import pytest
from a9_agents.db import owner, scoped
from a9_agents.extraction.claims import EXTRACTOR_VERSION, RegexClaimExtractor, extract_corpus
from a9_agents.extraction.normalise import Normaliser, smiles_to_inchikey
from cassette import CassetteTransport
from sources_fixtures import CASSETTES, fast_client
from test_retrieval import add_paper

X = RegexClaimExtractor()


def test_measurements_are_found_with_exact_offsets_and_normalised_units() -> None:
    text = "Compound 7 inhibited EGFR with an IC50 of 4.2 nM in cells. The Ki was 0.35 µM, whereas the EC50 = 12 uM."
    claims = X.extract(text)
    assert [(c.assay, c.value, c.unit) for c in claims] == [
        ("IC50", 4.2, "nM"),
        ("Ki", 0.35, "µM"),
        ("EC50", 12.0, "µM"),
    ]
    assert [c.value_nm for c in claims] == [4.2, 350.0, 12000.0]
    for c in claims:
        assert text[c.start : c.end].startswith(c.assay[:1])
    assert text[claims[0].start : claims[0].end] == "IC50 of 4.2 nM"
    assert claims[0].entity_raw == "Compound 7" and claims[0].target_raw == "EGFR"
    assert claims[0].sentence.startswith("Compound 7 inhibited EGFR")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The IC₅₀ value was < 1 nM.", [("IC50", "<", 1.0, "nM")]),
        ("Binding was tight (Kd = 3 pM).", [("Kd", None, 3.0, "pM")]),
        ("GI50 of approximately 2.5 μM across lines.", [("GI50", None, 2.5, "µM")]),
        ("IC50 values ranged widely.", []),  # no number: nothing is invented
        ("The dose was 5 nM.", []),  # a number and unit with no assay is not a measured activity
        ("We used 10 mM Tris and IC50 assays.", []),
    ],
)
def test_phrasings_and_non_claims(
    text: str, expected: list[tuple[str, str | None, float, str]]
) -> None:
    assert [
        (c.assay, c.qualifier, c.value, c.unit.replace("μ", "µ")) for c in X.extract(text)
    ] == expected


def test_a_claims_span_lies_inside_its_chunk_text() -> None:
    text = "x " * 40 + "Inhibitor A showed an IC50 of 12 nM against the mutant. " + "y " * 40
    (c,) = X.extract(text)
    assert 0 <= c.start < c.end <= len(text) and "IC50" in text[c.start : c.end]


async def test_claims_carry_their_full_provenance_and_absolute_document_offsets(pool: Any) -> None:
    paper = await add_paper(pool, "kinase")
    async with owner(pool) as c:
        await c.execute("UPDATE chunks SET text = %s, text_hash = %s WHERE paper_id = %s AND kind = 'body' AND section_path = ARRAY['Discussion']",
                        ("Inhibitor 12 blocked EGFR with an IC50 of 4 nM in resistant cells.", uuid.uuid4().hex, paper))  # fmt: skip
        row = await (
            await c.execute(
                "SELECT id, char_start FROM chunks WHERE paper_id = %s AND text LIKE 'Inhibitor 12%%'",
                (paper,),
            )
        ).fetchone()
    assert row is not None
    async with scoped(pool, role="a9_worker") as conn:
        stats = await extract_corpus(conn, X, [paper], uuid.uuid4())
    assert stats.claims == 1 and stats.extractions == stats.chunks
    async with owner(pool) as c:
        claim = await (
            await c.execute("SELECT * FROM claims WHERE paper_id = %s", (paper,))
        ).fetchone()
    assert claim is not None
    assert claim["chunk_id"] == row["id"] and claim["char_start"] >= row["char_start"]
    assert (
        claim["parser_version"] == "test-v1"
        and claim["extraction_model"] == EXTRACTOR_VERSION
        and claim["run_id"]
    )


async def test_a_rerun_on_the_same_corpus_is_a_cache_hit_end_to_end(pool: Any) -> None:
    paper = await add_paper(pool, "kinase")
    async with owner(
        pool
    ) as c:  # the cache is global by design; give this paper text nobody has extracted before
        await c.execute(
            "UPDATE chunks SET text_hash = md5(random()::text || id::text) WHERE paper_id = %s",
            (paper,),
        )
    calls = {"n": 0}

    class Counting(RegexClaimExtractor):
        def extract(self, text: str) -> Any:
            calls["n"] += 1
            return super().extract(text)

    async with scoped(pool, role="a9_worker") as conn:
        first = await extract_corpus(conn, Counting(), [paper], uuid.uuid4())
    first_calls = calls["n"]
    async with scoped(pool, role="a9_worker") as conn:
        second = await extract_corpus(conn, Counting(), [paper], uuid.uuid4())
    assert first.cache_hits == 0 and first_calls == first.chunks > 0
    assert (second.cache_hits, second.extractions) == (second.chunks, 0) and calls[
        "n"
    ] == first_calls  # not one extractor call


async def test_a_claim_without_a_complete_envelope_raises(pool: Any) -> None:
    paper = await add_paper(pool, "kinase")
    async with owner(pool) as c:
        chunk = await (
            await c.execute("SELECT id FROM chunks WHERE paper_id = %s LIMIT 1", (paper,))
        ).fetchone()
    assert chunk
    cols = "chunk_id, kind, assay, value, unit, value_nm, sentence, paper_id, section_path, page, char_start, char_end, parser_version, extraction_model, prompt_version, run_id"
    good: dict[str, Any] = dict(
        zip(
            cols.split(", "),
            [
                chunk["id"],
                "measurement",
                "IC50",
                1.0,
                "nM",
                1.0,
                "s",
                paper,
                ["R"],
                1,
                0,
                5,
                "p",
                "m",
                "n",
                uuid.uuid4(),
            ],
            strict=True,
        )
    )
    for missing in (
        "paper_id",
        "section_path",
        "page",
        "char_start",
        "char_end",
        "parser_version",
        "extraction_model",
        "prompt_version",
        "run_id",
    ):
        row = {k: v for k, v in good.items() if k != missing}
        with pytest.raises(psycopg.errors.NotNullViolation):
            async with owner(pool) as c:
                await c.execute(
                    f"INSERT INTO claims ({', '.join(row)}) VALUES ({', '.join(['%s'] * len(row))})",
                    list(row.values()),
                )


# --- normalisation ------------------------------------------------------------------------------------


def norm() -> Normaliser:
    def c(name: str) -> Any:
        return fast_client(name, CassetteTransport(CASSETTES / f"entities_{name}.json"))

    return Normaliser(uniprot=c("uniprot"), hgnc=c("hgnc"), ols=c("mondo"), pubchem=c("pubchem"))


def test_smiles_normalise_offline_to_the_known_inchikey() -> None:
    assert (
        smiles_to_inchikey("CC(=O)OC1=CC=CC=C1C(=O)O").identifier == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    )  # aspirin
    assert (
        smiles_to_inchikey("OC(=O)c1ccccc1OC(C)=O").identifier == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    )  # same molecule, written differently
    for bad in ("osimertinib", "not a smiles", "", "C"):
        n = smiles_to_inchikey(bad)
        assert not n.ok and n.flag and n.raw == bad


async def test_a_gene_symbol_grounds_to_uniprot_and_hgnc_and_a_fake_one_is_flagged() -> None:
    n = norm()
    assert (await n.gene_uniprot("EGFR")).identifier == "P00533"
    h = await n.gene_hgnc("EGFR")
    assert h.identifier == "HGNC:3236" and h.label == "EGFR"
    fake = await n.gene_hgnc("NOTAGENE1")
    assert (
        not fake.ok and fake.raw == "NOTAGENE1" and "no approved HGNC symbol" in (fake.flag or "")
    )


async def test_a_compound_name_grounds_to_an_inchikey_via_pubchem() -> None:
    n = await norm().compound("osimertinib")
    assert n.ok and len(n.identifier or "") == 27 and (n.identifier or "").count("-") == 2


async def test_a_disease_needs_an_exact_mondo_match_not_a_fuzzy_neighbour() -> None:
    ok = await norm().disease("lung adenocarcinoma")
    assert ok.identifier == "MONDO:0005061" and ok.label
    fuzzy = await norm().disease("lung adenocarcinoma of unknown origin")
    assert not fuzzy.ok  # also not in the recording: it must fail closed, not guess
