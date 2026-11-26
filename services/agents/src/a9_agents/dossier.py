"""Dossiers: a versioned, immutable record of the chain from plan to candidates, and its sign-off.

Every version carries the research-use-only statement and names what it contains and what it does not
(for example: no synthesis routes, predictions are hypotheses). Export needs an approved sign-off against
that exact version; the database refuses it otherwise."""

from __future__ import annotations

import uuid
from typing import Any

from psycopg.types.json import Jsonb

from a9_agents.db import Conn
from a9_agents.paper_list import build_paper_list
from a9_agents.plans import latest_plan

RESEARCH_USE_ONLY = (
    "Research use only. This dossier contains literature evidence, structures and model predictions that are "
    "hypotheses. It contains no synthesis procedures, dosing or clinical or regulatory claims, and none of it "
    "has been experimentally verified."
)


class ExportRefusedError(Exception):
    """No approved sign-off exists for this dossier version."""


async def assemble(conn: Conn, *, user_id: uuid.UUID, conversation_id: uuid.UUID) -> dict[str, Any]:
    """Create the next dossier version from the conversation's current state."""
    plan = await latest_plan(conn, conversation_id)
    papers = await build_paper_list(conn, conversation_id)
    cur = await conn.execute(
        """SELECT m.id, m.smiles, m.inchikey,
                  COALESCE((SELECT jsonb_agg(jsonb_build_object('gate', g.gate, 'hard', g.hard, 'passed', g.passed, 'detail', g.detail) ORDER BY g.gate)
                            FROM molecule_gates g WHERE g.molecule_id = m.id), '[]') AS gates,
                  COALESCE((SELECT jsonb_agg(jsonb_build_object('endpoint', s.endpoint, 'value', s.value, 'lower', s.lower, 'upper', s.upper,
                                                                 'coverage', s.coverage, 'in_domain', s.in_domain, 'nn_similarity', s.nn_similarity,
                                                                 'model', jsonb_build_object('name', md.name, 'version', md.version, 'calibrated_at', md.calibrated_at,
                                                                                             'training_data', md.training_data, 'domain_notes', md.domain_notes)))
                            FROM molecule_scores s JOIN models md ON md.id = s.model_id WHERE s.molecule_id = m.id), '[]') AS scores
           FROM molecules m WHERE m.conversation_id = %s ORDER BY m.created_at, m.id""",
        (conversation_id,),
    )
    molecules = [{**r, "id": str(r["id"])} for r in await cur.fetchall()]
    content = {
        "statement": RESEARCH_USE_ONLY,
        "plan": plan.to_json() if plan else None,
        "corpus": papers.model_dump(mode="json"),
        "candidates": molecules,
    }
    version = (
        await (
            await conn.execute(
                "SELECT COALESCE(max(version), 0) + 1 AS v FROM dossiers WHERE conversation_id = %s",
                (conversation_id,),
            )
        ).fetchone()
        or {"v": 1}
    )["v"]
    row = await (
        await conn.execute(
            "INSERT INTO dossiers (user_id, conversation_id, version, content) VALUES (%s, %s, %s, %s) RETURNING id, version",
            (user_id, conversation_id, version, Jsonb(content)),
        )
    ).fetchone()
    assert row is not None
    return {"id": str(row["id"]), "version": row["version"], "content": content}


async def sign_off(
    conn: Conn,
    *,
    user_id: uuid.UUID,
    dossier_id: uuid.UUID,
    reviewer_name: str,
    decision: str,
    note: str | None,
) -> uuid.UUID:
    row = await (
        await conn.execute(
            "INSERT INTO signoffs (dossier_id, user_id, reviewer_name, decision, note) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (dossier_id, user_id, reviewer_name, decision, note),
        )
    ).fetchone()
    assert row is not None
    return uuid.UUID(str(row["id"]))


async def export(
    conn: Conn, *, user_id: uuid.UUID, dossier_id: uuid.UUID, fmt: str = "json"
) -> dict[str, Any]:
    """Export a dossier version. Raises ExportRefusedError unless an approved sign-off exists for it."""
    cur = await conn.execute(
        "SELECT id, reviewer_name, created_at FROM signoffs WHERE dossier_id = %s AND decision = 'approved' ORDER BY created_at DESC LIMIT 1",
        (dossier_id,),
    )
    approved = await cur.fetchone()
    if approved is None:
        raise ExportRefusedError("this dossier version has no approved sign-off")
    d = await (
        await conn.execute("SELECT version, content FROM dossiers WHERE id = %s", (dossier_id,))
    ).fetchone()
    if d is None:
        raise LookupError("dossier not found")
    await conn.execute(
        "INSERT INTO exports (dossier_id, user_id, format, signoff_id) VALUES (%s, %s, %s, %s)",
        (dossier_id, user_id, fmt, approved["id"]),
    )
    return {
        "dossier_id": str(dossier_id),
        "version": d["version"],
        "signed_off_by": approved["reviewer_name"],
        "signed_off_at": approved["created_at"].isoformat(),
        "statement": RESEARCH_USE_ONLY,
        "content": d["content"],
    }
