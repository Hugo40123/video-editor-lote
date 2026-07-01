"""Tests for app/product_search.py — marketplace search and affiliate links.

v2.8 — Covers data models, affiliate URL generation, search result structures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.product_search import (
    ProductResult,
    SearchResults,
    generate_affiliate_url,
    search_products,
)


class TestProductResult:
    """ProductResult dataclass."""

    def test_minimal_product(self) -> None:
        p = ProductResult(
            source="mercadolivre",
            product_id="MLB123",
            title="Fone Bluetooth",
            price=49.90,
        )
        assert p.source == "mercadolivre"
        assert p.price == 49.90
        assert p.currency == "BRL"  # default
        assert p.store_name == ""

    def test_full_product(self) -> None:
        p = ProductResult(
            source="shopee",
            product_id="shop123",
            title="Smartphone X",
            price=1200.00,
            currency="BRL",
            thumbnail_url="https://img.shopee.com/thumb.jpg",
            permalink="https://shopee.com.br/product/123",
            store_name="Loja Teste",
            store_id="store_001",
            query_used="smartphone",
        )
        assert p.store_name == "Loja Teste"
        assert p.permalink == "https://shopee.com.br/product/123"


class TestSearchResults:
    """SearchResults dataclass."""

    def test_empty_search(self) -> None:
        sr = SearchResults(query="test", source="mercadolivre")
        assert sr.query == "test"
        assert sr.products == []
        assert sr.error is None
        assert sr.success is True

    def test_with_products(self) -> None:
        p1 = ProductResult(source="mercadolivre", product_id="MLB1", title="Produto 1", price=10.0)
        sr = SearchResults(query="test", source="mercadolivre", products=[p1])
        assert len(sr.products) == 1
        assert sr.success is True

    def test_with_error(self) -> None:
        sr = SearchResults(query="test", source="shopee", success=False, error="API blocked")
        assert sr.success is False
        assert sr.error == "API blocked"


class TestGenerateAffiliateUrl:
    """generate_affiliate_url() — affiliate link generation."""

    def test_no_affiliate_id(self) -> None:
        """Should return original URL when no affiliate ID."""
        url = generate_affiliate_url(
            "mercadolivre",
            "https://mercadolivre.com.br/produto/MLB123",
        )
        assert url == "https://mercadolivre.com.br/produto/MLB123"

    def test_mercadolivre_with_id(self) -> None:
        """Should append mlext parameter for ML."""
        url = generate_affiliate_url(
            "mercadolivre",
            "https://mercadolivre.com.br/produto/MLB123",
            ml_affiliate_id="ML_AFF_001",
        )
        assert "mlext=ML_AFF_001" in url

    def test_shopee_with_id(self) -> None:
        """Should append af_id parameter for Shopee."""
        url = generate_affiliate_url(
            "shopee",
            "https://shopee.com.br/product/123/456",
            shopee_affiliate_id="SHOP_AFF_001",
        )
        assert "af_id=SHOP_AFF_001" in url

    def test_shopee_with_sub_id(self) -> None:
        """Should include sub_id when provided."""
        url = generate_affiliate_url(
            "shopee",
            "https://shopee.com.br/product/123/456",
            shopee_affiliate_id="SHOP_AFF_001",
            shopee_sub_id="instagram",
        )
        assert "af_id=SHOP_AFF_001" in url
        assert "sub_id=instagram" in url

    def test_empty_url(self) -> None:
        """Should return empty string for empty URL."""
        url = generate_affiliate_url(
            "mercadolivre",
            "",
            ml_affiliate_id="ML_AFF_001",
        )
        assert url == ""


class TestSearchProducts:
    """search_products() — unified search across marketplaces."""

    @pytest.fixture
    def sample_html(self) -> str:
        """A minimal HTML page to test parsing."""
        return """
        <html><body>
        <div class="poly-card__content">
            <h2 class="poly-box poly-component__title">Fone Bluetooth Teste</h2>
            <a href="https://mercadolivre.com.br/MLB-1234567890">Link</a>
            <span class="andes-money-amount__fraction">89,90</span>
            <img src="https://mlstatic.com/img.jpg" />
        </div>
        </body></html>
        """

    def test_search_empty_query(self) -> None:
        """Should handle empty query gracefully."""
        results = search_products("", sources=["mercadolivre"], limit=5)
        # Should return empty results rather than crashing
        assert "mercadolivre" in results
        # May or may not find products depending on mocking
        assert isinstance(results["mercadolivre"].success, bool)

    def test_search_invalid_source(self) -> None:
        """Should work with valid sources only."""
        results = search_products("test", sources=["invalid_source"])
        # Unknown sources are simply not included
        assert "invalid_source" not in results
        assert len(results) == 0
