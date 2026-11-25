"""Search plans: versioned, editable until approved, approved by their owner.

Every edit inserts a NEW version; nothing is overwritten, so the history of what the user changed
before the search fired is kept. A plan is editable only while it is the latest version and unapproved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg.errors
from a9_contracts.search_plan import SearchPlan
from psycopg.types.json import Jsonb

from a9_agents.db import Conn


class PlanConflictError(Exception):
    """The plan is stale (not the latest version), already approved, or lost a race."""


class PlanNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class PlanRecord:
    id: uuid.UUID
    conversation_id: uuid.UUID
    version: int
    plan: SearchPlan
    approved_by: uuid.UUID | None
    approved_at: datetime | None

    @property
    def approved(self) -> bool:
        return self.approved_at is not None

    def to_json(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "version": self.version,
            "plan": self.plan.model_dump(mode="json"),
            "approved": self.approved,
            "approved_by": str(self.approved_by) if self.approved_by else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }


_COLUMNS = "id, conversation_id, version, plan, approved_by, approved_at"


def _record(row: dict[str, Any]) -> PlanRecord:
    return PlanRecord(
        id=row["id"],
        conversation_id=row["conversation_id"],
        version=row["version"],
        plan=SearchPlan.model_validate(row["plan"]),
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
    )


async def get_plan(
    conn: Conn, plan_id: uuid.UUID, *, for_update: bool = False
) -> PlanRecord | None:
    lock = " FOR UPDATE" if for_update else ""
    cur = await conn.execute(f"SELECT {_COLUMNS} FROM search_plans WHERE id = %s{lock}", (plan_id,))
    row = await cur.fetchone()
    return _record(row) if row else None


async def latest_plan(conn: Conn, conversation_id: uuid.UUID) -> PlanRecord | None:
    cur = await conn.execute(
        f"SELECT {_COLUMNS} FROM search_plans WHERE conversation_id = %s ORDER BY version DESC LIMIT 1",
        (conversation_id,),
    )
    row = await cur.fetchone()
    return _record(row) if row else None


async def create_next_version(
    conn: Conn, *, user_id: uuid.UUID, conversation_id: uuid.UUID, plan: SearchPlan
) -> PlanRecord:
    """Insert the next version for the conversation (1 if there is none)."""
    current = await latest_plan(conn, conversation_id)
    version = current.version + 1 if current else 1
    try:
        async with (
            conn.transaction()
        ):  # savepoint: a lost race must not poison the caller's transaction
            cur = await conn.execute(
                f"""INSERT INTO search_plans (user_id, conversation_id, version, plan)
                    VALUES (%s, %s, %s, %s) RETURNING {_COLUMNS}""",
                (user_id, conversation_id, version, Jsonb(plan.model_dump(mode="json"))),
            )
            row = await cur.fetchone()
    except psycopg.errors.UniqueViolation:
        raise PlanConflictError("another version was created at the same time") from None
    assert row is not None
    return _record(row)


async def save_edit(
    conn: Conn, *, user_id: uuid.UUID, plan_id: uuid.UUID, plan: SearchPlan
) -> PlanRecord:
    base = await get_plan(conn, plan_id, for_update=True)
    if base is None:
        raise PlanNotFoundError(str(plan_id))
    if base.approved:
        raise PlanConflictError("this plan is already approved and can no longer be edited")
    latest = await latest_plan(conn, base.conversation_id)
    if latest is not None and latest.version != base.version:
        raise PlanConflictError(f"this is version {base.version}; the latest is {latest.version}")
    return await create_next_version(
        conn, user_id=user_id, conversation_id=base.conversation_id, plan=plan
    )


async def approve(conn: Conn, *, user_id: uuid.UUID, plan_id: uuid.UUID) -> tuple[PlanRecord, bool]:
    """Approve the latest version. Returns (record, newly_approved); approving twice is a no-op."""
    base = await get_plan(conn, plan_id, for_update=True)
    if base is None:
        raise PlanNotFoundError(str(plan_id))
    if base.approved:
        return base, False
    latest = await latest_plan(conn, base.conversation_id)
    if latest is not None and latest.version != base.version:
        raise PlanConflictError(f"this is version {base.version}; the latest is {latest.version}")
    cur = await conn.execute(
        f"""UPDATE search_plans SET approved_by = %s, approved_at = now()
            WHERE id = %s RETURNING {_COLUMNS}""",
        (user_id, plan_id),
    )
    row = await cur.fetchone()
    assert row is not None
    return _record(row), True


async def audit(
    conn: Conn,
    *,
    user_id: uuid.UUID | None,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    detail: dict[str, Any] | None = None,
) -> None:
    await conn.execute(
        """INSERT INTO audit_log (user_id, actor, action, entity_type, entity_id, detail)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (user_id, actor, action, entity_type, entity_id, Jsonb(detail or {})),
    )
