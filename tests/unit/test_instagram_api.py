"""Tests for app/instagram_api.py — Instagram Graph API client.

v2.8 — Covers config, client initialization, API calls (mocked).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.instagram_api import (
    DEFAULT_API_VERSION,
    DEFAULT_GRAPH_HOST,
    InstagramApiError,
    InstagramClient,
    InstagramConfig,
)


class TestInstagramConfig:
    """InstagramConfig dataclass."""

    def test_default_values(self) -> None:
        config = InstagramConfig(
            ig_user_id="12345",
            access_token="token123",
        )
        assert config.ig_user_id == "12345"
        assert config.access_token == "token123"
        assert config.api_version == DEFAULT_API_VERSION
        assert config.graph_host == DEFAULT_GRAPH_HOST

    def test_base_url(self) -> None:
        config = InstagramConfig(
            ig_user_id="12345",
            access_token="token123",
        )
        expected = f"{DEFAULT_GRAPH_HOST}/{DEFAULT_API_VERSION}"
        assert config.base_url == expected

    def test_custom_graph_host(self) -> None:
        config = InstagramConfig(
            ig_user_id="12345",
            access_token="token123",
            graph_host="https://custom.graph.com",
        )
        assert "custom.graph.com" in config.base_url


class TestInstagramClient:
    """InstagramClient — API interaction (all HTTP mocked)."""

    @pytest.fixture
    def client(self) -> InstagramClient:
        config = InstagramConfig(
            ig_user_id="test_user",
            access_token="test_token",
        )
        return InstagramClient(config)

    def test_init(self, client: InstagramClient) -> None:
        assert client.config.ig_user_id == "test_user"

    @patch("app.instagram_api.requests.request")
    def test_test_connection_success(
        self, mock_request, client: InstagramClient
    ) -> None:
        """test_connection() should return user data on success."""
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "12345", "username": "test_user"},
        )
        result = client.test_connection()
        assert result["id"] == "12345"
        assert result["username"] == "test_user"

    @patch("app.instagram_api.requests.request")
    def test_test_connection_error(
        self, mock_request, client: InstagramClient
    ) -> None:
        """test_connection() should raise on API error."""
        mock_request.return_value = MagicMock(
            status_code=400,
            json=lambda: {
                "error": {"message": "Invalid token", "type": "OAuthException"}
            },
        )
        with pytest.raises(InstagramApiError, match="Invalid token"):
            client.test_connection()

    def test_publish_local_video_file_not_found(
        self, client: InstagramClient
    ) -> None:
        """Should raise if video file doesn't exist."""
        with pytest.raises(InstagramApiError, match="não foi encontrado"):
            client.publish_local_video(
                video_path=Path("/nonexistent/video.mp4"),
                caption="Test",
            )

    def test_create_media_container(
        self, client: InstagramClient
    ) -> None:
        """create_media_container() should build correct payload."""
        with patch("app.instagram_api.requests.request") as mock_req:
            mock_req.return_value = MagicMock(
                status_code=200,
                json=lambda: {"id": "container_123"},
            )
            result = client.create_media_container(
                caption="Test caption",
                media_type="REELS",
                share_to_feed=True,
            )
            assert result["id"] == "container_123"
            # Verify the API was called
            mock_req.assert_called_once()

    @patch("app.instagram_api.requests.request")
    def test_get_container_status(
        self, mock_request, client: InstagramClient
    ) -> None:
        """get_container_status() should return status fields."""
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status_code": "FINISHED", "status": "PUBLISHED"},
        )
        result = client.get_container_status("container_123")
        assert result["status_code"] == "FINISHED"

    @patch("app.instagram_api.requests.request")
    def test_publish_container(
        self, mock_request, client: InstagramClient
    ) -> None:
        """publish_container() should return published ID."""
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "ig_123456"},
        )
        result = client.publish_container("container_123")
        assert result["id"] == "ig_123456"

    @patch("app.instagram_api.requests.request")
    def test_upload_video(
        self, mock_request, client: InstagramClient, tmp_path: Path
    ) -> None:
        """upload_video() should upload file content."""
        # Create a temporary video file
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video content")

        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "uploaded_123"},
        )
        result = client.upload_video(
            "container_123", video_file
        )
        assert result["id"] == "uploaded_123"
        # Verify the file was sent (upload content check)
        mock_request.assert_called_once()

    @patch("app.instagram_api.requests.request")
    def test_wait_until_container_ready_finished(
        self, mock_request, client: InstagramClient
    ) -> None:
        """Should return FINISHED status when ready."""
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status_code": "FINISHED"},
        )
        status = client.wait_until_container_ready(
            "container_123",
            timeout_seconds=5,
            interval_seconds=1,
        )
        assert status == "FINISHED"

    @patch("app.instagram_api.requests.request")
    def test_wait_until_container_ready_error(
        self, mock_request, client: InstagramClient
    ) -> None:
        """Should raise on ERROR status."""
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status_code": "ERROR"},
        )
        with pytest.raises(InstagramApiError, match="ERROR"):
            client.wait_until_container_ready(
                "container_123",
                timeout_seconds=5,
                interval_seconds=1,
            )

    @patch("app.instagram_api.requests.request")
    def test_wait_until_container_ready_timeout(
        self, mock_request, client: InstagramClient
    ) -> None:
        """Should raise on timeout."""
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status_code": "PROCESSING"},
        )
        with pytest.raises(InstagramApiError, match="Tempo limite"):
            client.wait_until_container_ready(
                "container_123",
                timeout_seconds=1,
                interval_seconds=2,  # Will exceed timeout immediately
            )


class TestPublishResult:
    """PublishResult dataclass (from instagram_api)."""

    def test_default_values(self) -> None:
        from app.instagram_api import PublishResult as IGPublishResult
        result = IGPublishResult(
            container_id="c1",
            instagram_post_id="ig1",
            final_status="FINISHED",
        )
        assert result.container_id == "c1"
        assert result.instagram_post_id == "ig1"
        assert result.final_status == "FINISHED"

    def test_publisher_result(self) -> None:
        from app.workers.publisher import PublishResult as PubResult
        result = PubResult(
            success=True,
            container_id="c1",
            instagram_post_id="ig1",
            final_status="PUBLISHED",
            logs=["Published!"],
        )
        assert result.success is True
        assert len(result.logs) == 1
