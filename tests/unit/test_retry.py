"""Tests for app/workers/retry.py — exponential backoff and stuck post reset.

v2.8 — Covers get_retry_delay, count_errored_posts, reset_stuck_posts.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.workers.retry import (
    MAX_RETRY_ATTEMPTS,
    MAX_RETRY_DELAY_SECONDS,
    get_retry_delay,
    count_errored_posts,
    reset_stuck_posts,
)


class TestGetRetryDelay:
    """get_retry_delay() — exponential backoff calculation."""

    def test_attempt_zero(self) -> None:
        """First retry: 5 minutes (300s)."""
        delay = get_retry_delay(0)
        assert delay == 300

    def test_attempt_one(self) -> None:
        """Second retry: 10 minutes (600s)."""
        delay = get_retry_delay(1)
        assert delay == 600

    def test_attempt_two(self) -> None:
        """Third retry: 20 minutes (1200s)."""
        delay = get_retry_delay(2)
        assert delay == 1200

    def test_attempt_three(self) -> None:
        """Fourth retry: 40 minutes (2400s)."""
        delay = get_retry_delay(3)
        assert delay == 2400

    def test_never_exceeds_max(self) -> None:
        """Should cap at MAX_RETRY_DELAY_SECONDS even for high attempts."""
        delay = get_retry_delay(10)
        assert delay <= MAX_RETRY_DELAY_SECONDS

    def test_exponential_growth(self) -> None:
        """Each attempt should double the delay."""
        d0 = get_retry_delay(0)
        d1 = get_retry_delay(1)
        d2 = get_retry_delay(2)
        assert d1 == d0 * 2
        assert d2 == d1 * 2


class TestCountErroredPosts:
    """count_errored_posts() — count posts with ERRO status."""

    @patch("app.workers.retry.list_posts")
    def test_no_errors(self, mock_list_posts) -> None:
        """Should return 0 when no posts have ERRO status."""
        mock_list_posts.return_value = [
            {"status": "PENDENTE"},
            {"status": "PUBLICADO"},
        ]
        assert count_errored_posts() == 0

    @patch("app.workers.retry.list_posts")
    def test_some_errors(self, mock_list_posts) -> None:
        """Should count only posts with ERRO status."""
        mock_list_posts.return_value = [
            {"status": "ERRO"},
            {"status": "PUBLICADO"},
            {"status": "ERRO"},
            {"status": "AGENDADO"},
        ]
        assert count_errored_posts() == 2

    @patch("app.workers.retry.list_posts")
    def test_empty_list(self, mock_list_posts) -> None:
        """Should return 0 when no posts exist."""
        mock_list_posts.return_value = []
        assert count_errored_posts() == 0

    @patch("app.workers.retry.list_posts")
    def test_case_insensitive(self, mock_list_posts) -> None:
        """Should handle lowercase 'erro' status."""
        mock_list_posts.return_value = [
            {"status": "erro"},
            {"status": "Erro"},
        ]
        assert count_errored_posts() == 2


class TestResetStuckPosts:
    """reset_stuck_posts() — reset posts stuck in PROCESSANDO."""

    @patch("app.workers.retry.list_posts")
    @patch("app.workers.retry.update_post")
    def test_no_stuck_posts(
        self, mock_update_post, mock_list_posts
    ) -> None:
        """Should not reset any posts when none are stuck."""
        mock_list_posts.return_value = [
            {"status": "PENDENTE", "processing_started_at": ""},
            {"status": "PUBLICADO", "processing_started_at": ""},
        ]
        result = reset_stuck_posts(timeout_seconds=600)
        assert result == 0
        mock_update_post.assert_not_called()

    @patch("app.workers.retry.list_posts")
    @patch("app.workers.retry.update_post")
    def test_resets_stuck_post(
        self, mock_update_post, mock_list_posts
    ) -> None:
        """Should reset posts stuck in PROCESSANDO beyond timeout."""
        old_time = (datetime.now() - timedelta(minutes=30)).isoformat()
        mock_list_posts.return_value = [
            {
                "id": "stuck_001",
                "status": "PROCESSANDO",
                "processing_started_at": old_time,
            }
        ]
        result = reset_stuck_posts(timeout_seconds=600)
        assert result == 1
        mock_update_post.assert_called_once_with(
            "stuck_001",
            status="ERRO",
            last_error="Timeout: processing took too long.",
            worker_lock="",
        )

    @patch("app.workers.retry.list_posts")
    @patch("app.workers.retry.update_post")
    def test_ignores_recent_processing(
        self, mock_update_post, mock_list_posts
    ) -> None:
        """Should not reset posts that started recently."""
        recent = datetime.now().isoformat()
        mock_list_posts.return_value = [
            {
                "id": "recent_001",
                "status": "PROCESSANDO",
                "processing_started_at": recent,
            }
        ]
        result = reset_stuck_posts(timeout_seconds=600)
        assert result == 0
        mock_update_post.assert_not_called()

    @patch("app.workers.retry.list_posts")
    @patch("app.workers.retry.update_post")
    def test_missing_started_at(
        self, mock_update_post, mock_list_posts
    ) -> None:
        """Should skip posts without processing_started_at."""
        mock_list_posts.return_value = [
            {
                "id": "no_start",
                "status": "PROCESSANDO",
                "processing_started_at": "",
            }
        ]
        result = reset_stuck_posts(timeout_seconds=600)
        assert result == 0
        mock_update_post.assert_not_called()
