"""Database setup and connection management.

Supports SQLite (development) and PostgreSQL (production) via DATABASE_URL.

v2.5 — Refactored to use SQLAlchemy ORM with Alembic migrations.
       SQLite is the default (dev), PostgreSQL when DATABASE_URL is set (prod).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base
from .utils import writable_root

DB_FILENAME = "app.db"

# Allow overriding the database location via environment variable
# SQLite (dev):   DATABASE_URL="" or unset → local SQLite file
# PostgreSQL (prod): DATABASE_URL=postgresql://user:pass@host:5432/dbname
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Worker lock timeout in seconds
WORKER_LOCK_TIMEOUT = 600

# Global engine and session factory
_engine: Any = None
_session_factory: Any = None


def db_path() -> Path:
    """Path to the local SQLite database file."""
    return writable_root() / "config" / DB_FILENAME


def _is_sqlite() -> bool:
    """Check if we're using SQLite (default/dev)."""
    return not DATABASE_URL


def _is_postgres() -> bool:
    """Check if we're using PostgreSQL (prod)."""
    return DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres://")


def _build_sqlite_url() -> str:
    """Build SQLite connection URL."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def _build_engine() -> Any:
    """Create the SQLAlchemy engine based on DATABASE_URL."""
    global DATABASE_URL
    url = DATABASE_URL if DATABASE_URL else _build_sqlite_url()

    if _is_sqlite():
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
            pool_pre_ping=True,
        )
        # Enable WAL mode and foreign keys for SQLite
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(text("PRAGMA busy_timeout=5000"))
            conn.commit()
    else:
        engine = create_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        # Verify connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    return engine


def get_engine():
    """Get or create the SQLAlchemy engine (singleton)."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory():
    """Get or create the session factory (singleton)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine())
    return _session_factory


def get_session() -> Session:
    """Get a new SQLAlchemy session."""
    return get_session_factory()()


def init_database() -> None:
    """Create all tables if they don't exist and run migrations.

    Uses SQLAlchemy Base.metadata.create_all for table creation.
    Runs legacy migrations for existing SQLite databases.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)

    # Run legacy migrations for SQLite (existing data migration)
    if _is_sqlite():
        _run_legacy_migrations()


def _run_legacy_migrations() -> None:
    """Run idempotent migrations for existing SQLite databases."""
    conn = get_session()
    try:
        # Migration v2.3: Add new columns if missing (raw SQL for safety)
        _migrate_sqlite_add_column(conn, "posts", "retry_count", "INTEGER DEFAULT 0")
        _migrate_sqlite_add_column(conn, "posts", "worker_lock", "TEXT DEFAULT ''")
        _migrate_sqlite_add_column(conn, "posts", "processing_started_at", "TEXT DEFAULT ''")
        _migrate_sqlite_add_column(conn, "posts", "published_at", "TEXT DEFAULT ''")

        # Migration v2.4: Add product columns
        _migrate_sqlite_add_column(conn, "posts", "product_source", "TEXT DEFAULT ''")
        _migrate_sqlite_add_column(conn, "posts", "product_id_ref", "TEXT DEFAULT ''")

        # Migration v2.3: Update old status values to new format
        conn.execute(text("UPDATE posts SET status = 'PENDENTE' WHERE status = 'Pronto'"))
        conn.execute(text("UPDATE posts SET status = 'AGENDADO' WHERE status = 'Agendado'"))
        conn.execute(text("UPDATE posts SET status = 'PUBLICADO' WHERE status = 'Postado'"))
        conn.execute(text("UPDATE posts SET status = 'ERRO' WHERE status = 'Erro'"))
        conn.commit()
    finally:
        conn.close()


def _migrate_sqlite_add_column(conn: Session, table: str, column: str, col_def: str) -> None:
    """Add a column to SQLite table if it doesn't exist (idempotent)."""
    try:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
        conn.commit()
    except Exception:
        conn.rollback()  # Column already exists


def dispose_engine() -> None:
    """Dispose the engine (useful for testing/cleanup)."""
    global _engine, _session_factory
    if _engine:
        _engine.dispose()
    _engine = None
    _session_factory = None


# ═══════════════════════════════════════════════════════════════════════════════
# Compatibility layer — keep old-style helpers for smooth migration
# ═══════════════════════════════════════════════════════════════════════════════


def get_connection():
    """Backward-compatible: return SQLAlchemy session.

    Previously returned sqlite3.Connection. Now returns Session.
    """
    return get_session()


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    """Execute a raw SQL query and return the first row as a dict."""
    conn = get_session()
    try:
        result = conn.execute(text(sql), params)
        row = result.fetchone()
        if row is None:
            return None
        return dict(row._mapping)
    finally:
        conn.close()


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Execute a raw SQL query and return all rows as a list of dicts."""
    conn = get_session()
    try:
        result = conn.execute(text(sql), params)
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]
    finally:
        conn.close()


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    """Execute a single raw SQL statement and return rowcount."""
    conn = get_session()
    try:
        result = conn.execute(text(sql), params)
        conn.commit()
        return result.rowcount
    finally:
        conn.close()


def execute_many(sql: str, params_list: list[tuple[Any, ...]]) -> int:
    """Execute a statement for multiple parameter sets."""
    conn = get_session()
    try:
        count = 0
        for params in params_list:
            result = conn.execute(text(sql), params)
            count += result.rowcount
        conn.commit()
        return count
    finally:
        conn.close()
