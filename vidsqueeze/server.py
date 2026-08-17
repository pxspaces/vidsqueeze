"""The local web interface.

A small HTTP server on the loopback address, which the user's own browser talks
to. It is not reachable from the network. Because the interface can read folders
and, when asked, delete originals, every request must carry a token generated
fresh for each run, and requests claiming a non-loopback Host are refused. That
prevents another program on the machine, or a web page in another tab, from
driving it.
"""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
import shutil
import socket
import string
import subprocess
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, fields
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import deps, history, hwaccel, images, media, presets, raw, selfupdate, updates, watch
from .encode import (
    CODEC_LABELS,
    CONTAINER_RULES,
    QUALITY_LABELS,
    SCALE_PRESETS,
    SPEEDS,
    JobSpec,
    free_space,
)
from .jobs import Queue, sensible_concurrency
from .paths import (
    APP_DIR,
    OUTPUT_DIR,
    ensure_dirs,
    human_size,
    load_settings,
    open_in_file_manager,
    save_settings,
    system_key,
)
from .probe import (
    MEDIA_EXTENSIONS,
    ProbeError,
    kind_for_extension,
    matches_kinds,
    probe,
    scan_folder,
)

from . import __version__ as VERSION

WEB_DIR = Path(__file__).resolve().parent / "web"

#: Preferences the interface is allowed to store. Anything else is ignored, so
#: a stray value cannot end up steering the encoder.
ALLOWED_SETTINGS = {
    "preset", "output_dir", "concurrency", "hardware", "browser",
    "replace_originals", "recursive", "theme", "sample_seconds",
    "media_mode", "asked_media_mode",
}


class Session:
    """Everything the server needs to remember between requests."""

    def __init__(self) -> None:
        self.token = secrets.token_urlsafe(24)
        self.tools: deps.Tools | None = deps.find_tools()
        self.queue: Queue | None = None
        self.setup_state = {"running": False, "message": "", "fraction": -1.0, "error": "", "done": False}
        self.sample_state: dict = {"running": False, "source": "", "results": [], "error": "", "done": False}
        self.watcher: watch.Watcher | None = None
        self.update_state = {"running": False, "message": "", "fraction": -1.0,
                             "error": "", "done": False, "result": ""}
        self.lock = threading.Lock()
        self.should_quit = threading.Event()

    # -- dependency setup --------------------------------------------------

    def start_setup(self) -> None:
        if self.setup_state["running"] or self.tools is not None:
            return
        self.setup_state.update({"running": True, "message": "Starting", "fraction": -1.0, "error": "", "done": False})

        def progress(message: str, fraction: float) -> None:
            self.setup_state["message"] = message
            self.setup_state["fraction"] = fraction

        def work() -> None:
            try:
                self.tools = deps.install_ffmpeg(progress)
                self.setup_state.update({"message": "Ready", "fraction": 1.0, "done": True})
            except deps.DependencyError as exc:
                self.setup_state["error"] = str(exc)
            except Exception as exc:  # noqa: BLE001 - surfaced in the interface
                self.setup_state["error"] = f"Unexpected problem: {exc}"
            finally:
                self.setup_state["running"] = False

        threading.Thread(target=work, daemon=True).start()


SESSION = Session()


# --------------------------------------------------------------------------
# File browsing
# --------------------------------------------------------------------------


def _windows_drives() -> list[dict]:
    drives = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        if root.exists():
            drives.append({"name": f"{letter}:", "path": str(root), "kind": "drive"})
    return drives


def places() -> list[dict]:
    """Shortcuts to the folders people actually keep video in."""
    home = Path.home()
    entries: list[dict] = [{"name": "Home", "path": str(home), "kind": "home"}]

    for label in ("Desktop", "Downloads", "Videos", "Movies", "Documents", "Pictures"):
        candidate = home / label
        if candidate.is_dir():
            entries.append({"name": label, "path": str(candidate), "kind": "folder"})

    entries.append({"name": "VidSqueeze output", "path": str(OUTPUT_DIR), "kind": "output"})

    if system_key() == "windows":
        entries += _windows_drives()
    else:
        # Removable media: memory cards, USB sticks, external drives.
        roots = [Path("/Volumes")] if system_key() == "macos" else [
            Path("/media") / os.environ.get("USER", ""),
            Path("/media"),
            Path("/mnt"),
            Path("/run/media") / os.environ.get("USER", ""),
        ]
        seen = set()
        for root in roots:
            if not root.is_dir():
                continue
            try:
                for child in sorted(root.iterdir()):
                    if child.is_dir() and not child.name.startswith(".") and child.name not in seen:
                        seen.add(child.name)
                        entries.append({"name": child.name, "path": str(child), "kind": "drive"})
            except OSError:
                continue
        entries.append({"name": "Whole computer", "path": "/", "kind": "root"})

    return entries


