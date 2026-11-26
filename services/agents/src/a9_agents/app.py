"""The agents service. Never exposed to the browser: the Next route handlers authenticate the user
and call this service with an internal key and the user id."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from a9_agents.auth import User
from a9_agents.db import Pool, open_pool, owner, scoped
from a9_agents.events import events_since
from a9_agents.routes_chat import router as chat_router
from a9_agents.routes_papers import router as papers_router
from a9_agents.routes_planning import router as planning_router
from a9_agents.runs import create_job, create_run
from a9_agents.settings import pubsub_channel, queue_name, redis_url

log = logging.getLogger(__name__)

TERMINAL_EVENTS = {"run_finished", "run_failed"}
KEEPALIVE_SECONDS = 15.0
POLL_SECONDS = 1.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.pool = await open_pool()
    app.state.redis = Redis.from_url(redis_url())
    app.state.arq = None
    try:
        app.state.arq = await create_pool(
            RedisSettings.from_dsn(redis_url()), default_queue_name=queue_name()
        )
    except Exception:
        # Degrade, do not fail: queued jobs are picked up by the reaper once Redis is back.
        log.warning(
            "could not connect Arq to Redis; jobs will be enqueued by the reaper", exc_info=True
        )
    try:
        yield
    finally:
        if app.state.arq is not None:
            await app.state.arq.aclose()
        await app.state.redis.aclose()
        await app.state.pool.close()


app = FastAPI(title="A9 agents", lifespan=lifespan)
app.include_router(planning_router)
app.include_router(papers_router)
app.include_router(chat_router)


def _pool(request: Request) -> Pool:
    pool: Pool = request.app.state.pool
    return pool


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, request: Request, user: User) -> dict[str, Any]:
    async with scoped(_pool(request), role="a9_app", user_id=user) as conn:
        cur = await conn.execute(
            "SELECT id, conversation_id, kind, status, last_seq, coverage_notes FROM runs WHERE id = %s",
            (run_id,),
        )
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "run not found")
    return {**row, "id": str(row["id"]), "conversation_id": str(row["conversation_id"])}


def _sse(event: dict[str, Any]) -> bytes:
    # No `event:` line, so a browser EventSource delivers every type through onmessage.
    return f"id: {event['seq']}\ndata: {json.dumps(event, separators=(',', ':'))}\n\n".encode()


@app.get("/runs/{run_id}/events")
async def stream_events(
    run_id: uuid.UUID,
    request: Request,
    user: User,
    last_event_id: Annotated[str | None, Header()] = None,
    after: Annotated[int | None, Query(ge=0)] = None,
) -> StreamingResponse:
    """Server-sent events for one run. Replays everything after Last-Event-ID, then follows live."""
    pool: Pool = _pool(request)
    redis: Redis = request.app.state.redis
    try:
        last = int(last_event_id) if last_event_id else (after or 0)
    except ValueError:
        raise HTTPException(400, "Last-Event-ID must be an integer") from None

    async with scoped(pool, role="a9_app", user_id=user) as conn:
        cur = await conn.execute("SELECT 1 FROM runs WHERE id = %s", (run_id,))
        if await cur.fetchone() is None:
            raise HTTPException(404, "run not found")

    async def body() -> AsyncIterator[bytes]:
        nonlocal last
        sub = redis.pubsub()
        try:
            await sub.subscribe(pubsub_channel(run_id))
        except Exception:
            log.warning("redis subscribe failed; falling back to polling", exc_info=True)
        last_write = time.monotonic()
        try:
            while True:
                # Read after subscribing, so nothing published in between is missed.
                async with scoped(pool, role="a9_app", user_id=user) as conn:
                    events = await events_since(conn, run_id, last)
                    cur = await conn.execute("SELECT status FROM runs WHERE id = %s", (run_id,))
                    status_row = await cur.fetchone()
                for event in events:
                    yield _sse(event)
                    last = event["seq"]
                    last_write = time.monotonic()
                    if event["type"] in TERMINAL_EVENTS:
                        return
                if events:
                    continue
                if status_row is None or status_row["status"] in ("failed", "finished"):
                    return
                if time.monotonic() - last_write > KEEPALIVE_SECONDS:
                    yield b": keepalive\n\n"
                    last_write = time.monotonic()
                try:
                    await sub.get_message(ignore_subscribe_messages=True, timeout=POLL_SECONDS)
                except Exception:
                    await asyncio.sleep(POLL_SECONDS)
        finally:
            try:
                await sub.aclose()  # type: ignore[no-untyped-call]
            except Exception:
                pass

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


# --- dev-only: start the dummy ten-step job ---------------------------------------------------


class DummyRunRequest(BaseModel):
    steps: int = Field(10, ge=1, le=100)
    step_delay: float = Field(0.5, ge=0, le=10)


if os.environ.get("A9_ENABLE_DEV_ENDPOINTS") == "1":

    @app.post("/dev/dummy-run")
    async def dummy_run(body: DummyRunRequest, request: Request, user: User) -> dict[str, str]:
        pool = _pool(request)
        async with owner(pool) as conn:  # dev only: there is no signup flow yet
            await conn.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user, f"{user}@dev.local"),
            )
        async with scoped(pool, role="a9_app", user_id=user) as conn:
            cur = await conn.execute(
                "INSERT INTO projects (user_id, name) VALUES (%s, 'dev') RETURNING id", (user,)
            )
            project = await cur.fetchone()
            assert project is not None
            cur = await conn.execute(
                "INSERT INTO conversations (user_id, project_id) VALUES (%s, %s) RETURNING id",
                (user, project["id"]),
            )
            conversation = await cur.fetchone()
            assert conversation is not None
            run_id = await create_run(
                conn, user_id=user, conversation_id=conversation["id"], kind="ingest"
            )
            key, _ = await create_job(
                conn,
                user_id=user,
                run_id=run_id,
                kind="dummy_pipeline",
                payload={"steps": body.steps, "step_delay": body.step_delay},
            )
        arq: ArqRedis | None = request.app.state.arq
        if arq is not None:
            try:
                await arq.enqueue_job("run_job", key, _job_id=key)
            except Exception:
                log.warning("enqueue failed for %s; the reaper will pick it up", key, exc_info=True)
        return {"run_id": str(run_id), "job_key": key}
