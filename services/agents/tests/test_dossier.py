"""Dossiers are versioned and immutable; export needs an approved sign-off for that exact version."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import psycopg.errors
import pytest
from a9_agents.app import app
from a9_agents.db import owner, scoped
from a9_agents.design.conformal import Prediction
from a9_agents.design.gates import run_gates
from a9_agents.design.registry import register_model, store_candidate, store_score
from a9_agents.dossier import RESEARCH_USE_ONLY, ExportRefusedError, assemble, export, sign_off
from psycopg.types.json import Jsonb
from test_design import ASPIRIN
from test_retrieval import make_conv


async def new_dossier(pool: Any, user: uuid.UUID, conv: uuid.UUID) -> dict[str, Any]:
    async with scoped(pool, role="a9_app", user_id=user) as c:
        return await assemble(c, user_id=user, conversation_id=conv)


async def test_versions_count_up_and_carry_the_whole_chain_with_model_provenance(pool: Any) -> None:
    user, conv = await make_conv(pool)
    async with scoped(pool, role="a9_worker") as c:
        mid = await register_model(
            c,
            name="esol-ridge",
            version=uuid.uuid4().hex[:6],
            endpoint="logS",
            training_data="ESOL",
            calibrated_at=datetime.now(UTC),
            domain_notes="small organics",
        )
        mol = await store_candidate(
            c, user_id=user, conversation_id=conv, report=run_gates(ASPIRIN)
        )
        assert mol is not None
        await store_score(
            c,
            molecule_id=mol,
            user_id=user,
            model_id=mid,
            endpoint="logS",
            prediction=Prediction(-2.0, -3.0, -1.0, 0.9, True, 0.6),
        )
    v1, v2 = await new_dossier(pool, user, conv), await new_dossier(pool, user, conv)
    assert (v1["version"], v2["version"]) == (1, 2)
    content = v2["content"]
    assert (
        content["statement"] == RESEARCH_USE_ONLY
        and "no synthesis procedures" in content["statement"]
    )
    (cand,) = content["candidates"]
    assert cand["inchikey"] == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N" and {
        g["gate"] for g in cand["gates"]
    } >= {"validity", "pains", "synthetic_accessibility"}
    (score,) = cand["scores"]
    assert (
        score["in_domain"] is True
        and score["model"]["training_data"] == "ESOL"
        and score["model"]["name"] == "esol-ridge"
    )
    assert content["corpus"]["counts"]["total"] == 0 and content["plan"] is None


async def test_a_dossier_version_cannot_be_edited(pool: Any) -> None:
    user, conv = await make_conv(pool)
    d = await new_dossier(pool, user, conv)
    for sql, params in (
        ("UPDATE dossiers SET content = %s WHERE id = %s", (Jsonb({"edited": True}), d["id"])),
        ("UPDATE dossiers SET version = 99 WHERE id = %s", (d["id"],)),
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="immutable"):
            async with owner(pool) as c:  # even the table owner
                await c.execute(sql, params)


async def insert_export(pool: Any, user: uuid.UUID, dossier: str, signoff: uuid.UUID) -> None:
    async with owner(pool) as c:
        await c.execute(
            "INSERT INTO exports (dossier_id, user_id, format, signoff_id) VALUES (%s, %s, 'json', %s)",
            (dossier, user, signoff),
        )


async def test_the_database_itself_refuses_an_export_without_an_approved_signoff_for_that_version(
    pool: Any,
) -> None:
    user, conv = await make_conv(pool)
    v1, v2 = await new_dossier(pool, user, conv), await new_dossier(pool, user, conv)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        rejected = await sign_off(
            c,
            user_id=user,
            dossier_id=uuid.UUID(v1["id"]),
            reviewer_name="Dr R",
            decision="rejected",
            note=None,
        )
        approved_v1 = await sign_off(
            c,
            user_id=user,
            dossier_id=uuid.UUID(v1["id"]),
            reviewer_name="Dr R",
            decision="approved",
            note=None,
        )
    with pytest.raises(psycopg.errors.CheckViolation, match="no approved sign-off"):
        await insert_export(pool, user, v1["id"], uuid.uuid4())  # no sign-off at all
    with pytest.raises(psycopg.errors.CheckViolation, match="no approved sign-off"):
        await insert_export(pool, user, v1["id"], rejected)  # a rejection is not an approval
    with pytest.raises(psycopg.errors.CheckViolation, match="no approved sign-off"):
        await insert_export(
            pool, user, v2["id"], approved_v1
        )  # v1's approval says nothing about v2
    await insert_export(pool, user, v1["id"], approved_v1)  # the one valid combination


async def test_export_follows_the_signoff_and_is_per_version(pool: Any) -> None:
    user, conv = await make_conv(pool)
    v1 = await new_dossier(pool, user, conv)
    did = uuid.UUID(v1["id"])
    async with scoped(pool, role="a9_app", user_id=user) as c:
        with pytest.raises(ExportRefusedError):
            await export(c, user_id=user, dossier_id=did)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        await sign_off(
            c,
            user_id=user,
            dossier_id=did,
            reviewer_name="Dr R",
            decision="rejected",
            note="not yet",
        )
        with pytest.raises(ExportRefusedError):
            await export(c, user_id=user, dossier_id=did)  # rejected is not enough
    async with scoped(pool, role="a9_app", user_id=user) as c:
        await sign_off(
            c, user_id=user, dossier_id=did, reviewer_name="Dr R", decision="approved", note=None
        )
        out = await export(c, user_id=user, dossier_id=did)
    assert (
        out["signed_off_by"] == "Dr R"
        and out["statement"] == RESEARCH_USE_ONLY
        and out["version"] == 1
    )
    v2 = await new_dossier(pool, user, conv)  # a later version needs its own review
    async with scoped(pool, role="a9_app", user_id=user) as c:
        with pytest.raises(ExportRefusedError):
            await export(c, user_id=user, dossier_id=uuid.UUID(v2["id"]))


async def test_a_signoff_needs_a_named_human(pool: Any) -> None:
    user, conv = await make_conv(pool)
    d = await new_dossier(pool, user, conv)
    for blank in ("", "   "):
        with pytest.raises(psycopg.errors.CheckViolation):
            async with scoped(pool, role="a9_app", user_id=user) as c:
                await sign_off(
                    c,
                    user_id=user,
                    dossier_id=uuid.UUID(d["id"]),
                    reviewer_name=blank,
                    decision="approved",
                    note=None,
                )


@pytest.fixture()
async def client(pool: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("A9_INTERNAL_KEY", "k")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=30
        ) as c:
            yield c


async def test_the_api_flow_refuses_then_allows_and_audits_every_step(
    client: Any, pool: Any
) -> None:
    user, conv = await make_conv(pool)
    h = {"X-A9-Internal-Key": "k", "X-A9-User-Id": str(user)}
    d = (await client.post(f"/conversations/{conv}/dossiers", headers=h)).json()
    refused = await client.post(f"/dossiers/{d['id']}/export", headers=h)
    assert refused.status_code == 403 and "no approved sign-off" in refused.text
    assert (
        await client.post(
            f"/dossiers/{d['id']}/signoff",
            json={"reviewer_name": "  ", "decision": "approved"},
            headers=h,
        )
    ).status_code == 422
    assert (
        await client.post(
            f"/dossiers/{d['id']}/signoff",
            json={"reviewer_name": "Dr R", "decision": "maybe"},
            headers=h,
        )
    ).status_code == 422
    assert (
        await client.post(
            f"/dossiers/{d['id']}/signoff",
            json={"reviewer_name": "Dr R", "decision": "approved"},
            headers=h,
        )
    ).status_code == 200
    ok = await client.post(f"/dossiers/{d['id']}/export", headers=h)
    assert (
        ok.status_code == 200
        and ok.json()["signed_off_by"] == "Dr R"
        and "Research use only" in ok.json()["statement"]
    )
    stranger = {"X-A9-Internal-Key": "k", "X-A9-User-Id": str((await make_conv(pool))[0])}
    assert (await client.post(f"/dossiers/{d['id']}/export", headers=stranger)).status_code == 404
    async with owner(pool) as c:
        actions = [
            r["action"]
            for r in await (
                await c.execute(
                    "SELECT action FROM audit_log WHERE user_id = %s ORDER BY id", (user,)
                )
            ).fetchall()
        ]
    assert actions == [
        "dossier.created",
        "dossier.export_refused",
        "dossier.approved",
        "dossier.exported",
    ]
