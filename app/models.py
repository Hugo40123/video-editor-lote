"""SQLAlchemy ORM models for VideoEditorLote.

v2.5 — All tables mapped for SQLite (dev) and PostgreSQL (prod).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _utcnow() -> datetime:
    return datetime.utcnow()


# ═══════════════════════════════════════════════════════════════════════════════
# Base
# ═══════════════════════════════════════════════════════════════════════════════


class Base(DeclarativeBase):
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Users (v2.5)
# ═══════════════════════════════════════════════════════════════════════════════


class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(20), default="operator")  # admin | operator
    active = Column(Boolean, default=True)
    created_at = Column(String(32), default=_now)
    updated_at = Column(String(32), default=_now, onupdate=_now)

    accounts = relationship("Account", back_populates="user", lazy="selectin")


class Account(Base):
    """Multi-account Instagram support (v2.5)."""

    __tablename__ = "accounts"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=True)
    name = Column(String(100), default="Perfil principal")
    ig_user_id = Column(String(100), default="")
    ig_access_token = Column(String(512), default="")
    ig_api_version = Column(String(10), default="v25.0")
    ml_affiliate_id = Column(String(100), default="")
    shopee_affiliate_id = Column(String(100), default="")
    shopee_sub_id = Column(String(100), default="")
    active = Column(Boolean, default=True)
    created_at = Column(String(32), default=_now)
    updated_at = Column(String(32), default=_now, onupdate=_now)

    user = relationship("User", back_populates="accounts", lazy="selectin")


# ═══════════════════════════════════════════════════════════════════════════════
# Posts (existing + expanded)
# ═══════════════════════════════════════════════════════════════════════════════


class Post(Base):
    __tablename__ = "posts"

    id = Column(String(32), primary_key=True, default=_uuid)
    video_path = Column(Text, nullable=False)
    profile = Column(String(100), default="Perfil principal")
    caption = Column(Text, default="")
    content_title = Column(String(255), default="")
    content_cta = Column(String(255), default="")
    content_hashtags = Column(String(500), default="")
    product_keywords = Column(String(500), default="")
    product_query = Column(String(500), default="")
    affiliate_link = Column(Text, default="")
    content_status = Column(String(32), default="Pendente")
    status = Column(String(32), default="PENDENTE", index=True)
    scheduled_for = Column(String(32), default="")
    instagram_post_id = Column(String(100), default="")
    last_error = Column(Text, default="")
    retry_count = Column(Integer, default=0)
    worker_lock = Column(String(32), default="")
    processing_started_at = Column(String(32), default="")
    published_at = Column(String(32), default="")
    product_source = Column(String(20), default="")
    product_id_ref = Column(String(100), default="")
    account_id = Column(String(32), ForeignKey("accounts.id"), nullable=True)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=True)
    created_at = Column(String(32), default=_now)
    updated_at = Column(String(32), default=_now, onupdate=_now)

    products = relationship("Product", back_populates="post", lazy="selectin")


# ═══════════════════════════════════════════════════════════════════════════════
# Content History
# ═══════════════════════════════════════════════════════════════════════════════


class ContentHistory(Base):
    __tablename__ = "content_history"

    id = Column(String(32), primary_key=True, default=_uuid)
    video_path = Column(Text, nullable=False)
    title = Column(String(255), default="")
    caption = Column(Text, default="")
    cta = Column(String(255), default="")
    hashtags = Column(String(500), default="")
    product_query = Column(String(500), default="")
    source = Column(String(32), default="local")
    post_id = Column(String(32), ForeignKey("posts.id"), nullable=True)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=True)
    created_at = Column(String(32), default=_now)


# ═══════════════════════════════════════════════════════════════════════════════
# Products
# ═══════════════════════════════════════════════════════════════════════════════


class Product(Base):
    __tablename__ = "products"

    id = Column(String(32), primary_key=True, default=_uuid)
    post_id = Column(String(32), ForeignKey("posts.id"), default="")
    source = Column(String(32), nullable=False)
    product_id = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False)
    price = Column(Float, default=0.0)
    currency = Column(String(10), default="BRL")
    thumbnail_url = Column(Text, default="")
    permalink = Column(Text, default="")
    affiliate_url = Column(Text, default="")
    store_name = Column(String(255), default="")
    store_id = Column(String(100), default="")
    query_used = Column(String(500), default="")
    selected = Column(Integer, default=0)
    created_at = Column(String(32), default=_now)
    updated_at = Column(String(32), default=_now, onupdate=_now)

    post = relationship("Post", back_populates="products", lazy="selectin")


# ═══════════════════════════════════════════════════════════════════════════════
# Settings
# ═══════════════════════════════════════════════════════════════════════════════


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False, default="")


# ═══════════════════════════════════════════════════════════════════════════════
# Worker Logs
# ═══════════════════════════════════════════════════════════════════════════════


class WorkerLog(Base):
    __tablename__ = "worker_logs"

    id = Column(String(32), primary_key=True, default=_uuid)
    post_id = Column(String(32), default="", index=True)
    level = Column(String(10), default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(String(32), default=_now, index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Batch History
# ═══════════════════════════════════════════════════════════════════════════════


class BatchHistory(Base):
    __tablename__ = "batch_history"

    id = Column(String(32), primary_key=True, default=_uuid)
    upload_count = Column(Integer, default=0)
    process_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    template = Column(String(100), default="")
    created_at = Column(String(32), default=_now)


# ═══════════════════════════════════════════════════════════════════════════════
# Metadata - used by Alembic for autogenerate
# ═══════════════════════════════════════════════════════════════════════════════

# Expose all models for Alembic
__all__ = [
    "Base",
    "User",
    "Account",
    "Post",
    "ContentHistory",
    "Product",
    "Setting",
    "WorkerLog",
    "BatchHistory",
]
