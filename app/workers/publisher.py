"""Publisher — reusable Instagram publishing logic for workers and manual posts.

Extracted from web/routes/posts.py so both the scheduler and manual publish share the same code.
"""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.instagram_api import (
    DEFAULT_API_VERSION,
    InstagramApiError,
    InstagramClient,
    InstagramConfig,
)
from app.repository import get_setting, update_post


@dataclass(frozen=True)
class PublishResult:
    success: bool
    instagram_post_id: str = ""
    container_id: str = ""
    final_status: str = ""
    error: str = ""
    logs: list[str] = None

    def __post_init__(self) -> None:
        if self.logs is None:
            object.__setattr__(self, "logs", [])


LogCallback = Callable[[str], None]


def publish_post_to_instagram(
    post_id: str,
    video_path: Path,
    caption: str,
    *,
    ig_user_id: str | None = None,
    access_token: str | None = None,
    api_version: str = DEFAULT_API_VERSION,
    media_type: str = "REELS",
    share_to_feed: bool = True,
    log_callback: LogCallback | None = None,
) -> PublishResult:
    """Publish a post to Instagram.

    Can be called from the scheduler (auto) or from the manual publish endpoint.
    Reads credentials from DB if not provided explicitly.
    """
    logs: list[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)
        if log_callback:
            log_callback(msg)

    # Resolve credentials: explicit > DB settings
    uid = ig_user_id or get_setting("instagram_user_id", "")
    token = access_token or get_setting("instagram_access_token", "")

    if not uid or not token:
        err = "Instagram credentials not configured. Set IG User ID and Access Token in Settings."
        _log(err)
        update_post(post_id, status="ERRO", last_error=err)
        return PublishResult(success=False, error=err, logs=logs)

    if not video_path.is_file():
        err = f"Video not found: {video_path}"
        _log(err)
        update_post(post_id, status="ERRO", last_error=err)
        return PublishResult(success=False, error=err, logs=logs)

    config = InstagramConfig(
        ig_user_id=uid,
        access_token=token,
        api_version=api_version,
    )

    try:
        client = InstagramClient(config)
        _log("Creating media container on Instagram...")
        result = client.publish_local_video(
            video_path,
            caption,
            media_type=media_type,
            share_to_feed=share_to_feed,
            log_callback=_log,
        )

        update_post(
            post_id,
            status="PUBLICADO",
            instagram_post_id=result.instagram_post_id,
            last_error="",
            published_at=datetime.now().isoformat(timespec="seconds"),
        )
        _log(f"Published! Instagram ID: {result.instagram_post_id}")

        return PublishResult(
            success=True,
            instagram_post_id=result.instagram_post_id,
            container_id=result.container_id,
            final_status=result.final_status,
            logs=logs,
        )

    except InstagramApiError as exc:
        err = str(exc)
        _log(f"Error: {err}")
        update_post(post_id, status="ERRO", last_error=err)
        return PublishResult(success=False, error=err, logs=logs)
