"""Tests for app/workers/publisher.py — reusable Instagram publishing.

v2.8 — Covers publish_post_to_instagram with mocked dependencies.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.workers.publisher import PublishResult, publish_post_to_instagram


class TestPublishResult:
    """PublishResult dataclass."""

    def test_default_values(self) -> None:
        result = PublishResult(success=False, error="test error")
        assert result.logs == []
        assert result.success is False
        assert result.error == "test error"

    def test_success_with_logs(self) -> None:
        result = PublishResult(
            success=True,
            instagram_post_id="ig_123",
            final_status="PUBLISHED",
            logs=["Step 1 done", "Published!"],
        )
        assert len(result.logs) == 2
        assert result.instagram_post_id == "ig_123"


class TestPublishPostToInstagram:
    """publish_post_to_instagram() — end-to-end publish flow."""

    @patch("app.workers.publisher.get_setting")
    @patch("app.workers.publisher.update_post")
    def test_missing_credentials(
        self, mock_update, mock_get_setting
    ) -> None:
        mock_get_setting.side_effect = lambda key, default="": {
            "instagram_user_id": "",
            "instagram_access_token": "",
        }.get(key, default)

        result = publish_post_to_instagram(
            post_id="post_001",
            video_path=Path("/tmp/video.mp4"),
            caption="Test",
        )
        assert result.success is False
        assert "credentials" in result.error.lower()
        mock_update.assert_called_once()

    @patch("app.workers.publisher.get_setting")
    @patch("app.workers.publisher.update_post")
    def test_video_not_found(
        self, mock_update, mock_get_setting
    ) -> None:
        mock_get_setting.side_effect = lambda key, default="": {
            "instagram_user_id": "test_user",
            "instagram_access_token": "test_token",
        }.get(key, default)

        result = publish_post_to_instagram(
            post_id="post_001",
            video_path=Path("/nonexistent_video.mp4"),
            caption="Test",
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    @patch("app.workers.publisher.InstagramClient")
    @patch("app.workers.publisher.get_setting")
    @patch("app.workers.publisher.update_post")
    def test_successful_publish(
        self, mock_update, mock_get_setting, mock_client_class, tmp_path: Path
    ) -> None:
        mock_get_setting.side_effect = lambda key, default="": {
            "instagram_user_id": "test_user",
            "instagram_access_token": "test_token",
        }.get(key, default)

        mock_instance = MagicMock()
        mock_instance.publish_local_video.return_value = MagicMock(
            container_id="container_123",
            instagram_post_id="ig_456",
            final_status="PUBLISHED",
        )
        mock_client_class.return_value = mock_instance

        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"fake video content")

        result = publish_post_to_instagram(
            post_id="post_001",
            video_path=video_path,
            caption="Test caption #test",
        )
        assert result.success is True
        assert result.instagram_post_id == "ig_456"
        assert result.container_id == "container_123"
        mock_update.assert_called()

    @patch("app.workers.publisher.InstagramClient")
    @patch("app.workers.publisher.get_setting")
    @patch("app.workers.publisher.update_post")
    def test_api_error_handling(
        self, mock_update, mock_get_setting, mock_client_class, tmp_path: Path
    ) -> None:
        mock_get_setting.side_effect = lambda key, default="": {
            "instagram_user_id": "test_user",
            "instagram_access_token": "test_token",
        }.get(key, default)

        mock_instance = MagicMock()
        from app.instagram_api import InstagramApiError
        mock_instance.publish_local_video.side_effect = InstagramApiError(
            "API rate limit exceeded"
        )
        mock_client_class.return_value = mock_instance

        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"fake video")

        result = publish_post_to_instagram(
            post_id="post_001",
            video_path=video_path,
            caption="Test",
        )
        assert result.success is False
        assert "rate limit" in result.error.lower()
