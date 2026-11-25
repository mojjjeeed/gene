"""M0.3 gate, end to end over real processes:

a dummy ten-step job streams to a client, survives a worker being SIGKILLed mid-run, and replays the
backlog after a reconnect instead of showing a spinner. Postgres, Redis, the FastAPI service and two
Arq workers are all real.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest

KEY = "test-internal-key"
STEPS = 10
LEASE = 2


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _until(predicate: Any, timeout: float, what: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(f"timed out after {timeout}s waiting for {what}")


def parse_sse(lines: Iterator[str]) -> Iterator[dict[str, Any]]:
    """Yield one dict per SSE message that carries data; comments (keepalives) are skipped."""
    event_id: str | None = None
    data: list[str] = []
    for line in lines:
        if line == "":
            if data:
                payload = json.loads("\n".join(data))
                assert str(payload["seq"]) == event_id, "SSE id must equal the event's seq"
                yield payload
            event_id, data = None, []
        elif line.startswith("id:"):
            event_id = line[3:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())


@dataclass
class Scenario:
    base: str
    user: str
    run_id: str
    live: list[dict[str, Any]] = field(default_factory=list)
    count_when_killed: int = 0
    count_after_lease: int = 0
    database_url: str = ""
    env: dict[str, str] = field(default_factory=dict)

    def headers(self, user: str | None = None, key: str = KEY) -> dict[str, str]:
        return {"X-A9-Internal-Key": key, "X-A9-User-Id": user or self.user}


@pytest.fixture(scope="module")
def scenario(
    migrated_url: str, redis_url_for_tests: str, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Scenario]:
    logs: Path = tmp_path_factory.mktemp("logs")
    port = _free_port()
    env = {
        **os.environ,
        "A9_DATABASE_URL": migrated_url.replace("postgresql://", "postgresql+psycopg://", 1),
        "A9_REDIS_URL": redis_url_for_tests,
        "A9_QUEUE_NAME": f"a9:test:{uuid.uuid4().hex[:8]}",
        "A9_INTERNAL_KEY": KEY,
        "A9_ENABLE_DEV_ENDPOINTS": "1",
        "A9_JOB_LEASE_SECONDS": str(LEASE),
        "A9_REAP_INTERVAL_SECONDS": "1",
    }
    procs: list[subprocess.Popen[bytes]] = []

    def spawn(name: str, *args: str) -> subprocess.Popen[bytes]:
        p = subprocess.Popen(
            [sys.executable, "-m", *args],
            env=env,
            stdout=open(logs / f"{name}.log", "wb"),
            stderr=subprocess.STDOUT,
        )
        procs.append(p)
        return p

    try:
        spawn("api", "uvicorn", "a9_agents.app:app", "--port", str(port), "--log-level", "warning")
        base = f"http://127.0.0.1:{port}"

        def api_up() -> bool:
            try:
                return httpx.get(f"{base}/health", timeout=1).status_code == 200
            except httpx.HTTPError:
                return False

        _until(api_up, 20, "api to start")
        worker1 = spawn("worker1", "arq", "a9_workers.worker.WorkerSettings")

        user = str(uuid.uuid4())
        r = httpx.post(
            f"{base}/dev/dummy-run",
            json={"steps": STEPS, "step_delay": 0.4},
            headers={"X-A9-Internal-Key": KEY, "X-A9-User-Id": user},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        sc = Scenario(
            base=base, user=user, run_id=r.json()["run_id"], database_url=migrated_url, env=env
        )

        def follow_live() -> None:
            with httpx.stream(
                "GET", f"{base}/runs/{sc.run_id}/events", headers=sc.headers(), timeout=None
            ) as resp:
                for event in parse_sse(resp.iter_lines()):
                    sc.live.append(event)

        client = threading.Thread(target=follow_live, daemon=True)
        client.start()

        _until(lambda: len(sc.live) >= 4, 20, "4 live events before the kill")
        worker1.send_signal(signal.SIGKILL)  # no cleanup, no goodbye
        worker1.wait(timeout=5)
        time.sleep(0.3)
        sc.count_when_killed = len(sc.live)
        assert sc.count_when_killed < STEPS + 3, "run finished before the kill; test is meaningless"

        time.sleep(LEASE + 0.5)  # lease expires; nobody is working
        sc.count_after_lease = len(sc.live)

        spawn("worker2", "arq", "a9_workers.worker.WorkerSettings")
        client.join(timeout=40)
        assert not client.is_alive(), f"stream never closed; live events: {len(sc.live)}"
        yield sc
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


def test_stream_delivers_every_event_exactly_once_across_a_worker_kill(scenario: Scenario) -> None:
    seqs = [e["seq"] for e in scenario.live]
    assert seqs == list(range(1, STEPS + 4)), seqs  # gapless, monotonic, no duplicates
    types = [e["type"] for e in scenario.live]
    assert types[0] == "stage_started"
    assert types[1 : 1 + STEPS] == ["progress"] * STEPS
    assert types[-2:] == ["stage_finished", "run_finished"]
    assert [e["done"] for e in scenario.live if e["type"] == "progress"] == list(
        range(1, STEPS + 1)
    )
    assert all(e["run_id"] == scenario.run_id for e in scenario.live)


def test_nothing_progressed_while_no_worker_held_the_job(scenario: Scenario) -> None:
    assert scenario.count_after_lease == scenario.count_when_killed


def test_the_job_was_taken_over_not_duplicated(scenario: Scenario) -> None:
    import psycopg

    with psycopg.connect(scenario.database_url) as conn:
        jobs = conn.execute(
            "SELECT status, attempts FROM jobs WHERE run_id = %s", (scenario.run_id,)
        ).fetchall()
        run = conn.execute(
            "SELECT status, last_seq FROM runs WHERE id = %s", (scenario.run_id,)
        ).fetchone()
    assert jobs == [("succeeded", 2)]  # attempt 1 was killed, attempt 2 finished it
    assert run == ("finished", STEPS + 3)


def test_reconnect_replays_the_backlog_after_last_event_id(scenario: Scenario) -> None:
    with httpx.stream(
        "GET",
        f"{scenario.base}/runs/{scenario.run_id}/events",
        headers={**scenario.headers(), "Last-Event-ID": "5"},
        timeout=10,
    ) as resp:
        replay = list(parse_sse(resp.iter_lines()))
    assert [e["seq"] for e in replay] == list(range(6, STEPS + 4))
    assert replay == scenario.live[5:]  # byte-for-byte the same events


def test_fresh_connect_replays_everything_and_a_caught_up_client_gets_nothing(
    scenario: Scenario,
) -> None:
    def fetch(last: str | None) -> list[dict[str, Any]]:
        headers = scenario.headers() | ({"Last-Event-ID": last} if last else {})
        with httpx.stream(
            "GET", f"{scenario.base}/runs/{scenario.run_id}/events", headers=headers, timeout=10
        ) as r:
            return list(parse_sse(r.iter_lines()))

    assert fetch(None) == scenario.live
    assert fetch(str(STEPS + 3)) == []


def test_other_users_and_bad_keys_cannot_read_the_stream(scenario: Scenario) -> None:
    url = f"{scenario.base}/runs/{scenario.run_id}/events"
    assert (
        httpx.get(url, headers=scenario.headers(user=str(uuid.uuid4())), timeout=5).status_code
        == 404
    )
    assert httpx.get(url, headers=scenario.headers(key="wrong"), timeout=5).status_code == 401
    assert httpx.get(url, headers={"X-A9-Internal-Key": KEY}, timeout=5).status_code == 401
    assert (
        httpx.get(
            f"{scenario.base}/runs/{scenario.run_id}", headers=scenario.headers(), timeout=5
        ).json()["status"]
        == "finished"
    )


def test_running_the_finished_job_again_is_a_no_op(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    from a9_agents.db import open_pool
    from a9_workers.worker import run_job
    from redis.asyncio import Redis

    for k, v in scenario.env.items():
        monkeypatch.setenv(k, v)

    async def again() -> str:
        import psycopg

        with psycopg.connect(scenario.database_url) as conn:
            key = conn.execute(
                "SELECT job_key FROM jobs WHERE run_id = %s", (scenario.run_id,)
            ).fetchone()
        assert key is not None
        pool = await open_pool(max_size=2)
        redis = Redis.from_url(scenario.env["A9_REDIS_URL"])
        try:
            return await run_job({"pool": pool, "pubsub_redis": redis}, key[0])
        finally:
            await redis.aclose()
            await pool.close()

    assert asyncio.run(again()) == "skipped"
    r = httpx.get(f"{scenario.base}/runs/{scenario.run_id}", headers=scenario.headers(), timeout=5)
    assert r.json()["last_seq"] == STEPS + 3  # no new events
