"""Groq API — Transcription + caption generation.

Groq offers free tier with generous limits:
- 30 req/min, 14,400 req/day
- Whisper large-v3 for transcription
- Llama 3.1 for text generation
- Very fast inference
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .content_generator import ContentDraft, generate_content_draft


LogCallback = Callable[[str], None]

DEFAULT_WHISPER_MODEL = "whisper-large-v3"
DEFAULT_LLM_MODEL = "llama-3.1-8b-instant"
MIN_AUDIO_DURATION = 1.0


def generate_content_from_video(
    video_path: Path,
    *,
    api_key: str,
    keywords: str = "",
    base_hashtags: str = "#achadinhos #shopee #mercadolivre",
    whisper_model: str = DEFAULT_WHISPER_MODEL,
    llm_model: str = DEFAULT_LLM_MODEL,
    log_callback: LogCallback | None = None,
    ffmpeg_executable: str = "ffmpeg",
) -> tuple[ContentDraft | None, bool, str]:
    """Generate Instagram caption from video using Groq.

    1. Extract audio with FFmpeg
    2. Transcribe with Whisper on Groq
    3. Generate caption with Llama on Groq

    Returns (draft, has_audio, transcript).
    """
    if not api_key or not api_key.strip():
        _log(log_callback, "Groq API key nao configurada.")
        return None, False, ""

    if not video_path.is_file():
        _log(log_callback, f"Video nao encontrado: {video_path}")
        return None, False, ""

    try:
        from groq import Groq
    except ImportError:
        _log(log_callback, "Pacote groq nao instalado.")
        return None, False, ""

    try:
        client = Groq(api_key=api_key.strip())
    except Exception as exc:
        _log(log_callback, f"Erro ao inicializar Groq: {exc}")
        return None, False, ""

    # 1. Extract audio
    _log(log_callback, f"Extraindo audio do video: {video_path.name}")
    audio_path = _extract_audio(video_path, ffmpeg_executable)
    has_audio = False
    transcript = ""

    if audio_path:
        _log(log_callback, f"Audio extraido com sucesso: {audio_path}")
        duration = _get_audio_duration(audio_path, ffmpeg_executable)
        if duration:
            _log(log_callback, f"Duracao do audio: {duration:.1f}s (minimo: {MIN_AUDIO_DURATION}s)")
        else:
            _log(log_callback, "Nao foi possivel obter duracao do audio.")
        
        if duration and duration >= MIN_AUDIO_DURATION:
            has_audio = True
            _log(log_callback, f"Audio encontrado ({duration:.1f}s). Transcrevendo com Groq Whisper...")
            transcript = _transcribe_audio(client, audio_path, whisper_model, log_callback)
        else:
            _log(log_callback, "Audio muito curto ou vazio.")
        try:
            Path(audio_path).unlink(missing_ok=True)
        except Exception:
            pass
    else:
        _log(log_callback, "Nenhum audio encontrado no video. Verifique se o video possui trilha de audio.")

    # 2. Generate caption
    if has_audio and transcript:
        _log(log_callback, "Gerando legenda com Llama...")
        draft = _generate_from_transcript(
            client, transcript, video_path.name,
            keywords=keywords, base_hashtags=base_hashtags,
            llm_model=llm_model, log_callback=log_callback,
        )
        if draft:
            return draft, True, transcript

    # 3. Fallback: use frame
    _log(log_callback, "Gerando legenda a partir do frame (sem audio)...")
    draft = _generate_from_frame(
        client, video_path, keywords=keywords,
        base_hashtags=base_hashtags, llm_model=llm_model,
        log_callback=log_callback, ffmpeg_executable=ffmpeg_executable,
    )
    return draft, has_audio, transcript


def _extract_audio(video_path: Path, ffmpeg: str) -> str | None:
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        _log(None, f"Extraindo audio de: {video_path}")
        result = subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-i", str(video_path),
             "-vn", "-acodec", "libmp3lame", "-q:a", "4", tmp.name],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            _log(None, f"FFmpeg falhou (code {result.returncode}): {result.stderr[:200] if result.stderr else 'sem stderr'}")
            Path(tmp.name).unlink(missing_ok=True)
            return None
        
        file_size = Path(tmp.name).stat().st_size
        _log(None, f"Audio extraido: {tmp.name} ({file_size} bytes)")
        
        if file_size < 1000:
            _log(None, f"Audio muito pequeno ({file_size} bytes), ignorando.")
            Path(tmp.name).unlink(missing_ok=True)
            return None
        
        return tmp.name
    except Exception as e:
        _log(None, f"Erro ao extrair audio: {e}")
        return None


def _get_audio_duration(audio_path: str, ffmpeg: str) -> float | None:
    try:
        import shutil
        ffprobe = shutil.which("ffprobe") or ffmpeg.replace("ffmpeg", "ffprobe")
        _log(None, f"Verificando duracao com ffprobe: {ffprobe}")
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            _log(None, f"ffprobe falhou: {result.stderr[:100] if result.stderr else ''}")
            return None
        
        duration_str = result.stdout.strip()
        if not duration_str:
            _log(None, "ffprobe retornou duracao vazia.")
            return None
        
        duration = float(duration_str)
        _log(None, f"Duracao obtida: {duration:.2f}s")
        return duration
    except Exception as e:
        _log(None, f"Erro ao obter duracao: {e}")
        return None


def _extract_frame(video_path: Path, ffmpeg: str) -> str | None:
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        result = subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-ss", "00:00:01",
             "-i", str(video_path), "-frames:v", "1", "-q:v", "2", tmp.name],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and Path(tmp.name).stat().st_size > 0:
            return tmp.name
        Path(tmp.name).unlink(missing_ok=True)
        return None
    except Exception:
        return None


def _transcribe_audio(client, audio_path: str, model: str, log_callback) -> str:
    try:
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                file=(audio_path, f),
                model=model,
                language="pt",
            )
        if result and result.text:
            _log(log_callback, f"Transcricao obtida ({len(result.text)} caracteres).")
            return result.text.strip()
        return ""
    except Exception as exc:
        _log(log_callback, f"Erro na transcricao: {exc}")
        return ""


def _generate_from_transcript(
    client, transcript: str, video_name: str, *,
    keywords: str, base_hashtags: str, llm_model: str,
    log_callback,
) -> ContentDraft | None:
    system_instruction = (
        "Voce e um copywriter brasileiro especializado em posts de afiliados para Instagram. "
        "Voce recebeu a transcricao de um video de Reels/achadinhos.\n\n"
        "Regras:\n"
        "- Portugues do Brasil, tom persuasivo e natural\n"
        "- Comece com titulo chamativo com emojis\n"
        "- 4 a 6 paragrafos curtos\n"
        "- Identifique TODOS os produtos mencionados na transcricao\n"
        "- NAO copie trechos literais da transcricao\n"
        "- NAO invente precos, descontos, garantias ou lojas\n"
        "- Termine com 'Publi' em linha separada e hashtags\n"
        "- A legenda deve ter entre 800 e 1500 caracteres\n\n"
        "Responda SOMENTE com JSON valido, sem marcacao ```."
    )

    prompt = f"""Transcricao do video:
