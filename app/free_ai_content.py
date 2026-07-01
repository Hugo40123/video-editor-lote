"""AI content generation — uses Google Gemini as the sole AI provider.

Gemini processes video/audio natively (upload -> transcribe -> caption),
eliminating the need for separate Whisper transcription and Ollama LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .content_generator import ContentDraft, generate_content_draft
from .gemini_content import generate_content_from_video


class FreeAiError(RuntimeError):
    pass


@dataclass(frozen=True)
class FreeAiConfig:
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"


LogCallback = Callable[[str], None]


def generate_ai_content_from_video(
    video_path: Path,
    *,
    config: FreeAiConfig,
    ffmpeg_executable: str,
    keywords: str,
    base_hashtags: str,
    log_callback: LogCallback | None = None,
) -> ContentDraft:
    """Generate Instagram caption from a video using Gemini.

    Calls Gemini's File API to upload the video and generate both
    transcription and caption in a single request.

    Falls back to local draft generator if Gemini is not configured
    or if the API call fails.
    """
    if not video_path.is_file():
        raise FreeAiError("O video selecionado nao foi encontrado.")

    api_key = (config.gemini_api_key or "").strip()

    if not api_key:
        _log(log_callback, "Gemini API key nao configurada. Usando gerador local.")
        return generate_content_draft(video_path, keywords=keywords, base_hashtags=base_hashtags)

    _log(log_callback, "Usando Google Gemini para transcricao e legenda...")
    result = generate_content_from_video(
        video_path,
        api_key=api_key,
        keywords=keywords,
        base_hashtags=base_hashtags,
        model=config.gemini_model or "gemini-2.0-flash",
        log_callback=log_callback,
    )

    if result is not None:
        _log(log_callback, "Conteudo gerado com Gemini API!")
        return result

    _log(log_callback, "Gemini falhou. Usando gerador local como fallback.")
    return generate_content_draft(video_path, keywords=keywords, base_hashtags=base_hashtags)


def _log(callback: LogCallback | None, message: str) -> None:
    if callback:
        callback(message)
