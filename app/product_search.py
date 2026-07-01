"""Product search on Mercado Livre and Shopee.

v2.4 — Searches for products on Brazilian marketplaces and generates
affiliate links using the user's affiliate IDs.

Approach:
- Mercado Livre: Scrapes the search/offers page with cloudscraper
- Shopee: Uses Google search as a fallback (API is blocked by anti-bot)
  and also tries the internal API with cloudscraper
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ─── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class ProductResult:
    """A single product found in a marketplace search."""

    source: str               # "mercadolivre" or "shopee"
    product_id: str           # ID on the marketplace
    title: str                # Product title
    price: float              # Price in BRL
    currency: str = "BRL"
    thumbnail_url: str = ""
    permalink: str = ""       # Direct product link
    store_name: str = ""
    store_id: str = ""
    query_used: str = ""


@dataclass
class SearchResults:
    """Results from a product search."""

    query: str
    source: str
    products: list[ProductResult] = field(default_factory=list)
    error: str | None = None
    success: bool = True


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _normalize_price(value: Any) -> float:
    """Try to parse a price value to float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d,.]", "", value)
        cleaned = cleaned.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0


def _scrape(url: str, *, referer: str | None = None, timeout: int = 20) -> str | None:
    """Fetch a URL with cloudscraper to bypass Cloudflare/anti-bot protection."""
    import cloudscraper

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if referer:
        headers["Referer"] = referer

    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
        logger.warning("HTTP %d fetching %s", resp.status_code, url)
        return None
    except Exception as exc:
        logger.error("Error fetching %s: %s", url, exc)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# MERCADO LIVRE SEARCH
# ═══════════════════════════════════════════════════════════════════════════════


def search_mercadolivre(
    query: str,
    limit: int = 10,
) -> SearchResults:
    """Search for products on Mercado Livre (Brazil).

    Uses the Mercado Livre offers page and listing page with HTML scraping.
    The offers page (ofertas?q=) is the primary URL as it bypasses anti-bot.
    """
    results = SearchResults(query=query, source="mercadolivre")

    # Primary: Use the offers page (works better with anti-bot)
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.mercadolivre.com.br/ofertas?q={encoded_query}&limit=50"
    html = _scrape(url, referer="https://www.mercadolivre.com.br/")

    # Use offers page if we have content with actual products (> 50KB = real page)
    if html and len(html) > 50000:
        _parse_mercadolivre_html(html, results, limit)
    else:
        # Fallback: try the listing page
        sanitized = query.strip().replace(" ", "-").replace("/", "-")
        url = f"https://lista.mercadolivre.com.br/{sanitized}"
        html = _scrape(url, referer="https://www.mercadolivre.com.br/")
        if html:
            _parse_mercadolivre_html(html, results, limit)

    # Try JSON-based extraction if HTML parsing didn't find products
    if not results.products and html:
        _try_mercadolivre_json(html, results, limit)

    if not results.products:
        results.success = False
        results.error = "Nenhum produto encontrado no Mercado Livre."
        return results

    _deduplicate_products(results)

    if not results.products:
        results.success = False
        results.error = "Nenhum produto encontrado no Mercado Livre."

    return results


