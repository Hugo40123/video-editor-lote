"""Database setup and connection management.

Supports custom database URLs for future cloud migration (PostgreSQL, etc.)
via environment variable DATABASE_URL. Defaults to local SQLite file.

v2.3: Added worker_logs table, migrated post statuses, added retry/schedule columns.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from .utils import writable_root

DB_FILENAME = "app.db"

# Allow overriding the database location via environment variable
# For future use: DATABASE_URL=postgresql://user:pass@host/db
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Worker lock timeout in seconds
WORKER_LOCK_TIMEOUT = 600


def db_path() -> Path:
    return writable_root() / "config" / DB_FILENAME


def get_connection() -> sqlite3.Connection | Any:
    """Get a new database connection.

    Uses DATABASE_URL env var if set (for future cloud migration).
    Defaults to local SQLite with WAL mode for performance.
    """
    db_url = DATABASE_URL.strip()
    if db_url:
        # Future: Use SQLAlchemy or asyncpg for PostgreSQL/etc.
        raise RuntimeError(
            f"Banco de dados remoto configurado, mas ainda nao implementado. "
            f"URL: {db_url[:50]}... Use variavel DATABASE_URL para configurar."
        )

    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_database() -> None:
    """Create tables if they don't exist. Runs migrations for v2.3."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS posts (
                id              TEXT PRIMARY KEY,
                video_path      TEXT NOT NULL,
                profile         TEXT DEFAULT 'Perfil principal',
                caption         TEXT DEFAULT '',
                content_title   TEXT DEFAULT '',
                content_cta     TEXT DEFAULT '',
                content_hashtags TEXT DEFAULT '',
                product_keywords TEXT DEFAULT '',
                product_query   TEXT DEFAULT '',
                affiliate_link  TEXT DEFAULT '',
                content_status  TEXT DEFAULT 'Pendente',
                status          TEXT DEFAULT 'PENDENTE',
                scheduled_for   TEXT DEFAULT '',
                instagram_post_id TEXT DEFAULT '',
                last_error      TEXT DEFAULT '',
                retry_count     INTEGER DEFAULT 0,
                worker_lock     TEXT DEFAULT '',
                processing_started_at TEXT DEFAULT '',
                published_at    TEXT DEFAULT '',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS content_history (
                id          TEXT PRIMARY KEY,
                video_path  TEXT NOT NULL,
                title       TEXT DEFAULT '',
                caption     TEXT DEFAULT '',
                cta         TEXT DEFAULT '',
                hashtags    TEXT DEFAULT '',
                product_query TEXT DEFAULT '',
                source      TEXT DEFAULT 'local',
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS worker_logs (
                id          TEXT PRIMARY KEY,
                post_id     TEXT DEFAULT '',
                level       TEXT DEFAULT 'INFO',
                message     TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS batch_history (
                id          TEXT PRIMARY KEY,
                upload_count INTEGER DEFAULT 0,
                process_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count  INTEGER DEFAULT 0,
                template    TEXT DEFAULT '',
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id              TEXT PRIMARY KEY,
                post_id         TEXT DEFAULT '',
                source          TEXT NOT NULL,
                product_id      TEXT NOT NULL,
                title           TEXT NOT NULL,
                price           REAL DEFAULT 0,
                currency        TEXT DEFAULT 'BRL',
                thumbnail_url   TEXT DEFAULT '',
                permalink       TEXT DEFAULT '',
                affiliate_url   TEXT DEFAULT '',
                store_name      TEXT DEFAULT '',
                store_id        TEXT DEFAULT '',
                query_used      TEXT DEFAULT '',
                selected        INTEGER DEFAULT 0,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );
        """)

        # Migration v2.4: Add new columns if missing
        _migrate_add_column(conn, "posts", "product_source", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "posts", "product_id_ref", "TEXT DEFAULT ''")

        # Migration v2.3: Add new columns if missing (idempotent)
        _migrate_add_column(conn, "posts", "retry_count", "INTEGER DEFAULT 0")
        _migrate_add_column(conn, "posts", "worker_lock", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "posts", "processing_started_at", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "posts", "published_at", "TEXT DEFAULT ''")

        # Migration v2.3: Update old status values to new format
        conn.execute("UPDATE posts SET status = 'PENDENTE' WHERE status = 'Pronto'")
        conn.execute("UPDATE posts SET status = 'AGENDADO' WHERE status = 'Agendado'")
        conn.execute("UPDATE posts SET status = 'PUBLICADO' WHERE status = 'Postado'")
        conn.execute("UPDATE posts SET status = 'ERRO' WHERE status = 'Erro'")

        conn.commit()
    finally:
        conn.close()


def _migrate_add_column(conn: sqlite3.Connection, table: str, column: str, col_def: str) -> None:
    """Add a column if it doesn't exist (idempotent migration)."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
    except sqlite3.OperationalError:
        pass  # Column already exists


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    """Execute a query and return the first row as a dict."""
    conn = get_connection()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Execute a query and return all rows as a list of dicts."""
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    """Execute a single statement and return rowcount."""
    conn = get_connection()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def execute_many(sql: str, params_list: list[tuple[Any, ...]]) -> int:
    """Execute a statement for multiple parameter sets."""
    conn = get_connection()
    try:
        cursor = conn.executemany(sql, params_list)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
