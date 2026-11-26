"""Database fixtures: each test session gets a fresh, fully migrated database.

Tests need a Postgres server (`make db-up` locally, a service container in CI). If none is
reachable they skip locally; with A9_REQUIRE_DB=1 (set in CI) they fail instead, so an outage
can never turn into a green run.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import Connection
from psycopg.rows import TupleRow

AGENTS_DIR = Path(__file__).resolve().parents[1]
ADMIN_URL = os.environ.get("A9_PG_ADMIN_URL", "postgresql://localhost:5544/postgres")

DbConn = Connection[TupleRow]


def _admin() -> DbConn:
    try:
        return psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        if os.environ.get("A9_REQUIRE_DB") == "1":
            pytest.fail(f"Postgres required but unreachable at {ADMIN_URL}: {exc}")
        pytest.skip(f"Postgres not reachable at {ADMIN_URL} (run `make db-up`)")


def _alembic(url: str) -> Config:
    cfg = Config(str(AGENTS_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url.replace("postgresql://", "postgresql+psycopg://", 1))
    return cfg


@pytest.fixture(scope="session")
def make_database() -> Iterator[Callable[[], str]]:
    """Factory for empty scratch databases. All are dropped at the end of the session."""
    created: list[str] = []

    def _make() -> str:
        name = f"a9_test_{uuid.uuid4().hex[:10]}"
        with _admin() as admin:
            admin.execute(f'CREATE DATABASE "{name}"')
        created.append(name)
        return ADMIN_URL.rsplit("/", 1)[0] + "/" + name

    yield _make

    with _admin() as admin:
        for name in created:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def alembic_config_for() -> Callable[[str], Config]:
    return _alembic


@pytest.fixture(scope="session")
def migrated_url(make_database: Callable[[], str]) -> str:
    url = make_database()
    command.upgrade(_alembic(url), "head")
    return url


@pytest.fixture()
def db(migrated_url: str) -> Iterator[DbConn]:
    """A superuser connection inside a transaction that is rolled back after the test."""
    with psycopg.connect(migrated_url) as conn:
        yield conn
        conn.rollback()


@contextmanager
def as_user(conn: DbConn, user_id: uuid.UUID | None, role: str = "a9_app") -> Iterator[DbConn]:
    """Run statements as the app role with RLS scoped to `user_id` (None = no user set)."""
    conn.execute(f"SET LOCAL ROLE {role}")
    if user_id is not None:
        conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
    try:
        yield conn
    finally:
        conn.execute("RESET ROLE")
        conn.execute("RESET app.user_id")


# --- seeding helpers (run as the superuser connection, so RLS is bypassed) --------------------


def seed_user(conn: DbConn, email: str | None = None) -> uuid.UUID:
    row = conn.execute(
        "INSERT INTO users (email) VALUES (%s) RETURNING id",
        (email or f"{uuid.uuid4().hex[:8]}@example.org",),
    ).fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


def seed_conversation(conn: DbConn, user_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (project_id, conversation_id)."""
    project = conn.execute(
        "INSERT INTO projects (user_id, name) VALUES (%s, 'p') RETURNING id", (user_id,)
    ).fetchone()
    assert project is not None
    conv = conn.execute(
        "INSERT INTO conversations (user_id, project_id) VALUES (%s, %s) RETURNING id",
        (user_id, project[0]),
    ).fetchone()
    assert conv is not None
    return uuid.UUID(str(project[0])), uuid.UUID(str(conv[0]))


def seed_paper(
    conn: DbConn, *, licence: str | None = "CC-BY-4.0", full_text_allowed: bool = True
) -> uuid.UUID:
    row = conn.execute(
        """INSERT INTO papers (title, source, licence, full_text_allowed)
           VALUES ('A paper', 'europe_pmc', %s, %s) RETURNING id""",
        (licence, full_text_allowed),
    ).fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


@pytest.fixture(scope="session")
def redis_url_for_tests() -> str:
    """Redis for worker/stream tests. Same skip-or-fail rule as Postgres."""
    import redis as redis_sync

    url = os.environ.get("A9_REDIS_URL", "redis://localhost:6390/0")
    try:
        redis_sync.Redis.from_url(url, socket_connect_timeout=2).ping()
    except redis_sync.RedisError as exc:
        if os.environ.get("A9_REQUIRE_DB") == "1":
            pytest.fail(f"Redis required but unreachable at {url}: {exc}")
        pytest.skip(f"Redis not reachable at {url} (run `make redis-up`)")
    return url


@pytest.fixture()
async def pool(migrated_url: str, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Any]:
    """An app connection pool on the migrated test database (committed writes, unique ids per test)."""
    from a9_agents.db import open_pool

    monkeypatch.setenv(
        "A9_DATABASE_URL", migrated_url.replace("postgresql://", "postgresql+psycopg://", 1)
    )
    p = await open_pool(max_size=3)
    yield p
    await p.close()


@pytest.fixture(scope="session")
def embedder() -> Any:
    from a9_agents.index.embed import FastEmbedDense

    return FastEmbedDense()


@pytest.fixture(scope="session")
def reranker() -> Any:
    from a9_agents.index.embed import FastEmbedReranker

    return FastEmbedReranker()


@pytest.fixture()
def qdrant(embedder: Any) -> Any:
    from a9_agents.index.conversation_index import ensure_collections, make_client

    client = make_client(memory=True)
    ensure_collections(client, embedder.dims)
    return client
