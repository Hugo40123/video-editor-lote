"""Retry — logic for reattempting failed publications.

The retry logic is embedded in the scheduler's _is_due_for_publishing
check for simplicity. This module provides utility functions for
retry state management.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from app.repository import list_posts, update_post

MAX_RETRY_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 300  # 5 minutes
MAX_RETRY_DELAY_SECONDS = 86400  # 24 hours


def get_retry_delay(attempt: int) -> int:
    """Calculate exponential backoff delay.

    Args:
        attempt: Current retry attempt number (0-indexed).

    Returns:
        Delay in seconds before next retry.
    """
    delay = BASE_RETRY_DELAY_SECONDS * (2 ** attempt)
    return min(delay, MAX_RETRY_DELAY_SECONDS)


def count_errored_posts() -> int:
    """Count posts with retryable errors."""
    posts = list_posts()
    return sum(
        1 for p in posts
        if (p.get("status") or "").strip().upper() == "ERRO"
    )


def reset_stuck_posts(timeout_seconds: int = 600) -> int:
    """Reset posts stuck in PROCESSANDO status beyond timeout.

    This handles crashes where a worker died while processing.

    Args:
        timeout_seconds: Max allowed processing time.

    Returns:
        Number of posts unstuck.
    """
    posts = list_posts()
    now = datetime.now()
    unstuck = 0

    for post in posts:
        status = (post.get("status") or "").strip().upper()
        if status != "PROCESSANDO":
            continue

        started = (post.get("processing_started_at") or "").strip()
        if not started:
            continue

        try:
            started_dt = datetime.fromisoformat(started)
            elapsed = (now - started_dt).total_seconds()
            if elapsed >= timeout_seconds:
                update_post(
                    post.get("id", ""),
                    status="ERRO",
                    last_error="Timeout: processing took too long.",
                    worker_lock="",
                )
                unstuck += 1
        except (ValueError, TypeError):
            pass

    return unstuck
