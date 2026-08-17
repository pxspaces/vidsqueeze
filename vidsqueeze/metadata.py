"""Carrying a photograph's details across a conversion.

ffmpeg cannot do this for stills. Its image encoders write pixels and nothing
else, so a converted photograph loses the camera, the lens, the exposure and,
worst of all, the date it was taken. A folder of holiday pictures comes out
stamped with the day they were converted, and the order they were taken in is
gone for good.

So the details are read here and written back afterwards. Rather than relocating
the original block, which means rewriting every internal offset and is a fine
way to produce a file that half the world cannot open, a small fresh block is
built from the handful of fields worth keeping. Every offset in it is one we
calculated ourselves.

What is possible depends on the target:

- **JPEG** takes a full block, so everything below survives.
- **Everything else** gets the file's timestamp put back, so at least the
  ordering of a shoot is preserved. PNG and WebP can carry this properly and
  one day should.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

#: TIFF field types we handle, with the width of one component.
BYTE, ASCII, SHORT, LONG, RATIONAL = 1, 2, 3, 4, 5
_WIDTHS = {BYTE: 1, ASCII: 1, SHORT: 2, LONG: 4, RATIONAL: 8}

#: Tags kept from the main directory.
MAKE, MODEL, ORIENTATION, SOFTWARE, DATETIME = 0x010F, 0x0110, 0x0112, 0x0131, 0x0132

#: Pointer from the main directory to the one holding the photographic details.
EXIF_POINTER = 0x8769

#: Tags kept from that second directory.
EXPOSURE_TIME, F_NUMBER = 0x829A, 0x829D
ISO, DATETIME_ORIGINAL, DATETIME_DIGITIZED = 0x8827, 0x9003, 0x9004
FOCAL_LENGTH, LENS_MODEL, BODY_SERIAL = 0x920A, 0xA434, 0xA431

MAIN_TAGS = (MAKE, MODEL, SOFTWARE, DATETIME)
DETAIL_TAGS = (EXPOSURE_TIME, F_NUMBER, ISO, DATETIME_ORIGINAL,
               DATETIME_DIGITIZED, FOCAL_LENGTH, LENS_MODEL, BODY_SERIAL)


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def read(path: Path) -> dict:
    """Everything worth keeping from a JPEG, a TIFF or a camera RAW.

    Returns {tag: (type, [values])}. An empty dictionary means there was
    nothing to find, which is not an error: plenty of images have no details.
    """
    try:
        with open(path, "rb") as handle:
            start = handle.read(2)
            if start == b"\xff\xd8":
                base = _jpeg_exif_offset(handle)
                if base is None:
                    return {}
            elif start in (b"II", b"MM"):
                base = 0
            else:
                return {}
            return _read_directories(handle, base)
    except (OSError, ValueError):
        return {}


def _jpeg_exif_offset(handle) -> int | None:
    """Walk a JPEG's markers to where its details begin."""
    handle.seek(2)
    while True:
        marker = handle.read(2)
        if len(marker) < 2 or marker[0] != 0xFF:
            return None
        kind = marker[1]
        if kind in (0xD8, 0x01) or 0xD0 <= kind <= 0xD7:
            continue
        if kind in (0xDA, 0xD9):
            return None
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


def _read_directories(handle, base: int) -> dict:
    handle.seek(base)
    header = handle.read(8)
    if len(header) < 8 or header[:2] not in (b"II", b"MM"):
        return {}
    order = "little" if header[:2] == b"II" else "big"
    if int.from_bytes(header[2:4], order) != 42:
        return {}
    first = int.from_bytes(header[4:8], order)
    if first < 8:
        return {}

    found: dict = {}
    main = _read_one_directory(handle, base, first, order)
    for tag in MAIN_TAGS:
        if tag in main:
            found[tag] = main[tag]

    pointer = main.get(EXIF_POINTER)
    if pointer and pointer[1]:
        try:
            details = _read_one_directory(handle, base, int(pointer[1][0]), order)
        except (ValueError, TypeError):
            details = {}
        for tag in DETAIL_TAGS:
            if tag in details:
                found[tag] = details[tag]
    return found


def _read_one_directory(handle, base: int, offset: int, order: str) -> dict:
    handle.seek(base + offset)
    raw = handle.read(2)
    if len(raw) < 2:
        return {}
    entries: dict = {}
    # Bounded, so a corrupt count cannot send us reading forever.
    for _ in range(min(int.from_bytes(raw, order), 512)):
        entry = handle.read(12)
        if len(entry) < 12:
            break
        tag = int.from_bytes(entry[0:2], order)
        kind = int.from_bytes(entry[2:4], order)
        count = int.from_bytes(entry[4:8], order)
        if kind not in _WIDTHS or count > 4096:
            continue
        total = _WIDTHS[kind] * count
        if total <= 4:
            payload = entry[8:8 + total]
        else:
            where = int.from_bytes(entry[8:12], order)
            keep = handle.tell()
            handle.seek(base + where)
            payload = handle.read(total)
            handle.seek(keep)
            if len(payload) < total:
                continue
        values = _decode(kind, count, payload, order)
        if values is not None:
            entries[tag] = (kind, values)
    return entries


