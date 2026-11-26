"""M4.4: a user may have at most N jobs running at once; the rest wait, and other users are unaffected."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from a9_agents.db import owner
from a9_workers.leases import claim
from test_retrieval import make_conv


async def queue_jobs(pool: Any, user: uuid.UUID, conv: uuid.UUID, n: int) -> list[str]:
    keys = []
    async with owner(pool) as c:
        for _ in range(n):
            run = uuid.uuid4()
            await c.execute(
                "INSERT INTO runs (id, user_id, conversation_id, kind) VALUES (%s, %s, %s, 'ingest')",
                (run, user, conv),
            )
            key = f"cap:{uuid.uuid4().hex}"
            await c.execute(
                "INSERT INTO jobs (user_id, run_id, job_key, kind) VALUES (%s, %s, %s, 'dummy_pipeline')",
                (user, run, key),
            )
            keys.append(key)
    return keys


async def test_a_users_running_jobs_are_capped_and_the_rest_wait(
    pool: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("A9_MAX_CONCURRENT_RUNS", "3")
    user, conv = await make_conv(pool)
    other, other_conv = await make_conv(pool)
    keys, theirs = (
        await queue_jobs(pool, user, conv, 5),
        await queue_jobs(pool, other, other_conv, 1),
    )
    got = [await claim(pool, k) for k in keys]
    assert [j is not None for j in got] == [
        True,
        True,
        True,
        False,
        False,
    ]  # the 4th and 5th stay queued
    assert await claim(pool, theirs[0]) is not None  # another user is not held up
    async with owner(pool) as c:
        await c.execute("UPDATE jobs SET status = 'succeeded' WHERE job_key = %s", (keys[0],))
    assert await claim(pool, keys[3]) is not None  # a slot freed up
    assert await claim(pool, keys[4]) is None  # but only one
    assert await claim(pool, keys[3]) is None  # and a job already running is not claimed twice


async def test_a_crashed_jobs_slot_is_released_once_its_lease_expires(
    pool: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("A9_MAX_CONCURRENT_RUNS", "1")
    monkeypatch.setenv("A9_JOB_LEASE_SECONDS", "2")
    user, conv = await make_conv(pool)
    first, second = await queue_jobs(pool, user, conv, 2)
    assert await claim(pool, first) is not None
    assert await claim(pool, second) is None  # the one slot is taken by a live job
    async with owner(pool) as c:  # the first worker dies: its heartbeat goes stale
        await c.execute(
            "UPDATE jobs SET heartbeat_at = now() - interval '1 minute' WHERE job_key = %s",
            (first,),
        )
    assert await claim(pool, second) is not None  # a dead job must not hold a user's slot forever
