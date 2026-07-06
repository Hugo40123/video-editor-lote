"""API routes for application settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter
import requests

from app.repository import get_all_settings, get_setting, save_settings_bulk, set_setting
from app.utils import load_settings, save_settings, writable_root

router = APIRouter()


def _presets_dir() -> Path:
    """Path to the presets folder."""
    d = writable_root() / "config" / "presets"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─── Get all settings ─────────────────────────────────────────────────────────


@router.get("")
async def read_all_settings() -> dict[str, Any]:
    """Get all settings merged from DB and legacy JSON file."""
    db_settings = get_all_settings()
    json_settings = load_settings()

    # Merge: DB values take priority over JSON
    merged = {**{str(k): str(v) for k, v in json_settings.items()}, **db_settings}
    return {"settings": merged, "source": "db" if db_settings else "json"}


# ─── Update settings (bulk) ──────────────────────────────────────────────────


@router.put("")
async def update_settings(data: dict[str, str]) -> dict[str, Any]:
    """Save settings to both DB and legacy JSON file."""
    # Save to database
    save_settings_bulk(data)

    # Also save to legacy JSON for compatibility
    try:
        json_compat = {}
        json_settings = load_settings()
        if json_settings:
            json_compat = dict(json_settings)
        json_compat.update(data)
        save_settings(json_compat)
    except OSError:
        pass  # Non-critical; DB is the primary source

    return {"saved": True, "count": len(data)}


# ═══════════════════════════════════════════════════════════════════════════════
# EDITOR PRESETS (file-based in config/presets/)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/presets/list")
async def list_presets() -> dict[str, Any]:
    """List all saved editor presets from config/presets/ folder."""
    presets_dir = _presets_dir()
    presets = []
    for f in sorted(presets_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            presets.append({"name": f.stem, "data": data})
        except (json.JSONDecodeError, OSError):
            pass
    return {"presets": presets}


@router.post("/presets/save")
async def save_preset(data: dict[str, Any]) -> dict[str, Any]:
    """Save a preset as a JSON file in config/presets/."""
    name = (data.get("name") or "").strip()
    if not name:
        return {"error": "Nome do preset e obrigatorio."}

    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    if not safe_name:
        return {"error": "Nome invalido."}

    preset_data = {
        "video_template": data.get("video_template", ""),
        "video_size": data.get("video_size", 100),
        "video_width": data.get("video_width", 100),
        "video_offset_x": data.get("video_offset_x", 0),
        "video_offset_y": data.get("video_offset_y", 0),
        "apply_watermark": data.get("apply_watermark", False),
        "apply_text_watermark": data.get("apply_text_watermark", False),
        "text_watermark": data.get("text_watermark", ""),
        "text_watermark_size": data.get("text_watermark_size", 76),
        "text_watermark_offset_x": data.get("text_watermark_offset_x", 0),
        "text_watermark_offset_y": data.get("text_watermark_offset_y", 0),
        "remove_center_watermark": data.get("remove_center_watermark", False),
        "delogo_x": data.get("delogo_x", 190),
        "delogo_y": data.get("delogo_y", 860),
        "delogo_width": data.get("delogo_width", 700),
        "delogo_height": data.get("delogo_height", 160),
        "generate_cover_frame": data.get("generate_cover_frame", False),
        "rounded_corners": data.get("rounded_corners", False),
        "corner_radius": data.get("corner_radius", 30),
        "max_duration": data.get("max_duration", ""),
    }

    filepath = _presets_dir() / f"{safe_name}.json"
    filepath.write_text(json.dumps(preset_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"saved": True, "name": name, "file": str(filepath)}


@router.post("/presets/load")
async def load_preset(data: dict[str, str]) -> dict[str, Any]:
    """Load a preset by name from config/presets/ folder."""
    name = (data.get("name") or "").strip()
    if not name:
        return {"error": "Nome do preset e obrigatorio."}

    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    filepath = _presets_dir() / f"{safe_name}.json"

    if not filepath.is_file():
        return {"error": f"Preset '{name}' nao encontrado."}

    try:
        preset_data = json.loads(filepath.read_text(encoding="utf-8"))
        return {"preset": preset_data, "name": name}
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Erro ao ler preset: {e}"}


@router.delete("/presets/{name}")
async def delete_preset(name: str) -> dict[str, Any]:
    """Delete a preset file from config/presets/."""
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    filepath = _presets_dir() / f"{safe_name}.json"

    if not filepath.is_file():
        return {"error": f"Preset '{name}' nao encontrado."}

    filepath.unlink()
    remaining = len(list(_presets_dir().glob("*.json")))
    return {"deleted": True, "name": name, "total": remaining}


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE SETTING (MUST BE LAST - catches all)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{key}")
async def read_setting(key: str) -> dict[str, str]:
    value = get_setting(key)
    return {"key": key, "value": value}


# ─── Debug Instagram Connection ────────────────────────────────────────────────


@router.get("/debug/instagram")
async def debug_instagram() -> dict[str, Any]:
    """Debug endpoint to test Instagram token and find correct IG User ID."""
    settings = get_all_settings()
    json_settings = load_settings()
    merged = {**{str(k): str(v) for k, v in json_settings.items()}, **settings}

    token = merged.get("instagram_access_token", "")
    ig_user_id = merged.get("instagram_user_id", "")

    if not token:
        return {
            "error": "Token de acesso não configurado",
            "help": "Configure instagram_access_token nas configurações"
        }

    # Step 1: Test token validity - get pages
    try:
        pages_response = requests.get(
            "https://graph.facebook.com/v25.0/me/accounts",
            params={"access_token": token},
            timeout=10
        )
        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "error": "Token inválido",
                "details": pages_data["error"],
                "help": "Gere um novo token no Graph API Explorer"
            }

        pages = pages_data.get("data", [])
        if not pages:
            return {
                "error": "Nenhuma página encontrada",
                "help": "O token precisa ter permissão pages_show_list"
            }

        # Step 2: For each page, get connected Instagram account
        results = []
        for page in pages:
            page_id = page.get("id")
            page_name = page.get("name")
            page_token = page.get("access_token", token)

            try:
                ig_response = requests.get(
                    f"https://graph.facebook.com/v25.0/{page_id}",
                    params={
                        "fields": "instagram_business_account",
                        "access_token": page_token
                    },
                    timeout=10
                )
                ig_data = ig_response.json()

                ig_account = ig_data.get("instagram_business_account", {})
                if ig_account:
                    results.append({
                        "page_name": page_name,
                        "page_id": page_id,
                        "ig_user_id": ig_account.get("id"),
                        "status": "CONTA INSTAGRAM ENCONTRADA"
                    })
                else:
                    results.append({
                        "page_name": page_name,
                        "page_id": page_id,
                        "ig_user_id": None,
                        "status": "SEM CONTA INSTAGRAM VINCULADA"
                    })
            except Exception as e:
                results.append({
                    "page_name": page_name,
                    "page_id": page_id,
                    "error": str(e)
                })

        return {
            "token_valido": True,
            "paginas_encontradas": len(pages),
            "resultado": results,
            "configurado": {
                "instagram_user_id": ig_user_id,
                "token_preview": token[:20] + "..." if len(token) > 20 else token
            },
            "help": "Use o 'ig_user_id' retornado como instagram_user_id nas configurações"
        }

    except Exception as e:
        return {
            "error": f"Falha ao conectar: {str(e)}",
            "help": "Verifique sua conexão com a internet"
        }