---
{transcript}
---

Nome do arquivo: {video_name}
Palavras-chave: {keywords or "nenhuma"}
Hashtags base: {base_hashtags or "nenhuma"}

Crie a legenda de Instagram.

Responda EXATAMENTE este JSON:
{{
  "title": "titulo chamativo com emojis",
  "caption": "legenda completa para Instagram com Publi e hashtags",
  "cta": "chamada para acao curta",
  "hashtags": "#tag1 #tag2 #tag3",
  "product_query": "produto1, produto2",
  "product_keywords": "palavras-chave separadas por espaco"
}}"""

    try:
        response = client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1600,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            return None

        payload = _parse_json_response(content)
        return _payload_to_draft(payload, keywords, base_hashtags)

    except Exception as exc:
        _log(log_callback, f"Erro ao gerar legenda: {exc}")
        return None


def _generate_from_frame(
    client, video_path: Path, *,
    keywords: str, base_hashtags: str, llm_model: str,
    log_callback, ffmpeg_executable: str = "ffmpeg",
) -> ContentDraft | None:
    _log(log_callback, "Nao e possivel enviar imagem ao Groq. Usando fallback local.")
    return None


def _payload_to_draft(payload: dict, keywords: str, base_hashtags: str) -> ContentDraft | None:
    caption = str(payload.get("caption") or "").strip()
    if not caption or len(caption) < 50:
        return None
    return ContentDraft(
        title=str(payload.get("title") or "").strip() or "Achadinho imperdivel",
        caption=_caption_with_hashtags(caption, str(payload.get("hashtags") or base_hashtags)),
        cta=str(payload.get("cta") or "").strip() or "Salva e confere o link na bio.",
        hashtags=str(payload.get("hashtags") or "").strip() or base_hashtags,
        product_query=str(payload.get("product_query") or "").strip(),
        product_keywords=str(payload.get("product_keywords") or "").strip() or keywords,
    )


def _parse_json_response(content: str) -> dict[str, str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Nenhum JSON encontrado.")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Resposta nao e um dicionario.")
    return {str(k): str(v) for k, v in data.items()}


def _caption_with_hashtags(caption: str, hashtags: str) -> str:
    c = caption.strip()
    h = hashtags.strip()
    if not h or "#" in c:
        return c
    return f"{c}\n\n{h}"


def _log(callback: LogCallback | None, message: str) -> None:
    if callback:
        callback(message)
