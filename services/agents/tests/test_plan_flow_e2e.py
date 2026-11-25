"""M0.5 gate: a user edits a plan, 'closes the tab', reopens from another device, approves, and the
run resumes on the same thread.

Real processes throughout (API, Arq workers, Postgres, Redis). The worker is SIGKILLed while the run is
parked, and the edit and approval happen while NO worker is running: the run must pick up from the
Postgres checkpoint when the next worker starts.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest

KEY = "plan-flow-key"


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


@dataclass
class Flow:
    base: str
    database_url: str
    user: str
    conversation_id: str
    run_id: str
    plan_v1: dict[str, Any]
    plan_v2: dict[str, Any]
    approved: dict[str, Any]
    approved_again: dict[str, Any]
    status_while_no_worker: str
    events_while_no_worker: int
    statuses: dict[str, int] = field(default_factory=dict)

    def headers(self, user: str | None = None) -> dict[str, str]:
        return {"X-A9-Internal-Key": KEY, "X-A9-User-Id": user or self.user}

    def sql(self, query: str, *params: Any) -> list[tuple[Any, ...]]:
        with psycopg.connect(self.database_url) as conn:
            return conn.execute(query, params).fetchall()


@pytest.fixture(scope="module")
def flow(
    migrated_url: str, redis_url_for_tests: str, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Flow]:
    logs: Path = tmp_path_factory.mktemp("planlogs")
    port = _free_port()
    env = {
        **os.environ,
        "A9_DATABASE_URL": migrated_url.replace("postgresql://", "postgresql+psycopg://", 1),
        "A9_REDIS_URL": redis_url_for_tests,
        "A9_QUEUE_NAME": f"a9:test:{uuid.uuid4().hex[:8]}",
        "A9_INTERNAL_KEY": KEY,
        "A9_ENABLE_DEV_ENDPOINTS": "1",
        "A9_MODEL_PROVIDER": "stub",
        "A9_SOURCES": "fixture,fixture_down,fixture_partial",
        "A9_JOB_LEASE_SECONDS": "2",
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
        _until(lambda: _ok(f"{base}/health"), 20, "api to start")

        user = str(uuid.uuid4())
        h = {"X-A9-Internal-Key": KEY, "X-A9-User-Id": user}
        httpx.post(f"{base}/dev/user", headers=h, timeout=10).raise_for_status()
        project = httpx.post(
            f"{base}/projects", json={"name": "EGFR"}, headers=h, timeout=10
        ).json()["id"]
        conv = httpx.post(
            f"{base}/conversations", json={"project_id": project}, headers=h, timeout=10
        ).json()["id"]

        worker1 = spawn("worker1", "arq", "a9_workers.worker.WorkerSettings")
        r = httpx.post(
            f"{base}/conversations/{conv}/plan",
            json={"topic": "EGFR T790M resistance in lung cancer"},
            headers=h,
            timeout=10,
        )
        assert r.status_code == 200, r.text
        run_id = r.json()["run_id"]

        def run_status() -> str:
            return str(
                httpx.get(f"{base}/runs/{run_id}", headers=h, timeout=5).json().get("status")
            )

        _until(lambda: run_status() == "needs_input", 40, "the run to park for approval")

        # The tab is closed and the worker is gone. Everything from here is a different 'device'.
        worker1.send_signal(signal.SIGKILL)
        worker1.wait(timeout=5)

        device_b = httpx.Client(base_url=base, headers=h, timeout=10)
        v1 = device_b.get(f"/conversations/{conv}/plan").json()
        edited = json.loads(json.dumps(v1["plan"]))
        edited["concepts"][0]["synonyms"] = ["ERBB1", "HER1"]
        edited["exclude_criteria"].append("Case reports")
        v2 = device_b.patch(f"/plans/{v1['id']}", json={"plan": edited}).json()
        approved = device_b.patch(f"/plans/{v2['id']}", json={"approve": True}).json()
        approved_again = device_b.patch(f"/plans/{v2['id']}", json={"approve": True}).json()

        time.sleep(1.5)  # no worker: nothing may have happened
        with psycopg.connect(migrated_url) as conn:
            n_events = conn.execute(
                "SELECT count(*) FROM run_events WHERE run_id = %s", (run_id,)
            ).fetchone()
        assert n_events is not None
        status_without_worker = run_status()

        spawn("worker2", "arq", "a9_workers.worker.WorkerSettings")

        def finished() -> bool:
            with psycopg.connect(migrated_url) as conn:
                row = conn.execute(
                    "SELECT 1 FROM run_events WHERE run_id = %s AND type = 'stage_finished'",
                    (run_id,),
                ).fetchone()
            return row is not None

        _until(finished, 40, "the resumed run to finish")

        f = Flow(
            base=base, database_url=migrated_url, user=user, conversation_id=conv, run_id=run_id,
            plan_v1=v1, plan_v2=v2, approved=approved, approved_again=approved_again,
            status_while_no_worker=status_without_worker, events_while_no_worker=int(n_events[0]),
        )  # fmt: skip
        # Error cases, collected once.
        f.statuses["stale_edit"] = device_b.patch(
            f"/plans/{v1['id']}", json={"plan": edited}
        ).status_code
        f.statuses["edit_after_approval"] = device_b.patch(
            f"/plans/{v2['id']}", json={"plan": edited}
        ).status_code
        f.statuses["other_user_reads_plan"] = httpx.get(
            f"{base}/plans/{v2['id']}", headers={**h, "X-A9-User-Id": str(uuid.uuid4())}, timeout=5
        ).status_code
        f.statuses["other_user_approves"] = httpx.patch(
            f"{base}/plans/{v2['id']}",
            json={"approve": True},
            headers={**h, "X-A9-User-Id": str(uuid.uuid4())},
            timeout=5,
        ).status_code
        f.statuses["no_key"] = httpx.get(f"{base}/plans/{v2['id']}", timeout=5).status_code
        yield f
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


def _ok(url: str) -> bool:
    try:
        return httpx.get(url, timeout=1).status_code == 200
    except httpx.HTTPError:
        return False


def test_the_planner_proposes_v1_and_labels_it(flow: Flow) -> None:
    assert flow.plan_v1["version"] == 1 and flow.plan_v1["approved"] is False
    assert flow.plan_v1["plan"]["generated_by"] == "stub"
    assert [c["label"] for c in flow.plan_v1["plan"]["concepts"]][:2] == ["EGFR", "T790M"]


def test_edits_are_a_new_version_and_the_original_is_kept(flow: Flow) -> None:
    assert flow.plan_v2["version"] == 2 and flow.plan_v2["id"] != flow.plan_v1["id"]
    assert flow.plan_v2["plan"]["concepts"][0]["synonyms"] == ["ERBB1", "HER1"]
    rows = flow.sql(
        "SELECT version, approved_by IS NOT NULL FROM search_plans WHERE conversation_id = %s ORDER BY version",
        flow.conversation_id,
    )
    assert rows == [(1, False), (2, True)]


def test_approval_records_who_and_when(flow: Flow) -> None:
    assert flow.approved["approved"] is True and flow.approved["approved_by"] == flow.user
    assert flow.approved["approved_at"] is not None
    assert flow.approved_again == flow.approved  # approving twice changes nothing


def test_the_run_stayed_parked_while_no_worker_was_running(flow: Flow) -> None:
    assert flow.status_while_no_worker == "needs_input"
    assert flow.events_while_no_worker == 3  # stage_started, plan_created, needs_input


def test_the_run_resumed_on_the_same_thread_from_the_checkpoint(flow: Flow) -> None:
    ((status, thread_id),) = flow.sql(
        "SELECT status, thread_id FROM runs WHERE id = %s", flow.run_id
    )
    assert status == "finished"  # a source being down is reduced coverage, not a failed run
    assert thread_id == f"run-{flow.run_id}"
    ((checkpoints,),) = flow.sql("SELECT count(*) FROM checkpoints WHERE thread_id = %s", thread_id)
    assert checkpoints >= 4  # one per graph step, all under the one thread


def test_event_sequence_is_complete_and_names_the_approved_version(flow: Flow) -> None:
    rows = flow.sql("SELECT seq, data FROM run_events WHERE run_id = %s ORDER BY seq", flow.run_id)
    assert [r[0] for r in rows] == list(range(1, 15))
    kinds = [(r[1]["type"], (r[1].get("payload") or {}).get("event")) for r in rows]
    assert kinds[:5] == [
        ("stage_started", None),
        ("partial_result", "plan_created"),
        ("needs_input", None),
        ("partial_result", "plan_approved"),
        ("stage_finished", None),
    ]
    assert rows[2][1]["question"] == {
        "kind": "approve_plan",
        "plan_id": flow.plan_v1["id"],
        "version": 1,
    }
    assert (
        rows[3][1]["payload"]["plan_id"] == flow.plan_v2["id"]
        and rows[3][1]["payload"]["version"] == 2
    )
    assert kinds[5] == ("stage_started", None) and rows[5][1]["stage"] == "search"
    assert sorted(kinds[6:12]) == sorted(
        [("progress", None)] * 3 + [("partial_result", "source_done")] * 3
    )
    assert kinds[12:] == [("stage_finished", None), ("run_finished", None)]
    progress = [r[1]["done"] for r in rows[6:12] if r[1]["type"] == "progress"]
    assert progress == [1, 2, 3] and all(
        r[1]["total"] == 3 for r in rows[6:12] if r[1]["type"] == "progress"
    )


def test_every_source_is_reported_and_a_dead_one_becomes_a_named_note_not_a_failure(
    flow: Flow,
) -> None:
    rows = flow.sql(
        "SELECT data->'payload' FROM run_events WHERE run_id = %s AND data @> %s::jsonb ORDER BY seq",
        flow.run_id, json.dumps({"type": "partial_result", "payload": {"event": "source_done"}}),
    )  # fmt: skip
    by_source = {r[0]["source"]: r[0] for r in rows}
    assert set(by_source) == {"fixture", "fixture_down", "fixture_partial"}
    assert (
        by_source["fixture"]["count"],
        by_source["fixture"]["error"],
        by_source["fixture"]["partial_reason"],
    ) == (3, None, None)
    assert (
        by_source["fixture_down"]["count"] == 0 and "HTTP 503" in by_source["fixture_down"]["error"]
    )
    assert (
        by_source["fixture_partial"]["count"] == 2
        and "stopped early after 2 records" in by_source["fixture_partial"]["partial_reason"]
    )

    ((notes,),) = flow.sql("SELECT coverage_notes FROM runs WHERE id = %s", flow.run_id)
    assert sorted(n["source"] for n in notes) == ["fixture_down", "fixture_partial"]
    assert all(n["reason"] for n in notes)
    ((finished,),) = flow.sql(
        "SELECT data->'coverage_notes' FROM run_events WHERE run_id = %s AND type = 'run_finished'",
        flow.run_id,
    )
    assert finished == notes  # the user sees the same named gaps the run recorded


def test_records_from_surviving_sources_were_staged_for_dedup(flow: Flow) -> None:
    rows = flow.sql(
        "SELECT source, count(*) FROM source_records WHERE run_id = %s GROUP BY source", flow.run_id
    )
    assert rows == [
        ("fixture", 5)
    ]  # fixture and fixture_partial both label records 'fixture'; fixture_down gave none
    ((titles,),) = flow.sql(
        "SELECT count(DISTINCT record->>'title') FROM source_records WHERE run_id = %s", flow.run_id
    )
    # fixture_partial's two records share titles with fixture's first two: duplicates for M0.7 to collapse.
    assert titles == 3


def test_one_resume_job_despite_two_approve_calls(flow: Flow) -> None:
    jobs = flow.sql(
        "SELECT kind, status, attempts FROM jobs WHERE run_id = %s ORDER BY kind", flow.run_id
    )
    assert jobs == [("plan_pipeline", "succeeded", 1), ("resume_plan", "succeeded", 1)]


def test_edits_and_approval_are_audited_once_each(flow: Flow) -> None:
    rows = flow.sql(
        "SELECT action, user_id::text, entity_type FROM audit_log WHERE user_id = %s ORDER BY id",
        flow.user,
    )
    assert rows == [
        ("plan.edited", flow.user, "search_plan"),
        ("plan.approved", flow.user, "search_plan"),
    ]


def test_conflicts_and_isolation(flow: Flow) -> None:
    assert flow.statuses == {
        "stale_edit": 409,
        "edit_after_approval": 409,
        "other_user_reads_plan": 404,
        "other_user_approves": 404,
        "no_key": 401,
    }


def test_the_event_stream_replays_the_whole_story_to_a_late_client(flow: Flow) -> None:
    seqs: list[int] = []
    with httpx.stream(
        "GET", f"{flow.base}/runs/{flow.run_id}/events", headers=flow.headers(), timeout=15
    ) as r:
        for line in r.iter_lines():
            if line.startswith("id:"):
                seqs.append(int(line[3:]))
            if len(seqs) == 5:
                break  # the run has no terminal event yet, so the stream stays open: stop after the backlog
    assert seqs == [1, 2, 3, 4, 5]
