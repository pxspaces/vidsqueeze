"""Contact sheets: one image showing everything in a folder.

A shoot is sixty photographs that all look the same in a file listing. A contact
sheet is the oldest answer to that, a single sheet of small versions with the file
names under them, and it is still the fastest way to decide which four are worth
keeping.

Everything here goes through the ordinary picture machinery, so camera RAW works
exactly as it does elsewhere, including the develop and the look.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import images, raw
from .deps import Tools, _no_window
from .images import ImageSpec
from .probe import ProbeError, probe

#: Fonts to label with, in the order they are worth trying. There is no
#: guaranteed font on any of the three platforms, and the one bundled with the
#: interface is a web font that freetype cannot read, so this is a search with a
#: real possibility of failure. Failing means a sheet with no labels, which is
#: still a useful sheet.
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
)

#: Room under each thumbnail for its name, when there is a font to draw it with.
LABEL_HEIGHT = 22


class SheetError(RuntimeError):
    """Raised when a contact sheet cannot be produced."""


@dataclass
class SheetSpec:
    """What the sheet should look like."""

    columns: int = 4
    thumbnail: int = 320          # the longest side of each small picture
    background: str = "white"
    labels: bool = True
    raw_look: str = raw.NATURAL


def find_font() -> str | None:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def _thumbnail(
    tools: Tools,
    source: Path,
    target: Path,
    spec: SheetSpec,
    font: str | None,
    workdir: Path,
) -> bool:
    """One padded, optionally labelled thumbnail. False if it could not be read.

    Every thumbnail has to come out exactly the same size, because tiling them
    is a single filter that assumes a grid.
    """
    picture = source
    if raw.is_raw(source):
        try:
            picture, _ = raw.develop(source, workdir, look=spec.raw_look)
        except raw.RawError:
            return False

    box = spec.thumbnail
    height = box + (LABEL_HEIGHT if font and spec.labels else 0)

    chain = [
        f"scale={box}:{box}:force_original_aspect_ratio=decrease",
        f"pad={box}:{height}:(ow-iw)/2:(({box}-ih)/2):color={spec.background}",
    ]
    if font and spec.labels:
        # The name goes in a file rather than into the filter string. A filename
        # can contain colons, brackets, quotes and backslashes, every one of
        # which means something to the filter parser, and escaping them by hand
        # is a bug waiting to happen.
        note = workdir / f"{target.stem}.txt"
        note.write_text(source.name, encoding="utf-8")
        # expansion=none matters as much as the file does. Even read from a file,
        # drawtext expands percent and brace sequences by default, so a picture
        # called "100% done.jpg" fails with "stray %" and drops off the sheet.
        chain.append(
            f"drawtext=fontfile={_escape(font)}:textfile={_escape(str(note))}"
            f":expansion=none:fontsize=13:fontcolor=black:x=(w-text_w)/2:y={box + 4}"
        )

    command = [
        str(tools.ffmpeg), "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
        "-i", str(picture), "-vf", ",".join(chain),
        "-frames:v", "1", "-update", "1", str(target),
    ]
    result = subprocess.run(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, errors="replace", timeout=300, **_no_window(),
    )
    return result.returncode == 0 and target.exists() and target.stat().st_size > 64


def _escape(value: str) -> str:
    """Escape a path for use inside a filter argument."""
    return value.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def build(
    tools: Tools,
    sources: list[Path],
    output: Path,
    spec: SheetSpec | None = None,
    on_note: Callable[[str], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    keep_going: Callable[[], bool] | None = None,
) -> tuple[Path, list[str]]:
    """Tile the given pictures into one sheet. Returns the sheet and any notes.

    `on_progress` is called with (done, total) after each thumbnail, because a
    sheet of sixty camera RAW files takes a couple of minutes and a window with
    no sign of life looks broken. `keep_going` is asked before each one, so the
    work can be called off.
    """
    spec = spec or SheetSpec()
    notes: list[str] = []

    pictures = [Path(p) for p in sources if _is_picture(tools, Path(p))]
    if not pictures:
        raise SheetError("None of those files is a picture VidSqueeze can read.")

    columns = max(1, min(int(spec.columns), 20))
    font = find_font() if spec.labels else None
    if spec.labels and font is None:
        notes.append("No font was found to write the names with, so the sheet has none.")

    with tempfile.TemporaryDirectory(prefix="vidsqueeze-sheet-") as tmp:
        work = Path(tmp)
        made = 0
        for index, source in enumerate(pictures):
            if keep_going is not None and not keep_going():
                raise SheetError("The sheet was called off.")
            # Numbered from one, with no gaps, because the tiler reads a sequence
            # and a gap silently truncates the sheet.
            target = work / f"{made + 1:04d}.png"
            if _thumbnail(tools, source, target, spec, font, work):
                made += 1
            else:
                notes.append(f"{source.name} could not be read, so it is not on the sheet.")
            if on_progress:
                on_progress(index + 1, len(pictures))

        if made == 0:
            raise SheetError("None of those pictures could be read.")

        rows = (made + columns - 1) // columns
        # The last row is padded out, otherwise the tiler refuses an incomplete grid.
        command = [
            str(tools.ffmpeg), "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
            "-framerate", "1", "-i", str(work / "%04d.png"),
            "-vf", f"tile={columns}x{rows}:padding=6:margin=10:color={spec.background}",
            "-frames:v", "1", "-update", "1", str(output),
        ]
        result = subprocess.run(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, errors="replace", timeout=600, **_no_window(),
        )
        if result.returncode != 0 or not output.exists():
            raise SheetError(f"The sheet could not be assembled: {result.stderr.strip()}")

    notes.insert(0, f"{made} picture{'s' if made != 1 else ''} on a {columns} by {rows} sheet.")
    if on_note:
        for note in notes:
            on_note(note)
    return output, notes


def _is_picture(tools: Tools, path: Path) -> bool:
    """Whether this is something worth putting on a sheet.

    RAW is taken on trust, because measuring it means developing it and that is
    the expensive part. Everything else is asked.
    """
    if raw.is_raw(path):
        return True
    try:
        return probe(tools, path).is_image
    except ProbeError:
        return False
