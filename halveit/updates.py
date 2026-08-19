"""Checking whether newer versions exist.

Two separate questions: is there a newer HalveIt, and is there a newer
ffmpeg. Neither is checked unless the user asks, because a program that phones
home on startup is a program that phones home.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import deps
from .paths import CACHE_DIR, arch_key, system_key

RELEASES_API = "https://api.github.com/repos/pxspaces/halveit/releases/latest"
TAGS_API = "https://api.github.com/repos/pxspaces/halveit/tags"
PROJECT_URL = "https://github.com/pxspaces/halveit"

CACHE_FILE = CACHE_DIR / "updates.json"
CACHE_MAX_AGE = 6 * 3600  # a check is good for a few hours


def _fetch_json(url: str, timeout: int = 15):
    request = urllib.request.Request(url, headers={"User-Agent": deps.USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _version_tuple(text: str) -> tuple[int, ...]:
    """Turn a version string into something comparable.

    Only the leading numbers matter. Distribution builds append all sorts of
    things, so '6.1.1-3ubuntu5+esm10' has to compare as (6, 1, 1).
    """
    numbers = re.findall(r"\d+", (text or "").split("-")[0])
    return tuple(int(n) for n in numbers[:3]) or (0,)


def _newer(latest: str, current: str) -> bool:
    return _version_tuple(latest) > _version_tuple(current)


# --------------------------------------------------------------------------
# HalveIt itself
# --------------------------------------------------------------------------


#: How much of a release description to keep. Enough for a real list of changes,
#: short of letting a very long one push the window off the screen.
NOTES_LIMIT = 6000


def latest_app_version() -> tuple[str, str, str]:
    """The newest published version, where to get it, and what changed.

    Returns empty strings when there is nothing to report, which includes the
    perfectly normal case of the project not publishing releases yet. The notes
    are whatever the release description says, in Markdown, and may be empty even
    when there is a release: somebody has to have written them.
    """
    try:
        release = _fetch_json(RELEASES_API)
        tag = str(release.get("tag_name") or "").lstrip("v")
        if tag:
            notes = str(release.get("body") or "").strip()[:NOTES_LIMIT]
            return tag, str(release.get("html_url") or PROJECT_URL), notes
    except (urllib.error.HTTPError, urllib.error.URLError, ssl.SSLError, OSError, ValueError):
        pass

    # No releases, or no repository yet. Tags are the next best thing, though a
    # tag carries no description, so there is nothing to show but the number.
    try:
        tags = _fetch_json(TAGS_API)
        if isinstance(tags, list) and tags:
            newest = max((str(t.get("name") or "").lstrip("v") for t in tags), key=_version_tuple)
            if newest:
                return newest, PROJECT_URL, ""
    except (urllib.error.HTTPError, urllib.error.URLError, ssl.SSLError, OSError, ValueError):
        pass

    return "", "", ""


# --------------------------------------------------------------------------
# ffmpeg
# --------------------------------------------------------------------------


def latest_ffmpeg_version() -> str:
    """The newest ffmpeg the download sources are offering."""
    plat = system_key()

    if plat == "windows":
        try:
            release = _fetch_json(deps.BTBN_API)
            versions = []
            for asset in release.get("assets", []):
                match = re.match(r"^ffmpeg-n(\d+\.\d+)-latest-win", asset.get("name", ""))
                if match:
                    versions.append(match.group(1))
            if versions:
                return max(versions, key=_version_tuple)
        except (urllib.error.HTTPError, urllib.error.URLError, ssl.SSLError, OSError, ValueError):
            return ""
        return ""

    # The macOS and Linux build server redirects to a URL that carries the
    # version in its path, so a single request answers the question without
    # downloading anything.
    url = deps.MARTIN_RIEDL.format(os=plat, arch=arch_key(), tool="ffmpeg")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": deps.USER_AGENT, "Range": "bytes=0-1"})
        with urllib.request.urlopen(request, timeout=20) as response:
            final = response.geturl()
    except (urllib.error.HTTPError, urllib.error.URLError, ssl.SSLError, OSError):
        return ""

    match = re.search(r"/\d+_(\d+(?:\.\d+)*)/", final)
    return match.group(1) if match else ""


# --------------------------------------------------------------------------
# Putting it together
# --------------------------------------------------------------------------


def _load_cache() -> dict | None:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - data.get("checked_at", 0) > CACHE_MAX_AGE:
        return None
    return data


def _save_cache(payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def check(app_version: str, tools: deps.Tools | None, force: bool = False) -> dict:
    """Report on both HalveIt and ffmpeg."""
    if not force:
        cached = _load_cache()
        if cached is not None:
            return cached

    latest_app, app_url, notes = latest_app_version()
    latest_ffmpeg = latest_ffmpeg_version()
    current_ffmpeg = tools.version if tools else ""

    app = {
        "current": app_version,
        "latest": latest_app,
        "url": app_url or PROJECT_URL,
        "update_available": bool(latest_app) and _newer(latest_app, app_version),
        "checked": bool(latest_app),
        # What changed, as written in the release. Carried through so somebody can
        # see what they are being offered before they take it.
        "notes": notes,
    }

    ffmpeg = {
        "current": current_ffmpeg,
        "latest": latest_ffmpeg,
        "source": tools.source if tools else "",
        "update_available": bool(latest_ffmpeg) and bool(current_ffmpeg)
        and _newer(latest_ffmpeg, current_ffmpeg),
        "checked": bool(latest_ffmpeg),
        # Replacing a system ffmpeg means downloading our own copy alongside it,
        # which is worth saying plainly before anyone presses the button.
        "replaces_system": bool(tools and tools.source == "system"),
    }

    payload = {"checked_at": time.time(), "app": app, "ffmpeg": ffmpeg}
    _save_cache(payload)
    return payload


def summarise(report: dict) -> str:
    """One line describing the situation, for the terminal."""
    app, ffmpeg = report.get("app", {}), report.get("ffmpeg", {})
    parts = []
    if app.get("update_available"):
        parts.append(f"HalveIt {app['latest']} is available (you have {app['current']})")
    if ffmpeg.get("update_available"):
        parts.append(f"ffmpeg {ffmpeg['latest']} is available (you have {ffmpeg['current']})")
    if not parts:
        if not app.get("checked") and not ffmpeg.get("checked"):
            return "Could not reach the update servers."
        return "Everything is up to date."
    return ". ".join(parts) + "."
