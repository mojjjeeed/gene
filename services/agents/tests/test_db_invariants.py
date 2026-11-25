"""M0.2: the invariants live in the database, so they hold for every code path."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from conftest import DbConn, as_user, seed_conversation, seed_paper, seed_user

CHUNK_COLUMNS = [
    "paper_id",
    "kind",
    "text",
    "text_hash",
    "section_path",
    "page",
    "char_start",
    "char_end",
    "parser_version",
    "extraction_model",
    "prompt_version",
    "run_id",
]


def chunk_values(paper: uuid.UUID, /, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "paper_id": paper,
        "kind": "body",
        "text": "Compound 7 inhibited EGFR with IC50 of 4 nM.",
        "text_hash": "h1",
        "section_path": ["Results", "Potency"],
        "page": 4,
        "char_start": 100,
        "char_end": 144,
        "parser_version": "grobid-0.8.1",
        "extraction_model": "claude-sonnet-5-5",
        "prompt_version": "v1",
        "run_id": uuid.uuid4(),
    }
    values.update(overrides)
    return values


def insert_chunk(conn: DbConn, values: dict[str, Any]) -> uuid.UUID:
    cols = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    row = conn.execute(
        f"INSERT INTO chunks ({cols}) VALUES ({marks}) RETURNING id", list(values.values())
    ).fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


# --- migrations -------------------------------------------------------------------------------


def test_migrations_round_trip_cleanly(
    make_database: Callable[[], str], alembic_config_for: Callable[[str], Config]
) -> None:
    url = make_database()
    cfg = alembic_config_for(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    with psycopg.connect(url) as conn:
        left = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
        ).fetchall()
        funcs = conn.execute(
            "SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public'"
        ).fetchall()
    assert left == [] and funcs == []
    command.upgrade(cfg, "head")  # and back up again


def test_core_tables_exist(db: DbConn) -> None:
    names = {
        r[0]
        for r in db.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    }
    expected = {
        "users", "projects", "conversations", "messages", "runs", "jobs", "search_plans",
        "papers", "paper_assets", "chunks", "chunk_memberships", "screening_verdicts", "audit_log",
    }  # fmt: skip
    assert expected <= names


# --- provenance envelope ----------------------------------------------------------------------


def test_complete_chunk_inserts(db: DbConn) -> None:
    insert_chunk(db, chunk_values(seed_paper(db)))


@pytest.mark.parametrize("missing", CHUNK_COLUMNS)
def test_chunk_missing_any_envelope_column_raises_not_defaults(db: DbConn, missing: str) -> None:
    values = chunk_values(seed_paper(db))
    del values[missing]
    with pytest.raises(psycopg.errors.NotNullViolation), db.transaction():
        insert_chunk(db, values)


@pytest.mark.parametrize("column", CHUNK_COLUMNS)
def test_chunk_null_envelope_column_raises(db: DbConn, column: str) -> None:
    values = chunk_values(seed_paper(db), **{column: None})
    with pytest.raises(psycopg.errors.NotNullViolation), db.transaction():
        insert_chunk(db, values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"parser_version": ""},
        {"extraction_model": ""},
        {"prompt_version": ""},
        {"section_path": []},
        {"page": 0},
        {"char_start": -1},
        {"char_start": 50, "char_end": 50},
        {"char_start": 60, "char_end": 50},
    ],
    ids=lambda o: ",".join(f"{k}={v!r}" for k, v in o.items()),
)
def test_chunk_with_empty_or_nonsensical_envelope_value_raises(
    db: DbConn, overrides: dict[str, Any]
) -> None:
    values = chunk_values(seed_paper(db), **overrides)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        insert_chunk(db, values)


# --- licence gate -----------------------------------------------------------------------------


def test_full_text_chunk_refused_when_licence_is_null(db: DbConn) -> None:
    paper = seed_paper(db, licence=None, full_text_allowed=False)
    with pytest.raises(psycopg.errors.CheckViolation, match="licence"), db.transaction():
        insert_chunk(db, chunk_values(paper))


def test_full_text_chunk_refused_when_licence_does_not_permit_storage(db: DbConn) -> None:
    paper = seed_paper(db, licence="all-rights-reserved", full_text_allowed=False)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        insert_chunk(db, chunk_values(paper))


def test_abstract_chunk_allowed_without_full_text_licence(db: DbConn) -> None:
    paper = seed_paper(db, licence=None, full_text_allowed=False)
    insert_chunk(db, chunk_values(paper, kind="abstract", section_path=["Abstract"]))


def test_paper_cannot_claim_full_text_allowed_without_a_licence(db: DbConn) -> None:
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        seed_paper(db, licence=None, full_text_allowed=True)


@pytest.mark.parametrize(
    ("licence", "allowed", "ok"),
    [(None, False, False), ("all-rights-reserved", False, False), ("CC-BY-4.0", True, True)],
)
def test_paper_asset_write_checks_licence_first(
    db: DbConn, licence: str | None, allowed: bool, ok: bool
) -> None:
    paper = seed_paper(db, licence=licence, full_text_allowed=allowed)
    sql = (
        "INSERT INTO paper_assets (paper_id, kind, object_key, sha256) "
        "VALUES (%s, 'original_pdf', 'papers/x/original.pdf', 'abc')"
    )
    if ok:
        db.execute(sql, (paper,))
    else:
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute(sql, (paper,))


# --- retraction is a flag, not a deletion -----------------------------------------------------


def test_retracted_paper_is_storable_and_flagged(db: DbConn) -> None:
    row = db.execute(
        "INSERT INTO papers (title, source, doi, retraction_status) "
        "VALUES ('R', 'crossref', '10.1/retracted', 'retracted') RETURNING retraction_status"
    ).fetchone()
    assert row == ("retracted",)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("UPDATE papers SET retraction_status = 'gone' WHERE doi = '10.1/retracted'")


# --- identity ---------------------------------------------------------------------------------


def test_doi_is_unique_and_normalised(db: DbConn) -> None:
    db.execute("INSERT INTO papers (title, source, doi) VALUES ('a', 's', '10.1/x')")
    with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
        db.execute("INSERT INTO papers (title, source, doi) VALUES ('b', 's', '10.1/x')")
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("INSERT INTO papers (title, source, doi) VALUES ('c', 's', '10.1/UPPER')")


# --- idempotent jobs --------------------------------------------------------------------------


def test_job_key_makes_a_retry_a_no_op(db: DbConn) -> None:
    user = seed_user(db)
    _, conv = seed_conversation(db, user)
    run = db.execute(
        "INSERT INTO runs (user_id, conversation_id, kind) VALUES (%s, %s, 'ingest') RETURNING id",
        (user, conv),
    ).fetchone()
    assert run is not None
    insert = (
        "INSERT INTO jobs (user_id, run_id, job_key, kind) VALUES (%s, %s, 'search:europe_pmc:abc', 'search') "
        "ON CONFLICT (job_key) DO NOTHING"
    )
    first = db.execute(insert, (user, run[0]))
    second = db.execute(insert, (user, run[0]))
    assert (first.rowcount, second.rowcount) == (1, 0)
    count = db.execute("SELECT count(*) FROM jobs").fetchone()
    assert count == (1,)


# --- search plans -----------------------------------------------------------------------------


def test_plan_approval_needs_both_fields_and_the_owner(db: DbConn) -> None:
    user, other = seed_user(db), seed_user(db)
    _, conv = seed_conversation(db, user)
    base = "INSERT INTO search_plans (user_id, conversation_id, version, plan{}) VALUES (%s, %s, %s, '{{}}'{})"
    db.execute(base.format("", ""), (user, conv, 1))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(base.format(", approved_by", ", %s"), (user, conv, 2, user))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(base.format(", approved_by, approved_at", ", %s, now()"), (user, conv, 2, other))
    db.execute(base.format(", approved_by, approved_at", ", %s, now()"), (user, conv, 2, user))
    with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
        db.execute(base.format("", ""), (user, conv, 2))


# --- audit log --------------------------------------------------------------------------------


def test_audit_log_is_append_only_even_for_the_owner(db: DbConn) -> None:
    db.execute(
        "INSERT INTO audit_log (actor, action, entity_type) VALUES ('system', 'run.created', 'run')"
    )
    for stmt in ("UPDATE audit_log SET actor = 'x'", "DELETE FROM audit_log", "TRUNCATE audit_log"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="append-only"):
            with db.transaction():
                db.execute(stmt)


# --- screening verdicts -----------------------------------------------------------------------


def test_user_override_is_a_second_row_not_an_overwrite(db: DbConn) -> None:
    user = seed_user(db)
    _, conv = seed_conversation(db, user)
    paper = seed_paper(db)
    ins = (
        "INSERT INTO screening_verdicts (user_id, conversation_id, paper_id, verdict, reason, decided_by, model) "
        "VALUES (%s, %s, %s, %s, 'because', %s, %s)"
    )
    db.execute(ins, (user, conv, paper, "exclude", "model", "haiku"))
    db.execute(ins, (user, conv, paper, "include", "user", None))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(ins, (user, conv, seed_paper(db), "include", "model", None))
    assert db.execute("SELECT count(*) FROM screening_verdicts").fetchone() == (2,)


# --- row-level security -----------------------------------------------------------------------


def test_rls_is_enabled_and_forced_on_every_user_scoped_table(db: DbConn) -> None:
    rows = db.execute(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relnamespace = 'public'::regnamespace AND relname = ANY(%s)",
        (
            [
                "users", "projects", "conversations", "messages", "runs", "jobs", "search_plans",
                "chunk_memberships", "screening_verdicts", "audit_log", "chunks", "paper_assets",
            ],
        ),
    ).fetchall()  # fmt: skip
    assert len(rows) == 12
    assert all(r[1] and r[2] for r in rows), rows


def test_a_user_sees_only_their_own_rows(db: DbConn) -> None:
    alice, bob = seed_user(db), seed_user(db)
    seed_conversation(db, alice)
    seed_conversation(db, bob)
    with as_user(db, alice) as c:
        assert c.execute("SELECT count(*) FROM projects").fetchone() == (1,)
        assert c.execute("SELECT count(*) FROM conversations").fetchone() == (1,)
        assert c.execute("SELECT count(*) FROM users").fetchone() == (1,)
    with as_user(db, bob) as c:
        assert c.execute(
            "SELECT count(*) FROM projects WHERE user_id = %s", (alice,)
        ).fetchone() == (0,)


def test_no_user_set_fails_closed(db: DbConn) -> None:
    seed_conversation(db, seed_user(db))
    with as_user(db, None) as c:
        assert c.execute("SELECT count(*) FROM projects").fetchone() == (0,)
        assert c.execute("SELECT count(*) FROM users").fetchone() == (0,)


def test_a_user_cannot_write_rows_for_someone_else(db: DbConn) -> None:
    alice, bob = seed_user(db), seed_user(db)
    with as_user(db, alice) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), c.transaction():
            c.execute("INSERT INTO projects (user_id, name) VALUES (%s, 'stolen')", (bob,))
        c.execute("INSERT INTO projects (user_id, name) VALUES (%s, 'mine')", (alice,))


def test_a_user_cannot_attach_rows_to_someone_elses_conversation(db: DbConn) -> None:
    alice, bob = seed_user(db), seed_user(db)
    _, bobs_conversation = seed_conversation(db, bob)
    with as_user(db, alice) as c:
        with pytest.raises(psycopg.errors.ForeignKeyViolation), c.transaction():
            c.execute(
                "INSERT INTO messages (user_id, conversation_id, role, content) "
                "VALUES (%s, %s, 'user', 'hi')",
                (alice, bobs_conversation),
            )


def test_user_cannot_update_or_delete_other_users_rows(db: DbConn) -> None:
    alice, bob = seed_user(db), seed_user(db)
    seed_conversation(db, bob)
    with as_user(db, alice) as c:
        assert c.execute("UPDATE projects SET name = 'x'").rowcount == 0
        assert c.execute("DELETE FROM projects").rowcount == 0
    assert db.execute("SELECT count(*) FROM projects WHERE name = 'x'").fetchone() == (0,)


def test_chunks_are_reachable_only_through_the_users_own_membership(db: DbConn) -> None:
    alice, bob = seed_user(db), seed_user(db)
    _, alice_conv = seed_conversation(db, alice)
    _, bob_conv = seed_conversation(db, bob)
    paper = seed_paper(db)
    shared = insert_chunk(db, chunk_values(paper, text_hash="shared"))
    private = insert_chunk(db, chunk_values(paper, char_start=500, char_end=560, text_hash="p"))
    for user, conv, chunk in [(alice, alice_conv, shared), (bob, bob_conv, shared), (alice, alice_conv, private)]:  # fmt: skip
        db.execute(
            "INSERT INTO chunk_memberships (user_id, conversation_id, chunk_id) VALUES (%s, %s, %s)",
            (user, conv, chunk),
        )
    other_paper = seed_paper(db)
    unreachable = insert_chunk(db, chunk_values(other_paper))
    with as_user(db, alice) as c:
        seen = {r[0] for r in c.execute("SELECT id FROM chunks")}
        assert seen == {shared, private}
        assert unreachable not in seen
        assert c.execute("SELECT count(*) FROM paper_assets").fetchone() == (0,)
    with as_user(db, bob) as c:
        assert {r[0] for r in c.execute("SELECT id FROM chunks")} == {shared}
    with as_user(db, None) as c:
        assert c.execute("SELECT count(*) FROM chunks").fetchone() == (0,)


def test_request_role_cannot_write_global_tables(db: DbConn) -> None:
    alice = seed_user(db)
    paper = seed_paper(db)
    with as_user(db, alice) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), c.transaction():
            c.execute("INSERT INTO papers (title, source) VALUES ('x', 'y')")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), c.transaction():
            insert_chunk(c, chunk_values(paper))


def test_worker_role_can_ingest_on_behalf_of_a_user(db: DbConn) -> None:
    alice = seed_user(db)
    _, conv = seed_conversation(db, alice)
    with as_user(db, None, role="a9_worker") as c:
        paper = seed_paper(c)
        chunk = insert_chunk(c, chunk_values(paper))
        c.execute(
            "INSERT INTO chunk_memberships (user_id, conversation_id, chunk_id) VALUES (%s, %s, %s)",
            (alice, conv, chunk),
        )
    with as_user(db, alice) as c:
        assert c.execute("SELECT count(*) FROM chunks").fetchone() == (1,)


def test_users_can_read_and_append_their_own_audit_entries_only(db: DbConn) -> None:
    alice, bob = seed_user(db), seed_user(db)
    with as_user(db, alice) as c:
        c.execute(
            "INSERT INTO audit_log (user_id, actor, action, entity_type) VALUES (%s, 'user', 'plan.approved', 'plan')",
            (alice,),
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege), c.transaction():
            c.execute(
                "INSERT INTO audit_log (user_id, actor, action, entity_type) VALUES (%s, 'user', 'x', 'y')",
                (bob,),
            )
        assert c.execute("SELECT count(*) FROM audit_log").fetchone() == (1,)
    with as_user(db, bob) as c:
        assert c.execute("SELECT count(*) FROM audit_log").fetchone() == (0,)
