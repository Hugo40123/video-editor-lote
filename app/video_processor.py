from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .utils import default_font_path, ensure_directory, make_batch_output_path, make_unique_batch_output_path, get_next_sequential_number


CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920

TEMPLATE_1 = "Template 1: vídeo centralizado com fundo"
TEMPLATE_2 = "Template 2: vídeo grande com marca d'água"
TEMPLATE_3 = "Template 3: vídeo com faixas de texto"

TEMPLATE_LABELS = [TEMPLATE_1, TEMPLATE_2, TEMPLATE_3]


@dataclass(frozen=True)
class TemplateConfig:
    max_width: int
    max_height: int
    top_y: str
    bottom_y: str
    font_size: int
    boxed_text: bool = True
    bands: bool = False


TEMPLATE_CONFIGS = {
    TEMPLATE_1: TemplateConfig(
        max_width=900,
        max_height=1460,
        top_y="90",
        bottom_y="h-text_h-150",
        font_size=62,
    ),
    TEMPLATE_2: TemplateConfig(
        max_width=1000,
        max_height=1760,
        top_y="80",
        bottom_y="h-text_h-120",
        font_size=58,
    ),
    TEMPLATE_3: TemplateConfig(
        max_width=900,
        max_height=1320,
        top_y="70",
        bottom_y="h-text_h-75",
        font_size=58,
        boxed_text=False,
        bands=True,
    ),
}


@dataclass(frozen=True)
class RenderOptions:
    background_image: Path
    output_dir: Path
    logo_image: Path | None = None
    text_watermark: str = ""
    text_watermark_font_size: int = 76
    text_watermark_offset_x: int = 0
    text_watermark_offset_y: int = 0
    video_size_percent: int = 100
    video_width_percent: int = 100
    video_offset_x: int = 0
    video_offset_y: int = 0
    max_duration: float | None = None
    template: str = TEMPLATE_1
    apply_watermark: bool = True
    apply_text_watermark: bool = False
    remove_center_watermark: bool = False
    delogo_x: int = 190
    delogo_y: int = 860
    delogo_width: int = 700
    delogo_height: int = 160
    ffmpeg_executable: str = "ffmpeg"
    generate_cover_frame: bool = False
    rounded_corners: bool = False
    corner_radius: int = 30


@dataclass
class ProcessSummary:
    total: int
    successes: int = 0
    failures: int = 0
    output_files: list[Path] = field(default_factory=list)


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[float], None]


def get_template_labels() -> list[str]:
    return TEMPLATE_LABELS.copy()


def process_videos(
    video_files: Iterable[Path],
    options: RenderOptions,
    log_callback: LogCallback | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ProcessSummary:
    files = list(video_files)
    summary = ProcessSummary(total=len(files))
    output_dir = ensure_directory(options.output_dir)
    used_output_files: set[str] = set()

    # Get the next sequential number from existing files in the output folder
    start_index = get_next_sequential_number(output_dir)

    for index, input_video in enumerate(files, start=start_index):
        output_file = make_unique_batch_output_path(
            make_batch_output_path(output_dir, index),
            used_output_files,
        )
        command = build_ffmpeg_command(input_video, output_file, options)

        _log(log_callback, f"[{index}/{summary.total}] Processando: {input_video.name}")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode == 0:
            summary.successes += 1
            summary.output_files.append(output_file)
            _log(log_callback, f"Concluído: {output_file.name}")

            # Prepend cover frame to video if enabled
            if options.generate_cover_frame:
                success = _prepend_cover_frame(input_video, output_file, options.ffmpeg_executable)
                if success:
                    _log(log_callback, f"Capa inserida no início do vídeo.")
        else:
            summary.failures += 1
            stderr = result.stderr.strip() or "FFmpeg não retornou detalhes do erro."
            _log(log_callback, f"Erro ao processar {input_video.name}:")
            _log(log_callback, stderr)

        if progress_callback:
            progress_callback(index / summary.total if summary.total else 1.0)

    return summary


def build_ffmpeg_command(input_video: Path, output_file: Path, options: RenderOptions) -> list[str]:
    config = TEMPLATE_CONFIGS.get(options.template, TEMPLATE_CONFIGS[TEMPLATE_1])
    filter_complex = build_filter_complex(options, config)

    command = [
        options.ffmpeg_executable,
        "-y",
        "-hide_banner",
        "-i",
        str(input_video),
        "-loop",
        "1",
        "-i",
        str(options.background_image),
    ]

    if options.apply_watermark and options.logo_image:
        command.extend(["-loop", "1", "-i", str(options.logo_image)])

    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
        ]
    )

    if options.max_duration is not None:
        command.extend(["-t", _format_duration(options.max_duration)])

    command.append(str(output_file))
    return command


