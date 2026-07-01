"""Tests for app/content_generator.py — local content draft generation.

v2.8 — Covers ContentDraft dataclass and generate_content_draft function.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.content_generator import (
    ContentDraft,
    generate_content_draft,
)


class TestContentDraft:
    """ContentDraft dataclass creation and field defaults."""

    def test_create_minimal(self) -> None:
        """Should create with just required field."""
        draft = ContentDraft(
            title="Test",
            caption="Caption",
            cta="Buy now",
            hashtags="#test",
            product_query="product",
        )
        assert draft.title == "Test"
        assert draft.product_keywords == ""

    def test_create_full(self) -> None:
        """Should create with all fields."""
        draft = ContentDraft(
            title="Full Test",
            caption="Full caption here",
            cta="Click here",
            hashtags="#test #full",
            product_query="test product",
            product_keywords="test keywords",
        )
        assert draft.product_keywords == "test keywords"


class TestGenerateContentDraft:
    """generate_content_draft() — local fallback caption generation."""

    def test_with_keywords(self) -> None:
        """Should use keywords when provided."""
        path = Path("/videos/produto_x.mp4")
        draft = generate_content_draft(
            path,
            keywords="fone bluetooth",
            base_hashtags="#achadinhos",
        )
        assert "fone" in draft.product_query or "bluetooth" in draft.product_query
        assert draft.title.startswith("Achadinho:")
        assert draft.cta == "Salva para ver depois e confere o link na bio."
        assert "#achadinhos" in draft.hashtags
        assert len(draft.caption) > 50

    def test_uses_stem_from_filename(self) -> None:
        """Should extract terms from filename when no keywords."""
        path = Path("/videos/fone_bluetooth_xpto.mp4")
        draft = generate_content_draft(
            path,
            keywords="",
            base_hashtags="#achadinhos #shopee",
        )
        # 'fone' and 'bluetooth' should be extracted from the filename
        assert "fone" in draft.product_query or "bluetooth" in draft.product_query
        assert "#achadinhos" in draft.hashtags
        assert "#shopee" in draft.hashtags

    def test_empty_keywords_and_minimal_name(self) -> None:
        """Should handle edge case of no keywords and short filename."""
        path = Path("/videos/x.mp4")
        draft = generate_content_draft(
            path,
            keywords="",
            base_hashtags="#achadinhos",
        )
        # Should still generate something meaningful
        assert draft.title
        assert len(draft.caption) > 30
        assert draft.product_query

    def test_base_hashtags_included(self) -> None:
        """Base hashtags should always be present."""
        path = Path("/videos/produto.mp4")
        draft = generate_content_draft(
            path,
            keywords="mouse gamer",
            base_hashtags="#achadinhos #ofertas",
        )
        assert "#achadinhos" in draft.hashtags
        assert "#ofertas" in draft.hashtags

    def test_product_keywords_in_output(self) -> None:
        """product_keywords should contain top terms."""
        path = Path("/videos/teclado_mecanico_rgb.mp4")
        draft = generate_content_draft(
            path,
            keywords="teclado mecânico rgb",
            base_hashtags="#achadinhos",
        )
        assert draft.product_keywords
        assert "teclado" in draft.product_keywords.lower()


class TestContentDraftEdgeCases:
    """Edge cases for content generation."""

    def test_underscore_in_filename(self) -> None:
        """Underscores should be treated as spaces."""
        path = Path("/videos/cadeira_gamer_ergonomica.mp4")
        draft = generate_content_draft(path, keywords="", base_hashtags="#achadinhos")
        assert "cadeira" in draft.product_query

    def test_produto_fallback(self) -> None:
        """Should use 'produto interessante' as fallback."""
        path = Path("/videos/a.mp4")
        draft = generate_content_draft(path, keywords="", base_hashtags="#achadinhos")
        assert draft.title
        assert draft.caption

    def test_multiple_hashtags_limit(self) -> None:
        """Should not exceed 18 hashtags."""
        path = Path("/videos/smartphone_android_128gb_camera_dual.mp4")
        draft = generate_content_draft(
            path,
            keywords="smartphone android 128gb câmera dual chip processador",
            base_hashtags="#achadinhos #shopee #mercadolivre #ofertas #promocao",
        )
        tag_count = draft.hashtags.count("#")
        assert tag_count <= 18, f"Too many hashtags: {tag_count}"
