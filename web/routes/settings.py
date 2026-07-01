"""API routes for application settings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.repository import get_all_settings, get_setting, save_settings_bulk, set_setting
from app.utils import load_settings, save_settings

router = APIRouter()


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


# ─── Get single setting ───────────────────────────────────────────────────────


@router.get("/{key}")
async def read_setting(key: str) -> dict[str, str]:
    value = get_setting(key)
    return {"key": key, "value": value}