def browse(raw_path: str, kinds: set[str] | None = None) -> dict:
    """List the folders and media files inside a directory.

    When a kind filter is given, only files of those kinds are listed. Someone
    who has said they are working with photographs should not have to pick their
    way past a folder of video files.
    """
    target = Path(raw_path).expanduser() if raw_path else Path.home()
    try:
        target = target.resolve()
    except OSError:
        return {"error": "That folder cannot be opened.", "path": str(target)}

    if not target.is_dir():
        return {"error": "That is not a folder.", "path": str(target)}

    folders: list[dict] = []
    files: list[dict] = []
    hidden = 0          # files of other kinds, filtered out but worth mentioning
    try:
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith("."):
                continue
            try:
                if child.is_dir():
                    folders.append({"name": child.name, "path": str(child)})
                elif child.suffix.lower() in MEDIA_EXTENSIONS:
                    if not matches_kinds(child, kinds):
                        hidden += 1
                        continue
                    size = child.stat().st_size
                    files.append(
                        {
                            "name": child.name,
                            "path": str(child),
                            "bytes": size,
                            "size": human_size(size),
                            "kind": kind_for_extension(child),
                        }
                    )
            except OSError:
                continue  # unreadable entries are skipped, not fatal
    except PermissionError:
        return {"error": "You do not have permission to open that folder.", "path": str(target)}
    except OSError as exc:
        return {"error": f"That folder could not be read: {exc}", "path": str(target)}

    parent = str(target.parent) if target.parent != target else ""
    return {
        "path": str(target), "parent": parent,
        "folders": folders, "files": files, "hidden": hidden,
    }


def expand_selection(
    raw_paths: list[str],
    recursive: bool = True,
    kinds: list[str] | set[str] | None = None,
) -> tuple[list[Path], list[str]]:
    """Turn a mixed selection of files and folders into a flat list of files.

    A kind filter applies to folders and to individually chosen files alike, so
    that choosing a whole folder in photograph mode brings in the photographs
    and leaves the videos where they are.
    """
    wanted = set(kinds) if kinds else None
    collected: list[Path] = []
    problems: list[str] = []
    for raw in raw_paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            found = scan_folder(path, recursive=recursive, kinds=wanted)
            if not found:
                what = " or ".join(sorted(wanted)) if wanted else "video or audio"
                problems.append(f"No {what} files found in {path.name}.")
            collected += found
        elif path.is_file():
            if not matches_kinds(path, wanted):
                continue
            collected.append(path)
        else:
            problems.append(f"Not found: {raw}")

    # Never queue our own output as an input.
    try:
        output_root = OUTPUT_DIR.resolve()
        collected = [p for p in collected if output_root not in p.resolve().parents]
    except OSError:
        pass

    unique: list[Path] = []
    seen: set[str] = set()
    for path in collected:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique, problems


