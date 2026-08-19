"""Detecting graphics-card encoders that genuinely work.

Listing an encoder is not the same as being able to use it. Plenty of machines
advertise, say, hevc_vaapi and then fail at runtime with "no usable encoding
entrypoint" because the hardware only decodes that codec. The only dependable
test is to encode a few frames and see what happens, so that is what we do, once
per machine, and cache the answer.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from .deps import Tools, _no_window
from .paths import CACHE_DIR, system_key

CACHE_FILE = CACHE_DIR / "hwaccel.json"
CACHE_MAX_AGE = 30 * 24 * 3600  # re-test monthly, in case drivers change

#: Candidate encoders per codec, in the order we would prefer them. NVIDIA
#: first because it is the fastest and most widely available, then Intel,
#: then AMD, then Apple, then the generic Linux interface.
CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "h264": [
        ("h264_nvenc", "NVIDIA"),
        ("h264_qsv", "Intel Quick Sync"),
        ("h264_videotoolbox", "Apple"),
        ("h264_amf", "AMD"),
        ("h264_vaapi", "VA-API"),
    ],
    "h265": [
        ("hevc_nvenc", "NVIDIA"),
        ("hevc_qsv", "Intel Quick Sync"),
        ("hevc_videotoolbox", "Apple"),
        ("hevc_amf", "AMD"),
        ("hevc_vaapi", "VA-API"),
    ],
    "av1": [
        ("av1_nvenc", "NVIDIA"),
        ("av1_qsv", "Intel Quick Sync"),
        ("av1_amf", "AMD"),
    ],
}


@dataclass
class HardwareEncoder:
    """A graphics-card encoder that has been proven to run on this machine."""

    codec: str        # our codec key: h264 / h265 / av1
    encoder: str      # the ffmpeg encoder name
    vendor: str       # a human-readable label
    working: bool


def _test_encode(tools: Tools, encoder: str) -> bool:
    """Encode a handful of synthetic frames and report whether it succeeded."""
    command = [
        str(tools.ffmpeg), "-hide_banner", "-nostdin", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=0.4",
        "-frames:v", "10",
    ]
    # VA-API cannot take ordinary frames; they have to be uploaded to the GPU.
    if encoder.endswith("_vaapi"):
        command[1:1] = ["-vaapi_device", "/dev/dri/renderD128"]
        command += ["-vf", "format=nv12,hwupload"]

    command += ["-c:v", encoder, "-f", "null", "-"]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=45,
            **_no_window(),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _available_encoder_names(tools: Tools) -> set[str]:
    try:
        result = subprocess.run(
            [str(tools.ffmpeg), "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=30,
            **_no_window(),
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return set(re.findall(r"^\s*[A-Z.]+\s+(\S+)", result.stdout, re.M))


def _load_cache(fingerprint: str) -> list[HardwareEncoder] | None:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("fingerprint") != fingerprint:
        return None
    if time.time() - data.get("tested_at", 0) > CACHE_MAX_AGE:
        return None
    return [HardwareEncoder(**entry) for entry in data.get("encoders", [])]


def _save_cache(fingerprint: str, encoders: list[HardwareEncoder]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fingerprint": fingerprint,
        "tested_at": time.time(),
        "encoders": [asdict(e) for e in encoders],
    }
    try:
        CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass  # A cache we cannot write just means we re-test next time.


def detect(tools: Tools, force: bool = False) -> list[HardwareEncoder]:
    """Return the graphics-card encoders that actually work here.

    The first call may take a few seconds. After that the answer is cached in
    HalveIt/.cache and reused.
    """
    fingerprint = f"{system_key()}|{tools.version}|{tools.source}"
    if not force:
        cached = _load_cache(fingerprint)
        if cached is not None:
            return [e for e in cached if e.working]

    present = _available_encoder_names(tools)
    results: list[HardwareEncoder] = []
    for codec, options in CANDIDATES.items():
        for encoder, vendor in options:
            if encoder not in present:
                continue
            works = _test_encode(tools, encoder)
            results.append(HardwareEncoder(codec=codec, encoder=encoder, vendor=vendor, working=works))
            if works:
                break  # We only need the best working option per codec.

    _save_cache(fingerprint, results)
    return [e for e in results if e.working]


def best_for(tools: Tools, codec: str) -> HardwareEncoder | None:
    """The preferred working hardware encoder for a codec, if there is one."""
    for entry in detect(tools):
        if entry.codec == codec:
            return entry
    return None