def _parse_mercadolivre_html(html: str, results: SearchResults, limit: int) -> None:
    """Parse Mercado Livre HTML to extract product data using multiple strategies."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    # Strategy 1: Look for poly-card content containers (ML offers page)
    selectors = [
        "div.poly-card__content",
        "div.poly-card",
        "div.ui-search-result__wrapper",
        "li.ui-search-layout__item",
        "div.poly-component__content",
        "div[class*='poly-card']",
        "ol.ui-search-layout li",
        "div.ui-search-result__content",
    ]

    items: list[Any] = []
    for sel in selectors:
        items = soup.select(sel)
        if len(items) >= 3:  # At least 3 items to be valid
            logger.info("Found %d items with selector: %s", len(items), sel)
            break

    # Strategy 2: Look for anchor tags with ML product URLs (fallback)
    if len(items) < 3:
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            if "/MLB-" in href or "/p/" in href or "/produto/" in href:
                parent = a_tag.find_parent(["div", "li", "section"])
                items.append(parent or a_tag)
                if len(items) >= limit:
                    break

    # Strategy 3: Look for andes-card containers
    if len(items) < 3:
        for container in soup.find_all(["div", "li"], class_=True):
            cls = " ".join(container.get("class", []))
            if any(x in cls for x in ["item", "result", "product", "card"]) and "andes" not in cls.lower():
                if container.find(["h2", "h3", "a"]) and container.find(["img", "span"]):
                    items.append(container)
                    if len(items) >= limit * 2:
                        break

    for item in items[:limit]:
        try:
            product = _extract_ml_item(item)
            if product and product.title and len(product.title) > 5 and product.product_id:
                results.products.append(product)
        except Exception as exc:
            logger.debug("Error extracting ML item: %s", exc)
            continue


def _extract_ml_item(item: Any) -> ProductResult | None:
    """Extract product data from a Mercado Livre HTML element."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(str(item), "lxml")

    # ── Title ──
    title = ""
    for sel in [
        "h3.poly-component__title-wrapper",
        "h2.poly-box.poly-component__title",
        "h2[class*='ui-search-item__title']",
        "h2",
        "h3",
        "a[class*='ui-search-item__group__element']",
        "a",
    ]:
        el = soup.select_one(sel)
        if el:
            title = el.get_text(strip=True)
            # Clean up prefixes like "OFERTA DO DIA", "MAIS VENDIDO", etc.
            title = re.sub(r'^(OFERTA\s+(DO\s+)?DIA|MAIS\s+VENDIDO|OFERTA\s+(IMPERDÍVEL|RELÂMPAGO))\s+', '', title, flags=re.IGNORECASE)
            if title and len(title) > 5:
                break

    if not title or len(title) < 5:
        # Try meta tags
        meta = soup.select_one("meta[property='og:title']")
        if meta:
            title = meta.get("content", "")

    if not title or len(title) < 5:
        return None

    # ── Link / Product ID ──
    permalink = ""
    product_id = ""

    for sel in [
        "a.poly-component__title",
        "a.ui-search-link",
        "a[href*='mercadolivre']",
        "a[href*='/MLB-']",
        "a[href*='/p/']",
        "a",
    ]:
        el = soup.select_one(sel)
        if el and el.get("href"):
            permalink = el.get("href", "")
            break

    # If no link in child elements, look for a parent <a> tag
    if not permalink:
        a_tag = soup.find("a", href=re.compile(r"mercadolivre|/MLB-|/p/"))
        if a_tag:
            permalink = a_tag.get("href", "")

    # Extract MLB ID from URL
    if permalink:
        m = re.search(r"/MLB[-.]?(\d+)", permalink)
        if m:
            product_id = f"MLB{m.group(1)}"
        else:
            m = re.search(r"/p/(\w+)", permalink)
            if m:
                product_id = m.group(1)
            else:
                product_id = permalink.split("/")[-1] or permalink

    # ── Price ──
    price = 0.0
    for sel in [
        "span.andes-money-amount.poly-price__amount",
        "span.andes-money-amount__fraction",
        "span[class*='price-tag-fraction']",
        "span[class*='poly-price__current']",
        "span[class*='ui-search-price__part']",
        "div.poly-component__price",
        "meta[itemprop='price']",
        "span[class*='price']",
    ]:
        el = soup.select_one(sel)
        if el:
            if el.name == "meta":
                price = _normalize_price(el.get("content", "0"))
            else:
                text = el.get_text(strip=True)
                if text:
                    # Extract just the first price number (ignore fractions, discounts)
                    price = _normalize_price(text)
            if price > 0:
                break

    # ── Thumbnail ──
    thumbnail = ""
    for sel in [
        "img.poly-component__picture",
        "img[class*='ui-search-result-image__element']",
        "img[src*='mlstatic.com']",
        "img[src*='mercadolibre']",
        "img",
    ]:
        el = soup.select_one(sel)
        if el:
            thumbnail = (
                el.get("data-src", "")
                or el.get("src", "")
                or el.get("data-original", "")
            )
            if thumbnail and not thumbnail.startswith("data:"):
                break

    # ── Store ──
    store_name = ""
    for sel in [
        "span.poly-component__seller",
        "span[class*='ui-search-item__group__element']",
        "a[class*='ui-search-item__group__element']",
        "span[class*='seller']",
        "p.poly-component__seller",
    ]:
        el = soup.select_one(sel)
        if el:
            store_name = el.get_text(strip=True)
            if store_name:
                break

    if not product_id and permalink:
        product_id = permalink

    return ProductResult(
        source="mercadolivre",
        product_id=product_id,
        title=title[:200],
        price=price,
        thumbnail_url=thumbnail,
        permalink=permalink,
        store_name=store_name,
    )


