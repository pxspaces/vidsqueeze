"""Shared helpers for the suite.

Nothing here imports anything that is not in the standard library, for the same
reason the program itself does not: the tests have to run on whatever Python is
already on the machine.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

from vidsqueeze import deps
from vidsqueeze.probe import MediaInfo

#: Set by the runner when --fast is given. Anything that shells out to ffmpeg
#: checks this and skips itself.
FAST_ONLY = bool(os.environ.get("VIDSQUEEZE_TESTS_FAST"))

_tools = None
_looked = False


def tools():
    """The ffmpeg toolchain, or None. Never downloads: a test run must not
    reach for the network, and a machine without ffmpeg should skip rather
    than fail."""
    global _tools, _looked
    if not _looked:
        _looked = True
        try:
            _tools = deps.find_tools(require_h265=False)
        except Exception:
            _tools = None
    return _tools


def needs_ffmpeg(test):
    """Decorator: skip when ffmpeg is missing or --fast was asked for."""
    if FAST_ONLY:
        return unittest.skip("--fast")(test)
    if tools() is None:
        return unittest.skip("ffmpeg is not available")(test)
    return test


def fake_image_info(width=800, height=600, has_alpha=False, path="sample.png"):
    """A MediaInfo describing a still, without touching the disk.

    Command building must be testable without an encoder present, which is what
    keeps the fast half of the suite fast.
    """
    return MediaInfo(
        path=Path(path),
        size_bytes=1024,
        duration=0.0,
        container="png_pipe",
        has_video=True,
        has_audio=False,
        video_codec="png",
        width=width,
        height=height,
        frame_count=1,
        has_alpha=has_alpha,
    )


def arg_after(command, flag):
    """The value following a flag in a command, or None if the flag is absent."""
    parts = [str(part) for part in command]
    for index, part in enumerate(parts):
        if part == flag and index + 1 < len(parts):
            return parts[index + 1]
    return None


def make_test_image(target: Path, size="640x480") -> Path:
    """Generate a colour test pattern. Saturated edges are where chroma
    subsampling does its visible damage, so this is the right source for
    measuring it."""
    kit = tools()
    subprocess.run(
        [str(kit.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", f"testsrc2=size={size}:duration=1:rate=1",
         "-frames:v", "1", "-update", "1", "-pix_fmt", "rgb24", str(target)],
        check=True,
    )
    return target


def psnr(reference: Path, candidate: Path) -> float:
    """Average PSNR of candidate against reference, in dB.

    Returns infinity when the two are identical, which is the only acceptable
    answer for anything claiming to be lossless.
    """
    kit = tools()
    result = subprocess.run(
        [str(kit.ffmpeg), "-hide_banner", "-i", str(candidate), "-i", str(reference),
         "-lavfi", "[0][1]psnr", "-f", "null", "-"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors="replace",
    )
    for line in reversed((result.stderr or "").splitlines()):
        if "average:" not in line:
            continue
        value = line.split("average:")[1].split()[0]
        if value.startswith("inf"):
            return float("inf")
        try:
            return float(value)
        except ValueError:
            continue
    raise AssertionError(f"could not read a PSNR score from ffmpeg:\n{result.stderr}")


def probe_pix_fmt(path: Path) -> str:
    kit = tools()
    result = subprocess.run(
        [str(kit.ffprobe), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=pix_fmt", "-of", "csv=p=0", str(path)],
        stdout=subprocess.PIPE, text=True, errors="replace",
    )
    return (result.stdout or "").strip()


def run_command(command) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(part) for part in command],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors="replace",
    )