# --------------------------------------------------------------------------
# Request handling
# --------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "VidSqueeze"
    protocol_version = "HTTP/1.1"

    # -- plumbing ---------------------------------------------------------

    def log_message(self, *args) -> None:  # noqa: D102 - silence the default logging
        pass

    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        # The interface only ever talks to itself, so nothing may be embedded
        # or loaded from elsewhere.
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'",
        )
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, payload: dict, status: int = 200) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, message: str, status: int = 400) -> None:
        self._json({"error": message}, status)

    def _host_is_local(self) -> bool:
        """Refuse requests that reached us under a name we did not choose."""
        host = (self.headers.get("Host") or "").split(":")[0].strip("[]")
        return host in ("127.0.0.1", "localhost", "::1", "")

    def _authorised(self, query: dict) -> bool:
        supplied = self.headers.get("X-VidSqueeze-Token") or (query.get("token") or [""])[0]
        return secrets.compare_digest(supplied, SESSION.token)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if length <= 0 or length > 8 * 1024 * 1024:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, OSError):
            return {}

    # -- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - required name
        parsed = urlparse(self.path)
        route = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if not self._host_is_local():
            self._error("Refused: VidSqueeze only accepts local connections.", 403)
            return

        if route in ("/", "/index.html"):
            if not self._authorised(query):
                self._send(
                    HTTPStatus.FORBIDDEN,
                    b"<h1>VidSqueeze</h1><p>This link is missing its access token. "
                    b"Please use the address printed in the VidSqueeze window.</p>",
                    "text/html; charset=utf-8",
                )
                return
            self._serve_static("index.html")
            return

        if route.startswith("/static/"):
            self._serve_static(route[len("/static/"):])
            return

        if not route.startswith("/api/"):
            self._error("Not found", 404)
            return

        if not self._authorised(query):
            self._error("Not authorised", 403)
            return

        if route == "/api/state":
            self._json(self._state())
        elif route == "/api/browse":
            raw_kinds = (query.get("kinds") or [""])[0]
            wanted = {k for k in raw_kinds.split(",") if k} or None
            self._json(browse((query.get("path") or [""])[0], wanted))
        elif route == "/api/places":
            self._json({"places": places()})
        elif route == "/api/queue":
            self._json(SESSION.queue.snapshot() if SESSION.queue else {"items": [], "totals": {}})
        elif route == "/api/setup":
            self._json(dict(SESSION.setup_state, installed=SESSION.tools is not None))
        elif route == "/api/history":
            self._json(history.summary())
        elif route == "/api/frame":
            self._serve_frame(query)
        elif route == "/api/media":
            self._serve_media((query.get("path") or [""])[0])
        elif route == "/api/sample":
            self._json(SESSION.sample_state)
        elif route == "/api/watch":
            self._json(self._watch_state())
        elif route == "/api/updates":
            force = (query.get("force") or ["0"])[0] in ("1", "true")
            report = updates.check(VERSION, SESSION.tools, force=force)
            report["self"] = selfupdate.describe()
            self._json(report)
        elif route == "/api/updates/self":
            self._json(SESSION.update_state)
        else:
            self._error("Not found", 404)

    def do_POST(self) -> None:  # noqa: N802 - required name
        parsed = urlparse(self.path)
        route = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if not self._host_is_local():
            self._error("Refused: VidSqueeze only accepts local connections.", 403)
            return
        if not self._authorised(query):
            self._error("Not authorised", 403)
            return

        body = self._body()

        if route == "/api/setup/start":
            SESSION.start_setup()
            self._json({"started": True})
        elif route == "/api/inspect":
            self._inspect(body)
        elif route == "/api/describe":
            self._describe(body)
        elif route == "/api/queue/start":
            self._start_queue(body)
        elif route == "/api/queue/cancel":
            if SESSION.queue:
                SESSION.queue.cancel()
            self._json({"cancelled": True})
        elif route == "/api/queue/remove":
            removed = bool(SESSION.queue and SESSION.queue.remove(int(body.get("id", -1))))
            self._json({"removed": removed})
        elif route == "/api/queue/clear":
            if SESSION.queue:
                SESSION.queue.clear_finished()
            self._json({"cleared": True})
        elif route == "/api/queue/cancel-item":
            stopped = bool(SESSION.queue and SESSION.queue.cancel_item(int(body.get("id", -1))))
            self._json({"stopped": stopped})
        elif route == "/api/sample/start":
            self._start_sample(body)
        elif route == "/api/settings":
            save_settings(**{k: v for k, v in (body or {}).items() if k in ALLOWED_SETTINGS})
            self._json({"saved": True, "settings": load_settings()})
        elif route == "/api/watch/start":
            self._watch_start(body)
        elif route == "/api/watch/stop":
            if SESSION.watcher:
                SESSION.watcher.stop()
            self._json(self._watch_state())
        elif route == "/api/upgrade":
            self._upgrade_tools()
        elif route == "/api/updates/self":
            self._update_self()
        elif route == "/api/history/clear":
            history.clear()
            self._json({"cleared": True})
        elif route == "/api/open":
            target = Path(body.get("path") or "")
            if target.exists():
                open_in_file_manager(target)  # opens the file in its normal program
                self._json({"opened": True})
            else:
                self._error("That file is no longer there.", 404)
        elif route == "/api/reveal":
            target = Path(body.get("path") or OUTPUT_DIR)
            open_in_file_manager(target if target.is_dir() else target.parent)
            self._json({"opened": True})
        elif route == "/api/quit":
            self._json({"quitting": True})
            SESSION.should_quit.set()
        else:
            self._error("Not found", 404)

    # -- handlers ---------------------------------------------------------

    def _serve_static(self, name: str) -> None:
        candidate = (WEB_DIR / name).resolve()
        try:
            candidate.relative_to(WEB_DIR.resolve())
        except ValueError:
            self._error("Not found", 404)
            return
        if not candidate.is_file():
            self._error("Not found", 404)
            return

        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript",):
            content_type += "; charset=utf-8"

        data = candidate.read_bytes()
        if candidate.name == "index.html":
            data = data.replace(b"__VIDSQUEEZE_TOKEN__", SESSION.token.encode("ascii"))
        self._send(200, data, content_type)

    def _serve_frame(self, query: dict) -> None:
        """One frame from a video, as a JPEG, for the comparison view."""
        if SESSION.tools is None:
            self._error("ffmpeg is not set up yet.", 503)
            return
        path = Path((query.get("path") or [""])[0])
        try:
            when = float((query.get("t") or ["0"])[0])
            width = max(160, min(1920, int((query.get("w") or ["900"])[0])))
        except ValueError:
            self._error("Bad frame request.")
            return

        data = media.extract_frame(SESSION.tools, path, when, width)
        if data is None:
            self._error("That frame could not be read.", 404)
            return
        # Frames are immutable for a given file and time, so let the browser
        # keep them while the user drags the slider back and forth.
        self._send(200, data, "image/jpeg", {"Cache-Control": "private, max-age=600"})

    def _serve_media(self, raw_path: str) -> None:
        """Stream a video file, honouring range requests so seeking works."""
        path = Path(raw_path)
        if not path.is_file():
            self._error("That file is no longer there.", 404)
            return

        try:
            size = path.stat().st_size
        except OSError:
            self._error("That file cannot be read.", 404)
            return

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        start, end = 0, size - 1
        status = HTTPStatus.OK

        raw_range = self.headers.get("Range")
        if raw_range and raw_range.startswith("bytes="):
            spec = raw_range[6:].split(",")[0].strip()
            first, _, last = spec.partition("-")
            try:
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                elif last:
                    start = max(0, size - int(last))
            except ValueError:
                start, end = 0, size - 1
            start = max(0, min(start, size - 1))
            end = max(start, min(end, size - 1))
            status = HTTPStatus.PARTIAL_CONTENT

        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "private, max-age=60")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

        try:
            with open(path, "rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = handle.read(min(262144, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The browser moved on, which is normal when seeking.
        except OSError:
            pass

    def _start_sample(self, body: dict) -> None:
        """Encode a few seconds at several settings so they can be compared."""
        if SESSION.tools is None:
            self._error("ffmpeg is not set up yet.")
            return
        if SESSION.sample_state.get("running"):
            self._error("A sample is already being made.")
            return

        source = Path(body.get("path") or "")
        if not source.is_file():
            self._error("Choose a file to test first.")
            return

        try:
            base = _spec_from_request(body.get("spec") or {})
        except (TypeError, ValueError) as exc:
            self._error(f"Those settings are not valid: {exc}")
            return

        seconds = float(body.get("seconds") or 8)
        candidates = body.get("candidates") or []
        SESSION.sample_state = {
            "running": True, "source": str(source), "results": [], "error": "", "done": False,
        }

        def work() -> None:
            try:
                jobs = []
                if candidates:
                    for entry in candidates:
                        preset = presets.get(entry.get("preset", ""))
                        if preset is None:
                            continue
                        jobs.append((preset.key, preset.name, preset.description, preset.spec()))
                else:
                    jobs.append(("current", "Your settings", "", base))

                for key, label, description, spec in jobs:
                    if not SESSION.sample_state.get("running"):
                        return
                    result = media.encode_sample(
                        SESSION.tools, source, spec, key, label, description, seconds
                    )
                    SESSION.sample_state["results"].append(result.to_dict())
                SESSION.sample_state["done"] = True
            except Exception as exc:  # noqa: BLE001 - surfaced in the interface
                SESSION.sample_state["error"] = f"The sample failed: {exc}"
            finally:
                SESSION.sample_state["running"] = False

        threading.Thread(target=work, daemon=True).start()
        self._json({"started": True})

    def _state(self) -> dict:
        preset_list, warnings = presets.all_presets()
        tools = SESSION.tools
        hardware = []
        if tools is not None:
            hardware = [asdict(h) for h in hwaccel.detect(tools)]

        return {
            "app_dir": str(APP_DIR),
            "output_dir": str(OUTPUT_DIR),
            "free_space": human_size(free_space(APP_DIR)),
            "platform": system_key(),
            "ffmpeg": (
                {"version": tools.version, "source": tools.source, "encoders": sorted(tools.encoders)}
                if tools
                else None
            ),
            "download_size": deps.download_size_estimate(),
            "install_hint": deps.system_install_hint(),
            "hardware": hardware,
            "presets": [p.to_dict() for p in preset_list],
            "default_preset": presets.DEFAULT_PRESET,
            "warnings": warnings,
            "settings": load_settings(),
            "raw": raw.describe_support(),
            "app_version": VERSION,
            "image_formats": {
                name: {**spec, "available": name in images.available_formats(tools)}
                for name, spec in images.IMAGE_FORMATS.items()
            } if tools else {},
            "max_concurrency": sensible_concurrency(99),
            "history": history.summary(limit=12),
            "options": {
                "codecs": CODEC_LABELS,
                "containers": {k: sorted(v["video"]) for k, v in CONTAINER_RULES.items()},
                "container_audio": {k: sorted(v["audio"]) for k, v in CONTAINER_RULES.items()},
                "qualities": QUALITY_LABELS,
                "speeds": SPEEDS,
                "scales": SCALE_PRESETS,
            },
            "defaults": asdict(JobSpec()),
        }

    #: How many files get a full inspection. Reading a file's dimensions and
    #: length means running ffprobe on it, which is far too slow to do to a
    #: folder of five hundred photographs before showing anything. Beyond this
    #: point files are still listed, from their name and size alone.
    PROBE_LIMIT = 60

    def _basic_entry(self, path: Path) -> dict:
        """Describe a file without opening it. Cheap enough to do to thousands."""
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        kind = kind_for_extension(path) or "video"
        return {
            "path": str(path), "name": path.name,
            "summary": f"{path.suffix.lstrip('.').upper()}, {human_size(size)}",
            "bytes": size, "size": human_size(size), "duration": 0,
            "is_hdr": False, "has_video": kind != "audio", "width": 0, "height": 0,
            "resolution": "", "fps": 0, "codec": path.suffix.lstrip(".").lower(),
            "playable": False, "kind": kind, "has_alpha": False,
            "is_raw": False, "raw_ready": True, "probed": False,
        }

    def _raw_entry(self, path: Path) -> dict:
        """A camera RAW file, described without opening it."""
        entry = self._basic_entry(path)
        support = raw.describe_support()
        entry.update({
            "summary": f"{raw.camera_of(path)} RAW, {entry['size']}"
                       + (f", will use {support['decoder']}" if support["available"]
                          else ", no RAW decoder installed"),
            "resolution": "RAW", "codec": "raw", "kind": "image",
            "is_raw": True, "raw_ready": support["available"],
        })
        return entry

    def _inspect(self, body: dict) -> None:
        """Report what is in a selection, so the interface can preview it.

        Every file chosen is returned. Only the first batch is opened and
        measured; the rest are listed from their name and size, which is all the
        file list actually needs to show them.
        """
        if SESSION.tools is None:
            self._error("ffmpeg is not set up yet.")
            return

        paths, problems = expand_selection(
            body.get("paths") or [],
            bool(body.get("recursive", True)),
            kinds=body.get("kinds") or None,
        )

        unreadable: list[str] = []

        # Decide up front which files get opened. Everything else is listed from
        # its name, so the count is always the real one.
        to_probe = [p for p in paths if not raw.is_raw(p)][: self.PROBE_LIMIT]
        probe_set = {str(p) for p in to_probe}

        def measure(path: Path) -> tuple[str, dict | None, str]:
            try:
                info = probe(SESSION.tools, path)
            except ProbeError as exc:
                return str(path), None, str(exc)
            return str(path), {
                "path": str(path),
                "name": path.name,
                "summary": info.summary(),
                "bytes": info.size_bytes,
                "size": human_size(info.size_bytes),
                "duration": info.duration,
                "is_hdr": info.is_hdr,
                "has_video": info.has_video,
                "width": info.display_width,
                "height": info.display_height,
                "resolution": info.resolution_label,
                "fps": round(info.fps, 3),
                "codec": info.video_codec or info.audio_codec,
                "playable": media.can_browser_play(info),
                "kind": info.kind,
                "has_alpha": info.has_alpha,
                "is_raw": False,
                "raw_ready": True,
                "probed": True,
            }, ""

        # Each measurement is a separate short-lived process, so they overlap
        # happily. Done one at a time, sixty files took over five seconds before
        # the list appeared.
        measured: dict[str, dict] = {}
        if to_probe:
            workers = max(4, min(12, (os.cpu_count() or 4) * 2))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for key, entry, failure in pool.map(measure, to_probe):
                    if entry is not None:
                        measured[key] = entry
                    else:
                        problems.append(failure)
                        if deps.upgrade_would_help(key, SESSION.tools):
                            unreadable.append(key)

        details: list[dict] = []
        total_bytes = 0
        for path in paths:
            key = str(path)
            if raw.is_raw(path):
                entry = self._raw_entry(path)
            elif key in measured:
                entry = measured[key]
                # ffprobe will happily accept rubbish carrying a picture
                # extension and report it as an image with no dimensions. That
                # only fails later, during conversion, so it is called out now.
                if entry["kind"] == "image" and not entry["width"]:
                    entry = dict(entry, unreadable=True,
                                 summary=f"Not a readable image, {entry['size']}")
            elif key in probe_set:
                # It was opened and refused to be read. It still belongs in the
                # list, marked, rather than vanishing from the count.
                entry = self._basic_entry(path)
                entry["summary"] = f"Could not be read, {entry['size']}"
                entry["unreadable"] = True
            else:
                entry = self._basic_entry(path)

            details.append(entry)
            total_bytes += entry["bytes"]

        probed = len(measured)

        self._json(
            {
                "count": len(paths),
                "paths": [str(p) for p in paths],
                "details": details,
                "probed": probed,
                "total_bytes": total_bytes,
                "total_size": human_size(total_bytes),
                "problems": problems[:12],
                "kinds": sorted({d["kind"] for d in details}),
                "needs_raw_decoder": any(d.get("is_raw") and not d.get("raw_ready") for d in details),
                "raw_install_hint": raw.install_hint(),
                "unreadable": unreadable,
                "upgrade_offer": bool(unreadable),
            }
        )

    def _watch_state(self) -> dict:
        """The watcher's status, plus any files it has found since last asked."""
        if SESSION.watcher is None:
            return {"watching": False, "folder": "", "found": []}
        state = SESSION.watcher.to_dict()
        state["found"] = SESSION.watcher.take_found()
        return state

    def _watch_start(self, body: dict) -> None:
        folder, problem = watch.valid_folder(body.get("folder") or "")
        if folder is None:
            self._error(problem)
            return
        if SESSION.watcher is not None:
            SESSION.watcher.stop()
        SESSION.watcher = watch.Watcher(folder=folder, recursive=bool(body.get("recursive", True)))
        SESSION.watcher.start(include_existing=bool(body.get("include_existing")))
        self._json(SESSION.watcher.to_dict())

    def _update_self(self) -> None:
        """Replace the program's own files with the newest published version."""
        if SESSION.update_state.get("running"):
            self._error("An update is already in progress.")
            return
        SESSION.update_state.update(
            {"running": True, "message": "Starting", "fraction": -1.0,
             "error": "", "done": False, "result": ""}
        )

        def progress(message: str, fraction: float) -> None:
            SESSION.update_state["message"] = message
            SESSION.update_state["fraction"] = fraction

        def work() -> None:
            try:
                SESSION.update_state["result"] = selfupdate.perform(progress)
                SESSION.update_state["done"] = True
                SESSION.update_state["message"] = SESSION.update_state["result"]
                SESSION.update_state["fraction"] = 1.0
            except selfupdate.UpdateError as exc:
                SESSION.update_state["error"] = str(exc)
            except Exception as exc:  # noqa: BLE001 - surfaced in the interface
                SESSION.update_state["error"] = f"Unexpected problem: {exc}"
            finally:
                SESSION.update_state["running"] = False

        threading.Thread(target=work, daemon=True).start()
        self._json({"started": True})

    def _upgrade_tools(self) -> None:
        """Fetch a current ffmpeg when the installed one cannot read something."""
        if SESSION.setup_state.get("running"):
            self._error("A download is already in progress.")
            return
        SESSION.setup_state.update(
            {"running": True, "message": "Starting", "fraction": -1.0, "error": "", "done": False}
        )

        def progress(message: str, fraction: float) -> None:
            SESSION.setup_state["message"] = message
            SESSION.setup_state["fraction"] = fraction

        def work() -> None:
            try:
                SESSION.tools = deps.force_download(progress)
                SESSION.setup_state.update({"message": "Ready", "fraction": 1.0, "done": True})
            except deps.DependencyError as exc:
                SESSION.setup_state["error"] = str(exc)
            except Exception as exc:  # noqa: BLE001 - surfaced in the interface
                SESSION.setup_state["error"] = f"Unexpected problem: {exc}"
            finally:
                SESSION.setup_state["running"] = False

        threading.Thread(target=work, daemon=True).start()
        self._json({"started": True})

    def _describe(self, body: dict) -> None:
        """Describe exact files, including ones inside the output folder.

        The selection helper deliberately ignores anything we produced, so that
        results never get queued as inputs. The comparison view needs the
        opposite, so it asks here instead.
        """
        if SESSION.tools is None:
            self._error("ffmpeg is not set up yet.")
            return

        described = []
        for raw in (body.get("paths") or [])[:8]:
            path = Path(raw)
            if not path.is_file():
                described.append({"path": str(path), "error": "This file is no longer there."})
                continue
            try:
                info = probe(SESSION.tools, path)
            except ProbeError as exc:
                described.append({"path": str(path), "error": str(exc)})
                continue
            described.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "summary": info.summary(),
                    "bytes": info.size_bytes,
                    "size": human_size(info.size_bytes),
                    "duration": info.duration,
                    "width": info.display_width,
                    "height": info.display_height,
                    "resolution": info.resolution_label,
                    "fps": round(info.fps, 3),
                    "codec": info.video_codec,
                    "audio_codec": info.audio_codec,
                    "bitrate": info.overall_bitrate,
                    "has_video": info.has_video,
                    "is_hdr": info.is_hdr,
                    "playable": media.can_browser_play(info),
                    "kind": info.kind,
                    "has_alpha": info.has_alpha,
                }
            )
        self._json({"files": described})

    def _start_queue(self, body: dict) -> None:
        if SESSION.tools is None:
            self._error("ffmpeg is not set up yet.")
            return
        if SESSION.queue and SESSION.queue.running:
            self._error("A batch is already running.")
            return

        paths, problems = expand_selection(
            body.get("paths") or [],
            bool(body.get("recursive", True)),
            kinds=body.get("kinds") or None,
        )
        if not paths:
            self._error("No video or audio files were selected." + (" " + " ".join(problems) if problems else ""))
            return

        try:
            spec = _spec_from_request(body.get("spec") or {})
        except (TypeError, ValueError) as exc:
            self._error(f"Those settings are not valid: {exc}")
            return

        output_dir = Path(body.get("output_dir") or OUTPUT_DIR).expanduser()
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._error(f"That output folder cannot be used: {exc}")
            return

        SESSION.queue = Queue(
            tools=SESSION.tools,
            spec=spec,
            output_dir=output_dir,
            replace_originals=bool(body.get("replace_originals")),
            concurrency=int(body.get("concurrency") or 1),
            preset_key=str(body.get("preset") or ""),
        )
        SESSION.queue.add(paths)
        SESSION.queue.start()
        self._json({"started": True, "count": len(paths), "problems": problems})


