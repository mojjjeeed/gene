"""The ingest graph so far: plan -> request approval -> (interrupt) -> finish plan -> search -> conclude.

State lives in LangGraph's Postgres checkpointer, keyed by the run's thread id, so the run parks at
the interrupt and any later request, from any device, can resume the same thread. Nodes are idempotent
per run (checked against run_events), so a worker that dies mid-node and is replaced cannot emit
duplicate events or create a second plan.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from redis.asyncio import Redis

from a9_agents.db import Conn, Pool, scoped
from a9_agents.embedder import Embedder
from a9_agents.events import emit_event
from a9_agents.identity import RETRACTION_RANK, cluster_records, to_draft
from a9_agents.papers import lock_papers, record_retraction, upsert_paper
from a9_agents.planner import Planner
from a9_agents.plans import create_next_version, get_plan
from a9_agents.pubsub import notify
from a9_agents.retractions import RetractionChecker, RetractionResult
from a9_agents.sources.base import LiteratureSource, SourceError
from a9_agents.sources.fanout import SourceReport, search_all
from a9_agents.triage import TriageInput, Triager
from a9_agents.verdicts import run_counts, save_model_verdict

STAGE = "plan"
SEARCH = "search"
RESOLVE = "resolve"
RETRACTIONS = "retractions"
TRIAGE = "triage"
TRIAGE_BATCH = 5
RETRACTION_RECHECK_DAYS = 7


class PlanState(TypedDict, total=False):
    run_id: str
    user_id: str
    conversation_id: str
    topic: str
    plan_id: str
    version: int
    approved_plan_id: str
    approved_version: int


async def _marker(conn: Conn, run_id: uuid.UUID, contains: dict[str, Any]) -> dict[str, Any] | None:
    from psycopg.types.json import Jsonb

    cur = await conn.execute(
        "SELECT data FROM run_events WHERE run_id = %s AND data @> %s ORDER BY seq LIMIT 1",
        (run_id, Jsonb(contains)),
    )
    row = await cur.fetchone()
    return None if row is None else dict(row["data"])


async def _source_events(conn: Conn, run_id: uuid.UUID) -> list[dict[str, Any]]:
    from psycopg.types.json import Jsonb

    cur = await conn.execute(
        "SELECT data FROM run_events WHERE run_id = %s AND data @> %s ORDER BY seq",
        (run_id, Jsonb({"type": "partial_result", "payload": {"event": "source_done"}})),
    )
    return [dict(r["data"]) for r in await cur.fetchall()]


def build_plan_graph(
    *,
    pool: Pool,
    redis: Redis | None,
    planner: Planner,
    sources: Sequence[LiteratureSource] = (),
    source_limit: int = 100,
    source_timeout: float = 120.0,
    embedder: Embedder | None = None,
    similarity_threshold: float = 0.80,
    retraction_checker: RetractionChecker | None = None,
    triager: Triager | None = None,
) -> StateGraph[PlanState]:
    async def plan(state: PlanState) -> PlanState:
        run_id, user_id = uuid.UUID(state["run_id"]), uuid.UUID(state["user_id"])
        conversation_id = uuid.UUID(state["conversation_id"])
        async with scoped(pool, role="a9_worker") as conn:
            done = await _marker(
                conn, run_id, {"type": "partial_result", "payload": {"event": "plan_created"}}
            )
        if done is not None:  # this run already created its plan; never call the model twice
            return {"plan_id": done["payload"]["plan_id"], "version": done["payload"]["version"]}

        proposed = await planner.plan(state["topic"])
        async with scoped(pool, role="a9_worker") as conn:
            record = await create_next_version(
                conn, user_id=user_id, conversation_id=conversation_id, plan=proposed
            )
            await emit_event(conn, run_id, {"type": "stage_started", "stage": STAGE})
            last = await emit_event(
                conn,
                run_id,
                {
                    "type": "partial_result",
                    "stage": STAGE,
                    "payload": {
                        "event": "plan_created",
                        "plan_id": str(record.id),
                        "version": record.version,
                        "generated_by": proposed.generated_by.value,
                    },
                },
            )
        await notify(redis, run_id, last["seq"])
        return {"plan_id": str(record.id), "version": record.version}

    async def request_approval(state: PlanState) -> PlanState:
        run_id = uuid.UUID(state["run_id"])
        question = {
            "kind": "approve_plan",
            "plan_id": state["plan_id"],
            "version": state["version"],
        }
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(
                conn, run_id, {"type": "needs_input", "question": {"plan_id": state["plan_id"]}}
            ):
                return {}
            event = await emit_event(
                conn, run_id, {"type": "needs_input", "stage": STAGE, "question": question}
            )
        await notify(redis, run_id, event["seq"])
        return {}

    async def wait_for_approval(state: PlanState) -> PlanState:
        # Parks the run. The resume value is whatever the approval job passes back in.
        answer = interrupt({"kind": "approve_plan", "plan_id": state["plan_id"]})
        return {"approved_plan_id": answer["plan_id"], "approved_version": answer["version"]}

    async def finish_plan(state: PlanState) -> PlanState:
        run_id = uuid.UUID(state["run_id"])
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": STAGE}):
                return {}
            await emit_event(
                conn,
                run_id,
                {
                    "type": "partial_result",
                    "stage": STAGE,
                    "payload": {
                        "event": "plan_approved",
                        "plan_id": state["approved_plan_id"],
                        "version": state["approved_version"],
                    },
                },
            )
            event = await emit_event(conn, run_id, {"type": "stage_finished", "stage": STAGE})
        await notify(redis, run_id, event["seq"])
        return {}

    async def search(state: PlanState) -> PlanState:
        """Query every source at once; each result is staged and reported as it lands."""
        from psycopg.types.json import Jsonb

        run_id, user_id = uuid.UUID(state["run_id"]), uuid.UUID(state["user_id"])
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": SEARCH}):
                return {}
            record = await get_plan(conn, uuid.UUID(state["approved_plan_id"]))
            assert record is not None, "the approved plan disappeared"
            if not await _marker(conn, run_id, {"type": "stage_started", "stage": SEARCH}):
                event = await emit_event(conn, run_id, {"type": "stage_started", "stage": SEARCH})
                await notify(redis, run_id, event["seq"])
            done = {e["payload"]["source"] for e in await _source_events(conn, run_id)}

        pending = [s for s in sources if s.name not in done]
        finished = len(done)

        async def on_source_done(report: SourceReport, records: list[Any]) -> None:
            nonlocal finished
            async with scoped(pool, role="a9_worker") as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """INSERT INTO source_records (run_id, user_id, source, source_id, record)
                           VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                        [
                            (
                                run_id,
                                user_id,
                                r.source.value,
                                r.source_id,
                                Jsonb(r.model_dump(mode="json")),
                            )
                            for r in records
                        ],
                    )
                finished += 1
                await emit_event(
                    conn,
                    run_id,
                    {"type": "progress", "stage": SEARCH, "done": finished, "total": len(sources)},
                )
                event = await emit_event(
                    conn,
                    run_id,
                    {
                        "type": "partial_result",
                        "stage": SEARCH,
                        "payload": {
                            "event": "source_done",
                            "source": report.source,
                            "count": report.count,
                            "partial_reason": report.partial_reason,
                            "error": report.error,
                        },
                    },
                )
            await notify(redis, run_id, event["seq"])

        if pending:
            await search_all(
                pending, record.plan, limit=source_limit, per_source_timeout=source_timeout,
                on_source_done=on_source_done,
            )  # fmt: skip

        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": SEARCH}):
                return {}
            notes = [
                {
                    "source": e["payload"]["source"],
                    "reason": e["payload"]["error"] or e["payload"]["partial_reason"],
                }
                for e in await _source_events(conn, run_id)
                if e["payload"]["error"] or e["payload"]["partial_reason"]
            ]
            if not sources:
                notes.append(
                    {"source": "all sources", "reason": "no literature sources are configured"}
                )
            await conn.execute(
                "UPDATE runs SET coverage_notes = %s WHERE id = %s", (Jsonb(notes), run_id)
            )
            event = await emit_event(conn, run_id, {"type": "stage_finished", "stage": SEARCH})
        await notify(redis, run_id, event["seq"])
        return {}

    async def resolve(state: PlanState) -> PlanState:
        """Collapse the run's staged records into papers, recording why records merged."""
        from a9_contracts.literature_record import LiteratureRecord

        run_id = uuid.UUID(state["run_id"])
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": RESOLVE}):
                return {}
            if not await _marker(conn, run_id, {"type": "stage_started", "stage": RESOLVE}):
                await emit_event(conn, run_id, {"type": "stage_started", "stage": RESOLVE})
            cur = await conn.execute(
                "SELECT source, source_id, record FROM source_records WHERE run_id = %s ORDER BY source, source_id",
                (run_id,),
            )
            rows = await cur.fetchall()

        records = [LiteratureRecord.model_validate(r["record"]) for r in rows]
        clusters = await cluster_records(
            records, embedder=embedder, similarity_threshold=similarity_threshold
        )
        key = {
            id(rec): (row["source"], row["source_id"])
            for rec, row in zip(records, rows, strict=True)
        }

        outcomes = {"created": 0, "updated": 0, "ambiguous": 0}
        by_rung: dict[str, int] = {}
        async with scoped(pool, role="a9_worker") as conn:
            await lock_papers(conn)
            for cluster in clusters:
                paper_id, outcome = await upsert_paper(conn, to_draft(cluster))
                outcomes[outcome] += 1
                for why in cluster.reasons:
                    by_rung[why] = by_rung.get(why, 0) + 1
                for rec in cluster.records:
                    source, source_id = key[id(rec)]
                    await conn.execute(
                        "UPDATE source_records SET paper_id = %s, merge_reasons = %s WHERE run_id = %s AND source = %s AND source_id = %s",
                        (paper_id, cluster.reasons, run_id, source, source_id),
                    )
            await emit_event(
                conn,
                run_id,
                {
                    "type": "partial_result",
                    "stage": RESOLVE,
                    "payload": {
                        "event": "resolved",
                        "records": len(records),
                        "papers": len(clusters),
                        "duplicates_collapsed": len(records) - len(clusters),
                        "merged_by": by_rung,
                        **outcomes,
                    },
                },
            )
            event = await emit_event(conn, run_id, {"type": "stage_finished", "stage": RESOLVE})
        await notify(redis, run_id, event["seq"])
        return {}

    async def triage(state: PlanState) -> PlanState:
        """Screen each paper against the approved plan, streaming counts as batches land."""
        import asyncio

        from psycopg.types.json import Jsonb

        run_id, user_id = uuid.UUID(state["run_id"]), uuid.UUID(state["user_id"])
        conversation_id = uuid.UUID(state["conversation_id"])
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": TRIAGE}):
                return {}
            if not await _marker(conn, run_id, {"type": "stage_started", "stage": TRIAGE}):
                await emit_event(conn, run_id, {"type": "stage_started", "stage": TRIAGE})
            plan = await get_plan(conn, uuid.UUID(state["approved_plan_id"]))
            assert plan is not None
            cur = await conn.execute(
                """SELECT DISTINCT paper_id FROM source_records WHERE run_id = %s AND paper_id IS NOT NULL""",
                (run_id,),
            )
            total = len(await cur.fetchall())
            cur = await conn.execute(
                """SELECT p.id, p.title, p.abstract, p.year, p.journal, p.is_preprint
                   FROM papers p
                   WHERE p.id IN (SELECT paper_id FROM source_records WHERE run_id = %(run)s AND paper_id IS NOT NULL)
                     AND NOT EXISTS (SELECT 1 FROM screening_verdicts v
                                     WHERE v.conversation_id = %(conv)s AND v.paper_id = p.id AND v.decided_by = 'model')
                   ORDER BY p.id""",
                {"run": run_id, "conv": conversation_id},
            )
            pending = await cur.fetchall()

        done = total - len(pending)
        failures: list[str] = []
        if triager is not None:
            for start in range(0, len(pending), TRIAGE_BATCH):
                batch = pending[start : start + TRIAGE_BATCH]

                async def screen(p: dict[str, Any]) -> Any:
                    try:
                        return await triager.triage(
                            plan.plan,
                            TriageInput(
                                p["title"], p["abstract"], p["year"], p["journal"], p["is_preprint"]
                            ),
                        )
                    except Exception as exc:  # one paper failing must not stop the rest
                        failures.append(f"{type(exc).__name__}: {exc}")
                        return None

                verdicts = await asyncio.gather(*(screen(p) for p in batch))
                async with scoped(pool, role="a9_worker") as conn:
                    for paper, verdict in zip(batch, verdicts, strict=True):
                        if verdict is not None:
                            await save_model_verdict(
                                conn,
                                user_id=user_id,
                                conversation_id=conversation_id,
                                paper_id=paper["id"],
                                verdict=verdict,
                            )
                    done += len(batch)
                    await emit_event(
                        conn,
                        run_id,
                        {"type": "progress", "stage": TRIAGE, "done": done, "total": total},
                    )
                    event = await emit_event(
                        conn,
                        run_id,
                        {
                            "type": "partial_result",
                            "stage": TRIAGE,
                            "payload": {
                                "event": "verdicts",
                                "total": total,
                                **await run_counts(conn, run_id, conversation_id),
                            },
                        },
                    )
                await notify(redis, run_id, event["seq"])

        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": TRIAGE}):
                return {}
            notes: list[dict[str, str]] = []
            if triager is None and pending:
                notes.append(
                    {
                        "source": "triage",
                        "reason": f"not run: no triager is configured; {len(pending)} papers are unscreened",
                    }
                )
            elif failures:
                notes.append(
                    {
                        "source": "triage",
                        "reason": f"{len(failures)} of {len(pending)} papers could not be screened ({failures[0]}); they are unscreened, not excluded",
                    }
                )
            if notes:
                await conn.execute(
                    "UPDATE runs SET coverage_notes = coverage_notes || %s WHERE id = %s",
                    (Jsonb(notes), run_id),
                )
            event = await emit_event(conn, run_id, {"type": "stage_finished", "stage": TRIAGE})
        await notify(redis, run_id, event["seq"])
        return {}

    async def check_retractions(state: PlanState) -> PlanState:
        """Flag retracted work. Flagged papers stay in the corpus: the user may be asking about them."""
        import asyncio

        from psycopg.types.json import Jsonb

        run_id = uuid.UUID(state["run_id"])
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": RETRACTIONS}):
                return {}
            if not await _marker(conn, run_id, {"type": "stage_started", "stage": RETRACTIONS}):
                await emit_event(conn, run_id, {"type": "stage_started", "stage": RETRACTIONS})
            cur = await conn.execute(
                """SELECT DISTINCT p.id, p.doi, p.alt_dois, p.title, p.retraction_status
                   FROM papers p JOIN source_records s ON s.paper_id = p.id
                   WHERE s.run_id = %s
                     AND (p.retraction_checked_at IS NULL
                          OR p.retraction_checked_at < now() - make_interval(days => %s))""",
                (run_id, RETRACTION_RECHECK_DAYS),
            )
            todo = await cur.fetchall()

        results: dict[uuid.UUID, tuple[RetractionResult, list[str]]] = {}
        failures: list[str] = []
        if retraction_checker is not None:
            gate = asyncio.Semaphore(5)

            async def check_one(paper: dict[str, Any]) -> None:
                worst, notices, checked = "none", [], False
                for doi in [d for d in [paper["doi"], *paper["alt_dois"]] if d]:
                    async with gate:
                        try:
                            result = await retraction_checker.check(doi)
                        except SourceError as exc:
                            failures.append(exc.reason)
                            continue
                    checked = checked or result.checked
                    notices += result.notice_dois
                    if RETRACTION_RANK[result.status] > RETRACTION_RANK[worst]:
                        worst = result.status
                results[paper["id"]] = (RetractionResult(checked, worst, sorted(set(notices))), [])

            await asyncio.gather(*(check_one(p) for p in todo))

        titles = {p["id"]: p["title"] for p in todo}
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "stage_finished", "stage": RETRACTIONS}):
                return {}
            flagged = []
            for paper_id, (result, _) in results.items():
                await record_retraction(
                    conn,
                    paper_id,
                    status=result.status,
                    notice_dois=result.notice_dois,
                    checked=result.checked,
                )
                if result.status != "none":
                    flagged.append(
                        {
                            "paper_id": str(paper_id),
                            "status": result.status,
                            "title": titles[paper_id],
                        }
                    )
            # Papers the sources themselves call retracted (a title prefix or publication type) are
            # flagged whether or not Crossref could be reached.
            cur = await conn.execute(
                """SELECT DISTINCT p.id, p.retraction_status, p.title FROM papers p
                   JOIN source_records s ON s.paper_id = p.id
                   WHERE s.run_id = %s AND p.retraction_status <> 'none'""",
                (run_id,),
            )
            known = {
                str(r["id"]): {
                    "paper_id": str(r["id"]),
                    "status": r["retraction_status"],
                    "title": r["title"],
                }
                for r in await cur.fetchall()
            }
            for item in flagged:
                known[item["paper_id"]] = item
            checked_count = sum(1 for r, _ in results.values() if r.checked)
            notes: list[dict[str, str]] = []
            if retraction_checker is None:
                notes.append(
                    {"source": "retraction check", "reason": "not run: no checker is configured"}
                )
            elif failures:
                notes.append(
                    {
                        "source": retraction_checker.name,
                        "reason": f"retraction check failed for some DOIs ({failures[0]}); those papers are unchecked, not cleared",
                    }
                )
            await emit_event(
                conn,
                run_id,
                {
                    "type": "partial_result",
                    "stage": RETRACTIONS,
                    "payload": {
                        "event": "retraction_check",
                        "papers": len(todo),
                        "checked": checked_count,
                        "not_checked": len(todo) - checked_count,
                        "flagged": sorted(known.values(), key=lambda k: k["paper_id"]),
                    },
                },
            )
            if notes:
                await conn.execute(
                    "UPDATE runs SET coverage_notes = coverage_notes || %s WHERE id = %s",
                    (Jsonb(notes), run_id),
                )
            event = await emit_event(conn, run_id, {"type": "stage_finished", "stage": RETRACTIONS})
        await notify(redis, run_id, event["seq"])
        return {}

    async def conclude(state: PlanState) -> PlanState:
        run_id = uuid.UUID(state["run_id"])
        async with scoped(pool, role="a9_worker") as conn:
            if await _marker(conn, run_id, {"type": "run_finished"}):
                return {}
            cur = await conn.execute("SELECT coverage_notes FROM runs WHERE id = %s", (run_id,))
            row = await cur.fetchone()
            assert row is not None
            event = await emit_event(
                conn, run_id, {"type": "run_finished", "coverage_notes": row["coverage_notes"]}
            )
        await notify(redis, run_id, event["seq"])
        return {}

    builder: StateGraph[PlanState] = StateGraph(PlanState)
    builder.add_node("plan", plan)
    builder.add_node("request_approval", request_approval)
    builder.add_node("wait_for_approval", wait_for_approval)
    builder.add_node("finish_plan", finish_plan)
    builder.add_node("search", search)
    builder.add_node("resolve", resolve)
    builder.add_node("triage", triage)
    builder.add_node("check_retractions", check_retractions)
    builder.add_node("conclude", conclude)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "request_approval")
    builder.add_edge("request_approval", "wait_for_approval")
    builder.add_edge("wait_for_approval", "finish_plan")
    builder.add_edge("finish_plan", "search")
    builder.add_edge("search", "resolve")
    builder.add_edge("resolve", "triage")
    builder.add_edge("triage", "check_retractions")
    builder.add_edge("check_retractions", "conclude")
    builder.add_edge("conclude", END)
    return builder
