"""Where everything lives.

VidSqueeze is deliberately self-contained: the tools it downloads, the files it
writes and the settings it remembers all stay inside the VidSqueeze folder.
Nothing is scattered across the user's machine, and deleting the folder removes
every trace of the program.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

#: The VidSqueeze folder itself, i.e. the parent of this package. When the
#: program is started from a launcher this is the folder the user downloaded.
APP_DIR = Path(__file__).resolve().parent.parent

BIN_DIR = APP_DIR / "bin"            # downloaded ffmpeg / ffprobe
RUNTIME_DIR = APP_DIR / "runtime"    # downloaded Python (Windows only)
OUTPUT_DIR = APP_DIR / "output"      # compressed files, unless overridden
LOG_DIR = APP_DIR / "logs"
CACHE_DIR = APP_DIR / ".cache"       # partial downloads

SETTINGS_FILE = APP_DIR / "settings.json"
PRESETS_FILE = APP_DIR / "presets.json"


def system_key() -> str:
    """Return one of 'windows', 'macos' or 'linux'."""
    s = platform.system().lower()
    if s.startswith("win"):
        return "windows"
    if s == "darwin":
        return "macos"
    return "linux"


def arch_key() -> str:
    """Return 'amd64' or 'arm64', the only two architectures we ship tools for."""
    m = platform.machine().lower()
    if m in ("x86_64", "amd64", "x64"):
        return "amd64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    # 32-bit and everything exotic: try the 64-bit build and let it fail loudly
    # rather than guessing at a download that certainly does not exist.
    return "amd64"


def exe(name: str) -> str:
    """Add the .exe suffix on Windows."""
    return name + ".exe" if system_key() == "windows" else name


def ensure_dirs() -> None:
    for d in (BIN_DIR, OUTPUT_DIR, LOG_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def writable(path: Path) -> bool:
    """Check we can actually create files in a directory."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".vidsqueeze-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def human_size(num_bytes: float) -> str:
    """Format a byte count the way a person would say it."""
    if num_bytes < 0:
        return "?"
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def human_duration(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    if seconds is None or seconds < 0:
        return "?"
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def is_frozen_or_embedded() -> bool:
    """True when running under the bundled Windows Python we downloaded."""
    try:
        return RUNTIME_DIR in Path(sys.executable).resolve().parents
    except (OSError, ValueError):
        return False


def load_settings() -> dict:
    """Read the small settings file, returning an empty dict if there is none."""
    import json

    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(**changes) -> None:
    """Merge values into the settings file."""
    import json

    settings = load_settings()
    settings.update({k: v for k, v in changes.items() if v is not None})
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass  # Remembering a preference is a convenience, not a requirement.


def open_in_file_manager(path: Path) -> None:
    """Reveal a folder in Explorer / Finder / the Linux file manager."""
    path = Path(path)
    try:
        if system_key() == "windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system_key() == "macos":
            import subprocess

            subprocess.Popen(["open", str(path)])
        else:
            import subprocess

            subprocess.Popen(["xdg-open", str(path)])
    except (OSError, AttributeError):
        pass  # Opening a file manager is a convenience, never a hard failure.