def build_filter_complex(options: RenderOptions, config: TemplateConfig) -> str:
    video_width = max(2, round(config.max_width * options.video_size_percent / 100))
    video_height = max(2, round(config.max_height * options.video_size_percent / 100))

    main_video_filter = (
        f"[0:v]scale={video_width}:{video_height}:"
        f"force_original_aspect_ratio=decrease"
    )
    if options.video_width_percent != 100:
        main_video_filter += f",scale=trunc(iw*{options.video_width_percent}/100/2)*2:ih"
    main_video_filter += ",setsar=1[mainv]"

    filters: list[str] = [
        (
            f"[1:v]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT},setsar=1[bg]"
        ),
        main_video_filter,
        (
            f"[bg][mainv]overlay="
            f"{_offset_expression('(W-w)/2', options.video_offset_x)}:"
            f"{_offset_expression('(H-h)/2', options.video_offset_y)}:"
            f"shortest=1[stage0]"
        ),
    ]

    current_label = "stage0"
    stage = 1

    if options.remove_center_watermark:
        next_label = f"stage{stage}"
        x, y, width, height = _clamp_delogo_area(
            options.delogo_x,
            options.delogo_y,
            options.delogo_width,
            options.delogo_height,
        )
        filters.append(
            f"[{current_label}]delogo=x={x}:y={y}:w={width}:h={height}:show=0[{next_label}]"
        )
        current_label = next_label
        stage += 1

    if options.apply_watermark and options.logo_image:
        filters.append("[2:v]scale=180:-1:force_original_aspect_ratio=decrease,format=rgba[logo]")
        next_label = f"stage{stage}"
        filters.append(
            f"[{current_label}][logo]overlay=W-w-40:H-h-40:eof_action=repeat[{next_label}]"
        )
        current_label = next_label
        stage += 1

    if options.apply_text_watermark and options.text_watermark.strip():
        next_label = f"stage{stage}"
        filters.append(
            _drawtext_filter(
                current_label,
                next_label,
                options.text_watermark,
                x=_offset_expression("(w-text_w)/2", options.text_watermark_offset_x),
                y="(h-text_h)/2",
                y_offset=options.text_watermark_offset_y,
                font_size=options.text_watermark_font_size,
                boxed=False,
                font_color="white@0.35",
                border_width=3,
                border_color="black@0.20",
            )
        )
        current_label = next_label
        stage += 1

    # Rounded corners on the main video overlay
    if options.rounded_corners and options.corner_radius > 0:
        next_label = f"stage{stage}"
        r = options.corner_radius
        filters.append(
            f"[{current_label}]geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':"
            f"alpha='if(lt(abs(X-W/2),W/2-{r})*lt(abs(Y-H/2),H/2-{r}),255,"
            f"if(lt(hypot(abs(X-W/2)-(W/2-{r}),abs(Y-H/2)),{r}),255,"
            f"if(lt(hypot(abs(X-W/2)-(W/2-{r}),abs(Y-H/2)-(H/2-{r})),{r}),255,"
            f"if(lt(hypot(abs(X-W/2)+(W/2-{r}),abs(Y-H/2)),{r}),255,"
            f"if(lt(hypot(abs(X-W/2)+(W/2-{r}),abs(Y-H/2)-(H/2-{r})),{r}),255,0)))))'"
            f"[{next_label}]"
        )
        current_label = next_label
        stage += 1

    filters.append(f"[{current_label}]format=yuv420p[outv]")
    return ";".join(filters)


