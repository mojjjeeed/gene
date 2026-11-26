"""The screening gate: hits block and raise review items, near-misses alert, nothing is silently dropped."""

from __future__ import annotations

import uuid
from typing import Any

import psycopg.errors
import pytest
from a9_agents.db import owner, scoped
from a9_agents.design.gates import run_gates
from a9_agents.design.registry import store_candidate
from a9_agents.design.screening import NEAR_MISS_LIMIT, ScreeningBlockedError, admit, screen
from test_design import ASPIRIN
from test_retrieval import make_conv

# Well-known compounds used as test fixtures for the structural CLASS rules (no procedures are involved).
DIETHYL_FLUOROPHOSPHATE = "CCOP(=O)(OCC)F"
CYCLOPHOSPHAMIDE = (
    "ClCCN(CCCl)P1(=O)NCCCO1"  # a legitimate chemotherapeutic: held for review, not banned
)
TNT = "Cc1c([N+](=O)[O-])cc([N+](=O)[O-])cc1[N+](=O)[O-]"
NEAR_MISS = "CCOP(=O)(OCC)Cl"  # phosphoryl chloride: close to the class, not in it


@pytest.mark.parametrize(
    ("smiles", "rule"),
    [
        (DIETHYL_FLUOROPHOSPHATE, "organophosphate_leaving_group"),
        (CYCLOPHOSPHAMIDE, "bis_haloethyl_alkylator"),
        (TNT, "polynitro_energetic"),
    ],
)
def test_each_seed_class_is_caught_with_its_reason(smiles: str, rule: str) -> None:
    hits, _ = screen(smiles)
    assert [h.rule for h in hits] == [rule] and hits[0].why


@pytest.mark.parametrize(
    "smiles", [ASPIRIN, "CC(=O)Nc1ccc(O)cc1", "c1ccccc1N(=O)=O", "OCCN", "", "not smiles"]
)
def test_ordinary_molecules_and_garbage_are_not_hits(smiles: str) -> None:
    assert screen(smiles)[0] == []


def test_near_misses_are_reported_separately_from_hits() -> None:
    hits, near = screen(NEAR_MISS)
    assert hits == [] and near == ["organophosphate_leaving_group"]


async def hits_in_db(pool: Any, user: uuid.UUID) -> dict[str, Any]:
    async with owner(pool) as c:
        return {
            "molecules": (
                await (
                    await c.execute(
                        "SELECT count(*) AS n FROM molecules WHERE user_id = %s", (user,)
                    )
                ).fetchone()
            )["n"],  # type: ignore[index]
            "reviews": [
                dict(r)
                for r in await (
                    await c.execute(
                        "SELECT * FROM review_items WHERE user_id = %s ORDER BY created_at", (user,)
                    )
                ).fetchall()
            ],
            "audit": [
                r["action"]
                for r in await (
                    await c.execute(
                        "SELECT action FROM audit_log WHERE user_id = %s ORDER BY id", (user,)
                    )
                ).fetchall()
            ],
        }


async def test_a_hit_is_blocked_reviewed_audited_and_never_stored_or_shown(pool: Any) -> None:
    user, conv = await make_conv(pool)
    async with scoped(pool, role="a9_worker") as c:
        out = await admit(c, user_id=user, conversation_id=conv, smiles=DIETHYL_FLUOROPHOSPHATE)
    assert not out.admitted and out.review_id and out.rules == ("organophosphate_leaving_group",)
    state = await hits_in_db(pool, user)
    assert state["molecules"] == 0, "a blocked structure never reaches the molecules table"
    (review,) = state["reviews"]
    assert (
        review["status"] == "open"
        and review["rules"] == ["organophosphate_leaving_group"]
        and review["inchikey"]
    )
    assert state["audit"] == ["screening.blocked"]  # visible in the audit log: not a silent drop


async def test_nothing_can_store_a_held_structure_even_if_it_skips_admit(pool: Any) -> None:
    user, conv = await make_conv(pool)
    async with scoped(pool, role="a9_worker") as c:
        with pytest.raises(ScreeningBlockedError, match="organophosphate"):
            await store_candidate(
                c, user_id=user, conversation_id=conv, report=run_gates(DIETHYL_FLUOROPHOSPHATE)
            )
    assert (await hits_in_db(pool, user))["molecules"] == 0


async def test_clean_structures_are_admitted_and_stored_normally(pool: Any) -> None:
    user, conv = await make_conv(pool)
    async with scoped(pool, role="a9_worker") as c:
        out = await admit(c, user_id=user, conversation_id=conv, smiles=ASPIRIN)
        assert out.admitted and out.review_id is None and not out.alert
        assert (
            await store_candidate(c, user_id=user, conversation_id=conv, report=run_gates(ASPIRIN))
            is not None
        )


async def test_repeated_near_misses_on_one_account_raise_an_alert_and_others_are_unaffected(
    pool: Any,
) -> None:
    user, conv = await make_conv(pool)
    other, other_conv = await make_conv(pool)
    alerts = []
    async with scoped(pool, role="a9_worker") as c:
        for _ in range(NEAR_MISS_LIMIT):
            alerts.append(
                (await admit(c, user_id=user, conversation_id=conv, smiles=NEAR_MISS)).alert
            )
        calm = await admit(c, user_id=other, conversation_id=other_conv, smiles=NEAR_MISS)
    assert alerts == [False] * (NEAR_MISS_LIMIT - 1) + [True]
    assert "screening.pattern_alert" in (await hits_in_db(pool, user))["audit"]
    assert calm.admitted and not calm.alert
    assert (await hits_in_db(pool, user))["molecules"] == 0 and (await hits_in_db(pool, user))[
        "reviews"
    ] == []  # near-misses are admitted, just counted


async def test_the_owner_can_see_the_review_item_but_cannot_clear_it(pool: Any) -> None:
    user, conv = await make_conv(pool)
    async with scoped(pool, role="a9_worker") as c:
        out = await admit(c, user_id=user, conversation_id=conv, smiles=TNT)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        rows = await (await c.execute("SELECT status FROM review_items")).fetchall()
        assert [r["status"] for r in rows] == ["open"]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with c.transaction():
                await c.execute(
                    "UPDATE review_items SET status = 'cleared', resolved_by = 'me', resolved_at = now() WHERE id = %s",
                    (out.review_id,),
                )
    stranger, _ = await make_conv(pool)
    async with scoped(pool, role="a9_app", user_id=stranger) as c:
        assert await (await c.execute("SELECT 1 FROM review_items")).fetchall() == []
    with pytest.raises(psycopg.errors.CheckViolation):  # resolving needs a named resolver
        async with scoped(pool, role="a9_worker") as c:
            await c.execute(
                "UPDATE review_items SET status = 'cleared' WHERE id = %s", (out.review_id,)
            )
