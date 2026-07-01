"""API routes for AI content generation and management."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.content_generator import generate_content_draft
from app.free_ai_content import (
    FreeAiConfig,
    FreeAiError,
    generate_ai_content_from_video,
)
from app.repository import create_post, get_post, update_post
from app.utils import ffmpeg_path

router = APIRouter()


class AiConfigData(BaseModel):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"


class GenerateRequest(BaseModel):
    video_path: str
    keywords: str = ""
    base_hashtags: str = "#achadinhos #shopee #mercadolivre"
    ai_config: AiConfigData | None = None


# ─── Test Gemini connection ───────────────────────────────────────────────────


@router.post("/test-gemini")
async def test_gemini(data: AiConfigData) -> dict[str, Any]:
    """Test the Gemini API connection."""
    api_key = data.gemini_api_key or ""
    if not api_key.strip():
        return {"success": False, "error": "API key nao informada."}
    try:
        from google import genai
        client = genai.Client(api_key=api_key.strip())
        model = data.gemini_model or "gemini-2.0-flash"
        response = client.models.generate_content(
            model=model,
            contents="Responda apenas: OK",
            config={"max_output_tokens": 10},
        )
        if response and response.text:
            return {"success": True, "message": "Conexao com Gemini OK!"}
        return {"success": False, "error": "Resposta inesperada da API."}
    except ImportError:
        return {"success": False, "error": "Pacote google-genai nao instalado. Execute: pip install google-genai"}
    except Exception as exc:
        return {"success": False, "error": f"Erro: {exc}"}


# ─── Generate content locally ────────────────────────────────────────────────


@router.post("/generate-local")
async def generate_local(req: GenerateRequest) -> dict[str, Any]:
    video_path = Path(req.video_path)
    if not video_path.is_file():
        raise HTTPException(400, "Arquivo de vídeo não encontrado.")

    draft = generate_content_draft(
        video_path,
        keywords=req.keywords,
        base_hashtags=req.base_hashtags,
    )
    return {
        "success": True,
        "title": draft.title,
        "caption": draft.caption,
        "cta": draft.cta,
        "hashtags": draft.hashtags,
        "product_query": draft.product_query,
        "product_keywords": draft.product_keywords,
    }


# ─── Generate content with AI ────────────────────────────────────────────────


@router.post("/generate-ai")
async def generate_ai(req: GenerateRequest) -> dict[str, Any]:
    video_path = Path(req.video_path)
    if not video_path.is_file():
        raise HTTPException(400, "Arquivo de vídeo não encontrado.")

    executable = ffmpeg_path()
    if not executable:
        raise HTTPException(400, "FFmpeg não foi encontrado para extrair áudio/frames.")

    config_data = req.ai_config or AiConfigData()
    config = FreeAiConfig(
        gemini_api_key=config_data.gemini_api_key or "",
        gemini_model=config_data.gemini_model or "gemini-2.0-flash",
    )

    logs: list[str] = []

    def log_cb(msg: str) -> None:
        logs.append(msg)

    # Run blocking AI generation in a thread to avoid blocking the event loop
    loop = asyncio.get_running_loop()

    def _run_ai():
        return generate_ai_content_from_video(
            video_path,
            config=config,
            ffmpeg_executable=executable,
            keywords=req.keywords,
            base_hashtags=req.base_hashtags,
            log_callback=log_cb,
        )

    try:
        draft = await loop.run_in_executor(None, _run_ai)
        return {
            "success": True,
            "title": draft.title,
            "caption": draft.caption,
            "cta": draft.cta,
            "hashtags": draft.hashtags,
            "product_query": draft.product_query,
            "product_keywords": draft.product_keywords,
            "logs": logs,
        }
    except FreeAiError as exc:
        return {
            "success": False,
            "error": str(exc),
            "logs": logs,
        }


# ─── Quick draft from filename + keywords ────────────────────────────────────


@router.post("/draft")
async def quick_draft(data: dict[str, Any]) -> dict[str, Any]:
    """Quick content draft without full video processing."""
    from app.content_generator import generate_content_draft

    video_name = data.get("video_name", "video.mp4")
    keywords = data.get("keywords", "")
    base_hashtags = data.get("base_hashtags", "#achadinhos #shopee #mercadolivre")

    # Create a pseudo-path for name-based generation
    pseudo_path = Path(video_name)
    draft = generate_content_draft(
        pseudo_path,
        keywords=keywords,
        base_hashtags=base_hashtags,
    )
    return {
        "title": draft.title,
        "caption": draft.caption,
        "cta": draft.cta,
        "hashtags": draft.hashtags,
        "product_query": draft.product_query,
        "product_keywords": draft.product_keywords,
    }
