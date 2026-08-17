"""Reading what is actually inside a video file."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from .deps import Tools, _no_window
from .paths import human_duration, human_size

#: Extensions we offer to process. ffmpeg reads far more than this, but an
#: overly broad list turns folder scans into a mess of stray files.
VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv",
    ".flv", ".ts", ".m2ts", ".mts", ".3gp", ".ogv", ".vob", ".mxf", ".asf", ".rm",
}

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".alac"}

#: Still images. Some of these need a recent ffmpeg, which is checked at the
#: point of use rather than assumed here.
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".jpe", ".png", ".webp", ".avif", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".gif", ".jxl", ".qoi", ".ppm", ".pgm", ".pnm", ".tga",
}

#: Camera RAW. ffmpeg cannot read these, so they are developed by a separate
#: decoder first; see raw.py. They are listed here so they appear in the file
#: browser and folder scans like any other picture.
RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".raf",
    ".orf", ".rw2", ".pef", ".ptx", ".srw", ".dng", ".3fr", ".fff", ".dcr",
    ".kdc", ".mrw", ".mos", ".iiq", ".x3f", ".erf", ".rwl", ".rw1", ".gpr",
}

IMAGE_EXTENSIONS |= RAW_EXTENSIONS

MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS

#: Container names ffprobe reports for single images.
IMAGE_CONTAINERS = {
    "png_pipe", "jpeg_pipe", "webp_pipe", "tiff_pipe", "bmp_pipe", "image2",
    "jpegxl_pipe", "qoi_pipe", "gif_pipe", "pgm_pipe", "ppm_pipe", "tga_pipe", "avif",
}

KIND_VIDEO = "video"
KIND_AUDIO = "audio"
KIND_IMAGE = "image"


class ProbeError(RuntimeError):
    """Raised when a file cannot be read as media."""


@dataclass
class MediaInfo:
    """Everything we need to know about an input file."""

    path: Path
    size_bytes: int
    duration: float
    container: str
    has_video: bool
    has_audio: bool
    video_codec: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    pix_fmt: str = ""
    bit_depth: int = 8
    rotation: int = 0
    exif_orientation: int = 0          # 1 to 8 for stills, 0 when absent
    color_transfer: str = ""
    color_primaries: str = ""
    video_bitrate: int = 0
    audio_codec: str = ""
    audio_channels: int = 0
    audio_bitrate: int = 0
    subtitle_count: int = 0
    frame_count: int = 0
    has_alpha: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    # -- derived -----------------------------------------------------------

    @property
    def kind(self) -> str:
        """Whether this is a video, a sound file or a still image.

        Images are the awkward case: they have a video stream but no duration,
        so anything that divides by length has to know the difference.
        """
        if not self.has_video:
            return KIND_AUDIO
        container = (self.container or "").lower()
        looks_still = container in IMAGE_CONTAINERS or self.path.suffix.lower() in IMAGE_EXTENSIONS
        if looks_still and self.frame_count <= 1 and self.duration <= 0.2:
            return KIND_IMAGE
        return KIND_VIDEO

    @property
    def is_image(self) -> bool:
        return self.kind == KIND_IMAGE

    @property
    def is_audio(self) -> bool:
        return self.kind == KIND_AUDIO

    @property
    def is_hdr(self) -> bool:
        """True for HDR10/PQ or HLG footage, which needs tone mapping for SDR."""
        return self.color_transfer in ("smpte2084", "arib-std-b67")

    @property
    def display_width(self) -> int:
        """Width after the container's rotation flag is applied."""
        return self.height if self.rotation in (90, 270) else self.width

    @property
    def display_height(self) -> int:
        return self.width if self.rotation in (90, 270) else self.height

    @property
    def is_portrait(self) -> bool:
        return self.display_height > self.display_width

    @property
    def overall_bitrate(self) -> int:
        if self.duration <= 0:
            return 0
        return int(self.size_bytes * 8 / self.duration)

    @property
    def resolution_label(self) -> str:
        if not self.has_video:
            return "audio only"
        shortest = min(self.display_width, self.display_height)
        for limit, name in ((2160, "4K"), (1440, "1440p"), (1080, "1080p"), (720, "720p"), (480, "480p")):
            if shortest >= limit:
                return name
        return f"{self.display_height}p"

    def summary(self) -> str:
        if self.is_image:
            alpha = ", transparent" if self.has_alpha else ""
            return (
                f"{self.display_width}x{self.display_height}, "
                f"{self.video_codec}{alpha}, {human_size(self.size_bytes)}"
            )
        if not self.has_video:
            return f"{human_duration(self.duration)}, {self.audio_codec or 'audio'}, {human_size(self.size_bytes)}"
        return (
            f"{self.display_width}x{self.display_height} "
            f"({self.resolution_label}), {self.fps:g}fps, {self.video_codec}, "
            f"{human_duration(self.duration)}, {human_size(self.size_bytes)}"
        )


