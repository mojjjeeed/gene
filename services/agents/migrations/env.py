"""Alembic environment. Migrations are plain SQL files run in order; there is no ORM metadata."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

DEFAULT_URL = "postgresql+psycopg://localhost:5544/a9"

config = context.config


def database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or os.environ.get(
        "A9_DATABASE_URL", DEFAULT_URL
    )


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("offline mode is not supported: migrations are executed as SQL files")
run_migrations_online()
