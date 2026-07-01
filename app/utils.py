from __future__ import annotations

import json
import re
import shutil
import sys
import os
from pathlib import Path


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
SETTINGS_VERSION = 1


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Pasta para recursos empacotados, compatível com PyInstaller."""
    if is_frozen_app() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def writable_root() -> Path:
    """Pasta onde o app pode gravar arquivos quando virar .exe."""
    if is_frozen_app():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def upload_dir() -> Path:
    """Diretório para arquivos enviados via upload."""
    return ensure_directory(writable_root() / "uploads")


def default_input_dir() -> Path:
    return writable_root() / "entrada"


def default_output_dir() -> Path:
    return writable_root() / "saida"


def default_background_path() -> Path:
    return resource_root() / "assets" / "fundo_padrao.jpg"


def default_logo_path() -> Path:
    return resource_root() / "assets" / "logo_padrao.png"


def settings_path() -> Path:
    return writable_root() / "config" / "settings.json"


def load_settings() -> dict[str, object]:
    path = settings_path()
    if not path.is_file():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def save_settings(settings: dict[str, object]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": SETTINGS_VERSION,
        **settings,
    }
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def ffmpeg_path() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found

    for candidate in _ffmpeg_candidates():
        if candidate.is_file():
            return str(candidate)

    return None


def _ffmpeg_candidates() -> list[Path]:
    candidates = [
        writable_root() / "ffmpeg.exe",
        writable_root() / "bin" / "ffmpeg.exe",
        resource_root() / "ffmpeg.exe",
        resource_root() / "bin" / "ffmpeg.exe",
        Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe"),
    ]

    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidates.append(Path(user_profile) / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe")

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        winget_packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_packages.is_dir():
            for package_dir in winget_packages.glob("Gyan.FFmpeg*"):
                candidates.extend(package_dir.glob("**/ffmpeg.exe"))

    candidates.extend(_ffmpeg_from_windows_path_registry())
    return candidates


def _ffmpeg_from_windows_path_registry() -> list[Path]:
    if not sys.platform.startswith("win"):
        return []

    try:
        import winreg
    except ImportError:
        return []

    registry_locations = [
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ]
    candidates: list[Path] = []

    for root_key, sub_key in registry_locations:
        try:
            with winreg.OpenKey(root_key, sub_key) as key:
                raw_path, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue

        for folder in str(raw_path).split(os.pathsep):
            expanded = os.path.expandvars(folder.strip())
            if expanded:
                candidates.append(Path(expanded) / "ffmpeg.exe")

    return candidates


def list_video_files(folder: str | Path, *, recursive: bool = False) -> list[Path]:
    base = Path(folder)
    if not base.is_dir():
        return []

    files = base.rglob("*") if recursive else base.iterdir()
    return sorted(
        (
            file
            for file in files
            if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS
        ),
        key=lambda path: str(path).casefold(),
    )


def make_unique_batch_output_path(output_file: Path, used_output_files: set[str]) -> Path:
    candidate = output_file
    counter = 2

    while _output_key(candidate) in used_output_files:
        candidate = output_file.with_name(f"{output_file.stem}_{counter}{output_file.suffix}")
        counter += 1

    used_output_files.add(_output_key(candidate))
    return candidate


def _output_key(path: Path) -> str:
    return str(path.resolve()).casefold()


def ensure_directory(folder: str | Path) -> Path:
    path = Path(folder)
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_duration(value: str) -> float | None:
    cleaned = value.strip().replace(",", ".")
    if not cleaned:
        return None

    try:
        seconds = float(cleaned)
    except ValueError as exc:
        raise ValueError("Informe a duração máxima usando apenas números.") from exc

    if seconds <= 0:
        raise ValueError("A duração máxima precisa ser maior que zero.")

    return seconds


def make_output_path(input_video: Path, output_dir: str | Path) -> Path:
    safe_stem = sanitize_filename(input_video.stem)
    return Path(output_dir) / f"{safe_stem}_editado.mp4"


def make_batch_output_path(output_dir: str | Path, index: int) -> Path:
    return Path(output_dir) / f"video_{index:02d}.mp4"


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
    return cleaned or "video"


def default_font_path() -> str | None:
    fonts_dir = Path("C:/Windows/Fonts")
    candidates = [
        fonts_dir / "arial.ttf",
        fonts_dir / "segoeui.ttf",
        fonts_dir / "calibri.ttf",
        fonts_dir / "tahoma.ttf",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None
