"""Dossier endpoints: assemble a version, sign it off, export it (only after sign-off)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

import psycopg.errors
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from a9_agents.auth import User
from a9_agents.db import Pool, scoped
from a9_agents.dossier import ExportRefusedError, assemble, export, sign_off
from a9_agents.plans import audit

router = APIRouter()


class SignoffIn(BaseModel):
    reviewer_name: str = Field(min_length=1, max_length=200)
    decision: Literal["approved", "rejected"]
    note: str | None = None


@router.post("/conversations/{conversation_id}/dossiers")
async def create_dossier(
    conversation_id: uuid.UUID, request: Request, user: User
) -> dict[str, Any]:
    pool: Pool = request.app.state.pool
    async with scoped(pool, role="a9_app", user_id=user) as conn:
        if (
            await (
                await conn.execute("SELECT 1 FROM conversations WHERE id = %s", (conversation_id,))
            ).fetchone()
            is None
        ):
            raise HTTPException(404, "conversation not found")
        d = await assemble(conn, user_id=user, conversation_id=conversation_id)
        await audit(
            conn,
            user_id=user,
            actor="user",
            action="dossier.created",
            entity_type="dossier",
            entity_id=d["id"],
            detail={"version": d["version"]},
        )
    return {"id": d["id"], "version": d["version"]}


@router.post("/dossiers/{dossier_id}/signoff")
async def post_signoff(
    dossier_id: uuid.UUID, body: SignoffIn, request: Request, user: User
) -> dict[str, str]:
    pool: Pool = request.app.state.pool
    async with scoped(pool, role="a9_app", user_id=user) as conn:
        if (
            await (
                await conn.execute("SELECT 1 FROM dossiers WHERE id = %s", (dossier_id,))
            ).fetchone()
            is None
        ):
            raise HTTPException(404, "dossier not found")
        try:
            sid = await sign_off(
                conn,
                user_id=user,
                dossier_id=dossier_id,
                reviewer_name=body.reviewer_name,
                decision=body.decision,
                note=body.note,
            )
        except psycopg.errors.CheckViolation:
            raise HTTPException(422, "a named reviewer is required") from None
        await audit(
            conn,
            user_id=user,
            actor="user",
            action=f"dossier.{body.decision}",
            entity_type="dossier",
            entity_id=str(dossier_id),
            detail={"reviewer": body.reviewer_name},
        )
    return {"id": str(sid)}


@router.post("/dossiers/{dossier_id}/export")
async def post_export(dossier_id: uuid.UUID, request: Request, user: User) -> dict[str, Any]:
    pool: Pool = request.app.state.pool
    try:
        async with scoped(pool, role="a9_app", user_id=user) as conn:
            if (
                await (
                    await conn.execute("SELECT 1 FROM dossiers WHERE id = %s", (dossier_id,))
                ).fetchone()
                is None
            ):
                raise HTTPException(404, "dossier not found")
            result = await export(conn, user_id=user, dossier_id=dossier_id)
            await audit(
                conn,
                user_id=user,
                actor="user",
                action="dossier.exported",
                entity_type="dossier",
                entity_id=str(dossier_id),
                detail={"version": result["version"]},
            )
            return result
    except ExportRefusedError as exc:
        # Refused exports are themselves recorded, outside the rolled-back transaction.
        async with scoped(pool, role="a9_app", user_id=user) as conn:
            await audit(
                conn,
                user_id=user,
                actor="user",
                action="dossier.export_refused",
                entity_type="dossier",
                entity_id=str(dossier_id),
                detail={},
            )
        raise HTTPException(403, str(exc)) from None
