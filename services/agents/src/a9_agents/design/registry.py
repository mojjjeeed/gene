"""The model registry and score storage. Every prediction references a registered model version."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from a9_agents.db import Conn
from a9_agents.design.conformal import Prediction


async def register_model(
    conn: Conn,
    *,
    name: str,
    version: str,
    endpoint: str,
    training_data: str,
    calibrated_at: datetime,
    domain_notes: str,
    card: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Models are immutable: re-registering the same (name, version) returns the existing id unchanged."""
    cur = await conn.execute(
        """INSERT INTO models (name, version, endpoint, training_data, calibrated_at, domain_notes, card)
           VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (name, version) DO NOTHING RETURNING id""",
        (name, version, endpoint, training_data, calibrated_at, domain_notes, Jsonb(card or {})),
    )
    row = await cur.fetchone()
    if row is None:
        row = await (
            await conn.execute(
                "SELECT id FROM models WHERE name = %s AND version = %s", (name, version)
            )
        ).fetchone()
    assert row is not None
    return uuid.UUID(str(row["id"]))


async def store_score(
    conn: Conn,
    *,
    molecule_id: uuid.UUID,
    user_id: uuid.UUID,
    model_id: uuid.UUID,
    endpoint: str,
    prediction: Prediction,
) -> None:
    await conn.execute(
        """INSERT INTO molecule_scores (molecule_id, user_id, model_id, endpoint, value, lower, upper, coverage, in_domain, nn_similarity)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (molecule_id, model_id, endpoint) DO NOTHING""",
        (
            molecule_id,
            user_id,
            model_id,
            endpoint,
            prediction.value,
            prediction.lower,
            prediction.upper,
            prediction.coverage,
            prediction.in_domain,
            prediction.nn_similarity,
        ),
    )


async def store_candidate(
    conn: Conn,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    report: Any,
    run_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Persist a candidate and every gate result with its detail, passed or failed. Returns None if the
    structure was invalid (there is nothing to key it on); the failure is the report, not a row."""
    if report.inchikey is None or report.canonical is None:
        return None
    cur = await conn.execute(
        """INSERT INTO molecules (user_id, conversation_id, smiles, inchikey, run_id) VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (conversation_id, inchikey) DO NOTHING RETURNING id""",
        (user_id, conversation_id, report.canonical, report.inchikey, run_id),
    )
    row = await cur.fetchone()
    if row is None:
        row = await (
            await conn.execute(
                "SELECT id FROM molecules WHERE conversation_id = %s AND inchikey = %s",
                (conversation_id, report.inchikey),
            )
        ).fetchone()
    assert row is not None
    mol = uuid.UUID(str(row["id"]))
    for r in report.results:
        await conn.execute(
            """INSERT INTO molecule_gates (molecule_id, user_id, gate, hard, passed, detail) VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (molecule_id, gate) DO UPDATE SET passed = EXCLUDED.passed, detail = EXCLUDED.detail""",
            (mol, user_id, r.gate, r.hard, r.passed, Jsonb(r.detail)),
        )
    return mol
