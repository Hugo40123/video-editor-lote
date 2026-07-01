"""API routes for product search and affiliate link management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.database import execute as db_execute
from app.product_search import (
    generate_affiliate_url,
    search_mercadolivre,
    search_shopee,
)
from app.repository import (
    delete_product,
    get_post,
    get_product,
    list_products,
    save_product,
    select_product,
    update_post,
)

router = APIRouter()


class SearchQuery(BaseModel):
    query: str
    sources: list[str] = ["mercadolivre", "shopee"]
    limit: int = 10


class AssociateProduct(BaseModel):
    post_id: str
    source: str
    product_id: str
    title: str
    price: float = 0.0
    currency: str = "BRL"
    thumbnail_url: str = ""
    permalink: str = ""
    affiliate_url: str = ""
    store_name: str = ""
    store_id: str = ""
    query_used: str = ""


class GenerateAffiliateLink(BaseModel):
    source: str
    product_url: str
    ml_affiliate_id: str = ""
    shopee_affiliate_id: str = ""
    shopee_sub_id: str = ""


# ─── Search products ─────────────────────────────────────────────────────────


@router.post("/search")
async def search_products(data: SearchQuery) -> dict[str, Any]:
    """Search for products on Mercado Livre and/or Shopee."""
    if not data.query.strip():
        raise HTTPException(400, "Termo de busca não informado.")

    results: dict[str, Any] = {}
    errors: list[str] = []

    if "mercadolivre" in data.sources:
        ml = search_mercadolivre(data.query, limit=data.limit)
        results["mercadolivre"] = {
            "success": ml.success,
            "products": [_product_to_dict(p) for p in ml.products],
            "error": ml.error,
            "count": len(ml.products),
        }
        if not ml.success:
            errors.append(ml.error or "Erro no Mercado Livre")

    if "shopee" in data.sources:
        sp = search_shopee(data.query, limit=data.limit)
        results["shopee"] = {
            "success": sp.success,
            "products": [_product_to_dict(p) for p in sp.products],
            "error": sp.error,
            "count": len(sp.products),
        }
        if not sp.success:
            errors.append(sp.error or "Erro na Shopee")

    total = sum(r.get("count", 0) for r in results.values())

    return {
        "query": data.query,
        "results": results,
        "total": total,
        "errors": errors if errors else None,
    }


def _product_to_dict(p: Any) -> dict[str, Any]:
    """Convert a ProductResult dataclass to a dict."""
    return {
        "source": p.source,
        "product_id": p.product_id,
        "title": p.title,
        "price": p.price,
        "currency": p.currency,
        "thumbnail_url": p.thumbnail_url,
        "permalink": p.permalink,
        "store_name": p.store_name,
        "store_id": p.store_id,
        "query_used": p.query_used,
    }


# ─── Search single source ────────────────────────────────────────────────────


@router.get("/search/{source}")
async def search_single_source(
    source: str,
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, le=50),
) -> dict[str, Any]:
    """Search products on a specific marketplace."""
    source = source.lower()
    if source not in ("mercadolivre", "shopee"):
        raise HTTPException(400, "Fonte inválida. Use 'mercadolivre' ou 'shopee'.")

    if source == "mercadolivre":
        result = search_mercadolivre(q, limit=limit)
    else:
        result = search_shopee(q, limit=limit)

    return {
        "success": result.success,
        "query": q,
        "source": source,
        "products": [_product_to_dict(p) for p in result.products],
        "error": result.error,
        "count": len(result.products),
    }


# ─── Associate product with post ─────────────────────────────────────────────


@router.post("/associate")
async def associate_product(data: AssociateProduct) -> dict[str, Any]:
    """Save a product search result and associate it with a post."""
    post = get_post(data.post_id)
    if not post:
        raise HTTPException(404, "Post não encontrado.")

    # Check for existing product with same marketplace ID
    existing = None
    for prod in list_products(post_id=data.post_id):
        if (
            prod.get("source") == data.source
            and prod.get("product_id") == data.product_id
        ):
            existing = prod
            # Update it
            now = datetime.now().isoformat(timespec="seconds")
            db_execute(
                """UPDATE products SET selected=1, affiliate_url=?, title=?,
                   price=?, thumbnail_url=?, permalink=?, store_name=?,
                   updated_at=? WHERE id=?""",
                (
                    data.affiliate_url,
                    data.title,
                    data.price,
                    data.thumbnail_url,
                    data.permalink,
                    data.store_name,
                    now,
                    prod["id"],
                ),
            )
            select_product(prod["id"], data.post_id)
            break

    if not existing:
        # Save new product
        saved = save_product(
            post_id=data.post_id,
            source=data.source,
            product_id=data.product_id,
            title=data.title,
            price=data.price,
            currency=data.currency,
            thumbnail_url=data.thumbnail_url,
            permalink=data.permalink,
            affiliate_url=data.affiliate_url,
            store_name=data.store_name,
            store_id=data.store_id,
            query_used=data.query_used,
        )
        # Select it
        select_product(saved["id"], data.post_id)

    # Update post with product info
    update_post(
        data.post_id,
        product_query=data.query_used,
        affiliate_link=data.affiliate_url or data.permalink,
        product_keywords=data.title,
        product_source=data.source,
        product_id_ref=data.product_id,
    )

    return {
        "success": True,
        "post_id": data.post_id,
        "product_title": data.title,
    }


# ─── List products for a post ────────────────────────────────────────────────


@router.get("")
async def get_products(post_id: str = "") -> list[dict[str, Any]]:
    """List products, optionally filtered by post_id."""
    return list_products(post_id=post_id)


# ─── Generate affiliate link ────────────────────────────────────────────────


@router.post("/affiliate-link")
async def generate_link(data: GenerateAffiliateLink) -> dict[str, str]:
    """Generate an affiliate link for a product."""
    url = generate_affiliate_url(
        source=data.source,
        product_url=data.product_url,
        ml_affiliate_id=data.ml_affiliate_id,
        shopee_affiliate_id=data.shopee_affiliate_id,
        shopee_sub_id=data.shopee_sub_id,
    )
    return {"affiliate_url": url}


# ─── Delete product ──────────────────────────────────────────────────────────


@router.delete("/{prod_id}")
async def remove_product(prod_id: str) -> dict[str, bool]:
    """Remove a product association."""
    ok = delete_product(prod_id)
    return {"deleted": ok}
