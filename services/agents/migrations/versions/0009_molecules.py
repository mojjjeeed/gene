"""model registry, molecules, gates and scores

Revision ID: 0009
Revises: 0008
"""

from pathlib import Path

from alembic import op

revision = "0009"
down_revision = "0008"
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
    _run("0009_up.sql")


def downgrade() -> None:
    _run("0009_down.sql")
