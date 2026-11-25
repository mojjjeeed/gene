"""Writing resolved papers to the global `papers` table.

Papers are shared across every user and run, so this only ever ADDS information: it fills empty
fields and widens alt_dois, and never overwrites a value another run established. The one deliberate
change is promoting a preprint-only row to its journal version when that version turns up.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from a9_agents.db import Conn
from a9_agents.identity import RETRACTION_RANK, PaperDraft

log = logging.getLogger(__name__)

UPSERT_LOCK = "a9_papers_upsert"


async def lock_papers(conn: Conn) -> None:
    """Serialise paper upserts so two runs cannot create the same paper twice."""
    await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (UPSERT_LOCK,))


async def _owned_elsewhere(conn: Conn, column: str, value: str | None, paper_id: uuid.UUID) -> bool:
    if value is None:
        return False
    cur = await conn.execute(
        f"SELECT 1 FROM papers WHERE {column} = %s AND id <> %s", (value, paper_id)
    )  # column is internal
    return await cur.fetchone() is not None


async def upsert_paper(conn: Conn, draft: PaperDraft) -> tuple[uuid.UUID, str]:
    """Returns (paper_id, outcome) where outcome is 'created', 'updated' or 'ambiguous'.

    'ambiguous' means the draft's identifiers match more than one existing paper (two rows that are
    really one work). We attach to the oldest and leave the rest alone: merging rows that chunks and
    memberships already point at is a decision for a person, not an upsert.
    """
    dois = [d for d in [draft.doi, *draft.alt_dois] if d]
    cur = await conn.execute(
        """SELECT id, doi, alt_dois, pmid, pmcid, arxiv_id, is_preprint, abstract, journal, year,
                  retraction_status, retraction_notice_dois, publication_types
           FROM papers
           WHERE doi = ANY(%(dois)s) OR alt_dois && %(dois)s
              OR (%(pmid)s::text IS NOT NULL AND pmid = %(pmid)s)
              OR (%(pmcid)s::text IS NOT NULL AND pmcid = %(pmcid)s)
              OR (%(arxiv)s::text IS NOT NULL AND arxiv_id = %(arxiv)s)
           ORDER BY created_at, id""",
        {"dois": dois, "pmid": draft.pmid, "pmcid": draft.pmcid, "arxiv": draft.arxiv_id},
    )
    rows = await cur.fetchall()

    if not rows:
        cur = await conn.execute(
            """INSERT INTO papers (title, abstract, journal, year, source, doi, alt_dois, pmid, pmcid, arxiv_id,
                                   licence, is_open_access, is_preprint, publication_types, retraction_status)
               VALUES (%(title)s, %(abstract)s, %(journal)s, %(year)s, %(source)s, %(doi)s, %(alt)s, %(pmid)s,
                       %(pmcid)s, %(arxiv)s, %(licence)s, %(oa)s, %(preprint)s, %(types)s, %(status)s)
               RETURNING id""",
            {
                "title": draft.title, "abstract": draft.abstract, "journal": draft.journal, "year": draft.year,
                "source": draft.source, "doi": draft.doi, "alt": draft.alt_dois, "pmid": draft.pmid,
                "pmcid": draft.pmcid, "arxiv": draft.arxiv_id, "licence": draft.licence,
                "oa": draft.is_open_access, "preprint": draft.is_preprint, "types": draft.publication_types,
                "status": draft.retraction_hint,
            },
        )  # fmt: skip
        row = await cur.fetchone()
        assert row is not None
        return row["id"], "created"

    existing = rows[0]
    paper_id: uuid.UUID = existing["id"]
    promote = bool(existing["is_preprint"] and not draft.is_preprint and draft.doi)
    promote = promote and not await _owned_elsewhere(conn, "doi", draft.doi, paper_id)

    doi = existing["doi"]
    alt = set(existing["alt_dois"]) | set(draft.alt_dois)
    if promote:
        if existing["doi"]:
            alt.add(existing["doi"])
        doi = draft.doi
    elif doi is None and draft.doi and not await _owned_elsewhere(conn, "doi", draft.doi, paper_id):
        doi = draft.doi
    elif draft.doi and draft.doi != doi:
        alt.add(draft.doi)
    alt.discard(doi)

    async def fill(column: str, current: Any, new: str | None) -> Any:
        if (
            current is not None
            or new is None
            or await _owned_elsewhere(conn, column, new, paper_id)
        ):
            return current
        return new

    status = max(
        (existing["retraction_status"], draft.retraction_hint), key=lambda s: RETRACTION_RANK[s]
    )
    values: dict[str, Any] = {
        "id": paper_id,
        "doi": doi,
        "alt": sorted(alt),
        "pmid": await fill("pmid", existing["pmid"], draft.pmid),
        "pmcid": await fill("pmcid", existing["pmcid"], draft.pmcid),
        "arxiv": await fill("arxiv_id", existing["arxiv_id"], draft.arxiv_id),
        "abstract": existing["abstract"] or draft.abstract,
        "journal": existing["journal"] or draft.journal,
        "year": existing["year"] or draft.year,
        "types": sorted(set(existing["publication_types"]) | set(draft.publication_types)),
        "status": status,
        "promote": promote,
        "title": draft.title,
        "licence": draft.licence,
        "oa": draft.is_open_access,
    }
    await conn.execute(
        """UPDATE papers SET doi = %(doi)s, alt_dois = %(alt)s, pmid = %(pmid)s, pmcid = %(pmcid)s,
               arxiv_id = %(arxiv)s, abstract = %(abstract)s, journal = %(journal)s, year = %(year)s,
               publication_types = %(types)s, retraction_status = %(status)s,
               title = CASE WHEN %(promote)s THEN %(title)s ELSE title END,
               licence = CASE WHEN %(promote)s THEN %(licence)s ELSE licence END,
               full_text_allowed = CASE WHEN %(promote)s THEN false ELSE full_text_allowed END,
               is_open_access = CASE WHEN %(promote)s THEN %(oa)s ELSE is_open_access END,
               is_preprint = CASE WHEN %(promote)s THEN false ELSE is_preprint END
           WHERE id = %(id)s""",
        values,
    )
    if len(rows) > 1:
        log.warning(
            "paper identifiers matched %d existing rows; attached to the oldest (%s)",
            len(rows),
            paper_id,
        )
        return paper_id, "ambiguous"
    return paper_id, "updated"


async def record_retraction(
    conn: Conn, paper_id: uuid.UUID, *, status: str, notice_dois: list[str], checked: bool
) -> None:
    """Raise the paper's retraction status (never lower it) and stamp the check time."""
    await conn.execute(
        """UPDATE papers SET
             retraction_status = CASE WHEN %(rank)s > CASE retraction_status
                   WHEN 'retracted' THEN 3 WHEN 'withdrawn' THEN 2 WHEN 'expression_of_concern' THEN 1 ELSE 0 END
                 THEN %(status)s ELSE retraction_status END,
             retraction_notice_dois = ARRAY(SELECT DISTINCT unnest(retraction_notice_dois || %(notices)s::text[])),
             retraction_checked_at = CASE WHEN %(checked)s THEN now() ELSE retraction_checked_at END
           WHERE id = %(id)s""",
        {
            "rank": RETRACTION_RANK[status],
            "status": status,
            "notices": notice_dois,
            "checked": checked,
            "id": paper_id,
        },
    )