def _try_mercadolivre_json(html: str, results: SearchResults, limit: int) -> None:
    """Try to extract product data from embedded JSON in Mercado Livre page."""
    patterns = [
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            continue

        try:
            raw = match.group(1).strip()
            data = json.loads(raw)
            items = _extract_from_ml_json(data)
            for item in items[:limit]:
                results.products.append(item)
            if results.products:
                logger.info("Extracted %d items from JSON", len(items))
                return
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.debug("JSON extraction failed: %s", exc)
            continue


def _extract_from_ml_json(data: dict) -> list[ProductResult]:
    """Extract products from Mercado Livre JSON preloaded state."""
    products: list[ProductResult] = []

    search_paths = [
        ["results"],
        ["searchResult", "results"],
        ["initialState", "results"],
        ["props", "pageProps", "results"],
        ["items"],
        ["data", "results"],
    ]

    items = []
    for path in search_paths:
        d = data
        try:
            for key in path:
                d = d[key]
            if isinstance(d, list):
                items = d
                break
        except (KeyError, TypeError):
            continue

    for item in items:
        if isinstance(item, dict):
            p = ProductResult(
                source="mercadolivre",
                product_id=str(item.get("id", "")),
                title=str(item.get("title", "")),
                price=_normalize_price(item.get("price", 0)),
                thumbnail_url=str(item.get("thumbnail", "") or item.get("picture", "")),
                permalink=str(item.get("permalink", "")),
                store_name=str(item.get("seller", {}).get("nickname", "")),
            )
            if p.title and p.product_id:
                products.append(p)

    return products


# ═══════════════════════════════════════════════════════════════════════════════
# SHOPEE SEARCH
# ═══════════════════════════════════════════════════════════════════════════════


def search_shopee(
    query: str,
    limit: int = 10,
) -> SearchResults:
    """Search for products on Shopee (Brazil).

    Uses multiple strategies:
    1. Internal API with cloudscraper (may be blocked)
    2. Google search as fallback to find Shopee product links
    """
    results = SearchResults(query=query, source="shopee")

    # Strategy 1: Try the Shopee internal search API with cloudscraper
    _try_shopee_api(query, results, limit)

    # Strategy 2: Fallback — use Google search to find Shopee products
    if not results.products:
        _try_shopee_google_fallback(query, results, limit)

    if not results.products:
        results.success = False
        results.error = (
            "Não foi possível buscar na Shopee (proteção anti-bot). "
            "Use o Mercado Livre ou tente manualmente."
        )

    _deduplicate_products(results)
    return results


def _try_shopee_api(query: str, results: SearchResults, limit: int) -> None:
    """Try to search Shopee using their internal API with cloudscraper."""
    import cloudscraper

    encoded = urllib.parse.quote(query)
    url = (
        f"https://shopee.com.br/api/v4/search/search_items"
        f"?by=relevancy&keyword={encoded}&limit={limit}&newest=0"
        f"&order=desc&page_type=search"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": f"https://shopee.com.br/search?keyword={encoded}",
        "x-requested-with": "XMLHttpRequest",
        "x-api-source": "pc",
    }

    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, headers=headers, timeout=15)

        if resp.status_code != 200:
            logger.warning("Shopee API returned %d", resp.status_code)
            return

        data = resp.json()
        items = data.get("items", [])

        for item in items:
            try:
                shopee_item = item.get("item_basic", item)
                product_id = str(shopee_item.get("itemid", ""))
                shop_id = str(shopee_item.get("shopid", ""))

                if not product_id:
                    continue

                title = shopee_item.get("name", "")
                price_min = shopee_item.get("price_min", 0)
                price = price_min / 100000.0 if price_min else 0.0

                permalink = f"https://shopee.com.br/product/{shop_id}/{product_id}"

                image_id = shopee_item.get("image", "")
                thumbnail = (
                    f"https://down-br.img.susercontent.com/file/{image_id}"
                    if image_id
                    else ""
                )

                p = ProductResult(
                    source="shopee",
                    product_id=product_id,
                    title=title[:200],
                    price=price,
                    thumbnail_url=thumbnail,
                    permalink=permalink,
                    store_id=shop_id,
                    query_used=query,
                )
                results.products.append(p)

                if len(results.products) >= limit:
                    break
            except Exception:
                continue
    except Exception as exc:
        logger.error("Shopee API error: %s", exc)


