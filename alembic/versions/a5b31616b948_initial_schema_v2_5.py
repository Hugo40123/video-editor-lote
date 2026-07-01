"""v2.5 — Add new tables and columns for PostgreSQL migration support.

This migration adds:
- users, accounts tables (handled by create_all, but we create them here for PostgreSQL)
- account_id, user_id columns to posts
- post_id, user_id columns to content_history
- Indexes for performance

Revision ID: a5b31616b948
Revises:
Create Date: 2026-07-01 13:58:15.906164
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a5b31616b948"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ─── Helper: add column if not exists ─────────────────────────────────
    conn = op.get_bind()
    dialect = conn.dialect.name

    def _has_column(table: str, column: str) -> bool:
        if dialect == "sqlite":
            result = conn.execute(
                sa.text(f"PRAGMA table_info({table})")
            ).fetchall()
            return any(row[1] == column for row in result)
        # PostgreSQL: check information_schema
        result = conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='{table}' AND column_name='{column}'"
            )
        ).fetchone()
        return result is not None

    def _has_table(table: str) -> bool:
        if dialect == "sqlite":
            result = conn.execute(
                sa.text(
                    "SELECT name FROM sqlite_master "
                    f"WHERE type='table' AND name='{table}'"
                )
            ).fetchone()
            return result is not None
        result = conn.execute(
            sa.text(
                "SELECT tablename FROM pg_catalog.pg_tables "
                f"WHERE tablename='{table}'"
            )
        ).fetchone()
        return result is not None

    def _has_index(index: str) -> bool:
        if dialect == "sqlite":
            result = conn.execute(
                sa.text(
                    "SELECT name FROM sqlite_master "
                    f"WHERE type='index' AND name='{index}'"
                )
            ).fetchone()
            return result is not None
        result = conn.execute(
            sa.text(
                "SELECT indexname FROM pg_catalog.pg_indexes "
                f"WHERE indexname='{index}'"
            )
        ).fetchone()
        return result is not None

    # ─── Create new tables if not exist ───────────────────────────────────

    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("username", sa.String(100), unique=True, nullable=False),
            sa.Column("email", sa.String(255), nullable=True, unique=True),
            sa.Column("password_hash", sa.String(255), nullable=True),
            sa.Column("role", sa.String(20), server_default="operator"),
            sa.Column("active", sa.Boolean(), server_default=sa.text("1")),
            sa.Column("created_at", sa.String(32), nullable=True),
            sa.Column("updated_at", sa.String(32), nullable=True),
        )

    if not _has_table("accounts"):
        op.create_table(
            "accounts",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), nullable=True),
            sa.Column("name", sa.String(100), server_default="Perfil principal"),
            sa.Column("ig_user_id", sa.String(100), server_default=""),
            sa.Column("ig_access_token", sa.String(512), server_default=""),
            sa.Column("ig_api_version", sa.String(10), server_default="v25.0"),
            sa.Column("ml_affiliate_id", sa.String(100), server_default=""),
            sa.Column("shopee_affiliate_id", sa.String(100), server_default=""),
            sa.Column("shopee_sub_id", sa.String(100), server_default=""),
            sa.Column("active", sa.Boolean(), server_default=sa.text("1")),
            sa.Column("created_at", sa.String(32), nullable=True),
            sa.Column("updated_at", sa.String(32), nullable=True),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], name="fk_accounts_user_id"
            ),
        )

    # ─── Add columns to posts ─────────────────────────────────────────────

    if not _has_column("posts", "account_id"):
        with op.batch_alter_table("posts") as batch_op:
            batch_op.add_column(
                sa.Column("account_id", sa.String(32), nullable=True)
            )

    if not _has_column("posts", "user_id"):
        with op.batch_alter_table("posts") as batch_op:
            batch_op.add_column(
                sa.Column("user_id", sa.String(32), nullable=True)
            )

    if not _has_index("ix_posts_status"):
        with op.batch_alter_table("posts") as batch_op:
            batch_op.create_index("ix_posts_status", ["status"])

    # ─── Add columns to content_history ───────────────────────────────────

    if not _has_column("content_history", "post_id"):
        with op.batch_alter_table("content_history") as batch_op:
            batch_op.add_column(
                sa.Column("post_id", sa.String(32), nullable=True)
            )

    if not _has_column("content_history", "user_id"):
        with op.batch_alter_table("content_history") as batch_op:
            batch_op.add_column(
                sa.Column("user_id", sa.String(32), nullable=True)
            )

    # ─── Add indexes to worker_logs ───────────────────────────────────────

    if not _has_index("ix_worker_logs_created_at"):
        with op.batch_alter_table("worker_logs") as batch_op:
            batch_op.create_index(
                "ix_worker_logs_created_at", ["created_at"]
            )

    if not _has_index("ix_worker_logs_post_id"):
        with op.batch_alter_table("worker_logs") as batch_op:
            batch_op.create_index("ix_worker_logs_post_id", ["post_id"])


def downgrade() -> None:
    """Downgrade schema — reverse all changes."""

    conn = op.get_bind()
    dialect = conn.dialect.name

    def _has_column(table: str, column: str) -> bool:
        if dialect == "sqlite":
            result = conn.execute(
                sa.text(f"PRAGMA table_info({table})")
            ).fetchall()
            return any(row[1] == column for row in result)
        result = conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='{table}' AND column_name='{column}'"
            )
        ).fetchone()
        return result is not None

    # Remove new columns
    if _has_column("content_history", "post_id"):
        with op.batch_alter_table("content_history") as batch_op:
            batch_op.drop_column("post_id")
    if _has_column("content_history", "user_id"):
        with op.batch_alter_table("content_history") as batch_op:
            batch_op.drop_column("user_id")

    if _has_column("posts", "account_id"):
        with op.batch_alter_table("posts") as batch_op:
            batch_op.drop_column("account_id")
    if _has_column("posts", "user_id"):
        with op.batch_alter_table("posts") as batch_op:
            batch_op.drop_column("user_id")

    # Drop indexes
    with op.batch_alter_table("posts") as batch_op:
        batch_op.drop_index("ix_posts_status")
    with op.batch_alter_table("worker_logs") as batch_op:
        batch_op.drop_index("ix_worker_logs_created_at")
        batch_op.drop_index("ix_worker_logs_post_id")

    # Drop new tables
    if dialect != "sqlite":
        op.drop_table("accounts")
        op.drop_table("users")
