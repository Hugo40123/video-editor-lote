"""API routes for video editing operations."""

from __future__ import annotations

import asyncio
import json
import queue
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.utils import (
    default_background_path,
    default_input_dir,
    default_output_dir,
    ensure_directory,
    ffmpeg_path,
    list_video_files,
    parse_duration,
    upload_dir,
)
from app.video_processor import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    TEMPLATE_CONFIGS,
    get_template_labels,
    process_videos,
    RenderOptions,
)

router = APIRouter()

# Store running tasks with their log queues
# Use thread-safe queue.Queue for cross-thread communication
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="video_worker")
_tasks: dict[str, dict[str, Any]] = {}


class ProcessRequest(BaseModel):
    video_files: list[str] = []
    output_folder: str = ""
    background_image: str = ""
    logo_image: str = ""
    text_watermark: str = ""
    text_watermark_size: int = 76
    text_watermark_offset_x: int = 0
    text_watermark_offset_y: int = 0
    video_size: int = 100
    video_width: int = 100
    video_offset_x: int = 0
    video_offset_y: int = 0
    max_duration: float | None = None
    template: str = ""
    apply_watermark: bool = False
    apply_text_watermark: bool = False
    remove_center_watermark: bool = False
    delogo_x: int = 190
    delogo_y: int = 860
    delogo_width: int = 700
    delogo_height: int = 160

    class Config:
        protected_namespaces = ()


# ─── Upload videos (max 10) ──────────────────────────────────────────────────


UPLOAD_MAX_FILES = 10
UPLOAD_MAX_SIZE_MB = 500  # per file
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _upload_session_dir() -> Path:
    """Create a unique session directory for uploads."""
    session_id = uuid.uuid4().hex[:12]
    session_dir = upload_dir() / session_id
    ensure_directory(session_dir)
    return session_dir


