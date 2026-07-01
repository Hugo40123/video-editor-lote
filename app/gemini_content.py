"""Google Gemini API — Content generation from video.

Gemini processes video/audio natively, replacing the need for
Whisper (transcription) + Ollama (text generation).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from .content_generator import ContentDraft, generate_content_draft


class GeminiError(RuntimeError):
    pass


LogCallback = Callable[[str], None]

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1600


def generate_content_from_video(
    video_path: Path,
    *,
    api_key: str,
    keywords: str = "",
    base_hashtags: str = "#achadinhos #shopee #mercadolivre",
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_output_tokens: int = DEFAULT_MAX_TOKENS,
    log_callback: LogCallback | None = None,
) -> ContentDraft | None:
    """Generate Instagram caption from a video using Gemini.

    Uploads the video to Gemini's File API, then sends a single
    prompt that handles both transcription AND caption writing.

    Returns None if the API call fails (caller should fall back).
    """
    if not api_key or not api_key.strip():
        _log(log_callback, "Gemini API key nao configurada.")
        return None

    if not video_path.is_file():
        _log(log_callback, f"Video nao encontrado: {video_path}")
        return None

    try:
        from google import genai
    except ImportError:
        _log(log_callback, "Pacote google-genai nao instalado. Execute: pip install google-genai")
        return None

    try:
        client = genai.Client(api_key=api_key.strip())
    except Exception as exc:
        _log(log_callback, f"Erro ao inicializar Gemini: {exc}")
        return None

    # 1. Upload video to Gemini File API
    _log(log_callback, "Enviando video para o Gemini (pode levar alguns segundos)...")
    try:
        video_file = client.files.upload(path=str(video_path))
        _log(log_callback, f"Video enviado: {video_file.name}")
    except Exception as exc:
        _log(log_callback, f"Erro ao enviar video para Gemini: {exc}")
        return None

    # 2. Wait for file processing
    _log(log_callback, "Aguardando processamento do video pelo Gemini...")
    try:
        import time
        while video_file.state.name == "PROCESSING":
            _log(log_callback, ".")
            time.sleep(2)
            video_file = client.files.get(name=video_file.name)

        if video_file.state.name == "FAILED":
            _log(log_callback, "Falha no processamento do video pelo Gemini.")
            return None
        _log(log_callback, " Video processado com sucesso!")
    except Exception as exc:
        _log(log_callback, f"Erro ao aguardar processamento: {exc}")
        return None

    # 3. Send prompt with video + transcription + caption request
    system_instruction = (
        "Voce e um copywriter brasileiro especializado em posts de afiliados para Instagram. "
        "Sua tarefa tem DUAS partes:\n"
        "1) TRANSCREVA o audio do video fielmente em portugues.\n"
        "2) Com base no que foi visto e ouvido no video, crie uma legenda de Instagram "
        "estilo publi para um Reels de achadinhos.\n\n"
        "Regras da legenda:\n"
        "- Portugues do Brasil, tom persuasivo e natural\n"
        "- Comece com titulo chamativo com emojis\n"
        "- 4 a 6 paragrafos curtos\n"
        "- Explique o problema/desejo e conecte ao produto\n"
        "- NAO copie trechos literais da transcricao\n"
        "- Termine com 'Publi' em linha separada e hashtags\n"
        "- Nao invente precos, descontos, garantias ou lojas\n"
        "- A legenda deve ter entre 800 e 1500 caracteres\n\n"
        "Responda SOMENTE com JSON valido, sem marcacao ```."
    )

    prompt = _build_video_prompt(
        video_name=video_path.name,
        keywords=keywords,
        base_hashtags=base_hashtags,
    )

    _log(log_callback, f"Gerando transcricao + legenda com Gemini ({model})...")
    try:
        response = client.models.generate_content(
            model=model,
            contents=[video_file, prompt],
            config={
                "system_instruction": system_instruction,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "response_mime_type": "application/json",
            },
        )
    except Exception as exc:
        _log(log_callback, f"Gemini API falhou: {exc}")
        return None

    # Clean up the uploaded file
    try:
        client.files.delete(name=video_file.name)
    except Exception:
        pass

    if not response or not response.text:
        _log(log_callback, "Gemini retornou resposta vazia.")
        return None

    content = response.text.strip()
    _log(log_callback, "Resposta recebida do Gemini. Processando...")

    try:
        payload = _parse_json_response(content)
    except (json.JSONDecodeError, ValueError) as exc:
        _log(log_callback, f"Gemini retornou JSON invalido: {exc}")
        return None

    # Extract transcript from response (if included)
    transcript = str(payload.get("transcript") or "").strip()
    if transcript:
        _log(log_callback, f"Transcricao obtida ({len(transcript)} caracteres).")

    # Build the final caption
    caption = str(payload.get("caption") or "").strip()
    if not caption or len(caption) < 100:
        _log(log_callback, "Legenda gerada muito curta ou vazia.")
        # Try fallback
        fallback = generate_content_draft(video_path, keywords=keywords, base_hashtags=base_hashtags)
        return _to_content_draft(fallback, payload, keywords, base_hashtags)

    title = str(payload.get("title") or "").strip()
    cta = str(payload.get("cta") or "").strip()
    hashtags = str(payload.get("hashtags") or "").strip() or base_hashtags
    product_query = str(payload.get("product_query") or "").strip()
    product_keywords = str(payload.get("product_keywords") or "").strip() or keywords

    return ContentDraft(
        title=title or f"O achadinho que chamou atencao",
        caption=_caption_with_hashtags(caption, hashtags),
        cta=cta or "Salva para ver depois e confere o link na bio.",
        hashtags=hashtags,
        product_query=product_query or keywords,
        product_keywords=product_keywords or keywords,
    )


def _build_video_prompt(
    *,
    video_name: str,
    keywords: str,
    base_hashtags: str,
) -> str:
    return f"""
