"""API routes for post queue management and scheduler control."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.instagram_api import DEFAULT_API_VERSION
from app.repository import (
    add_videos_to_queue,
    cleanup_orphan_posts,
    clean_worker_logs,
    create_post,
    delete_post,
    get_post,
    get_queue_stats,
    list_batch_history,
    list_content_history,
    list_posts,
    list_worker_logs,
    save_batch_history,
    update_post,
)
from app.utils import default_output_dir, list_video_files
from app.workers.publisher import publish_post_to_instagram
from app.workers.retry import count_errored_posts, reset_stuck_posts
from app.workers.scheduler import get_scheduler

router = APIRouter()


class PostCreate(BaseModel):
    video_paths: list[str]
    profile: str = "Perfil principal"
    caption: str = ""


class PostUpdate(BaseModel):
    profile: str | None = None
    caption: str | None = None
    content_title: str | None = None
    content_cta: str | None = None
    content_hashtags: str | None = None
    product_keywords: str | None = None
    product_query: str | None = None
    affiliate_link: str | None = None
    content_status: str | None = None
    status: str | None = None
    scheduled_for: str | None = None
    instagram_post_id: str | None = None
    last_error: str | None = None


class PublishRequest(BaseModel):
    ig_user_id: str | None = None
    access_token: str | None = None
    api_version: str = DEFAULT_API_VERSION
    media_type: str = "REELS"
    share_to_feed: bool = True


# ─── List all posts ───────────────────────────────────────────────────────────


@router.get("")
async def get_all_posts() -> list[dict[str, Any]]:
    return list_posts()


# ─── Get single post ──────────────────────────────────────────────────────────


@router.get("/{post_id}")
async def get_single_post(post_id: str) -> dict[str, Any]:
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post não encontrado.")
    return post


# ─── Create posts ─────────────────────────────────────────────────────────────


@router.post("")
async def create_posts(data: PostCreate) -> dict[str, Any]:
    """Add videos to the post queue."""
    paths = [Path(p) for p in data.video_paths if Path(p).is_file()]
    if not paths:
        raise HTTPException(400, "Nenhum arquivo de vídeo válido.")

    added = add_videos_to_queue(
        paths,
        profile=data.profile,
        caption=data.caption,
    )
    return {"added": added, "total": len(list_posts())}


# ─── Update post ──────────────────────────────────────────────────────────────


@router.put("/{post_id}")
async def update_single_post(post_id: str, data: PostUpdate) -> dict[str, Any]:
    existing = get_post(post_id)
    if not existing:
        raise HTTPException(404, "Post não encontrado.")

    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not fields:
        return {"updated": False}

    ok = update_post(post_id, **fields)
    return {"updated": ok, "post": get_post(post_id)}


# ─── Delete post ──────────────────────────────────────────────────────────────


@router.delete("/{post_id}")
async def delete_single_post(post_id: str) -> dict[str, bool]:
    ok = delete_post(post_id)
    return {"deleted": ok}


# ─── Publish post to Instagram (manual) ───────────────────────────────────────


@router.post("/{post_id}/publish")
async def publish_post(post_id: str, req: PublishRequest) -> dict[str, Any]:
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post não encontrado.")

    video_path = Path(post.get("video_path", ""))
    caption = post.get("caption", "")

    result = publish_post_to_instagram(
        post_id=post_id,
        video_path=video_path,
        caption=caption,
        ig_user_id=req.ig_user_id,
        access_token=req.access_token,
        api_version=req.api_version,
        media_type=req.media_type,
        share_to_feed=req.share_to_feed,
    )

    return {
        "success": result.success,
        "instagram_post_id": result.instagram_post_id,
        "container_id": result.container_id,
        "status": result.final_status,
        "error": result.error,
        "logs": result.logs or [],
    }


# ─── List output videos ───────────────────────────────────────────────────────


@router.get("/output/videos")
async def list_output_videos() -> dict[str, Any]:
    folder = default_output_dir()
    if not folder.is_dir():
        return {"videos": [], "folder": str(folder)}

    videos = list_video_files(folder, recursive=True)
    return {
        "videos": [str(v) for v in videos],
        "count": len(videos),
        "folder": str(folder),
    }


# ─── Queue stats ──────────────────────────────────────────────────────────────


@router.get("/stats/summary")
async def queue_summary() -> dict[str, Any]:
    posts = list_posts()
    status_counts: dict[str, int] = {}
    for post in posts:
        s = post.get("status", "PENDENTE")
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "total": len(posts),
        "by_status": status_counts,
        "errored": count_errored_posts(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/scheduler/status")
async def scheduler_status() -> dict[str, Any]:
    """Get scheduler running status."""
    sched = get_scheduler()
    return {"running": sched.is_running}


@router.post("/scheduler/start")
async def scheduler_start() -> dict[str, bool]:
    """Start the background scheduler."""
    get_scheduler().start()
    return {"running": True}


@router.post("/scheduler/stop")
async def scheduler_stop() -> dict[str, bool]:
    """Stop the background scheduler."""
    get_scheduler().stop()
    return {"running": False}


# ═══════════════════════════════════════════════════════════════════════════════
# WORKER LOGS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/logs")
async def get_worker_logs(
    post_id: str | None = None,
    level: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List worker logs, optionally filtered by post_id and level."""
    return list_worker_logs(post_id=post_id, level=level, limit=limit)


