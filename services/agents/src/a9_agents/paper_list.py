"""The paper list: a conversation's corpus as the UI shows it.

Nothing is dropped. Excluded papers and retracted papers are in the list, labelled; a paper whose
retraction has not been checked says so rather than looking clean; every paper has a link.
"""

from __future__ import annotations

import uuid
from typing import Any

from a9_contracts.paper_list import PaperList

from a9_agents.db import Conn

VERDICT_ORDER = {"include": 0, "unsure": 1, "unscreened": 2, "exclude": 3}


def paper_url(row: dict[str, Any], record_urls: list[str]) -> str:
    """A link that resolves: the DOI, else the strongest identifier, else the source's own link."""
    if row["doi"]:
        return f"https://doi.org/{row['doi']}"
    if row["pmid"]:
        return f"https://pubmed.ncbi.nlm.nih.gov/{row['pmid']}/"
    if row["pmcid"]:
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{row['pmcid']}/"
    if row["arxiv_id"]:
        return f"https://arxiv.org/abs/{row['arxiv_id']}"
    for url in record_urls:
        if url:
            return url
    raise ValueError(
        f"paper {row['id']} has no resolvable link"
    )  # a bug, never a blank link in the UI


async def build_paper_list(conn: Conn, conversation_id: uuid.UUID) -> PaperList:
    in_conversation = """(SELECT s.paper_id FROM source_records s JOIN runs r ON r.id = s.run_id
                          WHERE r.conversation_id = %(c)s AND s.paper_id IS NOT NULL)"""
    cur = await conn.execute(
        f"""SELECT p.id, p.title, p.abstract, p.authors, p.year, p.journal, p.doi, p.pmid, p.pmcid, p.arxiv_id,
                   p.licence, p.is_open_access, p.is_preprint, p.retraction_status, p.retraction_checked_at,
                   p.retraction_notice_dois,
                   m.verdict AS m_verdict, m.reason AS m_reason, u.verdict AS u_verdict, u.reason AS u_reason
            FROM papers p
            LEFT JOIN screening_verdicts m ON m.conversation_id = %(c)s AND m.paper_id = p.id AND m.decided_by = 'model'
            LEFT JOIN screening_verdicts u ON u.conversation_id = %(c)s AND u.paper_id = p.id AND u.decided_by = 'user'
            WHERE p.id IN {in_conversation}""",
        {"c": conversation_id},
    )
    rows = await cur.fetchall()

    cur = await conn.execute(
        """SELECT s.paper_id, s.source, s.record->>'url' AS url, s.merge_reasons
           FROM source_records s JOIN runs r ON r.id = s.run_id
           WHERE r.conversation_id = %s AND s.paper_id IS NOT NULL ORDER BY s.fetched_at, s.source_id""",
        (conversation_id,),
    )
    sources: dict[uuid.UUID, list[str]] = {}
    urls: dict[uuid.UUID, list[str]] = {}
    reasons: dict[uuid.UUID, list[str]] = {}
    for rec in await cur.fetchall():
        pid = rec["paper_id"]
        if rec["source"] not in sources.setdefault(pid, []):
            sources[pid].append(rec["source"])
        urls.setdefault(pid, []).append(rec["url"] or "")
        for why in rec["merge_reasons"]:
            if why not in reasons.setdefault(pid, []):
                reasons[pid].append(why)

    cur = await conn.execute(
        """SELECT id, status, coverage_notes FROM runs
           WHERE conversation_id = %s AND kind = 'ingest' ORDER BY created_at DESC LIMIT 1""",
        (conversation_id,),
    )
    run = await cur.fetchone()

    papers = []
    for r in rows:
        user = {"verdict": r["u_verdict"], "reason": r["u_reason"]} if r["u_verdict"] else None
        model = {"verdict": r["m_verdict"], "reason": r["m_reason"]} if r["m_verdict"] else None
        effective = (user or model or {"verdict": "unscreened"})["verdict"]
        papers.append(
            {
                "id": str(r["id"]),
                "title": r["title"],
                "abstract": r["abstract"],
                "authors": list(r["authors"]),
                "year": r["year"],
                "journal": r["journal"],
                "doi": r["doi"],
                "url": paper_url(r, urls.get(r["id"], [])),
                "sources": sources.get(r["id"], []),
                "licence": r["licence"],
                "is_open_access": r["is_open_access"],
                "is_preprint": r["is_preprint"],
                "retraction": {
                    "status": r["retraction_status"],
                    "checked": r["retraction_checked_at"] is not None,
                    "notice_dois": list(r["retraction_notice_dois"]),
                },
                "verdict": {"effective": effective, "user": user, "model": model},
                "merge_reasons": reasons.get(r["id"], []),
            }  # fmt: skip
        )
    papers.sort(
        key=lambda p: (
            VERDICT_ORDER[p["verdict"]["effective"]],
            -(p["year"] or 0),
            p["title"].lower(),
        )
    )

    counts = {
        k: sum(1 for p in papers if p["verdict"]["effective"] == k)
        for k in ("include", "exclude", "unsure", "unscreened")
    }
    counts["total"] = len(papers)
    counts["retracted"] = sum(1 for p in papers if p["retraction"]["status"] != "none")
    return PaperList.model_validate(
        {
            "conversation_id": str(conversation_id),
            "run": {
                "id": str(run["id"]),
                "status": run["status"],
                "coverage_notes": run["coverage_notes"],
            }
            if run
            else None,
            "counts": counts,
            "papers": papers,
        }
    )
