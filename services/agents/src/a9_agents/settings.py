"""Environment-driven settings. Read at call time so tests can override the environment."""

from __future__ import annotations

import os


def database_dsn() -> str:
    url = os.environ.get("A9_DATABASE_URL", "postgresql+psycopg://localhost:5544/a9")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def redis_url() -> str:
    return os.environ.get("A9_REDIS_URL", "redis://localhost:6390/0")


def queue_name() -> str:
    return os.environ.get("A9_QUEUE_NAME", "a9:queue")


def job_lease_seconds() -> float:
    """A running job whose heartbeat is older than this can be taken over by another worker."""
    return float(os.environ.get("A9_JOB_LEASE_SECONDS", "30"))


def max_job_attempts() -> int:
    return int(os.environ.get("A9_MAX_JOB_ATTEMPTS", "5"))


def pubsub_channel(run_id: object) -> str:
    return f"a9:run:{run_id}"