#: Values that mean "off" when a browser sends a checkbox or a select as text.
_FALSE_WORDS = {"", "0", "false", "no", "off", "none", "null"}


def _coerce(value, annotation: str, fallback):
    """Turn one value from the interface into the type the field declares.

    This reads the type off the dataclass rather than a list of field names
    kept by hand. That list once omitted the image fields, so a chosen image
    size arrived as the text "2560" and every later comparison against it threw
    a type error. Deriving it means a new field cannot be forgotten.
    """
    text = annotation.replace(" ", "")
    optional = "None" in text
    base = text.split("|")[0]

    if value is None:
        return None if optional else fallback
    if isinstance(value, str) and value.strip() == "":
        return None if optional else fallback

    try:
        if base == "bool":
            if isinstance(value, str):
                return value.strip().lower() not in _FALSE_WORDS
            return bool(value)
        if base == "int":
            # float() first, so "1080.0" and 1080.0 are both accepted.
            return int(float(value))
        if base == "float":
            return float(value)
        if base == "str":
            return str(value)
        if base.startswith("list"):
            return [str(v) for v in value] if isinstance(value, (list, tuple)) else []
        if base.startswith("tuple"):
            return tuple(int(v) for v in value) if value else None
    except (TypeError, ValueError):
        # Anything unusable falls back to the default rather than travelling
        # onwards as the wrong type and failing somewhere less obvious.
        return None if optional else fallback
    return value