@router.post("/upload")
async def upload_videos(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Upload video files (max 10). Accepts multipart form data with field name 'files'."""
    if not files:
        raise HTTPException(400, "Nenhum arquivo enviado.")

    if len(files) > UPLOAD_MAX_FILES:
        raise HTTPException(400, f"Máximo de {UPLOAD_MAX_FILES} arquivos por upload.")

    session_dir = _upload_session_dir()
    saved_files: list[dict[str, Any]] = []

    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            continue

        content = await file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > UPLOAD_MAX_SIZE_MB:
            continue

        safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        dest = session_dir / safe_name
        dest.write_bytes(content)

        saved_files.append({
            "original_name": file.filename,
            "server_path": str(dest),
            "size_mb": round(size_mb, 1),
        })

    if not saved_files:
        raise HTTPException(400, "Nenhum arquivo válido. Formatos aceitos: MP4, MOV, AVI, MKV, WEBM (máx 500MB cada).")

    return {
        "session_dir": str(session_dir),
        "files": saved_files,
        "count": len(saved_files),
    }


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a single image (background or logo)."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(400, "Formato de imagem não suportado. Use JPG, PNG, BMP ou WEBP.")

    session_dir = _upload_session_dir()
    safe_name = f"img_{uuid.uuid4().hex[:8]}{ext}"
    dest = session_dir / safe_name

    content = await file.read()
    dest.write_bytes(content)

    return {
        "original_name": file.filename,
        "server_path": str(dest),
        "size_mb": round(len(content) / (1024 * 1024), 1),
    }


# ─── Extract thumbnail from a video ─────────────────────────────────────────────


@router.post("/thumbnail")
async def get_thumbnail(data: dict[str, str]) -> dict[str, Any]:
    """Extract a frame from a video file for preview.
    Accepts either 'folder' (legacy) or 'video_path' (upload).
    """
    video_path_str = data.get("video_path", "") or data.get("folder", "")
    if not video_path_str:
        return {"thumbnail": None, "video_name": None}

    video_path = Path(video_path_str)
    videos: list[Path] = []
    if video_path.is_dir():
        videos = list_video_files(video_path, recursive=True)
        if not videos:
            return {"thumbnail": None, "video_name": None}
        first_video = videos[0]
    elif video_path.is_file():
        first_video = video_path
        videos = [first_video]
    else:
        return {"thumbnail": None, "video_name": None}
    executable = ffmpeg_path()
    if not executable:
        return {"thumbnail": None, "video_name": first_video.name}

    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            thumb_path = tmp.name

        result = subprocess.run(
            [
                executable,
                "-y",
                "-hide_banner",
                "-ss",
                "00:00:01",
                "-i",
                str(first_video),
                "-frames:v",
                "1",
                "-q:v",
                "4",
                "-vf",
                "scale=320:-2",
                thumb_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and Path(thumb_path).is_file() and Path(thumb_path).stat().st_size > 0:
            import base64
            img_b64 = base64.b64encode(Path(thumb_path).read_bytes()).decode("ascii")
            Path(thumb_path).unlink(missing_ok=True)
            return {
                "thumbnail": f"data:image/jpeg;base64,{img_b64}",
                "video_name": first_video.name,
                "video_count": len(videos),
            }

        Path(thumb_path).unlink(missing_ok=True)
        return {"thumbnail": None, "video_name": first_video.name, "video_count": len(videos)}
    except Exception:
        return {"thumbnail": None, "video_name": first_video.name}


# ─── List uploaded files from a session ────────────────────────────────────────


@router.post("/uploaded-files")
async def list_uploaded_files(data: dict[str, Any]) -> dict[str, Any]:
    """List videos in a given session directory."""
    session_dir = data.get("session_dir", "")
    if not session_dir:
        return {"videos": [], "count": 0}
    folder = Path(session_dir)
    if not folder.is_dir():
        return {"videos": [], "count": 0}
    videos = list_video_files(folder, recursive=False)
    return {
        "videos": [str(v) for v in videos],
        "count": len(videos),
        "folder": str(folder),
    }


# ─── Get template info ────────────────────────────────────────────────────────


@router.get("/templates")
async def get_templates() -> dict[str, Any]:
    labels = get_template_labels()
    configs = {}
    for label in labels:
        cfg = TEMPLATE_CONFIGS.get(label)
        if cfg:
            configs[label] = {
                "max_width": cfg.max_width,
                "max_height": cfg.max_height,
                "top_y": cfg.top_y,
                "bottom_y": cfg.bottom_y,
                "font_size": cfg.font_size,
                "bands": cfg.bands,
            }
    return {"labels": labels, "configs": configs}


# ─── Start video processing (from uploaded files) ──────────────────────────────


@router.post("/process")
async def start_processing(req: ProcessRequest) -> dict[str, Any]:
    executable = ffmpeg_path()
    if not executable:
        raise HTTPException(400, "FFmpeg não foi encontrado no sistema.")

    # Use uploaded video files or fall back to folder
    if req.video_files and len(req.video_files) > 0:
        video_files = [Path(p) for p in req.video_files if Path(p).is_file()]
        if not video_files:
            raise HTTPException(400, "Nenhum arquivo de vídeo válido encontrado nos arquivos enviados.")
    else:
        raise HTTPException(400, "Envie vídeos primeiro via upload arrastando-os para a área de upload.")

    if len(video_files) > UPLOAD_MAX_FILES:
        raise HTTPException(400, f"Máximo de {UPLOAD_MAX_FILES} vídeos por lote.")

    output_folder = Path(req.output_folder) if req.output_folder else default_output_dir()
    bg_image = Path(req.background_image) if req.background_image else default_background_path()

    if not bg_image.is_file():
        raise HTTPException(400, "Imagem de fundo não encontrada. Use a imagem padrão ou faça upload de uma.")

    logo_path: Path | None = None
    if req.apply_watermark and req.logo_image:
        logo_path = Path(req.logo_image)
        if not logo_path.is_file():
            raise HTTPException(400, "Logo não encontrada. Faça upload da logo primeiro.")

    ensure_directory(output_folder)

    options = RenderOptions(
        background_image=bg_image,
        logo_image=logo_path,
        output_dir=output_folder,
        text_watermark=req.text_watermark,
        text_watermark_font_size=req.text_watermark_size,
        text_watermark_offset_x=req.text_watermark_offset_x,
        text_watermark_offset_y=req.text_watermark_offset_y,
        video_size_percent=req.video_size,
        video_width_percent=req.video_width,
        video_offset_x=req.video_offset_x,
        video_offset_y=req.video_offset_y,
        max_duration=req.max_duration,
        template=req.template or get_template_labels()[0],
        apply_watermark=req.apply_watermark,
        apply_text_watermark=req.apply_text_watermark,
        remove_center_watermark=req.remove_center_watermark,
        delogo_x=req.delogo_x,
        delogo_y=req.delogo_y,
        delogo_width=req.delogo_width,
        delogo_height=req.delogo_height,
        ffmpeg_executable=executable,
    )

    task_id = uuid.uuid4().hex
    # Use thread-safe queue.Queue for cross-thread communication
    log_queue: queue.Queue[str] = queue.Queue()
    progress_queue: queue.Queue[float] = queue.Queue()

    _tasks[task_id] = {
        "log_queue": log_queue,
        "progress_queue": progress_queue,
        "completed": False,
        "summary": None,
        "cancelled": False,
    }

    # Run processing in the thread pool executor
    def _run():
        try:
            summary = process_videos(
                video_files,
                options,
                log_callback=lambda msg: log_queue.put(msg),
                progress_callback=lambda val: progress_queue.put(val),
            )
            _tasks[task_id]["completed"] = True
            _tasks[task_id]["summary"] = {
                "successes": summary.successes,
                "failures": summary.failures,
                "output_files": [str(p) for p in summary.output_files],
                "total": summary.total,
            }
            log_queue.put(f"✅ Processamento concluído: {summary.successes} sucesso(s), {summary.failures} erro(s).")
        except Exception as exc:
            log_queue.put(f"❌ Erro: {exc}")
            _tasks[task_id]["completed"] = True
            _tasks[task_id]["summary"] = {"error": str(exc)}

    _executor.submit(_run)

    return {
        "task_id": task_id,
        "video_count": len(video_files),
        "output_folder": str(output_folder),
        "video_files": [str(v) for v in video_files],
    }


# ─── SSE stream for task logs ─────────────────────────────────────────────────


@router.get("/stream/{task_id}")
async def stream_task(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    async def event_generator():
        log_q: queue.Queue[str] = task["log_queue"]
        progress_q: queue.Queue[float] = task["progress_queue"]
        loop = asyncio.get_running_loop()

        while not task["completed"]:
            # Drain log messages via thread-safe executor
            while not log_q.empty():
                try:
                    msg = await loop.run_in_executor(None, log_q.get_nowait)
                except queue.Empty:
                    break
                yield f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"

            # Drain progress
            while not progress_q.empty():
                try:
                    val = await loop.run_in_executor(None, progress_q.get_nowait)
                except queue.Empty:
                    break
                yield f"data: {json.dumps({'type': 'progress', 'value': val})}\n\n"

            await asyncio.sleep(0.1)

        # Task completed — drain remaining items
        while not log_q.empty():
            try:
                msg = await loop.run_in_executor(None, log_q.get_nowait)
            except queue.Empty:
                break
            yield f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"
        while not progress_q.empty():
            try:
                val = await loop.run_in_executor(None, progress_q.get_nowait)
            except queue.Empty:
                break
            yield f"data: {json.dumps({'type': 'progress', 'value': val})}\n\n"

        summary = task["summary"]
        yield f"data: {json.dumps({'type': 'complete', 'summary': summary})}\n\n"

        # Cleanup
        _tasks.pop(task_id, None)

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Get FFmpeg status ────────────────────────────────────────────────────────


@router.get("/ffmpeg-check")
async def check_ffmpeg() -> dict[str, Any]:
    exe = ffmpeg_path()
    if exe:
        return {"found": True, "path": exe}
    return {"found": False, "path": None}


# ─── Get default paths ────────────────────────────────────────────────────────


@router.get("/default-paths")
async def default_paths() -> dict[str, str]:
    return {
        "input_folder": "entrada (pasta interna do servidor)",
        "output_folder": "saida (pasta interna do servidor)",
        "background_image": str(default_background_path()),
        "upload_dir": "uploads (pasta interna do servidor)",
    }


# ─── Get upload limit info ───────────────────────────────────────────────────


@router.get("/upload-limits")
async def upload_limits() -> dict[str, Any]:
    return {
        "max_files": UPLOAD_MAX_FILES,
        "max_size_mb": UPLOAD_MAX_SIZE_MB,
        "allowed_video_extensions": list(ALLOWED_VIDEO_EXTENSIONS),
        "allowed_image_extensions": list(ALLOWED_IMAGE_EXTENSIONS),
    }
