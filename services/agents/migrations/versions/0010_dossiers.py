"""dossiers, sign-offs and exports

Revision ID: 0010
Revises: 0009
"""

from pathlib import Path

from alembic import op

revision = "0010"
down_revision = "0009"
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
    _run("0010_up.sql")


def downgrade() -> None:
    _run("0010_down.sql")
