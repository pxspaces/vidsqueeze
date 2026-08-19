"""Converting still images.

Images cannot go through the video pipeline: they have no duration, so anything
that reasons about bitrate or length is meaningless for them. They get their own
small pipeline here, sharing the same job and queue machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .deps import Tools
from .probe import MediaInfo

#: Output formats, with the encoder and file extension each needs.
IMAGE_FORMATS = {
    "jpeg": {"encoder": "mjpeg", "ext": "jpg", "label": "JPEG", "alpha": False,
             "note": "Universal. No transparency."},
    "png": {"encoder": "png", "ext": "png", "label": "PNG", "alpha": True,
            "note": "Lossless, keeps transparency. Large."},
    "webp": {"encoder": "libwebp", "ext": "webp", "label": "WebP", "alpha": True,
             "note": "Much smaller than JPEG, keeps transparency."},
    "avif": {"encoder": "libsvtav1", "ext": "avif", "label": "AVIF", "alpha": False,
             "note": "Smallest of all. Needs a recent browser or viewer."},
    "jxl": {"encoder": "libjxl", "ext": "jxl", "label": "JPEG XL", "alpha": True,
            "note": "Excellent quality per byte. Limited support so far."},
    "tiff": {"encoder": "tiff", "ext": "tiff", "label": "TIFF", "alpha": True,
             "note": "Lossless and very large. For print and archiving."},
    "bmp": {"encoder": "bmp", "ext": "bmp", "label": "BMP", "alpha": False,
            "note": "Uncompressed. Rarely what you want."},
}

#: Formats that store transparency. Anything else needs a flat background.
ALPHA_CAPABLE = {name for name, spec in IMAGE_FORMATS.items() if spec["alpha"]}

#: Formats that are lossless however they are asked for, so nothing about the
#: pixels may be thrown away on the way in.
ALWAYS_LOSSLESS = {"png", "tiff", "bmp"}

#: At or above this quality the user has asked for fidelity rather than a small
#: file, so colour stops being subsampled where the encoder allows it.
FULL_CHROMA_FROM = 90


@dataclass
class ImageSpec:
    """What to do with a still image."""

    image_format: str = "jpeg"     # a key of IMAGE_FORMATS
    quality: int = 82              # 1 to 100, higher is better
    lossless: bool = False         # WebP and JPEG XL only
    max_dimension: int | None = None   # longest side, in pixels
    background: str = "white"      # used when flattening transparency
    saturation: float = 1.0        # 1.0 leaves colour exactly as it arrived
    keep_metadata: bool = True
    strip_colour_profile: bool = False
    extra_args: list[str] = field(default_factory=list)


class ImageError(RuntimeError):
    """Raised when an image cannot be converted."""


def format_of(path: Path) -> str:
    """Best guess at the format key for an existing file."""
    suffix = path.suffix.lower().lstrip(".")
    if suffix in ("jpg", "jpeg", "jpe"):
        return "jpeg"
    if suffix in ("tif", "tiff"):
        return "tiff"
    if suffix in ("heic", "heif"):
        return "heic"
    return suffix


def available_formats(tools: Tools) -> list[str]:
    """Output formats this ffmpeg build can actually produce."""
    usable = []
    for name, spec in IMAGE_FORMATS.items():
        encoder = spec["encoder"]
        # The simple built-in encoders are always present; the library-backed
        # ones are not, so only those need checking.
        if encoder in ("mjpeg", "png", "tiff", "bmp") or tools.has(encoder):
            usable.append(name)
    return usable


def _quality_args(spec: ImageSpec) -> list[str]:
    """Translate one quality number into whatever each encoder expects."""
    quality = max(1, min(100, int(spec.quality)))
    fmt = spec.image_format

    if fmt == "jpeg":
        # ffmpeg's JPEG scale runs 2 (best) to 31 (worst), the opposite way round.
        value = round(2 + (100 - quality) * (31 - 2) / 99)
        return ["-q:v", str(value)]

    if fmt == "webp":
        if spec.lossless:
            return ["-lossless", "1"]
        return ["-quality", str(quality)]

    if fmt == "avif":
        # AV1 uses CRF, 0 (best) to 63 (worst). The still-picture flag belongs
        # to libaom and is rejected by the encoder we use, so it is not passed.
        value = round((100 - quality) * 63 / 99)
        return ["-crf", str(value)]

    if fmt == "jxl":
        if spec.lossless:
            return ["-distance", "0"]
        # JPEG XL distance: 0 is lossless, 1 is visually lossless, 15 is poor.
        distance = round((100 - quality) * 15 / 99, 1)
        return ["-distance", str(distance)]

    if fmt == "png":
        return ["-compression_level", "9"]

    return []


def pixel_format(spec: ImageSpec, info: MediaInfo) -> str | None:
    """The pixel format to force, or None to let ffmpeg decide.

    Forcing one is occasionally necessary and frequently harmful, so the default
    answer here is None. ffmpeg already picks the best format the encoder
    supports for the input it has, and it is right more often than we are.

    Lossless encoders especially must be left alone. Handing libwebp
    `yuv420p` threw three quarters of the colour away before the encoder saw
    the image: the result measured 30.7 dB against a source it was supposed to
    reproduce exactly, and came out twice as large, because subsampling noise
    does not compress. Left alone, libwebp picks `bgra` and reproduces the
    source perfectly.
    """
    fmt = spec.image_format
    quality = max(1, min(100, int(spec.quality)))

    if spec.lossless and fmt in ("webp", "jxl"):
        return None

    if fmt in ALWAYS_LOSSLESS:
        if quality >= FULL_CHROMA_FROM or fmt == "bmp":
            # Keep whatever depth the source has. A developed RAW is 16 bit per
            # channel, and this is how the user asks to keep all of it.
            return None
        # Otherwise cap at 8 bits per channel. This never raises an 8 bit
        # source, it only stops a 16 bit develop from producing a file several
        # times larger than the original, which is the opposite of the point.
        # A 26 megapixel RAW makes a 120 MB PNG at 16 bit and 37 MB at 8.
        return "rgba" if info.has_alpha else "rgb24"

    if fmt == "jpeg":
        # 4:2:0 costs about 3.7 dB of colour against 4:4:4 for identical luma.
        # That is a fair trade for a small file and a poor one when the user
        # has explicitly asked for quality.
        return "yuvj444p" if quality >= FULL_CHROMA_FROM else "yuvj420p"

    if fmt == "avif":
        # SVT-AV1 encodes 4:2:0 and nothing else. Do not "improve" this to
        # yuv444p: the encoder does not accept it and the conversion fails.
        # Depth is the only fidelity dial available here.
        return "yuv420p10le" if quality >= FULL_CHROMA_FROM else "yuv420p"

    # Lossy WebP is 4:2:0 inside whatever it is handed, and it manages alpha
    # itself, so there is nothing worth forcing.
    return None


def build_command(
    spec: ImageSpec,
    info: MediaInfo,
    tools: Tools,
    output: Path,
) -> tuple[list[str], list[str]]:
    """Produce the ffmpeg command for one image. Returns (command, notes)."""
    notes: list[str] = []
    fmt = spec.image_format
    if fmt not in IMAGE_FORMATS:
        raise ImageError(f"{fmt} is not a format HalveIt can write.")

    details = IMAGE_FORMATS[fmt]
    command = [str(tools.ffmpeg), "-hide_banner", "-nostdin", "-y", "-loglevel", "error"]

    filters: list[str] = []

    # Colour first, while the picture is still at full size, so the adjustment
    # is measured on the same pixels whatever resizing follows.
    if abs(spec.saturation - 1.0) > 0.001:
        filters.append(f"eq=saturation={spec.saturation:g}")

    if spec.max_dimension and info.display_width and info.display_height:
        longest = max(info.display_width, info.display_height)
        if longest > spec.max_dimension:
            # Scale the longer side and let the other follow. It has to be -2
            # rather than -1: that rounds to an even number, and formats with
            # subsampled colour, AVIF among them, refuse odd dimensions and
            # silently produce an empty file.
            if info.display_width >= info.display_height:
                filters.append(f"scale={spec.max_dimension}:-2:flags=lanczos")
            else:
                filters.append(f"scale=-2:{spec.max_dimension}:flags=lanczos")
        else:
            notes.append(f"{info.path.name} is already smaller than {spec.max_dimension}px, keeping its size.")

    flatten = info.has_alpha and fmt not in ALPHA_CAPABLE
    if flatten:
        notes.append(
            f"{details['label']} cannot store transparency, so the image is placed "
            f"on a {spec.background} background."
        )

    command += ["-i", str(info.path)]

    if flatten:
        # Draw the image over a solid colour of the same size, then flatten.
        size = f"{info.display_width}x{info.display_height}"
        chain = f"color={spec.background}:s={size}[bg];[bg][0:v]overlay=shortest=1"
        if filters:
            chain += "," + ",".join(filters)
        chain += "[out]"
        command += ["-filter_complex", chain, "-map", "[out]"]
    elif filters:
        command += ["-vf", ",".join(filters)]

    command += ["-c:v", details["encoder"]]
    command += _quality_args(spec)

    chosen = pixel_format(spec, info)
    if chosen:
        command += ["-pix_fmt", chosen]

    if not spec.keep_metadata:
        command += ["-map_metadata", "-1"]

    # A single frame, not a one-frame video. The update flag tells the image
    # muxer to write one file rather than a numbered sequence, but the AVIF
    # muxer does not accept it and writes nothing at all if it is given.
    command += ["-frames:v", "1"]
    if fmt == "avif":
        command += ["-f", "avif"]
    else:
        command += ["-update", "1"]

    command += spec.extra_args
    command += [str(output)]
    return command, notes


#: Sources that are already compressed hard. Turning one of these into a lossless
#: format makes it bigger, always, and there is nothing wrong with the program
#: when it happens.
ALREADY_COMPRESSED = {"jpeg", "jpg", "jpe", "heic", "heif", "webp", "avif", "jxl", "mp4"}


def size_expectation(spec: ImageSpec, source_format: str, is_raw: bool = False) -> str:
    """A plain warning that the result will be bigger, or "" when it will not.

    Said before the job rather than after. HalveIt reported "the result is not
    smaller" on every RAW to PNG conversion, which is true, unavoidable and reads
    like a fault. Anybody choosing PNG deserves to know that beforehand, when they
    can still choose something else.
    """
    fmt = spec.image_format
    source = (source_format or "").lower().lstrip(".")

    if fmt not in ALWAYS_LOSSLESS and not (spec.lossless and fmt in ("webp", "jxl")):
        return ""

    label = IMAGE_FORMATS.get(fmt, {}).get("label", fmt.upper())

    if is_raw:
        if fmt in ALWAYS_LOSSLESS and spec.quality >= FULL_CHROMA_FROM:
            return (
                f"{label} at this quality keeps every colour value from the camera, "
                f"so expect a file several times the size of the original. "
                f"Choose JPEG or WebP for something smaller, or a quality below "
                f"{FULL_CHROMA_FROM} for half the depth."
            )
        return (
            f"{label} throws nothing away, so a photograph converted to it is "
            f"normally larger than the camera file, not smaller. Choose JPEG, "
            f"WebP or AVIF if a smaller file is the point."
        )

    if source in ALREADY_COMPRESSED:
        return (
            f"This file is already compressed, and {label} throws nothing away, "
            f"so the result will almost certainly be larger. That is worth doing "
            f"to stop further quality loss, and not worth doing to save space."
        )
    return ""


def output_name(source: Path, spec: ImageSpec) -> str:
    """The file name a converted image should get."""
    extension = IMAGE_FORMATS[spec.image_format]["ext"]
    return f"{source.stem}.{extension}"


def describe(spec: ImageSpec) -> str:
    """A short human summary of what will happen."""
    details = IMAGE_FORMATS.get(spec.image_format)
    if not details:
        return "Unknown format"
    parts = [details["label"]]
    if spec.lossless and spec.image_format in ("webp", "jxl"):
        parts.append("lossless")
    elif spec.image_format not in ("png", "tiff", "bmp"):
        parts.append(f"quality {spec.quality}")
    if spec.max_dimension:
        parts.append(f"max {spec.max_dimension}px")
    return ", ".join(parts)
