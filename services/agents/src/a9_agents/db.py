"""Connection pool and role/tenant scoping.

Every unit of work runs in one transaction that first drops to a restricted role. For the request
path that is a9_app with app.user_id set, so row-level security applies. Workers use a9_worker.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from a9_agents.settings import database_dsn

Conn = AsyncConnection[Any]
Pool = AsyncConnectionPool[Any]
Role = Literal["a9_app", "a9_worker"]


async def open_pool(*, max_size: int = 10) -> Pool:
    pool: Pool = AsyncConnectionPool(
        database_dsn(),
        min_size=1,
        max_size=max_size,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await pool.open(wait=True, timeout=10)
    return pool


@asynccontextmanager
async def scoped(
    pool: Pool, *, role: Role, user_id: uuid.UUID | None = None
) -> AsyncIterator[Conn]:
    """A transaction running as `role`. With a9_app, `user_id` scopes every query via RLS."""
    async with pool.connection() as conn, conn.transaction():
        await conn.execute(f"SET LOCAL ROLE {role}")  # role is a closed Literal, not user input
        if user_id is not None:
            await conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
        yield conn


@asynccontextmanager
async def owner(pool: Pool) -> AsyncIterator[Conn]:
    """Unrestricted transaction, for dev seeding only. Never use on the request path."""
    async with pool.connection() as conn, conn.transaction():
        yield conn