Assista a este video de Reels/achadinhos e execute as duas tarefas abaixo.

Nome do arquivo: {video_name}

Palavras-chave: {keywords or "nenhuma"}
Hashtags base: {base_hashtags or "nenhuma"}

TAREFA 1 - TRANSCRICAO:
Transcreva todo o audio do video fielmente.

TAREFA 2 - LEGENDA:
Crie uma legenda de Instagram estilo publi com base no que voce viu e ouviu.

Responda EXATAMENTE este JSON:
{{
  "transcript": "transcricao completa do audio aqui",
  "title": "titulo chamativo com emojis",
  "caption": "legenda completa para Instagram com Publi e hashtags",
  "cta": "chamada para acao curta",
  "hashtags": "#tag1 #tag2 #tag3",
  "product_query": "termo de busca para marketplace",
  "product_keywords": "palavras-chave separadas por espaco"
}}
""".strip()


def _parse_json_response(content: str) -> dict[str, str]:
    """Parse JSON from Gemini response, handling possible markdown fences."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Nenhum JSON encontrado na resposta.")
        data = json.loads(match.group(0))

    if not isinstance(data, dict):
        raise ValueError("Resposta nao e um dicionario.")

    return {str(k): str(v) for k, v in data.items()}


def _caption_with_hashtags(caption: str, hashtags: str) -> str:
    cleaned_caption = caption.strip()
    cleaned_hashtags = hashtags.strip()
    if not cleaned_hashtags or "#" in cleaned_caption:
        return cleaned_caption
    return f"{cleaned_caption}\n\n{cleaned_hashtags}"


def _to_content_draft(
    fallback: ContentDraft,
    payload: dict[str, str],
    keywords: str,
    base_hashtags: str,
) -> ContentDraft:
    return ContentDraft(
        title=payload.get("title", "").strip() or fallback.title,
        caption=payload.get("caption", "").strip() or fallback.caption,
        cta=payload.get("cta", "").strip() or fallback.cta,
        hashtags=payload.get("hashtags", "").strip() or fallback.hashtags,
        product_query=payload.get("product_query", "").strip() or fallback.product_query,
        product_keywords=payload.get("product_keywords", "").strip() or fallback.product_keywords,
    )


def _log(callback: LogCallback | None, message: str) -> None:
    if callback:
        callback(message)
