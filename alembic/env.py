"""Alembic environment configuration for VideoEditorLote.

Uses the app's database.py for engine creation and our SQLAlchemy models.
Supports both SQLite (dev) and PostgreSQL (prod) via DATABASE_URL.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, engine_from_config

# Alembic Config object
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ═══ Import our models ═══════════════════════════════════════════════════════
# This is critical for Alembic autogenerate to detect schema changes
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import Base

# Set target_metadata for autogenerate support
target_metadata = Base.metadata

# ═══ Database URL configuration ═════════════════════════════════════════════
# Read DATABASE_URL from environment (same logic as app/database.py)
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if not DATABASE_URL:
    # Default: SQLite (same path as app/database.py)
    from app.utils import writable_root
    db_path = writable_root() / "config" / "app.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{db_path}"

config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL scripts)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Needed for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (applies directly to DB)."""
    # Use connect_args for SQLite compatibility
    connect_args = {}
    if DATABASE_URL.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Needed for SQLite ALTER TABLE
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
