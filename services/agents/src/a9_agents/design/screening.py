"""The screening gate: every generated structure is screened BEFORE it is stored or shown.

A hit blocks the candidate and raises a review item for a person; it is never silently dropped, because a
silent drop teaches the user nothing and hides a pattern from us. Repeated near-misses on one account
raise an alert.

SCOPE, stated plainly: the rules below are a small SEED set of well-known acute-hazard structural classes,
chosen to be conservative (some legitimate drugs will be held for review, such as nitrogen-mustard
chemotherapeutics). They need expert curation. A controlled-substance screen needs an authoritative,
current schedule from the relevant authority and is NOT implemented: this gate does not claim to cover it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import cache
from typing import Any

from rdkit import Chem as _Chem
from rdkit.Chem import inchi as _inchi

from a9_agents.db import Conn
from a9_agents.plans import audit

Chem: Any = _Chem
inchi: Any = _inchi

NEAR_MISS_LIMIT = 3  # near-misses by one user within the window raise an alert
NEAR_MISS_WINDOW_HOURS = 24


@dataclass(frozen=True)
class Rule:
    name: str
    smarts: str  # a hit blocks
    near: str | None  # a near-miss is counted but not blocked
    why: str


SEED_RULES: tuple[Rule, ...] = (
    Rule("organophosphate_leaving_group", "[PX4](=O)([#6,#8,#7])[F,$(C#N)]", "[PX4](=O)[Cl,Br,I]",
         "phosphorus esters with a fluoride or cyanide leaving group are acute cholinesterase-inhibitor classes"),
    Rule("bis_haloethyl_alkylator", "[N,S](CC[Cl,Br,I])CC[Cl,Br,I]", "[N,S]CC[Cl,Br,I]",
         "bis(2-haloethyl) amines and sulfides are potent alkylating agents (includes some chemotherapeutics: held for review)"),
    Rule("polynitro_energetic", "[$([N+](=O)[O-]),$(N(=O)=O)].[$([N+](=O)[O-]),$(N(=O)=O)].[$([N+](=O)[O-]),$(N(=O)=O)]", None,
         "three or more nitro groups on a small molecule: energetic-material class"),
)  # fmt: skip


@dataclass(frozen=True)
class Hit:
    rule: str
    why: str


@cache
def _compiled() -> list[tuple[Rule, Any, Any]]:
    return [
        (r, Chem.MolFromSmarts(r.smarts), Chem.MolFromSmarts(r.near) if r.near else None)
        for r in SEED_RULES
    ]


def screen(smiles: str) -> tuple[list[Hit], list[str]]:
    """Returns (hits, near_miss_rule_names). An unparseable structure is a hit-free, near-miss-free blank:
    validity is a different gate's job, and nothing unparseable is ever stored."""
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:
        return [], []
    hits, near = [], []
    for rule, pattern, near_pattern in _compiled():
        if mol.HasSubstructMatch(pattern):
            hits.append(Hit(rule.name, rule.why))
        elif near_pattern is not None and mol.HasSubstructMatch(near_pattern):
            near.append(rule.name)
    return hits, near


class ScreeningBlockedError(Exception):
    """A structure matched a screening rule and must not be stored or shown."""

    def __init__(self, hits: list[Hit], review_id: uuid.UUID | None = None):
        super().__init__("blocked by screening: " + ", ".join(h.rule for h in hits))
        self.hits, self.review_id = hits, review_id


@dataclass(frozen=True)
class Admission:
    admitted: bool
    review_id: uuid.UUID | None = None
    rules: tuple[str, ...] = ()
    alert: bool = False


async def admit(
    conn: Conn, *, user_id: uuid.UUID, conversation_id: uuid.UUID, smiles: str
) -> Admission:
    """Screen a generated structure. On a hit: raise a review item, record the event, audit it, and refuse.
    Near-misses are counted; enough of them in the window raise an alert (audited)."""
    hits, near = screen(smiles)
    if near:
        for rule in near:
            await conn.execute(
                "INSERT INTO screening_events (user_id, kind, rule) VALUES (%s, 'near_miss', %s)",
                (user_id, rule),
            )
    alert = False
    if hits or near:
        row = await (
            await conn.execute(
                "SELECT count(*) AS n FROM screening_events WHERE user_id = %s AND created_at > now() - make_interval(hours => %s)",
                (user_id, NEAR_MISS_WINDOW_HOURS),
            )
        ).fetchone()
        alert = bool(row and row["n"] >= NEAR_MISS_LIMIT)
        if alert:
            await audit(
                conn,
                user_id=user_id,
                actor="system",
                action="screening.pattern_alert",
                entity_type="user",
                entity_id=str(user_id),
                detail={"events_in_window": row["n"] if row else 0},
            )
    if not hits:
        return Admission(True, alert=alert)
    mol = Chem.MolFromSmiles(smiles)
    review = await (
        await conn.execute(
            """INSERT INTO review_items (user_id, conversation_id, kind, rules, smiles, inchikey)
               VALUES (%s, %s, 'screening_hit', %s, %s, %s) RETURNING id""",
            (
                user_id,
                conversation_id,
                [h.rule for h in hits],
                Chem.MolToSmiles(mol),
                inchi.MolToInchiKey(mol),
            ),
        )
    ).fetchone()
    assert review is not None
    for h in hits:
        await conn.execute(
            "INSERT INTO screening_events (user_id, kind, rule) VALUES (%s, 'hit', %s)",
            (user_id, h.rule),
        )
    await audit(
        conn,
        user_id=user_id,
        actor="system",
        action="screening.blocked",
        entity_type="review_item",
        entity_id=str(review["id"]),
        detail={"rules": [h.rule for h in hits]},
    )
    return Admission(False, uuid.UUID(str(review["id"])), tuple(h.rule for h in hits), alert)
