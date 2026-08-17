"""Camera RAW files.

ffmpeg cannot read camera RAW. Its "raw" decoders are Cintel, DPX and OpenEXR,
none of which is what comes off a Canon or a Nikon. Reading CR2, NEF, ARW and
their relatives means using a decoder built for the job.

So VidSqueeze looks for one, in descending order of how good the result is, and
uses the best it finds to develop the RAW into an ordinary image. That image
then goes through the normal picture pipeline, so every setting behaves exactly
as it does for a JPEG.

If nothing at all is installed, it falls back to the preview image the camera
embedded in the file. That always works and needs nothing, but it is the
camera's own rendering and is often well below full resolution, so it is
reported as such rather than passed off as a real conversion.
"""

from __future__ import annotations

import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .deps import _no_window
from .paths import system_key

#: Formats produced by digital cameras. Not every decoder reads every one, but
#: LibRaw and ImageMagick between them cover all of these.
RAW_EXTENSIONS = {
    ".cr2": "Canon", ".cr3": "Canon", ".crw": "Canon",
    ".nef": "Nikon", ".nrw": "Nikon",
    ".arw": "Sony", ".srf": "Sony", ".sr2": "Sony",
    ".raf": "Fujifilm",
    ".orf": "Olympus",
    ".rw2": "Panasonic", ".raw": "Panasonic",
    ".pef": "Pentax", ".ptx": "Pentax",
    ".srw": "Samsung",
    ".dng": "Adobe DNG",
    ".3fr": "Hasselblad", ".fff": "Hasselblad",
    ".dcr": "Kodak", ".kdc": "Kodak",
    ".mrw": "Minolta",
    ".mos": "Leaf",
    ".iiq": "Phase One",
    ".x3f": "Sigma",
    ".erf": "Epson",
    ".rwl": "Leica", ".rw1": "Leica",
    ".gpr": "GoPro",
}


class RawError(RuntimeError):
    """Raised when a RAW file cannot be developed."""


@dataclass
class Decoder:
    """A program that can turn a RAW file into an ordinary image."""

    name: str          # the executable
    label: str         # what to call it in the interface
    quality: str       # a short honest description
    full_resolution: bool


#: In descending order of result quality. The first one present wins.
CANDIDATES = [
    Decoder("darktable-cli", "darktable", "Full resolution, with the camera's own colour handling.", True),
    Decoder("rawtherapee-cli", "RawTherapee", "Full resolution, high quality development.", True),
    Decoder("dcraw_emu", "LibRaw", "Full resolution.", True),
    Decoder("dcraw", "dcraw", "Full resolution.", True),
    Decoder("magick", "ImageMagick", "Good quality, though often at half resolution.", False),
    Decoder("convert", "ImageMagick", "Good quality, though often at half resolution.", False),
]


def is_raw(path: Path | str) -> bool:
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def camera_of(path: Path | str) -> str:
    return RAW_EXTENSIONS.get(Path(path).suffix.lower(), "camera")


def _which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


def find_decoder() -> Decoder | None:
    """The best RAW decoder installed on this machine, if any."""
    for candidate in CANDIDATES:
        if _which(candidate.name):
            return candidate
    return None


def install_hint() -> str:
    """The right command for this machine, not a generic list.

    Guidance that names the wrong package manager is worse than none, so this
    is chosen per platform.
    """
    return {
        "windows": "winget install ImageMagick.ImageMagick",
        "macos": "brew install libraw",
        "linux": _linux_hint(),
    }[system_key()]


def _linux_hint() -> str:
    if _which("apt"):
        return "sudo apt install libraw-bin"
    if _which("dnf"):
        return "sudo dnf install LibRaw-tools"
    if _which("pacman"):
        return "sudo pacman -S libraw"
    if _which("zypper"):
        return "sudo zypper install libraw-tools"
    return "Install LibRaw or ImageMagick using your distribution's package manager."


# --------------------------------------------------------------------------
# Developing
# --------------------------------------------------------------------------