def _decode(kind: int, count: int, payload: bytes, order: str):
    if kind == ASCII:
        return [payload.split(b"\x00")[0].decode("utf-8", "replace")]
    numbers = []
    for index in range(count):
        chunk = payload[index * _WIDTHS[kind]:(index + 1) * _WIDTHS[kind]]
        if len(chunk) < _WIDTHS[kind]:
            return None
        if kind == RATIONAL:
            numerator = int.from_bytes(chunk[:4], order)
            denominator = int.from_bytes(chunk[4:], order) or 1
            numbers.append((numerator, denominator))
        else:
            numbers.append(int.from_bytes(chunk, order))
    return numbers


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def build_block(fields: dict) -> bytes:
    """Assemble a fresh EXIF block, ready to sit in a JPEG.

    Built rather than copied, so every offset inside is one we worked out here.
    Little endian throughout, because there is no reason to prefer the other and
    one code path is easier to be sure about.
    """
    main = {tag: fields[tag] for tag in MAIN_TAGS if tag in fields}
    details = {tag: fields[tag] for tag in DETAIL_TAGS if tag in fields}

    # The rotation has already been applied to the pixels by this point, so the
    # picture is upright and must say so. Leaving the original value here would
    # turn it a second time in every viewer that honours it.
    main[ORIENTATION] = (SHORT, [1])

    if not details:
        body, _ = _directory(main, 8)
        return b"II\x2a\x00" + (8).to_bytes(4, "little") + body

    # The main directory needs a pointer to the second one, whose position
    # depends on how big the main one turns out to be. So measure, then place.
    provisional = dict(main)
    provisional[EXIF_POINTER] = (LONG, [0])
    size = _directory_size(provisional)
    detail_at = 8 + size

    provisional[EXIF_POINTER] = (LONG, [detail_at])
    main_body, _ = _directory(provisional, 8)
    detail_body, _ = _directory(details, detail_at)
    return b"II\x2a\x00" + (8).to_bytes(4, "little") + main_body + detail_body


def _directory_size(fields: dict) -> int:
    total = 2 + 12 * len(fields) + 4
    for kind, values in fields.values():
        width = _payload(kind, values)
        if len(width) > 4:
            total += len(width)
    return total


def _directory(fields: dict, position: int) -> tuple[bytes, int]:
    """One directory, plus the overflow area for values too big to sit inline."""
    ordered = sorted(fields.items())
    header = len(ordered).to_bytes(2, "little")
    table = b""
    overflow = b""
    # Where the overflow area starts, relative to the whole block.
    data_at = position + 2 + 12 * len(ordered) + 4

    for tag, (kind, values) in ordered:
        payload = _payload(kind, values)
        count = len(values) if kind != ASCII else len(payload)
        entry = tag.to_bytes(2, "little") + kind.to_bytes(2, "little") + count.to_bytes(4, "little")
        if len(payload) <= 4:
            entry += payload.ljust(4, b"\x00")
        else:
            entry += (data_at + len(overflow)).to_bytes(4, "little")
            overflow += payload
        table += entry

    return header + table + b"\x00\x00\x00\x00" + overflow, data_at + len(overflow)


def _payload(kind: int, values) -> bytes:
    if kind == ASCII:
        text = str(values[0]) if values else ""
        return text.encode("utf-8", "replace")[:255] + b"\x00"
    out = b""
    for value in values:
        if kind == RATIONAL:
            numerator, denominator = value
            out += int(numerator).to_bytes(4, "little") + int(denominator).to_bytes(4, "little")
        else:
            out += int(value).to_bytes(_WIDTHS[kind], "little")
    return out


def splice_into_jpeg(path: Path, block: bytes) -> bool:
    """Put an EXIF block into a JPEG, replacing any block already there."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return False
    if not data.startswith(b"\xff\xd8"):
        return False

    payload = b"Exif\x00\x00" + block
    if len(payload) + 2 > 0xFFFF:
        return False
    segment = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload

    rest = data[2:]
    # Drop an existing block rather than ending up with two.
    if rest[:2] == b"\xff\xe1":
        length = int.from_bytes(rest[2:4], "big")
        rest = rest[2 + length:]
    try:
        Path(path).write_bytes(data[:2] + segment + rest)
    except OSError:
        return False
    return True


# --------------------------------------------------------------------------
# Timestamps
# --------------------------------------------------------------------------


def taken_at(fields: dict) -> float | None:
    """When the photograph was taken, as a timestamp, if it says."""
    for tag in (DATETIME_ORIGINAL, DATETIME_DIGITIZED, DATETIME):
        entry = fields.get(tag)
        if not entry or not entry[1]:
            continue
        try:
            return datetime.strptime(str(entry[1][0]).strip(), "%Y:%m:%d %H:%M:%S").timestamp()
        except (ValueError, TypeError):
            continue
    return None


def carry(source: Path, output: Path, fields: dict | None = None) -> str:
    """Move the details from one file to the other. Returns a short note.

    Never raises. A conversion that worked must not be reported as a failure
    because a date could not be copied.
    """
    source, output = Path(source), Path(output)
    fields = read(source) if fields is None else fields

    carried = False
    if output.suffix.lower() in (".jpg", ".jpeg") and fields:
        block = build_block(fields)
        carried = splice_into_jpeg(output, block)

    # Whatever the format, keep the file's own date, so a shoot stays in order
    # in any folder sorted by time.
    when = taken_at(fields)
    if when is None:
        try:
            when = source.stat().st_mtime
        except OSError:
            when = None
    if when is not None:
        try:
            os.utime(output, (when, when))
        except OSError:
            pass

    if carried:
        return "Camera details and the date it was taken were carried across."
    if when is not None:
        return "The date it was taken was kept."
    return ""
