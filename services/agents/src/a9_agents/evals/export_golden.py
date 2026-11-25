"""Build the labelling template: real records across two topics, with a blank `label` column.

    .venv-a9/bin/python -m a9_agents.evals.export_golden        (needs network)

It does NOT label anything. Labels must come from a person who can judge relevance to the plan.
"""

from __future__ import annotations

import asyncio
import csv
import random

from a9_agents.evals.triage import GOLDEN, PLANS, load_plans
from a9_agents.identity import cluster_records, to_draft
from a9_agents.sources.fanout import search_all
from a9_agents.sources.registry import build_sources

PER_TOPIC = 50
SEED = 20260101


async def main() -> None:
    rows = []
    for topic, plan in load_plans(PLANS).items():
        result = await search_all(
            build_sources("europe_pmc,pubmed,openalex,crossref"), plan, limit=25
        )
        papers = [to_draft(c) for c in await cluster_records(result.records)]
        random.Random(SEED).shuffle(
            papers
        )  # a fixed shuffle, so relevant and irrelevant papers are mixed
        for i, p in enumerate(papers[:PER_TOPIC]):
            rows.append(
                {"id": f"{topic}-{i:03d}", "topic": topic, "doi": p.doi or "", "year": p.year or "", "title": p.title,
                 "abstract": p.abstract or "", "label": ""}
            )  # fmt: skip
        print(
            f"{topic}: {len(papers)} unique papers found, {min(PER_TOPIC, len(papers))} exported; notes: {result.coverage_notes}"
        )
    with GOLDEN.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "topic", "doi", "year", "title", "abstract", "label"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {GOLDEN} (all unlabelled)")


if __name__ == "__main__":
    asyncio.run(main())
