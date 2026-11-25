"""Plan versioning, approval and isolation, against the real schema and row-level security."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from a9_agents.db import owner, scoped
from a9_agents.planner import StubPlanner
from a9_agents.plans import (
    PlanConflictError,
    approve,
    create_next_version,
    get_plan,
    latest_plan,
    save_edit,
)
from a9_contracts.search_plan import SearchPlan


async def _one(c: Any, sql: str, *params: object) -> Any:
    row = await (await c.execute(sql, params)).fetchone()
    assert row is not None
    return row["id"]


async def seed(pool: Any) -> tuple[uuid.UUID, uuid.UUID]:
    user = uuid.uuid4()
    async with owner(pool) as c:
        await c.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user, f"{user}@x.org"))
    async with scoped(pool, role="a9_app", user_id=user) as c:
        project = await _one(
            c, "INSERT INTO projects (user_id, name) VALUES (%s, 'p') RETURNING id", user
        )
        conv = await _one(
            c,
            "INSERT INTO conversations (user_id, project_id) VALUES (%s, %s) RETURNING id",
            user,
            project,
        )
    return user, conv


async def a_plan(topic: str = "EGFR resistance") -> SearchPlan:
    return await StubPlanner(today=date(2026, 1, 1)).plan(topic)


async def test_versions_count_up_and_history_is_kept(pool: Any) -> None:
    user, conv = await seed(pool)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        v1 = await create_next_version(c, user_id=user, conversation_id=conv, plan=await a_plan())
        edited = v1.plan.model_copy(deep=True)
        edited.concepts[0].synonyms = ["ERBB1"]
        v2 = await save_edit(c, user_id=user, plan_id=v1.id, plan=edited)
    assert (v1.version, v2.version) == (1, 2)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        assert (await get_plan(c, v1.id)).plan.concepts[0].synonyms == []  # type: ignore[union-attr]
        assert (await latest_plan(c, conv)).id == v2.id  # type: ignore[union-attr]


async def test_approval_records_who_and_when_and_is_idempotent(pool: Any) -> None:
    user, conv = await seed(pool)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        v1 = await create_next_version(c, user_id=user, conversation_id=conv, plan=await a_plan())
        assert not v1.approved and v1.approved_by is None
        rec, newly = await approve(c, user_id=user, plan_id=v1.id)
        again, newly_again = await approve(c, user_id=user, plan_id=v1.id)
    assert (newly, newly_again) == (True, False)
    assert rec.approved_by == user and rec.approved_at is not None
    assert again.approved_at == rec.approved_at  # the second call did not move the timestamp


async def test_cannot_edit_an_approved_plan_or_a_stale_one(pool: Any) -> None:
    user, conv = await seed(pool)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        v1 = await create_next_version(c, user_id=user, conversation_id=conv, plan=await a_plan())
        v2 = await save_edit(c, user_id=user, plan_id=v1.id, plan=v1.plan)
        with pytest.raises(PlanConflictError, match="latest is 2"):
            await save_edit(c, user_id=user, plan_id=v1.id, plan=v1.plan)  # stale base
        with pytest.raises(PlanConflictError, match="latest is 2"):
            await approve(c, user_id=user, plan_id=v1.id)  # stale approval
        await approve(c, user_id=user, plan_id=v2.id)
        with pytest.raises(PlanConflictError, match="already approved"):
            await save_edit(c, user_id=user, plan_id=v2.id, plan=v2.plan)


async def test_another_user_cannot_see_or_approve_a_plan(pool: Any) -> None:
    owner_id, conv = await seed(pool)
    other, _ = await seed(pool)
    async with scoped(pool, role="a9_app", user_id=owner_id) as c:
        v1 = await create_next_version(
            c, user_id=owner_id, conversation_id=conv, plan=await a_plan()
        )
    async with scoped(pool, role="a9_app", user_id=other) as c:
        assert await get_plan(c, v1.id) is None
        assert await latest_plan(c, conv) is None


async def test_the_database_refuses_approval_by_someone_else(pool: Any) -> None:
    import psycopg.errors

    user, conv = await seed(pool)
    other, _ = await seed(pool)
    async with scoped(pool, role="a9_app", user_id=user) as c:
        v1 = await create_next_version(c, user_id=user, conversation_id=conv, plan=await a_plan())
    with pytest.raises(psycopg.errors.CheckViolation):
        async with owner(pool) as c:  # even bypassing RLS, approved_by must be the plan's owner
            await c.execute(
                "UPDATE search_plans SET approved_by = %s, approved_at = now() WHERE id = %s",
                (other, v1.id),
            )
