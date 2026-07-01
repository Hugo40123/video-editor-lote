from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


STOP_WORDS = {
    "video",
    "editado",
    "final",
    "novo",
    "parte",
    "reels",
    "tiktok",
    "whatsapp",
    "instagram",
    "achadinho",
    "achadinhos",
}


@dataclass(frozen=True)
class ContentDraft:
    title: str
    caption: str
    cta: str
    hashtags: str
    product_query: str
    product_keywords: str = ""


def generate_content_draft(video_path: Path, *, keywords: str, base_hashtags: str) -> ContentDraft:
    terms = _extract_terms(video_path, keywords)
    product_query = " ".join(terms[:6]) or _clean_stem(video_path)
    product_name = _pretty_product_name(product_query)
    title = f"Achadinho: {product_name}"
    cta = "Salva para ver depois e confere o link na bio."
    hashtags = _build_hashtags(terms, base_hashtags)

    caption_parts = [
        title,
        "",
        f"Esse achadinho pode ser uma boa opcao para quem procura {product_name.lower()} com praticidade no dia a dia.",
        "",
        cta,
        "",
        hashtags,
    ]
    return ContentDraft(
        title=title,
        caption="\n".join(caption_parts),
        cta=cta,
        hashtags=hashtags,
        product_query=product_query,
        product_keywords=" ".join(terms[:10]),
    )


def _extract_terms(video_path: Path, keywords: str) -> list[str]:
    raw = f"{_clean_stem(video_path)} {keywords}".strip()
    terms: list[str] = []

    for word in re.findall(r"[A-Za-z0-9À-ÿ]+", raw.lower()):
        if len(word) < 3 or word in STOP_WORDS or word.isdigit():
            continue
        if word not in terms:
            terms.append(word)

    return terms


def _clean_stem(video_path: Path) -> str:
    stem = video_path.stem
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem)
    return stem.strip() or "produto"


def _pretty_product_name(product_query: str) -> str:
    cleaned = re.sub(r"\s+", " ", product_query).strip()
    if not cleaned:
        return "produto interessante"
    return cleaned[:1].upper() + cleaned[1:]


def _build_hashtags(terms: list[str], base_hashtags: str) -> str:
    tags: list[str] = []

    for raw_tag in base_hashtags.split():
        tag = _normalize_hashtag(raw_tag)
        if tag and tag not in tags:
            tags.append(tag)

    for term in terms[:8]:
        tag = _normalize_hashtag(term)
        if tag and tag not in tags:
            tags.append(tag)

    defaults = ["#achadinhos", "#ofertas", "#comprasonline"]
    for tag in defaults:
        if tag not in tags:
            tags.append(tag)

    return " ".join(tags[:18])


def _normalize_hashtag(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = cleaned[1:] if cleaned.startswith("#") else cleaned
    cleaned = re.sub(r"[^a-z0-9À-ÿ]+", "", cleaned)
    return f"#{cleaned}" if cleaned else ""
