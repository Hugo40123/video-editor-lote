"""Scheduler — background worker that publishes scheduled posts automatically.

Runs as a daemon thread inside the FastAPI lifespan.
Checks every N seconds for posts with status AGENDADO where scheduled_for <= now.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.database import WORKER_LOCK_TIMEOUT
from app.repository import (
    get_setting,
    list_posts,
    update_post,
    save_worker_log,
)
from app.workers.publisher import publish_post_to_instagram

logger = logging.getLogger("scheduler")

CHECK_INTERVAL_SECONDS = 30
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 300  # 5 minutes base


class Scheduler:
    """Background scheduler for automatic Instagram posting.

    Usage:
        scheduler = Scheduler()
        scheduler.start()   # starts daemon thread
        scheduler.stop()    # signals thread to stop
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="scheduler")
        self._thread.start()
        self._running = True
        save_worker_log("scheduler", "INFO", "Scheduler started.")

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False
        save_worker_log("scheduler", "INFO", "Scheduler stopping...")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.exception("Scheduler tick error: %s", exc)
                save_worker_log("scheduler", "ERROR", f"Scheduler error: {exc}")
            self._stop_event.wait(CHECK_INTERVAL_SECONDS)

    def _tick(self) -> None:
        """One scheduler tick: find due posts and publish them."""
        now = datetime.now().isoformat(timespec="seconds")
        posts = list_posts()

        # Find posts that are due for publishing
        due_posts = [
            p for p in posts
            if self._is_due_for_publishing(p, now)
        ]

        if not due_posts:
            return

        save_worker_log("scheduler", "INFO", f"Found {len(due_posts)} post(s) due for publishing.")

        for post in due_posts:
            if self._stop_event.is_set():
                break
            self._publish_single(post)

    def _is_due_for_publishing(self, post: dict[str, Any], now: str) -> bool:
        """Check if a post is ready to be published."""
        status = (post.get("status") or "").strip().upper()

        # Statuses that should be picked up
        if status in ("AGENDADO",):
            scheduled = (post.get("scheduled_for") or "").strip()
            if scheduled and scheduled <= now:
                return True
            return False

        # Retry errored posts
        if status in ("ERRO",):
            retry_count = post.get("retry_count") or 0
            if isinstance(retry_count, str):
                retry_count = int(retry_count) if retry_count.isdigit() else 0
            if retry_count >= RETRY_MAX_ATTEMPTS:
                return False

            scheduled = (post.get("scheduled_for") or "").strip()
            if scheduled and scheduled <= now:
                return True

            # Retry with backoff
            last_error_time = post.get("updated_at") or ""
            if last_error_time:
                try:
                    last_dt = datetime.fromisoformat(last_error_time)
                    elapsed = (datetime.now() - last_dt).total_seconds()
                    backoff = RETRY_BACKOFF_SECONDS * (2 ** retry_count)
                    if elapsed >= backoff:
                        return True
                except (ValueError, TypeError):
                    pass

            return False

        return False

    def _publish_single(self, post: dict[str, Any]) -> None:
        """Publish a single post, with lock anti-duplication."""
        post_id = post.get("id", "")
        if not post_id:
            return

        # Lock check: prevent duplicate processing
        lock = (post.get("worker_lock") or "").strip()
        if lock:
            try:
                lock_time = datetime.fromisoformat(lock)
                elapsed = (datetime.now() - lock_time).total_seconds()
                if elapsed < WORKER_LOCK_TIMEOUT:
                    return  # Another worker is processing this
            except (ValueError, TypeError):
                pass

        # Acquire lock
        now_str = datetime.now().isoformat(timespec="seconds")
        update_post(post_id, status="PROCESSANDO", worker_lock=now_str, processing_started_at=now_str)

        video_path = Path(post.get("video_path", ""))
        caption = post.get("caption") or ""
        retry_count = post.get("retry_count") or 0
        if isinstance(retry_count, str):
            retry_count = int(retry_count) if retry_count.isdigit() else 0

        save_worker_log(post_id, "INFO", f"Publishing: {video_path.name}")

        result = publish_post_to_instagram(
            post_id=post_id,
            video_path=video_path,
            caption=caption,
            log_callback=lambda msg: save_worker_log(post_id, "INFO", msg),
        )

        if result.success:
            save_worker_log(post_id, "INFO", "Published successfully!")
        else:
            new_retry = retry_count + 1
            update_post(post_id, retry_count=new_retry)
            save_worker_log(
                post_id, "ERROR",
                f"Publish failed (attempt {new_retry}/{RETRY_MAX_ATTEMPTS}): {result.error}",
            )


# Global singleton
_scheduler = Scheduler()


def get_scheduler() -> Scheduler:
    return _scheduler


def start_scheduler() -> None:
    get_scheduler().start()


def stop_scheduler() -> None:
    get_scheduler().stop()
