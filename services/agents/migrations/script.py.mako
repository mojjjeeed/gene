"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

from pathlib import Path

from alembic import op

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    # Raw driver call: no parameter parsing, so `%` in function bodies is left alone and a file
    # may hold many statements.
    driver = op.get_bind().connection.driver_connection
    assert driver is not None
    driver.execute((SQL_DIR / name).read_text())


def upgrade() -> None:
    _run("${up_revision}_up.sql")


def downgrade() -> None:
    _run("${up_revision}_down.sql")
