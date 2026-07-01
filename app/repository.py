"""Repository layer — database CRUD for posts, settings, history, and worker logs."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .database import execute, fetch_all, fetch_one

POST_STATUSES = ("PENDENTE", "AGENDADO", "PROCESSANDO", "PUBLICADO", "ERRO")
CONTENT_STATUSES = ("Pendente", "Gerado", "IA gerado", "Aprovado")
WORKER_LOG_MAX_AGE_DAYS = 30


# ─── Posts ────────────────────────────────────────────────────────────────────


def list_posts() -> list[dict[str, Any]]:
    rows = fetch_all("SELECT * FROM posts ORDER BY updated_at DESC")
    return rows


def get_post(post_id: str) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))


def create_post(
    video_path: str,
    *,
    profile: str = "Perfil principal",
    caption: str = "",
) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    post_id = uuid.uuid4().hex
    execute(
        """INSERT INTO posts (id, video_path, profile, caption, content_status, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'Pendente', 'Pronto', ?, ?)""",
        (post_id, video_path, profile, caption, now, now),
    )
    return get_post(post_id) or {}


def update_post(post_id: str, **fields: Any) -> bool:
    if not fields:
        return False
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [post_id]
    count = execute(f"UPDATE posts SET {set_clause} WHERE id = ?", tuple(values))
    return count > 0


def delete_post(post_id: str) -> bool:
    return execute("DELETE FROM posts WHERE id = ?", (post_id,)) > 0


def add_videos_to_queue(
    video_paths: list[Path],
    *,
    profile: str = "Perfil principal",
    caption: str = "",
) -> int:
    existing = {
        row["video_path"]
        for row in fetch_all("SELECT video_path FROM posts")
    }
    added = 0
    now = datetime.now().isoformat(timespec="seconds")
    rows: list[tuple[str, str, str, str, str, str, str, str]] = []

    for video_path in video_paths:
        key = str(video_path.resolve(strict=False))
        if key in existing:
            continue
        post_id = uuid.uuid4().hex
        rows.append((post_id, key, profile, caption, "Pendente", "PENDENTE", now, now))
        existing.add(key)
        added += 1

    if rows:
        execute_many(
            """INSERT INTO posts (id, video_path, profile, caption, content_status, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
    return added


# ─── Settings ─────────────────────────────────────────────────────────────────


def get_setting(key: str, default: str = "") -> str:
    row = fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def get_all_settings() -> dict[str, str]:
    rows = fetch_all("SELECT key, value FROM settings")
    return {row["key"]: row["value"] for row in rows}


def save_settings_bulk(settings: dict[str, str]) -> None:
    from .database import get_connection
    conn = get_connection()
    try:
        conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            list(settings.items()),
        )
        conn.commit()
    finally:
        conn.close()


# ─── Content History ──────────────────────────────────────────────────────────


def save_content_history(
    video_path: str,
    *,
    title: str = "",
    caption: str = "",
    cta: str = "",
    hashtags: str = "",
    product_query: str = "",
    source: str = "local",
) -> str:
    from .database import get_connection
    conn = get_connection()
    try:
        history_id = uuid.uuid4().hex
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            """INSERT INTO content_history (id, video_path, title, caption, cta, hashtags, product_query, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (history_id, video_path, title, caption, cta, hashtags, product_query, source, now),
        )
        conn.commit()
        return history_id
    finally:
        conn.close()


def list_content_history(limit: int = 50) -> list[dict[str, Any]]:
    return fetch_all(
        "SELECT * FROM content_history ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )


# ─── Worker Logs ────────────────────────────────────────────────────────────


def save_worker_log(post_id: str, level: str, message: str) -> str:
    """Save a log entry from a worker."""
    log_id = uuid.uuid4().hex
    now = datetime.now().isoformat(timespec="seconds")
    execute(
        "INSERT INTO worker_logs (id, post_id, level, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (log_id, post_id, level.upper(), message, now),
    )
    return log_id


def list_worker_logs(
    post_id: str | None = None,
    level: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List worker logs, optionally filtered by post_id and level."""
    conditions: list[str] = []
    params: list[Any] = []

    if post_id:
        conditions.append("post_id = ?")
        params.append(post_id)
    if level:
        conditions.append("level = ?")
        params.append(level.upper())

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT * FROM worker_logs {where} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return fetch_all(sql, tuple(params))


