"""Repository layer — database CRUD using SQLAlchemy ORM.

v2.5 — Refactored from raw SQL to SQLAlchemy ORM.
Supports both SQLite (dev) and PostgreSQL (prod) transparently.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, update

from .database import execute, fetch_all, fetch_one, get_session
from .models import (
    Account,
    BatchHistory,
    ContentHistory,
    Post,
    Product,
    Setting,
    User,
    WorkerLog,
)

POST_STATUSES = ("PENDENTE", "AGENDADO", "PROCESSANDO", "PUBLICADO", "ERRO")
CONTENT_STATUSES = ("Pendente", "Gerado", "IA gerado", "Aprovado")
WORKER_LOG_MAX_AGE_DAYS = 30


# ═══════════════════════════════════════════════════════════════════════════════
# Posts
# ═══════════════════════════════════════════════════════════════════════════════


def list_posts() -> list[dict[str, Any]]:
    """List all posts ordered by updated_at DESC."""
    session = get_session()
    try:
        posts = session.query(Post).order_by(Post.updated_at.desc()).all()
        return [_post_to_dict(p) for p in posts]
    finally:
        session.close()


def get_post(post_id: str) -> dict[str, Any] | None:
    """Get a single post by ID."""
    session = get_session()
    try:
        post = session.query(Post).filter(Post.id == post_id).first()
        return _post_to_dict(post) if post else None
    finally:
        session.close()


def create_post(
    video_path: str,
    *,
    profile: str = "Perfil principal",
    caption: str = "",
) -> dict[str, Any]:
    """Create a new post and return it."""
    session = get_session()
    try:
        post = Post(
            video_path=video_path,
            profile=profile,
            caption=caption,
            content_status="Pendente",
            status="PENDENTE",
        )
        session.add(post)
        session.commit()
        return _post_to_dict(post)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_post(post_id: str, **fields: Any) -> bool:
    """Update a post's fields. Returns True if updated."""
    session = get_session()
    try:
        post = session.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False
        for key, value in fields.items():
            if hasattr(post, key):
                setattr(post, key, value)
        post.updated_at = datetime.now().isoformat(timespec="seconds")
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def delete_post(post_id: str) -> bool:
    """Delete a post by ID."""
    session = get_session()
    try:
        post = session.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False
        session.delete(post)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def add_videos_to_queue(
    video_paths: list[Path],
    *,
    profile: str = "Perfil principal",
    caption: str = "",
) -> int:
    """Add multiple videos to the post queue, avoiding duplicates."""
    session = get_session()
    try:
        # Get existing paths
        existing = {
            row[0]
            for row in session.query(Post.video_path).all()
        }
        added = 0
        now = datetime.now().isoformat(timespec="seconds")

        for video_path in video_paths:
            key = str(video_path.resolve(strict=False))
            if key in existing:
                continue
            post = Post(
                video_path=key,
                profile=profile,
                caption=caption,
                content_status="Pendente",
                status="PENDENTE",
            )
            session.add(post)
            existing.add(key)
            added += 1

        if added:
            session.commit()
        return added
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _post_to_dict(post: Post) -> dict[str, Any]:
    """Convert a Post ORM object to a dict."""
    return {
        "id": post.id,
        "video_path": post.video_path,
        "profile": post.profile,
        "caption": post.caption,
        "content_title": post.content_title,
        "content_cta": post.content_cta,
        "content_hashtags": post.content_hashtags,
        "product_keywords": post.product_keywords,
        "product_query": post.product_query,
        "affiliate_link": post.affiliate_link,
        "content_status": post.content_status,
        "status": post.status,
        "scheduled_for": post.scheduled_for,
        "instagram_post_id": post.instagram_post_id,
        "last_error": post.last_error,
        "retry_count": post.retry_count,
        "worker_lock": post.worker_lock,
        "processing_started_at": post.processing_started_at,
        "published_at": post.published_at,
        "product_source": post.product_source,
        "product_id_ref": post.product_id_ref,
        "account_id": post.account_id,
        "user_id": post.user_id,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Settings
# ═══════════════════════════════════════════════════════════════════════════════


def get_setting(key: str, default: str = "") -> str:
    """Get a setting value by key."""
    session = get_session()
    try:
        setting = session.query(Setting).filter(Setting.key == key).first()
        return setting.value if setting else default
    finally:
        session.close()


def set_setting(key: str, value: str) -> None:
    """Set a setting value (upsert)."""
    session = get_session()
    try:
        setting = session.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = value
        else:
            session.add(Setting(key=key, value=value))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_all_settings() -> dict[str, str]:
    """Get all settings as a dict."""
    session = get_session()
    try:
        rows = session.query(Setting).all()
        return {row.key: row.value for row in rows}
    finally:
        session.close()


def save_settings_bulk(settings: dict[str, str]) -> None:
    """Save multiple settings at once (upsert)."""
    session = get_session()
    try:
        for key, value in settings.items():
            setting = session.query(Setting).filter(Setting.key == key).first()
            if setting:
                setting.value = value
            else:
                session.add(Setting(key=key, value=value))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Content History
# ═══════════════════════════════════════════════════════════════════════════════


def save_content_history(
    video_path: str,
    *,
    title: str = "",
    caption: str = "",
    cta: str = "",
    hashtags: str = "",
    product_query: str = "",
    source: str = "local",
    post_id: str = "",
) -> str:
    """Save a content history entry."""
    session = get_session()
    try:
        entry = ContentHistory(
            video_path=video_path,
            title=title,
            caption=caption,
            cta=cta,
            hashtags=hashtags,
            product_query=product_query,
            source=source,
            post_id=post_id,
        )
        session.add(entry)
        session.commit()
        return entry.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_content_history(limit: int = 50) -> list[dict[str, Any]]:
    """List content history entries."""
    session = get_session()
    try:
        entries = (
            session.query(ContentHistory)
            .order_by(ContentHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": e.id,
                "video_path": e.video_path,
                "title": e.title,
                "caption": e.caption,
                "cta": e.cta,
                "hashtags": e.hashtags,
                "product_query": e.product_query,
                "source": e.source,
                "post_id": e.post_id,
                "user_id": e.user_id,
                "created_at": e.created_at,
            }
            for e in entries
        ]
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Worker Logs
# ═══════════════════════════════════════════════════════════════════════════════


def save_worker_log(post_id: str, level: str, message: str) -> str:
    """Save a worker log entry."""
    session = get_session()
    try:
        log = WorkerLog(
            post_id=post_id,
            level=level.upper(),
            message=message,
        )
        session.add(log)
        session.commit()
        return log.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_worker_logs(
    post_id: str | None = None,
    level: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List worker logs with optional filters."""
    session = get_session()
    try:
        query = session.query(WorkerLog)
        if post_id:
            query = query.filter(WorkerLog.post_id == post_id)
        if level:
            query = query.filter(WorkerLog.level == level.upper())
        logs = (
            query
            .order_by(WorkerLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": log.id,
                "post_id": log.post_id,
                "level": log.level,
                "message": log.message,
                "created_at": log.created_at,
            }
            for log in logs
        ]
    finally:
        session.close()


def clean_worker_logs() -> int:
    """Remove logs older than WORKER_LOG_MAX_AGE_DAYS."""
    session = get_session()
    try:
        cutoff = (datetime.now() - timedelta(days=WORKER_LOG_MAX_AGE_DAYS)).isoformat(
            timespec="seconds"
        )
        deleted = (
            session.query(WorkerLog)
            .filter(WorkerLog.created_at < cutoff)
            .delete()
        )
        session.commit()
        return deleted
    except Exception:
        session.rollback()
        return 0
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Batch History
# ═══════════════════════════════════════════════════════════════════════════════


def save_batch_history(
    upload_count: int = 0,
    process_count: int = 0,
    success_count: int = 0,
    fail_count: int = 0,
    template: str = "",
) -> str:
    """Register a processing batch."""
    session = get_session()
    try:
        batch = BatchHistory(
            upload_count=upload_count,
            process_count=process_count,
            success_count=success_count,
            fail_count=fail_count,
            template=template,
        )
        session.add(batch)
        session.commit()
        return batch.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_batch_history(limit: int = 50) -> list[dict[str, Any]]:
    """List batch history entries."""
    session = get_session()
    try:
        batches = (
            session.query(BatchHistory)
            .order_by(BatchHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": b.id,
                "upload_count": b.upload_count,
                "process_count": b.process_count,
                "success_count": b.success_count,
                "fail_count": b.fail_count,
                "template": b.template,
                "created_at": b.created_at,
            }
            for b in batches
        ]
    finally:
        session.close()


def get_queue_stats() -> dict[str, int]:
    """Get queue summary by status."""
    session = get_session()
    try:
        rows = (
            session.query(Post.status, func.count(Post.id))
            .group_by(Post.status)
            .all()
        )
        counts: dict[str, int] = {}
        for status, count in rows:
            counts[status] = count
        return counts
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Products
# ═══════════════════════════════════════════════════════════════════════════════


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
    """Save a new product."""
    session = get_session()
    try:
        product = Product(
            post_id=post_id,
            source=source,
            product_id=product_id,
            title=title,
            price=price,
            currency=currency,
            thumbnail_url=thumbnail_url,
            permalink=permalink,
            affiliate_url=affiliate_url,
            store_name=store_name,
            store_id=store_id,
            query_used=query_used,
        )
        session.add(product)
        session.commit()
        return _product_to_dict(product)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_product(prod_id: str) -> dict[str, Any] | None:
    """Get a product by its database ID."""
    session = get_session()
    try:
        product = session.query(Product).filter(Product.id == prod_id).first()
        return _product_to_dict(product) if product else None
    finally:
        session.close()


def list_products(post_id: str = "") -> list[dict[str, Any]]:
    """List products, optionally filtered by post_id."""
    session = get_session()
    try:
        query = session.query(Product)
        if post_id:
            query = query.filter(Product.post_id == post_id)
        products = (
            query
            .order_by(Product.selected.desc(), Product.created_at.desc())
            .all()
        )
        return [_product_to_dict(p) for p in products]
    finally:
        session.close()


def delete_product(prod_id: str) -> bool:
    """Delete a product record."""
    session = get_session()
    try:
        product = session.query(Product).filter(Product.id == prod_id).first()
        if not product:
            return False
        session.delete(product)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def select_product(prod_id: str, post_id: str) -> bool:
    """Mark a product as selected and associate it with a post."""
    session = get_session()
    try:
        # Unselect all products for this post
        (
            session.query(Product)
            .filter(Product.post_id == post_id)
            .update({"selected": 0})
        )
        # Select the chosen product
        product = session.query(Product).filter(Product.id == prod_id).first()
        if not product:
            return False
        product.selected = 1
        product.post_id = post_id
        product.updated_at = datetime.now().isoformat(timespec="seconds")
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def _product_to_dict(product: Product) -> dict[str, Any]:
    """Convert a Product ORM object to a dict."""
    return {
        "id": product.id,
        "post_id": product.post_id,
        "source": product.source,
        "product_id": product.product_id,
        "title": product.title,
        "price": product.price,
        "currency": product.currency,
        "thumbnail_url": product.thumbnail_url,
        "permalink": product.permalink,
        "affiliate_url": product.affiliate_url,
        "store_name": product.store_name,
        "store_id": product.store_id,
        "query_used": product.query_used,
        "selected": product.selected,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Users (v2.5)
# ═══════════════════════════════════════════════════════════════════════════════


def create_user(
    username: str,
    *,
    email: str = "",
    password_hash: str = "",
    role: str = "operator",
) -> dict[str, Any]:
    """Create a new user."""
    session = get_session()
    try:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        session.add(user)
        session.commit()
        return _user_to_dict(user)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_user(user_id: str) -> dict[str, Any] | None:
    """Get a user by ID."""
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        return _user_to_dict(user) if user else None
    finally:
        session.close()


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Get a user by username."""
    session = get_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        return _user_to_dict(user) if user else None
    finally:
        session.close()


def list_users() -> list[dict[str, Any]]:
    """List all users."""
    session = get_session()
    try:
        users = session.query(User).order_by(User.created_at.desc()).all()
        return [_user_to_dict(u) for u in users]
    finally:
        session.close()


def _user_to_dict(user: User) -> dict[str, Any]:
    """Convert a User ORM object to a dict."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "active": user.active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Accounts (v2.5)
# ═══════════════════════════════════════════════════════════════════════════════


def create_account(
    *,
    user_id: str = "",
    name: str = "Perfil principal",
    ig_user_id: str = "",
    ig_access_token: str = "",
) -> dict[str, Any]:
    """Create a new Instagram account."""
    session = get_session()
    try:
        account = Account(
            user_id=user_id,
            name=name,
            ig_user_id=ig_user_id,
            ig_access_token=ig_access_token,
        )
        session.add(account)
        session.commit()
        return _account_to_dict(account)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_account(account_id: str) -> dict[str, Any] | None:
    """Get an account by ID."""
    session = get_session()
    try:
        account = session.query(Account).filter(Account.id == account_id).first()
        return _account_to_dict(account) if account else None
    finally:
        session.close()


def list_accounts(user_id: str = "") -> list[dict[str, Any]]:
    """List accounts, optionally filtered by user."""
    session = get_session()
    try:
        query = session.query(Account)
        if user_id:
            query = query.filter(Account.user_id == user_id)
        accounts = query.order_by(Account.created_at.desc()).all()
        return [_account_to_dict(a) for a in accounts]
    finally:
        session.close()


def update_account(account_id: str, **fields: Any) -> bool:
    """Update account fields."""
    session = get_session()
    try:
        account = session.query(Account).filter(Account.id == account_id).first()
        if not account:
            return False
        for key, value in fields.items():
            if hasattr(account, key):
                setattr(account, key, value)
        account.updated_at = datetime.now().isoformat(timespec="seconds")
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def delete_account(account_id: str) -> bool:
    """Delete an account."""
    session = get_session()
    try:
        account = session.query(Account).filter(Account.id == account_id).first()
        if not account:
            return False
        session.delete(account)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def _account_to_dict(account: Account) -> dict[str, Any]:
    """Convert an Account ORM object to a dict."""
    return {
        "id": account.id,
        "user_id": account.user_id,
        "name": account.name,
        "ig_user_id": account.ig_user_id,
        "ig_access_token": account.ig_access_token,
        "ig_api_version": account.ig_api_version,
        "ml_affiliate_id": account.ml_affiliate_id,
        "shopee_affiliate_id": account.shopee_affiliate_id,
        "shopee_sub_id": account.shopee_sub_id,
        "active": account.active,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }
