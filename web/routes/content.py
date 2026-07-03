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
    FreeAiResult,
    generate_ai_content_from_video,
)
from app.repository import create_post, get_post, update_post
from app.utils import ffmpeg_path

router = APIRouter()


class AiConfigData(BaseModel):
    provider: str = "groq"  # "groq" or "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"


class GenerateRequest(BaseModel):
    video_path: str
    keywords: str = ""
    base_hashtags: str = "#achadinhos #shopee #mercadolivre"
    ai_config: AiConfigData | None = None


# ─── Test Gemini connection ───────────────────────────────────────────────────


@router.post("/test-gemini")
async def test_gemini(data: AiConfigData) -> dict[str, Any]:
    """Test the Gemini API connection with multiple methods."""
    api_key = data.gemini_api_key or ""
    if not api_key.strip():
        return {"success": False, "error": "API key nao informada."}

    key = api_key.strip()
    logs = []

    # Method 1: Raw HTTP request (bypass library)
    logs.append("Teste 1: Chamada HTTP direta...")
    try:
        import requests
        model = data.gemini_model or "gemini-2.0-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        resp = requests.post(
            url,
            json={"contents": [{"parts": [{"text": "Responda apenas: OK"}]}]},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        logs.append(f"HTTP {resp.status_code}")
        if resp.status_code == 200:
            body = resp.json()
            text = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if text:
                logs.append(f"Resposta: {text.strip()}")
                return {"success": True, "message": "Conexao OK!", "logs": logs}
        elif resp.status_code == 429:
            logs.append("Limite de requisicoes atingido (quota do tier gratuito).")
            logs.append("Solucao: configure faturamento no Google Cloud Console ou aguarde.")
            return {"success": False, "error": "Quota do tier gratuito atingido.", "logs": logs}
        elif resp.status_code == 404:
            logs.append(f"Modelo '{model}' nao encontrado. Tentando gemini-2.0-flash...")
            # Retry with a known model
            url2 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
            resp2 = requests.post(
                url2,
                json={"contents": [{"parts": [{"text": "Responda apenas: OK"}]}]},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if resp2.status_code == 200:
                body2 = resp2.json()
                text2 = body2.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if text2:
                    logs.append(f"Modelo gemini-2.0-flash OK! Resposta: {text2.strip()}")
                    logs.append("ATENCAO: O modelo configurado nao existe. Use 'gemini-2.0-flash'.")
                    return {"success": True, "message": "Conexao OK! (modelo ajustado para gemini-2.0-flash)", "logs": logs}
            logs.append(f"Falha no modelo fallback tambem (HTTP {resp2.status_code})")
        else:
            error_body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_body.get("error", {}).get("message", resp.text[:200])
            logs.append(f"Erro HTTP: {error_msg}")
    except Exception as e:
        logs.append(f"Erro HTTP: {e}")

    # Method 2: google-genai library
    logs.append("Teste 2: Biblioteca google-genai...")
    try:
        from google import genai
        client = genai.Client(api_key=key)
        model_name = data.gemini_model or "gemini-2.0-flash"
        response = client.models.generate_content(
            model=model_name,
            contents="Responda apenas: OK",
            config={"max_output_tokens": 10},
        )
        if response and response.text:
            logs.append(f"Resposta: {response.text.strip()}")
            return {"success": True, "message": "Conexao OK!", "logs": logs}
        logs.append("Resposta vazia da API")
    except ImportError:
        logs.append("Pacote google-genai nao instalado")
    except Exception as e:
        logs.append(f"Erro lib: {str(e)[:150]}")

    return {"success": False, "error": "Falha na conexao. Veja os logs.", "logs": logs}


# ─── Test Groq connection ────────────────────────────────────────────────────


@router.post("/test-groq")
async def test_groq(data: AiConfigData) -> dict[str, Any]:
    """Test the Groq API connection."""
    api_key = data.groq_api_key or ""
    if not api_key.strip():
        return {"success": False, "error": "Groq API key nao informada.", "logs": []}

    key = api_key.strip()
    logs = []

    # Test 1: Raw HTTP
    logs.append("Teste 1: Chamada HTTP direta...")
    try:
        import requests
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": "Responda apenas: OK"}],
                "max_tokens": 5,
            },
            timeout=30,
        )
        logs.append(f"HTTP {resp.status_code}")
        if resp.status_code == 200:
            body = resp.json()
            text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            if text:
                logs.append(f"Resposta: {text.strip()}")
                return {"success": True, "message": "Conexao Groq OK!", "logs": logs}
        else:
            error_msg = resp.json().get("error", {}).get("message", resp.text[:200])
            logs.append(f"Erro: {error_msg}")
    except Exception as e:
        logs.append(f"Erro HTTP: {e}")

    # Test 2: groq library
    logs.append("Teste 2: Biblioteca groq...")
    try:
        from groq import Groq
        client = Groq(api_key=key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Responda apenas: OK"}],
            max_tokens=5,
        )
        if response and response.choices:
            text = response.choices[0].message.content
            logs.append(f"Resposta: {text.strip() if text else 'vazia'}")
            return {"success": True, "message": "Conexao Groq OK!", "logs": logs}
        logs.append("Resposta vazia")
    except ImportError:
        logs.append("Pacote groq nao instalado")
    except Exception as e:
        logs.append(f"Erro lib: {str(e)[:150]}")

    return {"success": False, "error": "Falha na conexao Groq. Veja os logs.", "logs": logs}


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
    provider = config_data.provider or "groq"

    if provider == "groq":
        config = FreeAiConfig(
            provider="groq",
            api_key=config_data.groq_api_key or "",
            model=config_data.groq_model or "llama-3.1-8b-instant",
        )
    else:
        config = FreeAiConfig(
            provider="gemini",
            api_key=config_data.gemini_api_key or "",
            model=config_data.gemini_model or "gemini-2.0-flash",
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
        result: FreeAiResult = await loop.run_in_executor(None, _run_ai)
        return {
            "success": True,
            "title": result.draft.title,
            "caption": result.draft.caption,
            "cta": result.draft.cta,
            "hashtags": result.draft.hashtags,
            "product_query": result.draft.product_query,
            "product_keywords": result.draft.product_keywords,
            "has_audio": result.has_audio,
            "transcript": result.transcript,
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
