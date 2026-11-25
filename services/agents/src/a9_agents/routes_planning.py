"""Projects, conversations and the search-plan endpoints.

All reads and writes run as a9_app scoped to the calling user, so row-level security is the backstop
if a handler forgets a filter.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from a9_contracts.search_plan import SearchPlan
from arq.connections import ArqRedis
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from a9_agents.auth import User
from a9_agents.db import Pool, owner, scoped
from a9_agents.plans import (
    PlanConflictError,
    PlanNotFoundError,
    approve,
    audit,
    get_plan,
    latest_plan,
    save_edit,
)
from a9_agents.queue import enqueue
from a9_agents.runs import create_job, create_run

router = APIRouter()


def _pool(request: Request) -> Pool:
    pool: Pool = request.app.state.pool
    return pool


class ProjectIn(BaseModel):
    name: str = Field(min_length=1)


class ConversationIn(BaseModel):
    project_id: uuid.UUID
    title: str | None = None


class PlanRequest(BaseModel):
    topic: str = Field(min_length=1)


class PlanPatch(BaseModel):
    plan: SearchPlan | None = None
    approve: bool = False


@router.post("/projects")
async def create_project(body: ProjectIn, request: Request, user: User) -> dict[str, str]:
    async with scoped(_pool(request), role="a9_app", user_id=user) as conn:
        cur = await conn.execute(
            "INSERT INTO projects (user_id, name) VALUES (%s, %s) RETURNING id", (user, body.name)
        )
        row = await cur.fetchone()
    assert row is not None
    return {"id": str(row["id"])}


@router.post("/conversations")
async def create_conversation(body: ConversationIn, request: Request, user: User) -> dict[str, str]:
    async with scoped(_pool(request), role="a9_app", user_id=user) as conn:
        cur = await conn.execute("SELECT 1 FROM projects WHERE id = %s", (body.project_id,))
        if await cur.fetchone() is None:
            raise HTTPException(404, "project not found")
        cur = await conn.execute(
            "INSERT INTO conversations (user_id, project_id, title) VALUES (%s, %s, %s) RETURNING id",
            (user, body.project_id, body.title),
        )
        row = await cur.fetchone()
    assert row is not None
    return {"id": str(row["id"])}


@router.post("/conversations/{conversation_id}/plan")
async def start_plan(
    conversation_id: uuid.UUID, body: PlanRequest, request: Request, user: User
) -> dict[str, str]:
    """Create a run that builds a search plan and parks for approval."""
    async with scoped(_pool(request), role="a9_app", user_id=user) as conn:
        cur = await conn.execute("SELECT 1 FROM conversations WHERE id = %s", (conversation_id,))
        if await cur.fetchone() is None:
            raise HTTPException(404, "conversation not found")
        run_id = await create_run(
            conn, user_id=user, conversation_id=conversation_id, kind="ingest"
        )
        thread_id = f"run-{run_id}"
        await conn.execute("UPDATE runs SET thread_id = %s WHERE id = %s", (thread_id, run_id))
        key, _ = await create_job(
            conn,
            user_id=user,
            run_id=run_id,
            kind="plan_pipeline",
            payload={
                "conversation_id": str(conversation_id),
                "topic": body.topic,
                "thread_id": thread_id,
            },
        )
    arq: ArqRedis | None = request.app.state.arq
    await enqueue(arq, key)
    return {"run_id": str(run_id)}


@router.get("/conversations/{conversation_id}/plan")
async def latest_conversation_plan(
    conversation_id: uuid.UUID, request: Request, user: User
) -> dict[str, Any]:
    async with scoped(_pool(request), role="a9_app", user_id=user) as conn:
        record = await latest_plan(conn, conversation_id)
    if record is None:
        raise HTTPException(404, "no plan yet")
    return record.to_json()


@router.get("/plans/{plan_id}")
async def read_plan(plan_id: uuid.UUID, request: Request, user: User) -> dict[str, Any]:
    async with scoped(_pool(request), role="a9_app", user_id=user) as conn:
        record = await get_plan(conn, plan_id)
    if record is None:
        raise HTTPException(404, "plan not found")
    return record.to_json()


@router.patch("/plans/{plan_id}")
async def patch_plan(
    plan_id: uuid.UUID, body: PlanPatch, request: Request, user: User
) -> dict[str, Any]:
    """Edit (creates a new version) and/or approve. Approving resumes the parked run."""
    job_key: str | None = None
    try:
        async with scoped(_pool(request), role="a9_app", user_id=user) as conn:
            record = await get_plan(conn, plan_id)
            if record is None:
                raise PlanNotFoundError(str(plan_id))
            if body.plan is not None:
                record = await save_edit(conn, user_id=user, plan_id=plan_id, plan=body.plan)
                await audit(
                    conn, user_id=user, actor="user", action="plan.edited", entity_type="search_plan",
                    entity_id=str(record.id), detail={"version": record.version},
                )  # fmt: skip
            if body.approve:
                record, newly = await approve(conn, user_id=user, plan_id=record.id)
                if newly:
                    await audit(
                        conn, user_id=user, actor="user", action="plan.approved", entity_type="search_plan",
                        entity_id=str(record.id),
                        detail={"version": record.version, "generated_by": record.plan.generated_by.value},
                    )  # fmt: skip
                    cur = await conn.execute(
                        """SELECT id, thread_id FROM runs
                           WHERE conversation_id = %s AND status = 'needs_input' AND thread_id IS NOT NULL
                           ORDER BY created_at DESC LIMIT 1""",
                        (record.conversation_id,),
                    )
                    run = await cur.fetchone()
                    if run is not None:
                        job_key, _ = await create_job(
                            conn, user_id=user, run_id=run["id"], kind="resume_plan",
                            payload={"plan_id": str(record.id), "version": record.version, "thread_id": run["thread_id"]},
                        )  # fmt: skip
    except PlanNotFoundError:
        raise HTTPException(404, "plan not found") from None
    except PlanConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    if job_key is not None:
        await enqueue(request.app.state.arq, job_key)
    return record.to_json()


if os.environ.get("A9_ENABLE_DEV_ENDPOINTS") == "1":

    @router.post("/dev/user")
    async def ensure_dev_user(request: Request, user: User) -> dict[str, str]:
        """Dev only: there is no signup flow yet, so create the calling user on demand."""
        async with owner(_pool(request)) as conn:
            await conn.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user, f"{user}@dev.local"),
            )
        return {"id": str(user)}