@router.post("/logs/clean")
async def clean_old_logs() -> dict[str, int]:
    """Remove logs older than 30 days."""
    removed = clean_worker_logs()
    return {"removed": removed}


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH HISTORY
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/batch-history")
async def get_batch_history(limit: int = 50) -> list[dict[str, Any]]:
    """List processing batch history."""
    return list_batch_history(limit=limit)


@router.post("/batch-history")
async def create_batch_history(data: dict[str, Any]) -> dict[str, str]:
    """Register a processing batch."""
    batch_id = save_batch_history(
        upload_count=data.get("upload_count", 0),
        process_count=data.get("process_count", 0),
        success_count=data.get("success_count", 0),
        fail_count=data.get("fail_count", 0),
        template=data.get("template", ""),
    )
    return {"batch_id": batch_id}


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT HISTORY
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/content-history")
async def get_content_history(limit: int = 50) -> list[dict[str, Any]]:
    """List content generation history."""
    return list_content_history(limit=limit)


# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/maintenance/reset-stuck")
async def maintenance_reset_stuck() -> dict[str, Any]:
    """Reset posts stuck in PROCESSANDO status."""
    unstuck = reset_stuck_posts()
    return {"unstuck": unstuck}


@router.post("/maintenance/cleanup-orphans")
async def maintenance_cleanup_orphans() -> dict[str, Any]:
    """Remove posts whose video files no longer exist."""
    removed = cleanup_orphan_posts()
    return {"removed": removed, "total": len(list_posts())}


# ═══════════════════════════════════════════════════════════════════════════════
# SMART SCHEDULING
# ═══════════════════════════════════════════════════════════════════════════════


class SmartScheduleRequest(BaseModel):
    posts_per_day: int = 3
    start_date: str = ""  # ISO date or empty for today
    time_slots: list[str] = []  # e.g. ["09:00", "13:00", "18:00"]


@router.post("/smart-schedule")
async def smart_schedule(req: SmartScheduleRequest) -> dict[str, Any]:
    """Auto-schedule pending posts across time slots."""
    from datetime import timedelta

    posts_per_day = max(1, min(req.posts_per_day, 10))

    # Default time slots based on posts_per_day
    default_slots = {
        1: ["12:00"],
        2: ["09:00", "18:00"],
        3: ["09:00", "14:00", "19:00"],
        4: ["09:00", "12:00", "15:00", "19:00"],
        5: ["08:00", "10:30", "13:00", "16:00", "19:00"],
    }
    time_slots = req.time_slots or default_slots.get(posts_per_day, default_slots[3])

    # Get start date
    if req.start_date:
        try:
            start = datetime.fromisoformat(req.start_date).replace(hour=0, minute=0, second=0)
        except ValueError:
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Get pending posts (PENDENTE status, ordered by created_at)
    all_posts = list_posts(status="PENDENTE")
    if not all_posts:
        return {"scheduled": 0, "message": "Nenhum post pendente para agendar."}

    scheduled_count = 0
    current_date = start
    slot_idx = 0

    for post in all_posts:
        # Find next available slot
        time_str = time_slots[slot_idx % len(time_slots)]
        hour, minute = map(int, time_str.split(":"))
        scheduled_dt = current_date.replace(hour=hour, minute=minute)

        # Skip past times on the first day
        if scheduled_dt <= datetime.now():
            slot_idx += 1
            if slot_idx >= len(time_slots):
                slot_idx = 0
                current_date += timedelta(days=1)
            time_str = time_slots[slot_idx % len(time_slots)]
            hour, minute = map(int, time_str.split(":"))
            scheduled_dt = current_date.replace(hour=hour, minute=minute)

        # Update the post
        update_post(post["id"],
            status="AGENDADO",
            scheduled_for=scheduled_dt.isoformat(timespec="minutes"),
        )
        scheduled_count += 1

        # Move to next slot
        slot_idx += 1
        if slot_idx >= len(time_slots):
            slot_idx = 0
            current_date += timedelta(days=1)

    return {
        "scheduled": scheduled_count,
        "time_slots": time_slots,
        "message": f"{scheduled_count} post(s) agendado(s) automaticamente.",
    }