def _try_shopee_google_fallback(query: str, results: SearchResults, limit: int) -> None:
    """Fallback: Search Google for Shopee products to find links and details."""
    import cloudscraper

    # Use Google search to find Shopee links
    search_query = urllib.parse.quote(f"site:shopee.com.br {query} produto")
    url = f"https://www.google.com/search?q={search_query}&hl=pt-BR&num={min(limit * 2, 20)}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, headers=headers, timeout=15)

        if resp.status_code != 200:
            return

        html = resp.text

        # Extract product links from Google search results
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")

            # Google search result links are usually in format /url?q=...
            if "shopee.com.br" not in href and "/url?q=" in href:
                # Extract actual URL from Google redirect
                m = re.search(r"/url\?q=([^&]+)", href)
                if m:
                    href = urllib.parse.unquote(m.group(1))

            # Look for Shopee product links
            if "shopee.com.br/" in href and ("product/" in href or "-i." in href):
                title = a_tag.get_text(strip=True) or _extract_title_from_url(href)

                # Extract product/shop IDs from URL
                m = re.search(r"/product/(\d+)/(\d+)", href)
                shop_id = m.group(1) if m else ""
                product_id = m.group(2) if m else ""

                if not product_id:
                    m = re.search(r"-i\.(\d+)\.(\d+)", href)
                    product_id = m.group(1) if m else href
                    shop_id = m.group(2) if m else ""

                if product_id and title:
                    p = ProductResult(
                        source="shopee",
                        product_id=product_id,
                        title=title[:200],
                        permalink=href,
                        store_id=shop_id,
                        query_used=query,
                    )
                    results.products.append(p)

                    if len(results.products) >= limit:
                        break
    except Exception as exc:
        logger.error("Shopee Google fallback error: %s", exc)


def _extract_title_from_url(url: str) -> str:
    """Extract a readable title from a Shopee URL."""
    try:
        path = urllib.parse.urlparse(url).path
        parts = [p for p in path.split("/") if p and p not in ("product",)]
        if parts:
            return parts[-1].replace("-", " ").replace("_", " ").title()
    except Exception:
        pass
    return "Produto Shopee"


# ═══════════════════════════════════════════════════════════════════════════════
# AFFILIATE LINK GENERATION
# ═══════════════════════════════════════════════════════════════════════════════


def generate_affiliate_url(
    source: str,
    product_url: str,
    *,
    ml_affiliate_id: str = "",
    shopee_affiliate_id: str = "",
    shopee_sub_id: str = "",
) -> str:
    """Generate an affiliate link for a marketplace product.

    Args:
        source: "mercadolivre" or "shopee"
        product_url: The original product URL
        ml_affiliate_id: Mercado Livre Cliques affiliate ID
        shopee_affiliate_id: Shopee Affiliate Program ID
        shopee_sub_id: Shopee sub-ID for tracking channels

    Returns:
        Affiliate URL string, or the original URL if no affiliate ID is configured.
    """
    if not product_url:
        return ""

    if source == "mercadolivre" and ml_affiliate_id:
        separator = "&" if "?" in product_url else "?"
        return f"{product_url}{separator}mlext={ml_affiliate_id}"

    elif source == "shopee" and shopee_affiliate_id:
        separator = "&" if "?" in product_url else "?"
        url = f"{product_url}{separator}af_id={shopee_affiliate_id}"
        if shopee_sub_id:
            url += f"&sub_id={shopee_sub_id}"
        return url

    return product_url


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED SEARCH
# ═══════════════════════════════════════════════════════════════════════════════


def search_products(
    query: str,
    *,
    sources: list[str] | None = None,
    limit: int = 10,
) -> dict[str, SearchResults]:
    """Search for products across multiple marketplaces."""
    if sources is None:
        sources = ["mercadolivre", "shopee"]

    results: dict[str, SearchResults] = {}

    if "mercadolivre" in sources:
        results["mercadolivre"] = search_mercadolivre(query, limit=limit)
    if "shopee" in sources:
        results["shopee"] = search_shopee(query, limit=limit)

    return results


def _deduplicate_products(results: SearchResults) -> None:
    """Remove duplicate products from results based on product_id."""
    seen: set[str] = set()
    unique: list[ProductResult] = []
    for p in results.products:
        key = p.product_id
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    results.products = unique
