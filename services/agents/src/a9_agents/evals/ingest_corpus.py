"""Measure full-text ingest on a real corpus (network required; not run in CI).

    .venv-a9/bin/python -m a9_agents.evals.ingest_corpus [--pdfs 100] [--jats 50] [--out DIR]

Reports, over EVERY document and EVERY chunk (not a sample): the parse rate, and whether each chunk
round-trips to its exact source span. PDFs come from arXiv (any licence: they are only read here for
measurement and written to a temp dir), JATS from PubMed Central.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import tempfile
import time
from collections import Counter
from pathlib import Path

import httpx

from a9_agents.fulltext.chunker import chunk_document, verify_chunks
from a9_agents.fulltext.fetch import NCBI_EFETCH
from a9_agents.fulltext.jats import parse_jats
from a9_agents.fulltext.pdfparse import parse_pdf
from a9_agents.sources.http import PolicedClient, Policy

TOPICS = [
    "protein structure prediction",
    "kinase inhibitor",
    "drug discovery machine learning",
    "single cell RNA sequencing",
    "molecular dynamics simulation",
    "clinical trial survival analysis",
    "genome assembly",
    "gene regulatory network",
    "protein language model",
    "cancer genomics",
    "medical image segmentation",
    "epidemic modelling",
    "molecular docking",
    "protein folding energy landscape",
    "neural decoding",
    "metabolic network",
]


async def arxiv_ids(client: PolicedClient, n: int) -> list[str]:
    ids: list[str] = []
    per = max(n // len(TOPICS) + 2, 4)
    for topic in TOPICS:
        r = await client.get(
            "https://export.arxiv.org/api/query",
            {"search_query": f'all:"{topic}"', "max_results": per, "sortBy": "relevance"},
        )
        ids += [
            re.sub(r"v\d+$", "", m)
            for m in re.findall(r"<id>https?://arxiv\.org/abs/([^<]+)</id>", r.text)
        ]
        if len(set(ids)) >= n + 10:
            break
    return list(dict.fromkeys(ids))[:n]


async def pmc_ids(client: PolicedClient, n: int) -> list[str]:
    r = await client.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {
            "db": "pmc",
            "term": '"cc by"[License] AND (kinase OR "drug resistance" OR genomics) AND "open access"[filter]',
            "retmax": n * 2,
            "retmode": "json",
            "sort": "relevance",
        },
    )
    return [f"PMC{i}" for i in r.json()["esearchresult"]["idlist"]][:n]


async def main(pdfs: int, jats: int, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    # ---- JATS from PMC
    ncbi = PolicedClient(Policy("pmc", min_interval=0.36, max_concurrency=2))
    for pmcid in await pmc_ids(ncbi, jats):
        row: dict[str, object] = {"set": "jats", "id": pmcid}
        try:
            xml = (
                await ncbi.get(NCBI_EFETCH, {"db": "pmc", "id": pmcid, "rettype": "xml"})
            ).content
            doc = parse_jats(xml)
            chunks = chunk_document(doc)
            problems = verify_chunks(doc, chunks)
            row |= {
                "ok": bool(chunks) and any(c.kind == "body" for c in chunks),
                "chunks": len(chunks),
                "problems": len(problems),
                "chars": len(doc.text),
                "sections": len({tuple(b.section_path) for b in doc.blocks if b.kind == "body"}),
                "has_abstract": any(c.kind == "abstract" for c in chunks),
                "kinds": dict(Counter(c.kind for c in chunks)),
            }
        except Exception as exc:
            row |= {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}"[:150],
                "chunks": 0,
                "problems": 0,
            }
        rows.append(row)
    await ncbi.aclose()

    # ---- PDFs from arXiv (polite: one request every ~3 s)
    ax = PolicedClient(Policy("arxiv", min_interval=3.1, max_concurrency=1, timeout=90))
    started = time.monotonic()
    for aid in await arxiv_ids(ax, pdfs):
        row = {"set": "pdf", "id": aid}
        try:
            data = (await ax.get(f"https://arxiv.org/pdf/{aid}")).content
            (out / f"{aid.replace('/', '_')}.pdf").write_bytes(data)
            doc = parse_pdf(data)
            chunks = chunk_document(doc)
            problems = verify_chunks(doc, chunks)
            row |= {
                "ok": bool(chunks),
                "chunks": len(chunks),
                "problems": len(problems),
                "chars": len(doc.text),
                "sections": len({tuple(b.section_path) for b in doc.blocks if b.kind == "body"}),
                "has_abstract": any(c.kind == "abstract" for c in chunks),
                "kinds": dict(Counter(c.kind for c in chunks)),
                "bytes": len(data),
            }
        except Exception as exc:
            row |= {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}"[:150],
                "chunks": 0,
                "problems": 0,
            }
        rows.append(row)
        if len(rows) % 20 == 0:
            print(f"  ... {len(rows)} documents, {time.monotonic() - started:.0f}s", flush=True)
    await ax.aclose()

    (out / "results.json").write_text(json.dumps(rows, indent=1))
    for name in ("jats", "pdf"):
        part = [r for r in rows if r["set"] == name]
        if not part:
            continue
        ok = [r for r in part if r["ok"]]
        all_chunks = sum(int(str(r["chunks"])) for r in part)
        bad = sum(int(str(r["problems"])) for r in part)
        print(f"\n{name.upper()}: {len(ok)}/{len(part)} parsed ({100 * len(ok) / len(part):.0f}%)")
        print(f"  chunks checked for exact round-trip: {all_chunks}; failures: {bad}")
        if ok:
            print(
                f"  chars/doc median {int(statistics.median(int(str(r['chars'])) for r in ok))}; documents with an abstract chunk: {sum(1 for r in ok if r.get('has_abstract'))}; with >=3 body sections: {sum(1 for r in ok if int(str(r.get('sections', 0))) >= 3)}"
            )
        for r in part:
            if not r["ok"]:
                print("  FAILED", r["id"], r.get("error"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdfs", type=int, default=100)
    ap.add_argument("--jats", type=int, default=50)
    ap.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "a9-corpus")
    a = ap.parse_args()
    asyncio.run(main(a.pdfs, a.jats, a.out))
    _ = httpx
