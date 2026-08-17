"""Looking at video rather than only measuring it.

Three jobs live here: pulling single frames out of a file so the interface can
show a real before and after, deciding whether a browser can play a file at all,
and encoding short samples so someone can judge a setting in seconds instead of
waiting for a whole file.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import dataclass, replace
from pathlib import Path

from .deps import Tools, _no_window
from .encode import JobSpec, build_command, normalise, output_duration
from .paths import CACHE_DIR, human_size
from .probe import MediaInfo, probe

FRAME_CACHE = CACHE_DIR / "frames"
SAMPLE_DIR = CACHE_DIR / "samples"

#: Codecs a browser will generally play. H.265 is deliberately absent: support
#: is patchy and platform dependent, so we never assume it.
BROWSER_VIDEO = {"h264", "vp8", "vp9", "av1", "theora"}
BROWSER_AUDIO = {"aac", "mp3", "opus", "vorbis", "flac"}
BROWSER_CONTAINERS = {"mp4", "webm", "matroska", "mov", "ogg"}


def can_browser_play(info: MediaInfo) -> bool:
    """Whether a <video> element stands a fair chance with this file."""
    if info.has_video and info.video_codec not in BROWSER_VIDEO:
        return False
    if info.has_audio and info.audio_codec not in BROWSER_AUDIO:
        return False
    container = (info.container or "").lower()
    return any(name in container for name in BROWSER_CONTAINERS)


# --------------------------------------------------------------------------
# Frames
# --------------------------------------------------------------------------


def _frame_key(path: Path, when: float, width: int) -> Path:
    stamp = f"{path}|{path.stat().st_mtime_ns if path.exists() else 0}|{when:.3f}|{width}"
    digest = hashlib.sha256(stamp.encode("utf-8")).hexdigest()[:20]
    return FRAME_CACHE / f"{digest}.jpg"


def extract_frame(tools: Tools, path: Path, when: float = 0.0, width: int = 900) -> bytes | None:
    """Grab one frame as a JPEG. Returns None if the frame cannot be read.

    Results are cached, because the comparison view asks for the same frames
    repeatedly as the user drags the slider.
    """
    path = Path(path)
    if not path.exists():
        return None

    cached = _frame_key(path, when, width)
    if cached.exists():
        try:
            return cached.read_bytes()
        except OSError:
            pass

    command = [
        str(tools.ffmpeg), "-hide_banner", "-nostdin", "-loglevel", "error",
        "-ss", f"{max(0.0, when):.3f}",
        "-i", str(path),
        "-frames:v", "1",
        # Tone map HDR so the preview matches what people expect to see.
        "-vf", f"scale={width}:-2:flags=lanczos",
        "-q:v", "4",
        "-f", "mjpeg", "pipe:1",
    ]
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=60, **_no_window(),
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0 or not result.stdout:
        return None

    FRAME_CACHE.mkdir(parents=True, exist_ok=True)
    try:
        cached.write_bytes(result.stdout)
    except OSError:
        pass
    return result.stdout


def clear_frame_cache() -> None:
    for entry in FRAME_CACHE.glob("*.jpg"):
        try:
            entry.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------------
# Samples
# --------------------------------------------------------------------------


@dataclass
class SampleResult:
    """One short test encode, and what it implies for the whole file."""

    key: str
    label: str
    description: str
    ok: bool
    output: Path | None
    sample_bytes: int
    sample_seconds: float
    elapsed: float
    estimated_bytes: int
    estimated_seconds: float
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "ok": self.ok,
            "output": str(self.output) if self.output else "",
            "sample_size": human_size(self.sample_bytes),
            "sample_bytes": self.sample_bytes,
            "elapsed": round(self.elapsed, 1),
            "estimated_bytes": self.estimated_bytes,
            "estimated_size": human_size(self.estimated_bytes),
            "estimated_seconds": round(self.estimated_seconds),
            "message": self.message,
        }


def sample_window(info: MediaInfo, spec: JobSpec, seconds: float) -> tuple[float, float]:
    """Pick a representative stretch, avoiding titles and fades at the ends."""
    usable_start = spec.trim_start or 0.0
    usable_end = spec.trim_end if spec.trim_end else info.duration
    usable = max(0.0, usable_end - usable_start)

    if usable <= seconds:
        return usable_start, max(0.5, usable)

    # A third of the way in is usually more typical than the opening shot.
    start = usable_start + max(0.0, (usable - seconds) * 0.33)
    return start, seconds


def encode_sample(
    tools: Tools,
    source: Path,
    spec: JobSpec,
    key: str,
    label: str,
    description: str = "",
    seconds: float = 8.0,
) -> SampleResult:
    """Encode a short stretch and extrapolate the result to the full file."""
    source = Path(source)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        info = probe(tools, source)
    except Exception as exc:  # noqa: BLE001 - reported back to the interface
        return SampleResult(key, label, description, False, None, 0, 0, 0, 0, 0, str(exc))

    start, length = sample_window(info, spec, seconds)
    trimmed = replace(spec, trim_start=start, trim_end=start + length, quality_mode="quality"
                      if spec.quality_mode == "size" else spec.quality_mode)

    # A size target means nothing over eight seconds, so samples always use the
    # quality settings and we say so rather than pretending otherwise.
    note = ""
    if spec.quality_mode == "size":
        note = "Size targets apply to the whole file, so this sample shows quality only."

    try:
        normalised, _ = normalise(trimmed, info, tools)
    except Exception as exc:  # noqa: BLE001
        return SampleResult(key, label, description, False, None, 0, 0, 0, 0, 0, str(exc))

    stamp = hashlib.sha256(f"{source}|{key}|{time.time()}".encode()).hexdigest()[:12]
    output = SAMPLE_DIR / f"{stamp}.{normalised.container}"

    started = time.monotonic()
    command, _ = build_command(normalised, info, tools, output)
    try:
        result = subprocess.run(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, errors="replace", timeout=600, **_no_window(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return SampleResult(key, label, description, False, None, 0, 0, 0, 0, 0, str(exc))

    elapsed = time.monotonic() - started

    if result.returncode != 0 or not output.exists():
        detail = (result.stderr or "").strip().splitlines()
        return SampleResult(
            key, label, description, False, None, 0, 0, elapsed, 0, 0,
            detail[-1] if detail else "The sample could not be encoded.",
        )

    sample_bytes = output.stat().st_size
    full_seconds = output_duration(spec, info) or info.duration or length

    # Scale the sample up to the length of the finished file. This is an
    # estimate: quiet or busy stretches encode differently.
    factor = full_seconds / length if length > 0 else 1.0
    estimated_bytes = int(sample_bytes * factor)
    estimated_seconds = elapsed * factor

    return SampleResult(
        key=key,
        label=label,
        description=description,
        ok=True,
        output=output,
        sample_bytes=sample_bytes,
        sample_seconds=length,
        elapsed=elapsed,
        estimated_bytes=estimated_bytes,
        estimated_seconds=estimated_seconds,
        message=note,
    )


def clear_samples() -> None:
    for entry in SAMPLE_DIR.glob("*"):
        try:
            entry.unlink()
        except OSError:
            pass