#: Numeric fields that have a meaningful range. Anything outside it is clamped
#: rather than refused, because a slider that has been dragged past the end is
#: not worth an error message.
_LIMITS = {
    "image_quality": (1, 100),
    "audio_bitrate": (8, 512),
    "crf": (0, 63),
    "scale": (16, 16384),
    "image_max_dimension": (16, 65536),
    "video_bitrate": (16, 500000),
    "target_size_mb": (0.05, 1000000.0),
}


#: Fields the program works out for itself. The interface has no business
#: setting them, and letting it would mean a stray value in a request could
#: quietly wreck the colour of every picture in a batch.
_INTERNAL_FIELDS = frozenset({"image_saturation"})


def _spec_from_request(body: dict) -> JobSpec:
    """Build a JobSpec from the interface, ignoring anything unexpected.

    The argument is deliberately not called `raw`: that is the name of the
    camera RAW module, imported at the top of this file, and shadowing it here
    made `raw.LOOKS` a puzzling AttributeError.
    """
    spec = JobSpec()
    defaults = JobSpec()
    annotations = {f.name: str(f.type) for f in fields(JobSpec)}

    for key, value in (body or {}).items():
        if key not in annotations or key in _INTERNAL_FIELDS:
            continue
        coerced = _coerce(value, annotations[key], getattr(defaults, key))
        if coerced is not None and key in _LIMITS:
            low, high = _LIMITS[key]
            coerced = max(low, min(high, coerced))
        setattr(spec, key, coerced)

    # Choices that must be one of a known set. A stray value would otherwise
    # only be noticed deep inside the encoder.
    if spec.speed not in SPEEDS:
        spec.speed = defaults.speed
    if spec.quality not in QUALITY_LABELS:
        spec.quality = defaults.quality
    if spec.quality_mode not in ("quality", "size", "bitrate"):
        spec.quality_mode = defaults.quality_mode
    if spec.image_format not in images.IMAGE_FORMATS:
        spec.image_format = defaults.image_format
    if spec.raw_look not in raw.LOOKS:
        spec.raw_look = defaults.raw_look

    return spec


