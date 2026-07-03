"""API routes for application settings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
import requests

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
