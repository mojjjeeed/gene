"""The paper list: nothing dropped, every paper linked, uncertainty shown rather than hidden."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from a9_agents.db import owner, scoped
from a9_agents.paper_list import build_paper_list
from psycopg.types.json import Jsonb


async def seed(pool: Any) -> dict[str, Any]:
    user, project, conv, run = (uuid.uuid4() for _ in range(4))
    notes = [{"source": "arxiv", "reason": "unavailable after 4 attempts (HTTP 503)"}]
    async with owner(pool) as c:
        await c.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user, f"{user}@x.org"))
        await c.execute(
            "INSERT INTO projects (id, user_id, name) VALUES (%s, %s, 'p')", (project, user)
        )
        await c.execute(
            "INSERT INTO conversations (id, user_id, project_id) VALUES (%s, %s, %s)",
            (conv, user, project),
        )
        await c.execute(
            "INSERT INTO runs (id, user_id, conversation_id, kind, status, coverage_notes) VALUES (%s, %s, %s, 'ingest', 'finished', %s)",
            (run, user, conv, Jsonb(notes)),
        )
    return {"user": user, "conv": conv, "run": run}


async def add_paper(
    pool: Any,
    ctx: dict[str, Any],
    *,
    sources: list[str],
    record_url: str = "https://example.org/r",
    **cols: Any,
) -> uuid.UUID:
    pid = uuid.uuid4()
    values = {
        "title": f"Paper {pid.hex[:6]} on kinase signalling in tumours",
        "source": sources[0],
        "retraction_status": "none",
        **cols,
    }
    names = ", ".join(["id", *values])
    async with owner(pool) as c:
        await c.execute(
            f"INSERT INTO papers ({names}) VALUES ({', '.join(['%s'] * (len(values) + 1))})",
            [pid, *values.values()],
        )
        for i, source in enumerate(sources):
            await c.execute(
                "INSERT INTO source_records (run_id, user_id, source, source_id, record, paper_id, merge_reasons) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    ctx["run"],
                    ctx["user"],
                    source,
                    f"{pid.hex}-{i}",
                    Jsonb({"url": record_url}),
                    pid,
                    ["doi"] if len(sources) > 1 else [],
                ),
            )
    return pid


async def verdict(pool: Any, ctx: dict[str, Any], pid: uuid.UUID, by: str, v: str) -> None:
    async with owner(pool) as c:
        await c.execute(
            "INSERT INTO screening_verdicts (user_id, conversation_id, paper_id, verdict, reason, decided_by, model) VALUES (%s, %s, %s, %s, 'because', %s, %s)",
            (ctx["user"], ctx["conv"], pid, v, by, "heuristic-v1" if by == "model" else None),
        )


async def listing(pool: Any, ctx: dict[str, Any], as_user: uuid.UUID | None = None) -> Any:
    async with scoped(pool, role="a9_app", user_id=as_user or ctx["user"]) as c:
        return await build_paper_list(c, ctx["conv"])


async def test_every_kind_of_paper_is_listed_with_counts_and_a_link(pool: Any) -> None:
    ctx = await seed(pool)
    doi = f"10.9/{uuid.uuid4().hex[:8]}"
    merged = await add_paper(
        pool,
        ctx,
        sources=["europe_pmc", "openalex"],
        doi=doi,
        year=2024,
        licence="cc by",
        is_open_access=True,
        authors=["Ada Lovelace"],
    )
    excluded = await add_paper(pool, ctx, sources=["pubmed"], pmid="4242", year=2020)
    retracted = await add_paper(
        pool,
        ctx,
        sources=["crossref"],
        doi=f"10.9/{uuid.uuid4().hex[:8]}",
        year=2010,
        retraction_status="retracted",
        retraction_checked_at="2026-01-01T00:00:00Z",
        retraction_notice_dois=["10.9/notice"],
    )
    bare = await add_paper(
        pool,
        ctx,
        sources=["biorxiv"],
        record_url="https://www.biorxiv.org/content/10.1101/x",
        is_preprint=True,
    )
    for pid, v in [(merged, "include"), (excluded, "exclude"), (retracted, "include")]:
        await verdict(pool, ctx, pid, "model", v)

    out = await listing(pool, ctx)
    by_id = {p.id: p for p in out.papers}
    assert len(out.papers) == 4, "nothing is dropped"
    assert out.counts.model_dump() == {
        "total": 4,
        "include": 2,
        "exclude": 1,
        "unsure": 0,
        "unscreened": 1,
        "retracted": 1,
    }

    assert by_id[str(merged)].url == f"https://doi.org/{doi}" and by_id[str(merged)].sources == [
        "europe_pmc",
        "openalex",
    ]
    assert (
        by_id[str(merged)].merge_reasons == ["doi"]
        and by_id[str(merged)].licence == "cc by"
        and by_id[str(merged)].authors == ["Ada Lovelace"]
    )
    assert (
        by_id[str(excluded)].url == "https://pubmed.ncbi.nlm.nih.gov/4242/"
    )  # no DOI: the next identifier
    assert (
        by_id[str(bare)].url == "https://www.biorxiv.org/content/10.1101/x"
    )  # no identifier at all: the source's own link
    assert all(p.url.startswith("https://") for p in out.papers)

    r = by_id[str(retracted)]
    assert (r.retraction.status.value, r.retraction.checked, r.retraction.notice_dois) == (
        "retracted",
        True,
        ["10.9/notice"],
    )
    assert by_id[str(merged)].retraction.checked is False, "unchecked is not the same as clean"
    assert (
        by_id[str(bare)].verdict.effective.value == "unscreened"
        and by_id[str(bare)].licence is None
    )


async def test_order_puts_kept_papers_first_and_excluded_last_but_keeps_them(pool: Any) -> None:
    ctx = await seed(pool)
    ids = {}
    for name, v, year in [
        ("old_include", "include", 2001),
        ("new_include", "include", 2024),
        ("unsure", "unsure", 2020),
        ("excluded", "exclude", 2025),
    ]:
        ids[name] = await add_paper(
            pool, ctx, sources=["pubmed"], pmid=str(uuid.uuid4().int)[:8], year=year
        )
        await verdict(pool, ctx, ids[name], "model", v)
    ids["unscreened"] = await add_paper(
        pool, ctx, sources=["pubmed"], pmid=str(uuid.uuid4().int)[:8], year=2022
    )
    order = [p.id for p in (await listing(pool, ctx)).papers]
    assert order == [
        str(ids[k]) for k in ("new_include", "old_include", "unsure", "unscreened", "excluded")
    ]


async def test_a_user_verdict_overrides_the_model_in_the_list_and_the_counts(pool: Any) -> None:
    ctx = await seed(pool)
    pid = await add_paper(pool, ctx, sources=["pubmed"], pmid=str(uuid.uuid4().int)[:8])
    await verdict(pool, ctx, pid, "model", "include")
    await verdict(pool, ctx, pid, "user", "exclude")
    out = await listing(pool, ctx)
    (paper,) = out.papers
    assert paper.verdict.effective.value == "exclude"
    assert paper.verdict.model and paper.verdict.model.verdict.value == "include"  # still visible
    assert (out.counts.include, out.counts.exclude) == (0, 1)


async def test_the_latest_runs_named_coverage_gaps_travel_with_the_list(pool: Any) -> None:
    ctx = await seed(pool)
    out = await listing(pool, ctx)
    assert out.run is not None and out.run.status.value == "finished"
    assert [(n.source, "HTTP 503" in n.reason) for n in out.run.coverage_notes] == [("arxiv", True)]
    assert (
        out.papers == [] and out.counts.total == 0
    )  # an empty corpus is still a well-formed answer


async def test_another_users_papers_and_runs_are_invisible(pool: Any) -> None:
    ctx = await seed(pool)
    await add_paper(pool, ctx, sources=["pubmed"], pmid=str(uuid.uuid4().int)[:8])
    stranger = (await seed(pool))["user"]
    out = await listing(pool, ctx, as_user=stranger)
    assert out.papers == [] and out.run is None


async def test_a_paper_with_no_link_at_all_is_a_loud_error_never_a_blank_link(pool: Any) -> None:
    ctx = await seed(pool)
    await add_paper(pool, ctx, sources=["pubmed"], record_url="")
    with pytest.raises(ValueError, match="no resolvable link"):
        await listing(pool, ctx)


def test_json_is_what_the_frontend_receives() -> None:
    from a9_contracts.paper_list import PaperList

    empty = PaperList.model_validate(
        {
            "conversation_id": "c",
            "run": None,
            "counts": dict.fromkeys(
                ("total", "include", "exclude", "unsure", "unscreened", "retracted"), 0
            ),
            "papers": [],
        }
    )
    assert json.loads(empty.model_dump_json())["run"] is None
