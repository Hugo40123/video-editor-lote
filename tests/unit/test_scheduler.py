"""Tests for app/workers/scheduler.py — background publication scheduler.

v2.8 — Covers scheduler lifecycle, post selection, locking, retry logic.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.workers.scheduler import (
    RETRY_BACKOFF_SECONDS,
    RETRY_MAX_ATTEMPTS,
    Scheduler,
)


class TestScheduler:
    """Scheduler lifecycle and tick logic."""

    def test_initial_state(self) -> None:
        """Scheduler should start as not running."""
        sched = Scheduler()
        assert sched.is_running is False

    def test_start_stop(self) -> None:
        """Should start and stop cleanly."""
        sched = Scheduler()
        sched.start()
        assert sched.is_running is True
        sched.stop()
        assert sched.is_running is False

    def test_double_start_is_idempotent(self) -> None:
        """Starting an already running scheduler should do nothing."""
        sched = Scheduler()
        sched.start()
        sched.start()  # second start
        assert sched.is_running is True
        sched.stop()


class TestSchedulerTick:
    """Scheduler._tick() — main tick logic for finding and publishing posts."""

    @patch("app.workers.scheduler.list_posts")
    @patch("app.workers.scheduler.save_worker_log")
    def test_no_due_posts(
        self, mock_log, mock_list_posts
    ) -> None:
        """Should do nothing when no posts are due."""
        mock_list_posts.return_value = [
            {"id": "1", "status": "PENDENTE", "scheduled_for": ""},
        ]
        sched = Scheduler()
        sched._tick()
        # No publish attempts should be made
        mock_log.assert_not_called()

    @patch("app.workers.scheduler.list_posts")
    @patch("app.workers.scheduler.save_worker_log")
    def test_due_scheduled_post(
        self, mock_log, mock_list_posts
    ) -> None:
        """Should find and publish due AGENDADO posts."""
        now = datetime.now().isoformat(timespec="seconds")
        mock_list_posts.return_value = [
            {
                "id": "due_001",
                "status": "AGENDADO",
                "scheduled_for": now,
                "video_path": "/tmp/video.mp4",
                "caption": "Test",
                "retry_count": 0,
                "worker_lock": "",
                "updated_at": now,
            },
        ]

        with patch.object(Scheduler, "_publish_single") as mock_publish:
            sched = Scheduler()
            sched._tick()
            mock_publish.assert_called_once()

    @patch("app.workers.scheduler.list_posts")
    @patch("app.workers.scheduler.save_worker_log")
    def test_future_post_not_published(
        self, mock_log, mock_list_posts
    ) -> None:
        """Should NOT publish a post scheduled in the future."""
        future = (datetime.now() + timedelta(hours=2)).isoformat(timespec="seconds")
        mock_list_posts.return_value = [
            {
                "id": "future_001",
                "status": "AGENDADO",
                "scheduled_for": future,
                "retry_count": 0,
                "worker_lock": "",
                "updated_at": datetime.now().isoformat(),
            },
        ]

        with patch.object(Scheduler, "_publish_single") as mock_publish:
            sched = Scheduler()
            sched._tick()
            mock_publish.assert_not_called()


class TestSchedulerIsDue:
    """Scheduler._is_due_for_publishing() — fine-grained due checks."""

    @pytest.fixture
    def scheduler(self) -> Scheduler:
        return Scheduler()

    def test_agendado_due(self, scheduler: Scheduler) -> None:
        """AGENDADO post with scheduled_for in the past should be due."""
        past = (datetime.now() - timedelta(minutes=5)).isoformat(timespec="seconds")
        now = datetime.now().isoformat(timespec="seconds")
        post = {
            "status": "AGENDADO",
            "scheduled_for": past,
        }
        assert scheduler._is_due_for_publishing(post, now) is True

    def test_agendado_future_not_due(self, scheduler: Scheduler) -> None:
        """AGENDADO post in the future should not be due."""
        future = (datetime.now() + timedelta(hours=1)).isoformat(timespec="seconds")
        now = datetime.now().isoformat(timespec="seconds")
        post = {
            "status": "AGENDADO",
            "scheduled_for": future,
        }
        assert scheduler._is_due_for_publishing(post, now) is False

    def test_erro_with_retries_left(self, scheduler: Scheduler) -> None:
        """ERRO post with retries left should be retried after backoff."""
        past_time = (datetime.now() - timedelta(minutes=30)).isoformat(timespec="seconds")
        now = datetime.now().isoformat(timespec="seconds")
        post = {
            "status": "ERRO",
            "retry_count": 1,
            "scheduled_for": past_time,
            "updated_at": past_time,
        }
        assert scheduler._is_due_for_publishing(post, now) is True

    def test_erro_max_retries_exhausted(self, scheduler: Scheduler) -> None:
        """ERRO past max retries should NOT be due."""
        post = {
            "status": "ERRO",
            "retry_count": RETRY_MAX_ATTEMPTS + 1,
            "scheduled_for": "",
            "updated_at": datetime.now().isoformat(),
        }
        now = datetime.now().isoformat(timespec="seconds")
        assert scheduler._is_due_for_publishing(post, now) is False

    def test_pendente_not_due(self, scheduler: Scheduler) -> None:
        """PENDENTE (not AGENDADO) should not be due."""
        post = {
            "status": "PENDENTE",
            "scheduled_for": "",
        }
        now = datetime.now().isoformat(timespec="seconds")
        assert scheduler._is_due_for_publishing(post, now) is False

    def test_publicado_not_due(self, scheduler: Scheduler) -> None:
        """PUBLICADO should not be due."""
        post = {
            "status": "PUBLICADO",
            "scheduled_for": "",
        }
        now = datetime.now().isoformat(timespec="seconds")
        assert scheduler._is_due_for_publishing(post, now) is False

    def test_erro_with_backoff_not_elapsed(self, scheduler: Scheduler) -> None:
        """ERRO should not retry before backoff has elapsed."""
        recent = (datetime.now() - timedelta(seconds=60)).isoformat(timespec="seconds")
        now = datetime.now().isoformat(timespec="seconds")
        post = {
            "status": "ERRO",
            "retry_count": 0,
            "scheduled_for": "",
            "updated_at": recent,
        }
        # Backoff for attempt 0 is 300s, only 60s have passed
        assert scheduler._is_due_for_publishing(post, now) is False


class TestSchedulerPublishSingle:
    """Scheduler._publish_single() — individual post publishing with locking."""

    @patch("app.workers.scheduler.update_post")
    @patch("app.workers.scheduler.save_worker_log")
    @patch("app.workers.scheduler.publish_post_to_instagram")
    def test_successful_publish(
        self, mock_publish, mock_log, mock_update
    ) -> None:
        """Should update status on successful publish."""
        mock_publish.return_value = MagicMock(success=True)

        sched = Scheduler()
        sched._publish_single({
            "id": "post_001",
            "video_path": "/tmp/video.mp4",
            "caption": "Test",
            "retry_count": 0,
            "worker_lock": "",
        })
        # Should set status to PROCESSANDO then call publisher
        mock_publish.assert_called_once()

    @patch("app.workers.scheduler.update_post")
    @patch("app.workers.scheduler.save_worker_log")
    @patch("app.workers.scheduler.publish_post_to_instagram")
    def test_failed_publish_increments_retry(
        self, mock_publish, mock_log, mock_update
    ) -> None:
        """Should increment retry_count on failed publish."""
        mock_publish.return_value = MagicMock(
            success=False, error="API error"
        )

        sched = Scheduler()
        sched._publish_single({
            "id": "post_001",
            "video_path": "/tmp/video.mp4",
            "caption": "Test",
            "retry_count": 0,
            "worker_lock": "",
        })
        # Should update retry_count to 1
        mock_update.assert_any_call("post_001", retry_count=1)

    @patch("app.workers.scheduler.save_worker_log")
    def test_locked_post_skipped(self, mock_log) -> None:
        """Post with active lock should be skipped."""
        lock_time = datetime.now().isoformat(timespec="seconds")
        sched = Scheduler()
        # Should return early without calling publish
        with patch.object(sched, "_is_due_for_publishing", return_value=True):
            with patch("app.workers.scheduler.update_post") as mock_update:
                with patch("app.workers.scheduler.publish_post_to_instagram") as mock_publish:
                    sched._publish_single({
                        "id": "locked_post",
                        "video_path": "/tmp/v.mp4",
                        "caption": "Test",
                        "retry_count": 0,
                        "worker_lock": lock_time,
                    })
                    # Should NOT publish because lock is active
                    mock_publish.assert_not_called()