def clean_worker_logs() -> int:
    """Remove logs older than WORKER_LOG_MAX_AGE_DAYS."""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=WORKER_LOG_MAX_AGE_DAYS)).isoformat(timespec="seconds")
    count = execute("DELETE FROM worker_logs WHERE created_at < ?", (cutoff,))
    return count


# ─── Batch History ───────────────────────────────────────────────────────────


def save_batch_history(
    upload_count: int = 0,
    process_count: int = 0,
    success_count: int = 0,
    fail_count: int = 0,
    template: str = "",
) -> str:
    """Register a processing batch."""
    batch_id = uuid.uuid4().hex
    now = datetime.now().isoformat(timespec="seconds")
    execute(
        """INSERT INTO batch_history (id, upload_count, process_count, success_count, fail_count, template, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (batch_id, upload_count, process_count, success_count, fail_count, template, now),
    )
    return batch_id


def list_batch_history(limit: int = 50) -> list[dict[str, Any]]:
    return fetch_all(
        "SELECT * FROM batch_history ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )


def get_queue_stats() -> dict[str, int]:
    """Get queue summary by status."""
    posts = fetch_all("SELECT status FROM posts")
    counts: dict[str, int] = {}
    for row in posts:
        s = row.get("status", "PENDENTE")
        counts[s] = counts.get(s, 0) + 1
    return counts


# ─── Products ─────────────────────────────────────────────────────────────────


def save_product(
    *,
    post_id: str = "",
    source: str,
    product_id: str,
    title: str,
    price: float = 0.0,
    currency: str = "BRL",
    thumbnail_url: str = "",
    permalink: str = "",
    affiliate_url: str = "",
    store_name: str = "",
    store_id: str = "",
    query_used: str = "",
) -> dict[str, Any]:
    """Save or update a product in the database."""
    now = datetime.now().isoformat(timespec="seconds")
    prod_id = uuid.uuid4().hex

    execute(
        """INSERT INTO products
           (id, post_id, source, product_id, title, price, currency,
            thumbnail_url, permalink, affiliate_url, store_name, store_id,
            query_used, selected, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (
            prod_id, post_id, source, product_id, title, price, currency,
            thumbnail_url, permalink, affiliate_url, store_name, store_id,
            query_used, now, now,
        ),
    )
    return get_product(prod_id) or {}


def get_product(prod_id: str) -> dict[str, Any] | None:
    """Get a single product by its database ID."""
    return fetch_one("SELECT * FROM products WHERE id = ?", (prod_id,))


def list_products(post_id: str = "") -> list[dict[str, Any]]:
    """List products, optionally filtered by post_id."""
    if post_id:
        return fetch_all(
            "SELECT * FROM products WHERE post_id = ? ORDER BY selected DESC, created_at DESC",
            (post_id,),
        )
    return fetch_all("SELECT * FROM products ORDER BY created_at DESC")


def delete_product(prod_id: str) -> bool:
    """Delete a product record."""
    return execute("DELETE FROM products WHERE id = ?", (prod_id,)) > 0


def select_product(prod_id: str, post_id: str) -> bool:
    """Mark a product as selected and associate it with a post."""
    now = datetime.now().isoformat(timespec="seconds")
    # Unselect all products for this post first
    execute("UPDATE products SET selected = 0 WHERE post_id = ?", (post_id,))
    # Select the chosen product
    count = execute(
        "UPDATE products SET selected = 1, post_id = ?, updated_at = ? WHERE id = ?",
        (post_id, now, prod_id),
    )
    return count > 0