# --------------------------------------------------------------------------
# Starting up
# --------------------------------------------------------------------------


def _free_port(preferred: int = 8722) -> int:
    """Use a predictable port when it is free, otherwise let the system pick."""
    for port in (preferred, preferred + 1, preferred + 2):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
            try:
                probe_socket.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        return probe_socket.getsockname()[1]


def open_browser_at(url: str, preferred: str | None = None) -> bool:
    """Open the interface in the computer's own default browser.

    Python's webbrowser module keeps its own idea of the default, which often
    disagrees with the system's: on a machine whose default is Chromium it will
    happily pick Chrome. So the operating system's own opener is tried first,
    since that is by definition what the user chose. A browser named explicitly
    still wins over both.
    """
    if preferred:
        try:
            return webbrowser.get(preferred).open(url)
        except webbrowser.Error:
            pass
        program = shutil.which(preferred) or preferred
        if Path(program).exists():
            try:
                subprocess.Popen([program, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError:
                pass
        print(f"  Could not open '{preferred}', falling back to the default browser.")

    system = system_key()
    try:
        if system == "windows":
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        opener = "open" if system == "macos" else "xdg-open"
        if shutil.which(opener):
            subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except (OSError, AttributeError):
        pass

    try:
        return webbrowser.open(url)
    except Exception:  # noqa: BLE001 - a browser that will not open is not fatal
        return False


def serve(open_browser: bool = True, port: int | None = None, browser: str | None = None) -> None:
    """Run the interface until the user closes it."""
    ensure_dirs()
    presets.write_example_file()

    # A browser named on the command line is remembered for next time.
    settings = load_settings()
    if browser:
        save_settings(browser=browser)
    preferred = browser or settings.get("browser")

    chosen = port or _free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", chosen), Handler)
    httpd.daemon_threads = True

    url = f"http://127.0.0.1:{chosen}/?token={SESSION.token}"

    print()
    print("  VidSqueeze is running.")
    print()
    print(f"  Open this address in your browser if it did not open by itself:")
    print(f"  {url}")
    print()
    print("  Leave this window open while you work. Close it, or press Ctrl+C, to quit.")
    print()

    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.3}, daemon=True)
    thread.start()

    if open_browser:
        open_browser_at(url, preferred)

    try:
        while not SESSION.should_quit.is_set():
            SESSION.should_quit.wait(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        if SESSION.queue and SESSION.queue.running:
            SESSION.queue.cancel()
        httpd.shutdown()
        print("  VidSqueeze has stopped.")