def _run(command: list[str], timeout: int = 300) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, **_no_window(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        return False, detail[-1] if detail else "the decoder reported an error"
    return True, ""


def develop(source: Path, workdir: Path, decoder: Decoder | None = None) -> tuple[Path, str]:
    """Turn a RAW file into an ordinary image.

    Returns the developed file and a note describing how it was produced. Falls
    back to the camera's embedded preview when no decoder is installed.
    """
    source = Path(source)
    workdir.mkdir(parents=True, exist_ok=True)
    target = workdir / f"{source.stem}-developed.tiff"

    decoder = decoder or find_decoder()

    if decoder is not None:
        ok, problem = _develop_with(decoder, source, target)
        if ok and target.exists() and target.stat().st_size > 1024:
            return target, f"Developed with {decoder.label}."
        # A decoder that is present but fails on this particular file should
        # not stop the conversion, so we still try the preview.
        note_prefix = f"{decoder.label} could not read it ({problem}). "
    else:
        note_prefix = "No RAW decoder is installed. "

    preview = workdir / f"{source.stem}-preview.jpg"
    dimensions = extract_preview(source, preview)
    if dimensions:
        width, height = dimensions
        return preview, (
            f"{note_prefix}Used the preview image the camera stored inside the file "
            f"({width} by {height}). For full quality, install a RAW decoder: {install_hint()}"
        )

    raise RawError(
        f"{note_prefix}There is no preview inside the file either. "
        f"Install a RAW decoder and try again: {install_hint()}"
    )


def _develop_with(decoder: Decoder, source: Path, target: Path) -> tuple[bool, str]:
    """Run one decoder. Each has its own idea of how to be told where to write."""
    name = decoder.name

    if name == "darktable-cli":
        return _run([name, str(source), str(target)])

    if name == "rawtherapee-cli":
        # RawTherapee writes into a directory and picks the name itself.
        ok, problem = _run([name, "-o", str(target.parent), "-t", "-Y", "-c", str(source)])
        if ok:
            produced = target.parent / f"{source.stem}.tif"
            if produced.exists():
                produced.replace(target)
                return True, ""
            return False, "it did not write the file where expected"
        return ok, problem

    if name == "dcraw_emu":
        # LibRaw's tool appends its own suffix to the input name.
        ok, problem = _run([name, "-T", "-w", str(source)])
        if ok:
            for candidate in (source.with_suffix(source.suffix + ".tiff"),
                              source.with_suffix(".tiff")):
                if candidate.exists():
                    candidate.replace(target)
                    return True, ""
            return False, "it did not write the file where expected"
        return ok, problem

    if name == "dcraw":
        try:
            with open(target, "wb") as handle:
                result = subprocess.run(
                    [name, "-T", "-w", "-c", str(source)],
                    stdout=handle, stderr=subprocess.PIPE, timeout=300, **_no_window(),
                )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)
        if result.returncode != 0:
            return False, "dcraw reported an error"
        return True, ""

    if name in ("magick", "convert"):
        command = [name, str(source), str(target)] if name == "convert" else [name, str(source), str(target)]
        return _run(command)

    return False, "unknown decoder"


# --------------------------------------------------------------------------
# The fallback: the preview the camera put inside the file
# --------------------------------------------------------------------------


def _jpeg_size(buf: bytes, start: int) -> tuple[int, int] | None:
    """Read a JPEG's dimensions by walking its markers from the given offset."""
    i = start + 2
    end = len(buf)
    while i < end - 9:
        if buf[i] != 0xFF:
            i += 1
            continue
        marker = buf[i + 1]
        if marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xD9 or marker == 0xDA:
            return None  # reached image data without finding a frame header
        if i + 4 > end:
            return None
        length = struct.unpack(">H", buf[i + 2:i + 4])[0]
        # Any of the start-of-frame markers carries the dimensions.
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", buf[i + 5:i + 9])
            return width, height
        i += 2 + length
    return None


def _jpeg_end(buf: bytes, start: int) -> int:
    """Find where a JPEG really ends.

    Scanning for the first end marker is wrong: that byte pair occurs freely
    inside compressed data. The markers have to be walked, and once image data
    begins the only reliable stop is a marker that is not a restart or a stuffed
    zero byte.
    """
    i = start + 2
    end = len(buf)
    while i < end - 1:
        if buf[i] != 0xFF:
            i += 1
            continue
        marker = buf[i + 1]
        if marker == 0xD9:
            return i + 2
        if marker == 0x00 or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            i += 2
            continue
        if marker == 0xDA:
            # Entropy-coded data follows; step through it byte by byte.
            i += 2 + struct.unpack(">H", buf[i + 2:i + 4])[0]
            while i < end - 1:
                if buf[i] == 0xFF and buf[i + 1] not in (0x00,) and not (0xD0 <= buf[i + 1] <= 0xD7):
                    break
                i += 1
            continue
        if i + 4 > end:
            break
        i += 2 + struct.unpack(">H", buf[i + 2:i + 4])[0]
    return end


def extract_preview(source: Path, target: Path) -> tuple[int, int] | None:
    """Pull the largest JPEG the camera embedded, without any external tool."""
    try:
        data = Path(source).read_bytes()
    except OSError:
        return None

    best: tuple[int, int, int, int] | None = None  # pixels, start, end, index
    position = 0
    while True:
        position = data.find(b"\xff\xd8\xff", position)
        if position < 0:
            break
        size = _jpeg_size(data, position)
        if size:
            end = _jpeg_end(data, position)
            pixels = size[0] * size[1]
            if end > position + 1024 and (best is None or pixels > best[0]):
                best = (pixels, position, end, 0)
                best_size = size
        position += 3

    if best is None:
        return None

    try:
        Path(target).write_bytes(data[best[1]:best[2]])
    except OSError:
        return None
    return best_size


def describe_support() -> dict:
    """What the interface should tell the user about RAW on this machine."""
    decoder = find_decoder()
    return {
        "available": decoder is not None,
        "decoder": decoder.label if decoder else "",
        "quality": decoder.quality if decoder else "",
        "full_resolution": decoder.full_resolution if decoder else False,
        "install_hint": install_hint(),
        "extensions": sorted(RAW_EXTENSIONS),
        "brands": sorted(set(RAW_EXTENSIONS.values())),
    }