def _parse_fps(value: str) -> float:
    """Turn ffprobe's '25/1' style fraction into a float."""
    if not value or value == "0/0":
        return 0.0
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return 0.0


def _rotation_of(stream: dict) -> int:
    """Read rotation from either the modern display matrix or the old tag."""
    for side_data in stream.get("side_data_list", []) or []:
        if "rotation" in side_data:
            try:
                return int(round(float(side_data["rotation"]))) % 360
            except (TypeError, ValueError):
                pass
    tag = (stream.get("tags") or {}).get("rotate")
    if tag:
        try:
            return int(float(tag)) % 360
        except ValueError:
            pass
    return 0


def _bit_depth_of(stream: dict) -> int:
    raw = stream.get("bits_per_raw_sample")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return 10 if "10" in (stream.get("pix_fmt") or "") else 8


def probe(tools: Tools, path: Path | str) -> MediaInfo:
    """Inspect a media file. Raises ProbeError if ffprobe cannot make sense of it."""
    path = Path(path)
    if not path.exists():
        raise ProbeError(f"File not found: {path}")

    command = [
        str(tools.ffprobe),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            timeout=120,
            **_no_window(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError(f"Could not read {path.name}: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        reason = detail[-1] if detail else "unrecognised format"
        raise ProbeError(f"Could not read {path.name}: {reason}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"Could not read {path.name}: unexpected ffprobe output") from exc

    fmt = data.get("format", {}) or {}
    streams = data.get("streams", []) or []
    video = next((s for s in streams if s.get("codec_type") == "video" and not _is_cover_art(s)), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    try:
        size_bytes = int(fmt.get("size") or path.stat().st_size)
    except (OSError, ValueError):
        size_bytes = 0

    try:
        duration = float(fmt.get("duration") or 0.0)
    except ValueError:
        duration = 0.0
    if duration <= 0 and video:
        try:
            duration = float(video.get("duration") or 0.0)
        except ValueError:
            duration = 0.0

    info = MediaInfo(
        path=path,
        size_bytes=size_bytes,
        duration=duration,
        container=(fmt.get("format_name") or "").split(",")[0],
        has_video=video is not None,
        has_audio=audio is not None,
        subtitle_count=sum(1 for s in streams if s.get("codec_type") == "subtitle"),
        raw=data,
    )

    if video:
        info.video_codec = video.get("codec_name", "")
        info.width = int(video.get("width") or 0)
        info.height = int(video.get("height") or 0)
        info.fps = _parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate") or "")
        info.pix_fmt = video.get("pix_fmt", "")
        info.bit_depth = _bit_depth_of(video)
        info.rotation = _rotation_of(video)
        info.color_transfer = video.get("color_transfer", "") or ""
        info.color_primaries = video.get("color_primaries", "") or ""
        info.has_alpha = _has_alpha(video)
        try:
            info.frame_count = int(video.get("nb_frames") or 0)
        except ValueError:
            info.frame_count = 0
        try:
            info.video_bitrate = int(video.get("bit_rate") or 0)
        except ValueError:
            info.video_bitrate = 0

    if audio:
        info.audio_codec = audio.get("codec_name", "")
        info.audio_channels = int(audio.get("channels") or 0)
        try:
            info.audio_bitrate = int(audio.get("bit_rate") or 0)
        except ValueError:
            info.audio_bitrate = 0

    if not info.has_video and not info.has_audio:
        raise ProbeError(f"{path.name} contains no video or audio")

    # Stills carry their rotation in EXIF, which ffprobe reports nowhere: no
    # tag, no side data, and the dimensions given as stored. The decoder rotates
    # anyway, so without this the rest of the program disagrees with ffmpeg
    # about which side of a sideways photograph is the long one.
    if info.is_image and not info.rotation:
        info.exif_orientation = _exif_orientation(path)
        if info.exif_orientation in SWAPPING_ORIENTATIONS:
            info.rotation = 90

    return info


#: EXIF orientations that put the long side the other way round. The mirrored
#: ones matter here too: 5 and 7 are a flip *and* a quarter turn.
SWAPPING_ORIENTATIONS = frozenset({5, 6, 7, 8})

#: The EXIF tag holding the orientation.
_ORIENTATION_TAG = 0x0112


def _exif_orientation(path: Path) -> int:
    """The EXIF orientation of a still, 1 to 8, or 0 when there is none.

    Written out by hand rather than pulled from a library, because the program
    has no third-party dependencies and this is a few dozen lines. It reads by
    seeking rather than loading the file, so it costs nothing on a 30 MB RAW.
    """
    try:
        with open(path, "rb") as handle:
            start = handle.read(2)
            if start == b"\xff\xd8":                    # JPEG
                base = _jpeg_exif_offset(handle)
                return _tiff_orientation(handle, base) if base is not None else 0
            if start in (b"II", b"MM"):                 # TIFF, and most RAW
                return _tiff_orientation(handle, 0)
            if start == b"\x89P":                       # PNG
                base = _chunk_exif_offset(handle, b"eXIf", png=True)
                return _tiff_orientation(handle, base) if base is not None else 0
            if start == b"RI":                          # RIFF, which means WebP
                base = _chunk_exif_offset(handle, b"EXIF", png=False)
                return _tiff_orientation(handle, base) if base is not None else 0
    except OSError:
        return 0
    return 0


def _chunk_exif_offset(handle, want: bytes, png: bool) -> int | None:
    """Find an EXIF chunk in a PNG or a WebP.

    Both are chunked formats that park a TIFF block inside a named chunk, which
    is a third and a fourth place a photograph can record which way up it is.
    A reader that only understands JPEG gets these silently wrong, because
    ffmpeg rotates them and says nothing.

    PNG counts big endian and pads nothing. RIFF counts little endian and pads
    odd-sized chunks to an even boundary.
    """
    order = "big" if png else "little"
    handle.seek(8 if png else 12)                       # past the signature
    for _ in range(64):                                 # bounded: headers are near the front
        header = handle.read(8)
        if len(header) < 8:
            return None
        if png:
            size, name = int.from_bytes(header[0:4], order), header[4:8]
        else:
            name, size = header[0:4], int.from_bytes(header[4:8], order)
        if name == want:
            return handle.tell()
        if name in (b"IDAT", b"IEND"):                  # pixel data, too late
            return None
        skip = size + (4 if png else 0)                 # PNG chunks carry a CRC
        if not png and size % 2:
            skip += 1                                   # RIFF pads to even
        handle.seek(skip, 1)
    return None


def _jpeg_exif_offset(handle) -> int | None:
    """Walk a JPEG's markers to the start of its EXIF block."""
    handle.seek(2)
    while True:
        marker = handle.read(2)
        if len(marker) < 2 or marker[0] != 0xFF:
            return None
        kind = marker[1]
        if kind in (0xD8, 0x01) or 0xD0 <= kind <= 0xD7:
            continue                                    # no payload
        if kind in (0xDA, 0xD9):
            return None                                 # image data, too late
        size = handle.read(2)
        if len(size) < 2:
            return None
        length = int.from_bytes(size, "big")
        if kind == 0xE1:
            if handle.read(6) == b"Exif\x00\x00":
                return handle.tell()
            handle.seek(length - 8, 1)
        else:
            handle.seek(length - 2, 1)


def _tiff_orientation(handle, base: int) -> int:
    """Read the orientation out of a TIFF header and its first directory."""
    handle.seek(base)
    header = handle.read(8)
    if len(header) < 8:
        return 0
    if header[:2] == b"II":
        order = "little"
    elif header[:2] == b"MM":
        order = "big"
    else:
        return 0
    if int.from_bytes(header[2:4], order) != 42:
        return 0

    first = int.from_bytes(header[4:8], order)
    if first < 8:
        return 0
    handle.seek(base + first)
    entries = handle.read(2)
    if len(entries) < 2:
        return 0

    # A bound on the loop: a corrupt count should not send us reading forever.
    for _ in range(min(int.from_bytes(entries, order), 512)):
        entry = handle.read(12)
        if len(entry) < 12:
            return 0
        if int.from_bytes(entry[0:2], order) == _ORIENTATION_TAG:
            value = int.from_bytes(entry[8:10], order)
            return value if 1 <= value <= 8 else 0
    return 0


#: Pixel formats that carry transparency. Flattening onto a background is only
#: needed when the source has alpha and the target format cannot store it.
_ALPHA_FORMATS = {
    "rgba", "bgra", "argb", "abgr", "yuva420p", "yuva422p", "yuva444p",
    "rgba64be", "rgba64le", "ya8", "ya16be", "ya16le", "pal8",
}


def _has_alpha(stream: dict) -> bool:
    pix_fmt = (stream.get("pix_fmt") or "").lower()
    return pix_fmt in _ALPHA_FORMATS or pix_fmt.startswith("yuva") or "a" == pix_fmt[-1:]


def _is_cover_art(stream: dict) -> bool:
    """Album artwork shows up as a single-frame video stream; ignore it."""
    disposition = stream.get("disposition") or {}
    return bool(disposition.get("attached_pic"))


def looks_like_media(path: Path) -> bool:
    """Cheap extension check used when scanning folders."""
    return path.suffix.lower() in MEDIA_EXTENSIONS


def kind_for_extension(path: Path | str) -> str | None:
    """Guess what a file is from its name alone, without opening it.

    This is deliberately cheap, so it can be used to filter a folder of
    thousands. It can be wrong in one direction: an animated GIF is called an
    image here and turns out to be a video once opened. Nothing depends on that
    distinction at the point this is used.
    """
    suffix = Path(path).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return KIND_VIDEO
    if suffix in AUDIO_EXTENSIONS:
        return KIND_AUDIO
    if suffix in IMAGE_EXTENSIONS:
        return KIND_IMAGE
    return None


def matches_kinds(path: Path | str, kinds: set[str] | None) -> bool:
    """Whether a file is one of the kinds asked for. No filter means everything."""
    if not kinds:
        return True
    return kind_for_extension(path) in kinds


def scan_folder(folder: Path, recursive: bool = True, kinds: set[str] | None = None) -> list[Path]:
    """Find media files in a folder, skipping our own output and hidden files."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    walker = folder.rglob("*") if recursive else folder.glob("*")
    results = []
    for candidate in walker:
        if not candidate.is_file() or candidate.name.startswith("."):
            continue
        if not looks_like_media(candidate):
            continue
        if not matches_kinds(candidate, kinds):
            continue
        results.append(candidate)
    return sorted(results)
