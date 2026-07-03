"""FastAPI application entry point."""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_database
from app.utils import resource_root, writable_root, upload_dir, default_output_dir


def _find_project_root() -> Path:
    """Find the project root directory (where templates/ and static/ live)."""
    # When frozen, use the exe directory
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # In development, look relative to this file
    here = Path(__file__).resolve().parent.parent
    if (here / "templates").is_dir():
        return here
    return here


PROJECT_ROOT = _find_project_root()
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, start scheduler, and open browser."""
    init_database()
    from app.workers.scheduler import start_scheduler
    start_scheduler()
    # Open browser after server starts
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    yield
    # Shutdown
    from app.workers.scheduler import stop_scheduler
    stop_scheduler()


app = FastAPI(
    title="VideoEditorLote",
    version="2.0.0",
    description="Editor de Vídeos em Lote — Ferramenta de operação para afiliados",
    lifespan=lifespan,
)

# Mount static files
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount assets directory for preview background/logo images
ASSETS_DIR = PROJECT_ROOT / "assets"
if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# Configure templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Import and include route modules
from web.routes import content as content_routes
from web.routes import editor as editor_routes
from web.routes import posts as posts_routes
from web.routes import products as products_routes
from web.routes import settings as settings_routes

app.include_router(editor_routes.router, prefix="/api/editor", tags=["Editor"])
app.include_router(content_routes.router, prefix="/api/content", tags=["Conteúdo"])
app.include_router(posts_routes.router, prefix="/api/posts", tags=["Postagens"])
app.include_router(products_routes.router, prefix="/api/products", tags=["Produtos"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["Configurações"])


# ─── Frontend routes ──────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
async def app_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


# ─── Serve uploaded files (videos, images) ───────────────────────────────────

from fastapi.responses import FileResponse
from fastapi import HTTPException


@app.get("/uploads/{session_id}/{filename}")
async def serve_upload(session_id: str, filename: str):
    """Serve uploaded files securely."""
    # Security: prevent path traversal
    if "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    if "/" in session_id or "\\" in session_id:
        raise HTTPException(400, "Invalid session")
    
    file_path = upload_dir() / session_id / filename
    if not file_path.is_file():
        raise HTTPException(404, "Arquivo não encontrado.")
    
    # Verify file is within upload directory (security check)
    try:
        file_path.resolve().relative_to(upload_dir().resolve())
    except ValueError:
        raise HTTPException(403)
    
    return FileResponse(str(file_path))


@app.get("/output/{filename}")
async def serve_output(filename: str):
    """Serve processed output videos for download."""
    if "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    
    file_path = default_output_dir() / filename
    if not file_path.is_file():
        raise HTTPException(404, "Arquivo não encontrado.")
    
    return FileResponse(str(file_path), media_type="video/mp4", filename=filename)


# ─── Health check ─────────────────────────────────────────────────────────────


@app.get("/api/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    from app.workers.scheduler import get_scheduler
    from app.utils import ffmpeg_path
    from app.repository import get_setting

    # FFmpeg check
    ffmpeg = ffmpeg_path() is not None

    # Gemini check
    gemini_key = get_setting("ai_gemini_key", "")
    gemini = bool(gemini_key)

    # Instagram check
    ig_id = get_setting("instagram_user_id", "")
    ig_token = get_setting("instagram_access_token", "")
    instagram = bool(ig_id and ig_token)

    return {
        "status": "ok",
        "version": "2.3.0",
        "app": "VideoEditorLote",
        "checks": {
            "ffmpeg": ffmpeg,
            "gemini": gemini,
            "instagram": instagram,
        },
        "scheduler_running": get_scheduler().is_running,
    }


# ─── Utility endpoint to get app config paths ─────────────────────────────────


@app.get("/api/config/paths", tags=["System"])
async def config_paths() -> dict[str, str]:
    return {
        "writable_root": str(writable_root()),
        "resource_root": str(resource_root()),
        "input_dir": "entrada (pasta interna do servidor)",
        "output_dir": "saida (pasta interna do servidor)",
    }


def run_server() -> None:
    """Start the FastAPI server with uvicorn."""
    import uvicorn

    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")

    print("  ========================================")
    print(f"  VideoEditorLote v2.9.0")
    print(f"  http://{host}:{port}")
    print(f"  Swagger: http://{host}:{port}/docs")
    print(f"  Pressione Ctrl+C para parar")
    print("  ========================================")
    print()

    uvicorn.run(app, host=host, port=port, log_level="info")
