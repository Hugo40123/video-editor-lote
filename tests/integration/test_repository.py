"""Integration tests for app/repository.py — CRUD operations with test database.

v2.8 — Uses in-memory SQLite database for isolated test runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.repository import (
    add_videos_to_queue,
    clean_worker_logs,
    create_post,
    delete_post,
    get_post,
    get_queue_stats,
    get_setting,
    list_posts,
    save_batch_history,
    save_content_history,
    save_product,
    save_worker_log,
    set_setting,
    update_post,
)


class TestPosts:
    """Post CRUD operations."""

    def test_create_and_get(self, suppress_db) -> None:
        post = create_post("/tmp/video.mp4", profile="Test Perfil")
        assert post["video_path"] == "/tmp/video.mp4"
        assert post["profile"] == "Test Perfil"
        assert post["status"] == "PENDENTE"

        retrieved = get_post(post["id"])
        assert retrieved is not None
        assert retrieved["id"] == post["id"]

    def test_update(self, suppress_db) -> None:
        post = create_post("/tmp/video.mp4")
        ok = update_post(post["id"], caption="New caption", status="AGENDADO")
        assert ok is True

        updated = get_post(post["id"])
        assert updated["caption"] == "New caption"
        assert updated["status"] == "AGENDADO"

    def test_update_nonexistent(self, suppress_db) -> None:
        ok = update_post("nonexistent", caption="test")
        assert ok is False

    def test_delete(self, suppress_db) -> None:
        post = create_post("/tmp/video.mp4")
        ok = delete_post(post["id"])
        assert ok is True
        assert get_post(post["id"]) is None

    def test_delete_nonexistent(self, suppress_db) -> None:
        assert delete_post("nonexistent") is False

    def test_list_posts(self, suppress_db) -> None:
        create_post("/tmp/video_a.mp4")
        create_post("/tmp/video_b.mp4")
        posts = list_posts()
        assert len(posts) >= 2

    def test_add_videos_to_queue(self, suppress_db) -> None:
        paths = [Path("/tmp/v1.mp4"), Path("/tmp/v2.mp4")]
        added = add_videos_to_queue(paths)
        assert added == 2

        added = add_videos_to_queue(paths)
        assert added == 0

    def test_get_queue_stats(self, suppress_db) -> None:
        stats = get_queue_stats()
        assert isinstance(stats, dict)

    def test_create_post_with_caption(self, suppress_db) -> None:
        post = create_post("/tmp/video.mp4", caption="Test caption")
        assert post["caption"] == "Test caption"


class TestSettings:
    """Settings CRUD operations."""

    def test_set_and_get(self, suppress_db) -> None:
        set_setting("test_key", "test_value")
        assert get_setting("test_key") == "test_value"

    def test_get_default(self, suppress_db) -> None:
        assert get_setting("nonexistent", "default_val") == "default_val"

    def test_get_empty_default(self, suppress_db) -> None:
        assert get_setting("nonexistent") == ""

    def test_upsert_updates_value(self, suppress_db) -> None:
        set_setting("key1", "value1")
        set_setting("key1", "value2")
        assert get_setting("key1") == "value2"


class TestWorkerLogs:
    """Worker log operations."""

    def test_save(self, suppress_db) -> None:
        log_id = save_worker_log("post_001", "INFO", "Test log message")
        assert log_id is not None
        assert len(log_id) > 0

    def test_clean_old_logs(self, suppress_db) -> None:
        save_worker_log("post_001", "INFO", "Log to clean")
        count = clean_worker_logs()
        assert isinstance(count, int)


class TestBatchHistory:
    """Batch history operations."""

    def test_save(self, suppress_db) -> None:
        batch_id = save_batch_history(
            upload_count=5, process_count=5, success_count=4, fail_count=1
        )
        assert batch_id is not None

    def test_save_with_template(self, suppress_db) -> None:
        batch_id = save_batch_history(template="Template 1")
        assert batch_id is not None


class TestContentHistory:
    """Content history operations."""

    def test_save(self, suppress_db) -> None:
        history_id = save_content_history(
            "/tmp/video.mp4",
            title="Test Title",
            caption="Test caption",
            source="local",
        )
        assert history_id is not None

    def test_save_with_product_query(self, suppress_db) -> None:
        history_id = save_content_history(
            "/tmp/video.mp4",
            title="Product Video",
            product_query="fone bluetooth",
        )
        assert history_id is not None


class TestProducts:
    """Product CRUD operations."""

    def test_save(self, suppress_db) -> None:
        product = save_product(
            source="mercadolivre",
            product_id="MLB123",
            title="Fone Bluetooth",
            price=89.90,
        )
        assert product["source"] == "mercadolivre"
        assert product["title"] == "Fone Bluetooth"
        assert product["price"] == 89.90

    def test_save_with_post_association(self, suppress_db) -> None:
        post = create_post("/tmp/video.mp4")
        product = save_product(
            post_id=post["id"],
            source="shopee",
            product_id="SP123",
            title="Smartphone",
            price=1500.00,
        )
        assert product["post_id"] == post["id"]
