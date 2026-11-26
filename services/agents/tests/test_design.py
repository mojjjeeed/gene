"""Cheap gates, conformal calibration with an applicability domain, and the model registry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg.errors
import pytest
from a9_agents.db import owner, scoped
from a9_agents.design.conformal import ApplicabilityDomain, Prediction, conformal_quantile
from a9_agents.design.esol import EsolModel, evaluate, load_esol
from a9_agents.design.gates import run_gates
from a9_agents.design.novelty import ChemblNovelty
from a9_agents.design.registry import register_model, store_candidate, store_score
from cassette import CassetteTransport
from sources_fixtures import CASSETTES, fast_client

ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"
RHODANINE = "S=C1SC(=Cc2ccccc2)C(=O)N1"  # a textbook PAINS (ene_rhod)
NITRO = "O=[N+]([O-])c1ccc(CC(=O)O)cc1"  # a Brenk alert, not a PAINS


def gate(report: Any, name: str) -> Any:
    return next(r for r in report.results if r.gate == name)


# --- gates ---------------------------------------------------------------------------------------------


def test_a_clean_molecule_passes_every_hard_gate_with_detail() -> None:
    r = run_gates(ASPIRIN, seen_inchikeys=set(), known_inchikeys=set())
    assert r.passed and r.failed == [] and r.inchikey == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    assert gate(r, "property_windows").detail["properties"]["mw"] == pytest.approx(180.16, abs=0.1)
    assert gate(r, "synthetic_accessibility").detail["sa_score"] < 3


@pytest.mark.parametrize("bad", ["", "not smiles", "C", "CC.O", "[Na+].[Cl-]"])
def test_invalid_or_trivial_structures_fail_validity_and_stop(bad: str) -> None:
    r = run_gates(bad)
    assert not r.passed and r.failed == ["validity"] and len(r.results) == 1


def test_pains_is_a_hard_fail_and_brenk_is_only_a_warning() -> None:
    pains = run_gates(RHODANINE)
    assert "pains" in pains.failed and gate(pains, "pains").detail["alerts"]
    nitro = run_gates(NITRO)
    assert nitro.passed and nitro.warnings == ["brenk"] and gate(nitro, "brenk").detail["alerts"]


def test_uniqueness_novelty_windows_sa_and_project_alerts_are_each_enforced() -> None:
    key = run_gates(ASPIRIN).inchikey or ""
    assert run_gates(ASPIRIN, seen_inchikeys={key}).failed == ["uniqueness"]
    assert run_gates(ASPIRIN, known_inchikeys={key}).failed == ["novelty"]
    assert "novelty" not in [
        r.gate for r in run_gates(ASPIRIN).results
    ]  # not asked: not reported, not assumed
    big = run_gates("C" * 60)
    assert (
        "property_windows" in big.failed
        and "mw" in gate(big, "property_windows").detail["violations"]
    )
    assert run_gates(ASPIRIN, sa_max=1.0).failed == ["synthetic_accessibility"]
    assert run_gates(ASPIRIN, project_alerts={"no_esters": "C(=O)O[#6]"}).failed == [
        "project_alerts"
    ]
    assert gate(
        run_gates(ASPIRIN, project_alerts={"no_esters": "C(=O)O[#6]"}), "project_alerts"
    ).detail["alerts"] == ["no_esters"]


async def test_novelty_against_chembl_from_real_recordings_and_unknown_is_not_novel() -> None:
    n = ChemblNovelty(fast_client("chembl", CassetteTransport(CASSETTES / "chembl.json")))
    assert await n.is_known("DUYJMQONPNNFPI-UHFFFAOYSA-N") is True  # osimertinib
    assert await n.is_known("NYDVZIHTURABKH-UHFFFAOYSA-N") is False
    import httpx

    down = ChemblNovelty(fast_client("chembl", httpx.MockTransport(lambda r: httpx.Response(503))))
    assert await down.is_known("X") is None


# --- conformal calibration and the applicability domain --------------------------------------------------


def test_the_conformal_quantile_is_finite_sample_corrected() -> None:
    assert conformal_quantile(list(range(1, 11)), 0.2) == 9.0  # ceil(11 * 0.8) = 9th of 10
    assert conformal_quantile([1.0, 2.0], 0.05) == float(
        "inf"
    )  # too few points for 95%: no useful interval
    assert conformal_quantile([], 0.1) == float("inf")


def test_the_domain_refuses_structures_unlike_its_training_set() -> None:
    d = ApplicabilityDomain(["CCO", "CCCO", "CCCCO", "CCN"], threshold=0.4)
    assert (
        d.contains("CCCCCO")
        and not d.contains("c1ccc2c(c1)ccc1ccccc12")
        and d.nn_similarity("not smiles") == 0.0
    )
    with pytest.raises(ValueError):
        ApplicabilityDomain(["not smiles"])


ESOL = Path(__file__).parent / "fixtures" / "esol.csv"


def test_real_held_out_coverage_is_close_to_nominal_and_the_domain_abstains() -> None:
    """ESOL: 1,128 measured solubilities, split 60/20/20 train/calibration/test with a fixed seed."""
    model, test = EsolModel.train(load_esol(ESOL))
    m90, m95 = evaluate(model, test, 0.90), evaluate(model, test, 0.95)
    assert m90["n_test"] >= 200
    assert abs(m90["coverage"] - 0.90) <= 0.05 and abs(m95["coverage"] - 0.95) <= 0.05
    assert (
        0.5 < m90["frac_in_domain"] < 1.0
    )  # some held-out molecules are outside the domain and get nothing
    assert (
        m90["mae"] < 1.0 and m90["mean_width"] < m95["mean_width"]
    )  # a higher level is a wider, not a different, interval


def test_out_of_domain_means_no_number_at_all() -> None:
    model, _ = EsolModel.train(load_esol(ESOL), domain_threshold=0.3)
    far = model.predict("[Pt](Cl)(Cl)(N)N")
    assert far == Prediction(None, None, None, None, False, far.nn_similarity)
    near = model.predict(ASPIRIN)
    assert (
        near.in_domain
        and near.lower is not None
        and near.value is not None
        and near.upper is not None
    )
    assert near.lower < near.value < near.upper and near.coverage == 0.9


def test_the_model_round_trips_through_json_unchanged() -> None:
    model, test = EsolModel.train(load_esol(ESOL))
    again = EsolModel.from_json(model.to_json())
    assert [again.predict(s) for s, _ in test[:20]] == [model.predict(s) for s, _ in test[:20]]


# --- the registry and the database's refusals ---------------------------------------------------------------


async def seed_molecule(pool: Any) -> tuple[uuid.UUID, uuid.UUID]:
    user, project, conv, mol = (uuid.uuid4() for _ in range(4))
    async with owner(pool) as c:
        await c.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user, f"{user}@x.org"))
        await c.execute(
            "INSERT INTO projects (id, user_id, name) VALUES (%s, %s, 'p')", (project, user)
        )
        await c.execute(
            "INSERT INTO conversations (id, user_id, project_id) VALUES (%s, %s, %s)",
            (conv, user, project),
        )
        await c.execute(
            "INSERT INTO molecules (id, user_id, conversation_id, smiles, inchikey) VALUES (%s, %s, %s, 'CCO', %s)",
            (mol, user, conv, uuid.uuid4().hex),
        )
    return user, mol


async def model_id(pool: Any) -> uuid.UUID:
    async with scoped(pool, role="a9_worker") as c:
        return await register_model(
            c,
            name="esol-ridge",
            version=uuid.uuid4().hex[:6],
            endpoint="logS",
            training_data="ESOL (Delaney 2004), 1,128 measurements",
            calibrated_at=datetime.now(UTC),
            domain_notes="small neutral organics; Tanimoto NN >= 0.3",
        )


async def test_registering_a_model_is_idempotent_and_requires_its_provenance(pool: Any) -> None:
    async with scoped(pool, role="a9_worker") as c:
        kw: dict[str, Any] = dict(
            name="m",
            version=uuid.uuid4().hex,
            endpoint="e",
            training_data="t",
            calibrated_at=datetime.now(UTC),
            domain_notes="d",
        )
        first, again = (
            await register_model(c, **kw),
            await register_model(c, **{**kw, "domain_notes": "changed"}),
        )
    assert first == again  # immutable: a second registration does not rewrite it
    for field in ("training_data", "domain_notes"):
        with pytest.raises(psycopg.errors.CheckViolation):
            async with scoped(pool, role="a9_worker") as c:
                await register_model(c, **{**kw, "version": uuid.uuid4().hex, field: ""})


async def test_a_score_needs_a_registered_model_and_an_in_domain_flag(pool: Any) -> None:
    user, mol = await seed_molecule(pool)
    ok = Prediction(-2.0, -3.0, -1.0, 0.9, True, 0.6)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        async with scoped(pool, role="a9_worker") as c:
            await store_score(
                c,
                molecule_id=mol,
                user_id=user,
                model_id=uuid.uuid4(),
                endpoint="logS",
                prediction=ok,
            )
    mid = await model_id(pool)
    with pytest.raises(psycopg.errors.NotNullViolation):
        async with owner(pool) as c:
            await c.execute(
                "INSERT INTO molecule_scores (molecule_id, user_id, model_id, endpoint, nn_similarity) VALUES (%s, %s, %s, 'logS', 0.5)",
                (mol, user, mid),
            )
    async with scoped(pool, role="a9_worker") as c:
        await store_score(
            c, molecule_id=mol, user_id=user, model_id=mid, endpoint="logS", prediction=ok
        )


async def test_the_database_refuses_a_number_outside_the_domain_and_an_inverted_interval(
    pool: Any,
) -> None:
    user, mol = await seed_molecule(pool)
    mid = await model_id(pool)
    for bad in (
        Prediction(-2.0, -3.0, -1.0, 0.9, False, 0.1),
        Prediction(-2.0, -1.0, -3.0, 0.9, True, 0.6),
        Prediction(None, None, None, None, True, 0.6),
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            async with scoped(pool, role="a9_worker") as c:
                await store_score(
                    c, molecule_id=mol, user_id=user, model_id=mid, endpoint="logS", prediction=bad
                )
    async with scoped(pool, role="a9_worker") as c:  # an honest blank is fine
        await store_score(
            c,
            molecule_id=mol,
            user_id=user,
            model_id=mid,
            endpoint="logS",
            prediction=Prediction(None, None, None, None, False, 0.1),
        )


async def test_scores_and_gates_are_private_to_their_owner(pool: Any) -> None:
    user, mol = await seed_molecule(pool)
    other, _ = await seed_molecule(pool)
    mid = await model_id(pool)
    async with scoped(pool, role="a9_worker") as c:
        await store_score(
            c,
            molecule_id=mol,
            user_id=user,
            model_id=mid,
            endpoint="logS",
            prediction=Prediction(-2.0, -3.0, -1.0, 0.9, True, 0.6),
        )
        await c.execute(
            "INSERT INTO molecule_gates (molecule_id, user_id, gate, hard, passed, detail) VALUES (%s, %s, 'pains', true, true, '{}')",
            (mol, user),
        )
    for as_user, expected in ((user, 1), (other, 0)):
        async with scoped(pool, role="a9_app", user_id=as_user) as c:
            assert (
                await (await c.execute("SELECT count(*) AS n FROM molecule_scores")).fetchone()
            )["n"] >= expected  # type: ignore[index]
            mine = (
                await (
                    await c.execute(
                        "SELECT count(*) AS n FROM molecule_scores WHERE molecule_id = %s", (mol,)
                    )
                ).fetchone()
            )["n"]  # type: ignore[index]
            assert mine == expected


async def test_gate_results_are_stored_with_their_detail_pass_or_fail(pool: Any) -> None:
    user, mol = await seed_molecule(pool)
    async with owner(pool) as c:
        conv = (
            await (
                await c.execute("SELECT conversation_id FROM molecules WHERE id = %s", (mol,))
            ).fetchone()
        )["conversation_id"]  # type: ignore[index]
    async with scoped(pool, role="a9_worker") as c:
        stored = await store_candidate(
            c, user_id=user, conversation_id=conv, report=run_gates(RHODANINE)
        )
        again = await store_candidate(
            c, user_id=user, conversation_id=conv, report=run_gates(RHODANINE)
        )
        assert (
            await store_candidate(
                c, user_id=user, conversation_id=conv, report=run_gates("not smiles")
            )
            is None
        )
    assert stored is not None and stored == again  # the same structure is one candidate
    async with owner(pool) as c:
        rows = {
            r["gate"]: r
            for r in await (
                await c.execute("SELECT * FROM molecule_gates WHERE molecule_id = %s", (stored,))
            ).fetchall()
        }
    assert (
        rows["pains"]["passed"] is False
        and rows["pains"]["hard"] is True
        and rows["pains"]["detail"]["alerts"]
    )
    assert rows["validity"]["passed"] is True and "property_windows" in rows