def _drawtext_filter(
    input_label: str,
    output_label: str,
    text: str,
    *,
    y: str,
    font_size: int,
    boxed: bool,
    x: str = "(w-text_w)/2",
    y_offset: int = 0,
    font_color: str = "white",
    border_width: int = 0,
    border_color: str = "black@0.20",
) -> str:
    params = []
    font = default_font_path()
    if font:
        params.append(f"fontfile='{_escape_filter_path(font)}'")

    params.extend(
        [
            f"text='{_escape_drawtext_text(text)}'",
            f"fontcolor={font_color}",
            f"fontsize={font_size}",
            f"x={x}",
            f"y={_offset_expression(y, y_offset)}",
            "line_spacing=10",
        ]
    )

    if border_width > 0:
        params.extend([f"borderw={border_width}", f"bordercolor={border_color}"])

    if boxed:
        params.extend(["box=1", "boxcolor=black@0.45", "boxborderw=24"])

    return f"[{input_label}]drawtext={':'.join(params)}[{output_label}]"


def _escape_filter_path(path: str) -> str:
    value = Path(path).as_posix()
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _escape_drawtext_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _format_duration(seconds: float) -> str:
    return f"{seconds:.3f}".rstrip("0").rstrip(".")


def _offset_expression(base: str, offset: int) -> str:
    if offset > 0:
        return f"{base}+{offset}"
    if offset < 0:
        return f"{base}{offset}"
    return base


def _clamp_delogo_area(x: int, y: int, width: int, height: int) -> tuple[int, int, int, int]:
    x = max(0, min(x, CANVAS_WIDTH - 2))
    y = max(0, min(y, CANVAS_HEIGHT - 2))
    width = max(2, min(width, CANVAS_WIDTH - x))
    height = max(2, min(height, CANVAS_HEIGHT - y))
    return x, y, width, height


def _prepend_cover_frame(input_video: Path, output_video: Path, ffmpeg: str) -> bool:
    """Extract first frame and prepend it as a 2-second cover to the output video."""
    import tempfile
    try:
        # Extract first frame as image
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_img:
            img_path = tmp_img.name

        result = subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-ss", "00:00:00.5",
             "-i", str(input_video), "-frames:v", "1", "-q:v", "2", img_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not Path(img_path).is_file():
            return False

        # Create 2-second video from the frame
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_vid:
            cover_video = tmp_vid.name

        result = subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-loop", "1", "-i", img_path,
             "-t", "2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
             "-pix_fmt", "yuv420p", "-r", "30", cover_video],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not Path(cover_video).is_file():
            Path(img_path).unlink(missing_ok=True)
            return False

        # Create concat list
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"file '{cover_video}'\n")
            f.write(f"file '{output_video.resolve().as_posix()}'\n")
            concat_list = f.name

        # Concat cover + original video
        temp_output = output_video.with_suffix(".tmp.mp4")
        result = subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-f", "concat", "-safe", "0",
             "-i", concat_list, "-c", "copy", str(temp_output)],
            capture_output=True, text=True, timeout=300,
        )

        # Cleanup
        Path(img_path).unlink(missing_ok=True)
        Path(cover_video).unlink(missing_ok=True)
        Path(concat_list).unlink(missing_ok=True)

        if result.returncode == 0 and temp_output.is_file():
            temp_output.replace(output_video)
            return True
        else:
            temp_output.unlink(missing_ok=True)
            return False
    except Exception:
        return False


def _log(callback: LogCallback | None, message: str) -> None:
    if callback:
        callback(message)
