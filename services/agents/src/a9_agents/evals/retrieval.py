"""Retrieval evaluation on a SYNTHETIC golden question set built from real open-access papers.

    .venv-a9/bin/python -m a9_agents.evals.retrieval [--papers 20] [--per-paper 5]   (network + a running Postgres)

Questions are templated from real sentences, so the supporting span is known by construction. That makes
this a regression harness, NOT an expert benchmark: the questions share vocabulary with their answers, so
the score is optimistic. A hit means a retrieved chunk fully contains the supporting sentence.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import re
import statistics
import time
import uuid

import psycopg
from alembic import command
from alembic.config import Config

from a9_agents.db import open_pool, scoped
from a9_agents.fulltext.fetch import PmcJats
from a9_agents.fulltext.ingest import add_memberships, ingest_paper
from a9_agents.fulltext.jats import parse_jats
from a9_agents.fulltext.store import LocalObjectStore
from a9_agents.index.conversation_index import ConversationIndex, ensure_collections, make_client
from a9_agents.index.embed import FastEmbedDense, FastEmbedReranker
from a9_agents.index.pipeline import index_conversation
from a9_agents.index.retrieval import retrieve
from a9_agents.sources.http import PolicedClient, Policy

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_STOP = frozenset(
    "the a an of in on and or to for with by from that this was were is are as at be it its their which these those than then also not".split()
)


def question_from(sentence: str) -> str | None:
    """A templated question from a sentence's distinctive words (numbers and capitalised terms first)."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", sentence)
    keep = [w for w in words if w.lower() not in _STOP]
    ranked = sorted(
        dict.fromkeys(keep),
        key=lambda w: (-(any(c.isupper() for c in w[1:]) or any(c.isdigit() for c in w)), -len(w)),
    )
    return (
        f"What does the paper report about {', '.join(ranked[:4])}?" if len(ranked) >= 4 else None
    )


async def main(n_papers: int, per_paper: int) -> None:
    admin = os.environ.get("A9_PG_ADMIN_URL", "postgresql://localhost:5544/postgres")
    name = f"a9_eval_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    url = admin.rsplit("/", 1)[0] + "/" + name
    os.environ["A9_DATABASE_URL"] = url.replace("postgresql://", "postgresql+psycopg://", 1)
    cfg = Config("services/agents/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["A9_DATABASE_URL"])
    command.upgrade(cfg, "head")
    pool = await open_pool()
    try:
        ncbi = PolicedClient(Policy("pmc", min_interval=0.36))
        r = await ncbi.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {
                "db": "pmc",
                "term": '"cc by"[License] AND (kinase OR "drug resistance" OR genomics OR "single cell") AND "open access"[filter]',
                "retmax": n_papers * 3,
                "retmode": "json",
                "sort": "relevance",
            },
        )
        pmcids = [f"PMC{i}" for i in r.json()["esearchresult"]["idlist"]]
        store, route = LocalObjectStore("/tmp/a9-eval-objects"), PmcJats(ncbi=ncbi)
        user, project, conv = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with pool.connection() as conn:
            await conn.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s)", (user, f"{user}@x.org")
            )
            await conn.execute(
                "INSERT INTO projects (id, user_id, name) VALUES (%s, %s, 'eval')", (project, user)
            )
            await conn.execute(
                "INSERT INTO conversations (id, user_id, project_id) VALUES (%s, %s, %s)",
                (conv, user, project),
            )
            await conn.commit()
        golden: list[
            tuple[str, uuid.UUID, int, int]
        ] = []  # (question, paper id, sentence start, end) in document coordinates
        rng = random.Random(20260101)
        paper_ids: list[uuid.UUID] = []
        for pmcid in pmcids:
            if len(paper_ids) >= n_papers:
                break
            try:
                full = await route.fetch({"pmcid": pmcid})
            except Exception:
                continue
            doc = parse_jats(full.data)
            pid = uuid.uuid4()
            async with pool.connection() as conn:
                await conn.execute(
                    "INSERT INTO papers (id, title, source, abstract, pmcid, licence) VALUES (%s, %s, 'pmc', %s, %s, %s)",
                    (
                        pid,
                        doc.title or pmcid,
                        next(
                            (doc.text[b.start : b.end] for b in doc.blocks if b.kind == "abstract"),
                            None,
                        ),
                        pmcid,
                        full.licence_raw,
                    ),
                )
                await conn.commit()
            async with scoped(pool, role="a9_worker") as conn:
                cur = await conn.execute("SELECT * FROM papers WHERE id = %s", (pid,))
                row = await cur.fetchone()
                assert row is not None
                res = await ingest_paper(
                    conn, store, dict(row), uuid.uuid4(), routes=[PmcJats(ncbi=ncbi)]
                )
            if res.status != "parsed":
                continue
            paper_ids.append(pid)
            body = [b for b in doc.blocks if b.kind == "body"]
            sentences = []
            for b in body:
                pos = 0
                text = doc.text[b.start : b.end]
                for part in _SENT.split(text):
                    i = text.index(part, pos)
                    pos = i + len(part)
                    if len(part.split()) >= 14 and (q := question_from(part)):
                        sentences.append((q, b.start + i, b.start + i + len(part)))
            for q, s, e in rng.sample(sentences, min(per_paper, len(sentences))):
                golden.append((q, pid, s, e))
        async with scoped(pool, role="a9_worker") as conn:
            await add_memberships(conn, user_id=user, conversation_id=conv, paper_ids=paper_ids)
            embedder, reranker = FastEmbedDense(), FastEmbedReranker()
            client = make_client(memory=True)
            ensure_collections(client, embedder.dims)
            index = ConversationIndex(client, conv)
            stats = await index_conversation(conn, index, embedder, conv)
        print(
            f"[{time.strftime('%H:%M:%S')}] corpus: {len(paper_ids)} papers, {stats.chunks_total} chunks; {len(golden)} synthetic questions"
        )
        async with scoped(pool, role="a9_app", user_id=user) as conn:
            await retrieve(conn, index, conv, embedder, reranker, "warm up the models")
            hit10 = hit20 = 0
            times: list[float] = []
            for k, (q, pid, s, e) in enumerate(golden, 1):
                if k % 10 == 0:
                    print(
                        f"  [{time.strftime('%H:%M:%S')}] {k}/{len(golden)} questions", flush=True
                    )
                got = await retrieve(
                    conn, index, conv, embedder, reranker, q, final=20, expand=False
                )
                times.append(got.ms["total"])
                spans = [(c.paper_id, c.char_start, c.char_end) for c in got.chunks]
                contains = [(p == pid and cs <= s and e <= ce) for p, cs, ce in spans]
                hit10 += any(contains[:10])
                hit20 += any(contains)
        n = len(golden)
        ts = sorted(times)
        print(
            f"recall@10 = {hit10 / n:.3f}   recall@20 = {hit20 / n:.3f}   (n={n}, synthetic, optimistic)"
        )
        print(
            f"retrieval latency: p50 {statistics.median(ts):.0f} ms, p95 {ts[int(0.95 * (n - 1))]:.0f} ms, max {ts[-1]:.0f} ms (CPU, in-memory vector store, {stats.chunks_total} chunks)"
        )
    finally:
        await pool.close()
        with psycopg.connect(admin, autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=int, default=20)
    ap.add_argument("--per-paper", type=int, default=5)
    a = ap.parse_args()
    asyncio.run(main(a.papers, a.per_paper))
