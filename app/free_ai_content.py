"""AI content generation — supports Groq and Gemini.

Strategy: extract audio → transcribe → generate caption.
If no audio: fallback to frame or local generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .content_generator import ContentDraft, generate_content_draft


class FreeAiError(RuntimeError):
    pass


@dataclass(frozen=True)
class FreeAiConfig:
    provider: str = "groq"  # "groq" or "gemini"
    api_key: str = ""
    model: str = ""


@dataclass
class FreeAiResult:
    draft: ContentDraft
    has_audio: bool
    transcript: str


LogCallback = Callable[[str], None]


def generate_ai_content_from_video(
    video_path: Path,
    *,
    config: FreeAiConfig,
    ffmpeg_executable: str,
    keywords: str,
    base_hashtags: str,
    log_callback: LogCallback | None = None,
) -> FreeAiResult:
    """Generate Instagram caption using the configured AI provider."""
    if not video_path.is_file():
        raise FreeAiError("O video selecionado nao foi encontrado.")

    api_key = (config.api_key or "").strip()

    if not api_key:
        _log(log_callback, f"Chave da API {config.provider} nao configurada. Usando gerador local.")
        draft = generate_content_draft(video_path, keywords=keywords, base_hashtags=base_hashtags)
        return FreeAiResult(draft=draft, has_audio=False, transcript="")

    if config.provider == "groq":
        return _generate_with_groq(
            video_path, api_key=api_key, model=config.model,
            keywords=keywords, base_hashtags=base_hashtags,
            ffmpeg_executable=ffmpeg_executable, log_callback=log_callback,
        )
    elif config.provider == "gemini":
        return _generate_with_gemini(
            video_path, api_key=api_key, model=config.model,
            keywords=keywords, base_hashtags=base_hashtags,
            ffmpeg_executable=ffmpeg_executable, log_callback=log_callback,
        )
    else:
        _log(log_callback, f"Provider desconhecido: {config.provider}")
        draft = generate_content_draft(video_path, keywords=keywords, base_hashtags=base_hashtags)
        return FreeAiResult(draft=draft, has_audio=False, transcript="")


def _generate_with_groq(
    video_path, *, api_key, model, keywords, base_hashtags, ffmpeg_executable, log_callback,
) -> FreeAiResult:
    from .groq_content import generate_content_from_video as groq_generate

    _log(log_callback, "Usando Groq (Whisper + Llama)...")
    draft, has_audio, transcript = groq_generate(
        video_path,
        api_key=api_key,
        keywords=keywords,
        base_hashtags=base_hashtags,
        llm_model=model or "llama-3.1-8b-instant",
        log_callback=log_callback,
        ffmpeg_executable=ffmpeg_executable,
    )

    if draft is not None:
        _log(log_callback, "Conteudo gerado com Groq!")
        return FreeAiResult(draft=draft, has_audio=has_audio, transcript=transcript)

    _log(log_callback, "Groq falhou. Usando gerador local.")
    draft = generate_content_draft(video_path, keywords=keywords, base_hashtags=base_hashtags)
    return FreeAiResult(draft=draft, has_audio=has_audio, transcript=transcript)


def _generate_with_gemini(
    video_path, *, api_key, model, keywords, base_hashtags, ffmpeg_executable, log_callback,
) -> FreeAiResult:
    from .gemini_content import generate_content_from_video as gemini_generate

    _log(log_callback, "Usando Google Gemini...")
    draft, has_audio, transcript = gemini_generate(
        video_path,
        api_key=api_key,
        keywords=keywords,
        base_hashtags=base_hashtags,
        model=model or "gemini-2.0-flash",
        log_callback=log_callback,
        ffmpeg_executable=ffmpeg_executable,
    )

    if draft is not None:
        _log(log_callback, "Conteudo gerado com Gemini!")
        return FreeAiResult(draft=draft, has_audio=has_audio, transcript=transcript)

    _log(log_callback, "Gemini falhou. Usando gerador local.")
    draft = generate_content_draft(video_path, keywords=keywords, base_hashtags=base_hashtags)
    return FreeAiResult(draft=draft, has_audio=has_audio, transcript=transcript)


def _log(callback: LogCallback | None, message: str) -> None:
    if callback:
        callback(message)
