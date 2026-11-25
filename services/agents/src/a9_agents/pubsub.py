"""Best-effort live wake-ups over Redis. Postgres stays the source of truth for replay."""

from __future__ import annotations

import logging
import uuid

from redis.asyncio import Redis

from a9_agents.settings import pubsub_channel

log = logging.getLogger(__name__)


async def notify(redis: Redis | None, run_id: uuid.UUID, seq: int) -> None:
    """Tell live listeners a new event exists. Failure only costs latency: listeners also poll."""
    if redis is None:
        return
    try:
        await redis.publish(pubsub_channel(run_id), str(seq))
    except Exception:
        log.warning("redis publish failed for run %s; listeners will poll", run_id, exc_info=True)
