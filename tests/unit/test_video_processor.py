"""Tests for app/video_processor.py — FFmpeg pipeline and template config.

v2.8 — Covers template configs, filter building, FFmpeg command assembly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.video_processor import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    TEMPLATE_1,
    TEMPLATE_2,
    TEMPLATE_3,
    TEMPLATE_CONFIGS,
    TEMPLATE_LABELS,
    RenderOptions,
    build_ffmpeg_command,
    build_filter_complex,
    get_template_labels,
    process_videos,
)


class TestTemplateConfig:
    """TEMPLATE_CONFIGS — ensure all templates are properly defined."""

    def test_all_templates_have_config(self) -> None:
        """Each template label should have a config."""
        for label in TEMPLATE_LABELS:
            assert label in TEMPLATE_CONFIGS, f"Missing config for {label}"

    def test_template_dimensions(self) -> None:
        """All templates should have reasonable dimensions."""
        for label, cfg in TEMPLATE_CONFIGS.items():
            assert cfg.max_width > 0, f"{label} max_width is 0"
            assert cfg.max_height > 0, f"{label} max_height is 0"
            assert cfg.font_size > 0, f"{label} font_size is 0"

    def test_template_1_defaults(self) -> None:
        """Template 1 should have boxed_text=True, bands=False."""
        cfg = TEMPLATE_CONFIGS[TEMPLATE_1]
        assert cfg.boxed_text is True
        assert cfg.bands is False
        assert cfg.max_width == 900

    def test_template_3_bands(self) -> None:
        """Template 3 should have bands=True."""
        cfg = TEMPLATE_CONFIGS[TEMPLATE_3]
        assert cfg.bands is True
        assert cfg.boxed_text is False


class TestGetTemplateLabels:
    """get_template_labels() — should return copy of template labels."""

    def test_returns_list(self) -> None:
        labels = get_template_labels()
        assert isinstance(labels, list)
        assert len(labels) == 3

    def test_does_not_mutate_original(self) -> None:
        labels = get_template_labels()
        labels.append("Custom")
        assert len(get_template_labels()) == 3  # original unchanged


class TestRenderOptions:
    """RenderOptions dataclass defaults."""

    def test_default_values(self) -> None:
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
        )
        assert opts.logo_image is None
        assert opts.video_size_percent == 100
        assert opts.video_width_percent == 100
        assert opts.video_offset_x == 0
        assert opts.video_offset_y == 0
        assert opts.max_duration is None
        assert opts.template == TEMPLATE_1
        assert opts.apply_watermark is True
        assert opts.apply_text_watermark is False
        assert opts.remove_center_watermark is False
        assert opts.ffmpeg_executable == "ffmpeg"

    def test_logo_set(self) -> None:
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
            logo_image=Path("/logo.png"),
        )
        assert opts.logo_image == Path("/logo.png")


class TestBuildFilterComplex:
    """build_filter_complex() — FFmpeg filter graph generation."""

    def test_basic_filter(self) -> None:
        """Should produce a valid filter complex string."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
        )
        cfg = TEMPLATE_CONFIGS[TEMPLATE_1]
        filters = build_filter_complex(opts, cfg)
        assert isinstance(filters, str)
        assert len(filters) > 50
        assert "[outv]" in filters
        assert "scale" in filters
        assert "overlay" in filters

    def test_delogo_filter(self) -> None:
        """Should include delogo when remove_center_watermark is True."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
            remove_center_watermark=True,
            delogo_x=190,
            delogo_y=860,
            delogo_width=700,
            delogo_height=160,
        )
        cfg = TEMPLATE_CONFIGS[TEMPLATE_1]
        filters = build_filter_complex(opts, cfg)
        assert "delogo" in filters

    def test_text_watermark_filter(self) -> None:
        """Should include drawtext when apply_text_watermark is True."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
            apply_text_watermark=True,
            text_watermark="@test",
        )
        cfg = TEMPLATE_CONFIGS[TEMPLATE_1]
        filters = build_filter_complex(opts, cfg)
        assert "drawtext" in filters
        assert "@test" in filters

    def test_logo_filter(self) -> None:
        """Should include logo overlay when logo is provided."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
            logo_image=Path("/logo.png"),
            apply_watermark=True,
        )
        cfg = TEMPLATE_CONFIGS[TEMPLATE_1]
        filters = build_filter_complex(opts, cfg)
        assert "[logo]" in filters

    def test_filter_stages_chain(self) -> None:
        """Filters should chain correctly through stage labels."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
            remove_center_watermark=True,
            logo_image=Path("/logo.png"),
            apply_watermark=True,
            apply_text_watermark=True,
            text_watermark="@test",
        )
        cfg = TEMPLATE_CONFIGS[TEMPLATE_1]
        filters = build_filter_complex(opts, cfg)
        # Should have [stage0], [stage1], [stage2] etc.
        assert "[stage0]" in filters
        assert "[stage1]" in filters
        assert "[outv]" in filters


class TestBuildFfmpegCommand:
    """build_ffmpeg_command() — full FFmpeg CLI command assembly."""

    def test_basic_command(self) -> None:
        """Should produce a valid FFmpeg command list."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
        )
        cmd = build_ffmpeg_command(
            Path("/input.mp4"),
            Path("/out/video_01.mp4"),
            opts,
        )
        assert isinstance(cmd, list)
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-filter_complex" in cmd
        assert str(Path("/input.mp4")) in cmd
        assert str(Path("/out/video_01.mp4")) in cmd

    def test_watermark_logo_included(self) -> None:
        """Logo should be added as third input when present."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
            logo_image=Path("/logo.png"),
            apply_watermark=True,
        )
        cmd = build_ffmpeg_command(
            Path("/input.mp4"),
            Path("/out/video_01.mp4"),
            opts,
        )
        # Should have 3 -i flags (video, background, logo)
        i_count = sum(1 for i, arg in enumerate(cmd) if arg == "-i")
        assert i_count == 3

    def test_no_logo_means_two_inputs(self) -> None:
        """Without logo, should have only 2 -i flags."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
            apply_watermark=False,
        )
        cmd = build_ffmpeg_command(
            Path("/input.mp4"),
            Path("/out/video_01.mp4"),
            opts,
        )
        i_count = sum(1 for i, arg in enumerate(cmd) if arg == "-i")
        assert i_count == 2

    def test_max_duration_adds_t_flag(self) -> None:
        """Should add -t flag when max_duration is set."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
            max_duration=60.0,
        )
        cmd = build_ffmpeg_command(
            Path("/input.mp4"),
            Path("/out/video_01.mp4"),
            opts,
        )
        assert "-t" in cmd
        t_idx = cmd.index("-t")
        assert float(cmd[t_idx + 1]) == 60.0

    def test_output_format(self) -> None:
        """Should set H.264 codec, AAC audio, yuv420p."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=Path("/out"),
        )
        cmd = build_ffmpeg_command(
            Path("/input.mp4"),
            Path("/out/video_01.mp4"),
            opts,
        )
        assert "libx264" in cmd
        assert "aac" in cmd
        assert "yuv420p" in cmd
        assert "veryfast" in cmd


class TestProcessVideos:
    """process_videos() — batch processing (mocked FFmpeg)."""

    def test_empty_file_list(self, sample_output_dir: Path) -> None:
        """Should handle empty video list gracefully."""
        opts = RenderOptions(
            background_image=Path("/bg.jpg"),
            output_dir=sample_output_dir,
        )
        summary = process_videos([], opts)
        assert summary.total == 0
        assert summary.successes == 0
        assert summary.failures == 0
