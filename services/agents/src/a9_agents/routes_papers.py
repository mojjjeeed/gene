"""A user's own screening decisions on the papers in a conversation."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from a9_agents.auth import User
from a9_agents.db import Pool, scoped
from a9_agents.plans import audit
from a9_agents.verdicts import clear_user_verdict, paper_verdicts, set_user_verdict

router = APIRouter()


class VerdictIn(BaseModel):
    verdict: Literal["include", "exclude", "unsure"]
    reason: str = "set by user"


async def _require_paper_in_conversation(
    conn: Any, conversation_id: uuid.UUID, paper_id: uuid.UUID
) -> None:
    """Row-level security scopes both tables to the caller, so another user's ids simply do not exist."""
    cur = await conn.execute(
        """SELECT 1 FROM source_records s JOIN runs r ON r.id = s.run_id
           WHERE r.conversation_id = %s AND s.paper_id = %s LIMIT 1""",
        (conversation_id, paper_id),
    )
    if await cur.fetchone() is None:
        raise HTTPException(404, "paper not found in this conversation")


@router.put("/conversations/{conversation_id}/papers/{paper_id}/verdict")
async def override_verdict(
    conversation_id: uuid.UUID, paper_id: uuid.UUID, body: VerdictIn, request: Request, user: User
) -> dict[str, Any]:
    """Override the model's screening verdict. The model's own verdict is kept beside it."""
    pool: Pool = request.app.state.pool
    async with scoped(pool, role="a9_app", user_id=user) as conn:
        await _require_paper_in_conversation(conn, conversation_id, paper_id)
        await set_user_verdict(
            conn,
            user_id=user,
            conversation_id=conversation_id,
            paper_id=paper_id,
            verdict=body.verdict,
            reason=body.reason,
        )
        await audit(
            conn, user_id=user, actor="user", action="verdict.overridden", entity_type="paper", entity_id=str(paper_id),
            detail={"conversation_id": str(conversation_id), "verdict": body.verdict},
        )  # fmt: skip
        return await paper_verdicts(conn, conversation_id, paper_id)


@router.delete("/conversations/{conversation_id}/papers/{paper_id}/verdict")
async def clear_override(
    conversation_id: uuid.UUID, paper_id: uuid.UUID, request: Request, user: User
) -> dict[str, Any]:
    """Withdraw the user's override, so the model's verdict applies again."""
    pool: Pool = request.app.state.pool
    async with scoped(pool, role="a9_app", user_id=user) as conn:
        await _require_paper_in_conversation(conn, conversation_id, paper_id)
        if await clear_user_verdict(conn, conversation_id=conversation_id, paper_id=paper_id):
            await audit(
                conn, user_id=user, actor="user", action="verdict.override_cleared", entity_type="paper",
                entity_id=str(paper_id), detail={"conversation_id": str(conversation_id)},
            )  # fmt: skip
        return await paper_verdicts(conn, conversation_id, paper_id)
