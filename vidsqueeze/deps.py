"""Finding, and if necessary fetching, the tools VidSqueeze needs.

The only external tools required are ffmpeg and ffprobe. If they are already on
the machine we use them. If they are not, we download a self-contained build
into VidSqueeze/bin. That path needs no administrator rights, touches nothing
outside the VidSqueeze folder, and works identically on all three platforms.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .paths import BIN_DIR, CACHE_DIR, arch_key, exe, system_key

USER_AGENT = "VidSqueeze/1.0 (+https://github.com/pxspaces/vidsqueeze)"

# Builds for macOS and Linux. These redirect URLs always resolve to the current
# release build, so they do not need updating when ffmpeg publishes a version.
MARTIN_RIEDL = "https://ffmpeg.martin-riedl.de/redirect/latest/{os}/{arch}/release/{tool}.zip"

# Windows builds. BtbN publishes both x64 and ARM64 under a rolling "latest"
# tag; we look for the newest numbered release and fall back to the master build.
BTBN_API = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/tags/latest"
BTBN_FALLBACK = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-{plat}-gpl-shared.zip"
)

#: Encoders we would like to have available. Missing entries are not fatal;
#: they simply remove options from the interface.
#: Every encoder we might select must be listed here, because a name missing
#: from this set reads as "not available" and silently falls back to something
#: else. FLAC was once absent, which quietly turned archive-quality audio into
#: AAC without a word to anyone.
WANTED_ENCODERS = (
    "libx265", "libx264", "libsvtav1", "libvpx-vp9",
    "libopus", "aac", "libmp3lame", "flac",
    "mjpeg", "png", "libwebp", "libjxl", "tiff", "bmp",
)

ProgressFn = Callable[[str, float], None]  # (message, fraction 0..1 or -1)


class DependencyError(RuntimeError):
    """Raised when a required tool cannot be found or installed."""


@dataclass
class Tools:
    """Resolved paths to the ffmpeg toolchain, plus what it can do."""

    ffmpeg: Path
    ffprobe: Path
    version: str
    encoders: frozenset[str]
    source: str  # "bundled" (our bin folder) or "system"

    def has(self, encoder: str) -> bool:
        return encoder in self.encoders

    @property
    def needs_strict_opus(self) -> bool:
        """Older ffmpeg treats Opus in an MP4 container as experimental.

        Those builds refuse the combination unless '-strict -2' is passed. It is
        harmless on new builds but we only add it where it is actually needed.
        """
        match = re.search(r"(\d+)\.", self.version)
        return bool(match) and int(match.group(1)) < 5


# --------------------------------------------------------------------------
# Locating an existing install
# --------------------------------------------------------------------------


def _run_ok(cmd: list[str]) -> str | None:
    """Run a command and return its combined output, or None if it will not run."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            text=True,
            errors="replace",
            **_no_window(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _no_window() -> dict:
    """Stop Windows flashing a console window for every helper process."""
    if system_key() == "windows":
        startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        return {"startupinfo": startupinfo, "creationflags": 0x08000000}
    return {}


def _candidate_pairs() -> Iterable[tuple[Path, Path, str]]:
    """Yield (ffmpeg, ffprobe, source) pairs worth testing, best first."""
    bundled_ffmpeg = BIN_DIR / exe("ffmpeg")
    bundled_ffprobe = BIN_DIR / exe("ffprobe")
    if bundled_ffmpeg.exists() and bundled_ffprobe.exists():
        yield bundled_ffmpeg, bundled_ffprobe, "bundled"

    sys_ffmpeg = shutil.which("ffmpeg")
    sys_ffprobe = shutil.which("ffprobe")
    if sys_ffmpeg and sys_ffprobe:
        yield Path(sys_ffmpeg), Path(sys_ffprobe), "system"


def _inspect(ffmpeg: Path, ffprobe: Path, source: str) -> Tools | None:
    """Confirm a candidate pair actually runs, and record its capabilities."""
    banner = _run_ok([str(ffmpeg), "-hide_banner", "-version"])
    if not banner or not _run_ok([str(ffprobe), "-hide_banner", "-version"]):
        return None

    version_match = re.search(r"ffmpeg version (\S+)", banner)
    version = version_match.group(1) if version_match else "unknown"

    encoder_dump = _run_ok([str(ffmpeg), "-hide_banner", "-encoders"]) or ""
    found = {name for name in WANTED_ENCODERS if re.search(rf"^\s*\S+\s+{re.escape(name)}\s", encoder_dump, re.M)}

    return Tools(ffmpeg=ffmpeg, ffprobe=ffprobe, version=version, encoders=frozenset(found), source=source)


def find_tools(require_h265: bool = True) -> Tools | None:
    """Return a working toolchain, or None if nothing suitable is installed.

    A system ffmpeg that cannot encode H.265 is rejected in favour of
    downloading a full build, since H.265 is the default codec.
    """
    for ffmpeg, ffprobe, source in _candidate_pairs():
        tools = _inspect(ffmpeg, ffprobe, source)
        if tools is None:
            continue
        if require_h265 and not tools.has("libx265"):
            continue
        return tools
    return None


# --------------------------------------------------------------------------
# Downloading
# --------------------------------------------------------------------------


def _download(url: str, dest: Path, progress: ProgressFn | None, label: str) -> Path:
    """Fetch a URL to a file, reporting progress as we go.

    urllib is tried first. Some Python installs (notably the python.org builds
    on macOS) ship without usable root certificates, so curl is used as a
    fallback rather than disabling certificate checking.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")

    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(partial, "wb") as handle:
                while True:
                    chunk = response.read(262144)
                    if not chunk:
                        break
                    handle.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(label, done / total if total else -1)
        partial.replace(dest)
        return dest
    except (urllib.error.URLError, ssl.SSLError, OSError) as exc:
        partial.unlink(missing_ok=True)
        curl = shutil.which("curl")
        if not curl:
            raise DependencyError(f"Could not download {url}: {exc}") from exc

    if progress:
        progress(f"{label} (retrying)", -1)
    result = subprocess.run(
        [curl, "-fL", "--retry", "3", "-A", USER_AGENT, "-o", str(partial), url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        **_no_window(),
    )
    if result.returncode != 0:
        partial.unlink(missing_ok=True)
        raise DependencyError(f"Could not download {url}: {result.stderr.strip()}")
    partial.replace(dest)
    return dest


def _windows_asset_url() -> str:
    """Pick the newest numbered Windows build, preferring a real release."""
    plat = "win64" if arch_key() == "amd64" else "winarm64"
    try:
        request = urllib.request.Request(BTBN_API, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.load(response)
        pattern = re.compile(rf"^ffmpeg-n(\d+)\.(\d+)-latest-{plat}-gpl-shared-[\d.]+\.zip$")
        best: tuple[tuple[int, int], str] | None = None
        for asset in release.get("assets", []):
            match = pattern.match(asset.get("name", ""))
            if match:
                version = (int(match.group(1)), int(match.group(2)))
                if best is None or version > best[0]:
                    best = (version, asset["browser_download_url"])
        if best:
            return best[1]
    except (urllib.error.URLError, ssl.SSLError, OSError, ValueError, KeyError):
        pass  # Fall through to the rolling master build.
    return BTBN_FALLBACK.format(plat=plat)


def _extract_binaries(archive: Path, wanted: set[str], into: Path) -> set[str]:
    """Pull the named executables, and any DLLs beside them, out of an archive.

    Returns the set of names that were found.
    """
    into.mkdir(parents=True, exist_ok=True)
    found: set[str] = set()

    def keep(member_name: str) -> str | None:
        base = os.path.basename(member_name)
        stem = base[:-4] if base.lower().endswith(".exe") else base
        if stem in wanted and not member_name.endswith("/"):
            return base
        # Shared Windows builds keep their libraries next to the executables.
        if base.lower().endswith(".dll") and "/bin/" in member_name.replace("\\", "/"):
            return base
        return None

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                target_name = keep(member)
                if not target_name:
                    continue
                with zf.open(member) as src, open(into / target_name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                stem = target_name[:-4] if target_name.lower().endswith(".exe") else target_name
                if stem in wanted:
                    found.add(stem)
    else:
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                target_name = keep(member.name)
                if not target_name:
                    continue
                src = tf.extractfile(member)
                if src is None:
                    continue
                with src, open(into / target_name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                stem = target_name[:-4] if target_name.lower().endswith(".exe") else target_name
                if stem in wanted:
                    found.add(stem)

    if system_key() != "windows":
        for name in found:
            (into / name).chmod(0o755)
    return found


def download_size_estimate() -> str:
    """A rough figure to show the user before asking them to commit."""
    return "about 75 MB" if system_key() == "windows" else "about 60 MB"


def install_ffmpeg(progress: ProgressFn | None = None) -> Tools:
    """Download a self-contained ffmpeg into VidSqueeze/bin and verify it."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    plat = system_key()

    with tempfile.TemporaryDirectory(dir=CACHE_DIR) as tmp:
        tmpdir = Path(tmp)
        if plat == "windows":
            url = _windows_asset_url()
            archive = _download(url, tmpdir / "ffmpeg-win.zip", progress, "Downloading ffmpeg")
            found = _extract_binaries(archive, {"ffmpeg", "ffprobe"}, BIN_DIR)
        else:
            found = set()
            for index, tool in enumerate(("ffmpeg", "ffprobe")):
                url = MARTIN_RIEDL.format(os=plat, arch=arch_key(), tool=tool)
                archive = _download(
                    url,
                    tmpdir / f"{tool}.zip",
                    progress,
                    f"Downloading {tool} ({index + 1} of 2)",
                )
                found |= _extract_binaries(archive, {tool}, BIN_DIR)

    missing = {"ffmpeg", "ffprobe"} - found
    if missing:
        raise DependencyError(
            f"The download completed but {', '.join(sorted(missing))} was not inside it. "
            "Please report this, or install ffmpeg yourself and restart VidSqueeze."
        )

    if progress:
        progress("Checking the download", -1)

    tools = _inspect(BIN_DIR / exe("ffmpeg"), BIN_DIR / exe("ffprobe"), "bundled")
    if tools is None:
        raise DependencyError(
            "ffmpeg was downloaded but will not run on this machine. "
            f"Try installing it yourself, then restart VidSqueeze. Files are in {BIN_DIR}."
        )
    if progress:
        progress("Ready", 1.0)
    return tools


def ensure_tools(progress: ProgressFn | None = None, allow_download: bool = True) -> Tools:
    """Return a working toolchain, downloading one if that is the only option."""
    tools = find_tools()
    if tools is not None:
        return tools
    if not allow_download:
        raise DependencyError(
            "ffmpeg was not found. Run VidSqueeze without --no-download to fetch it automatically."
        )
    return install_ffmpeg(progress)


#: Formats that only a reasonably recent ffmpeg can open. When one of these
#: fails to load, a newer build is very likely to fix it, so we say so rather
#: than leaving the user to guess.
UPGRADEABLE_EXTENSIONS = {".heic", ".heif", ".avif", ".jxl", ".qoi"}


def upgrade_would_help(path, tools: Tools | None) -> bool:
    """Whether downloading a newer ffmpeg is likely to make this file readable.

    Only worth suggesting when the current toolchain came from the system, since
    a build we downloaded ourselves is already current.
    """
    if tools is not None and tools.source == "bundled":
        return False
    try:
        suffix = Path(path).suffix.lower()
    except (TypeError, ValueError):
        return False
    return suffix in UPGRADEABLE_EXTENSIONS


def force_download(progress: ProgressFn | None = None) -> Tools:
    """Fetch a current ffmpeg even though one is already installed."""
    return install_ffmpeg(progress)


def system_install_hint() -> str:
    """The command a terminal user could run instead, if they would rather."""
    return {
        "windows": "winget install Gyan.FFmpeg",
        "macos": "brew install ffmpeg",
        "linux": "sudo apt install ffmpeg   (or dnf/pacman equivalent)",
    }[system_key()]
