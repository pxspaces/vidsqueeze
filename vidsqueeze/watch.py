"""Watching a folder for new files.

Cameras, phones and download folders fill up on their own. A watcher notices
new media appearing and adds it to the queue, but never starts work by itself:
converting somebody's files without being asked is not a decision a program
should make.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .probe import looks_like_media, scan_folder

#: How long a file must stop changing size before we believe it is complete.
#: Copying a large video off a card takes time, and converting a half-written
#: file wastes effort and produces a broken result.
SETTLE_SECONDS = 4.0
POLL_SECONDS = 3.0


@dataclass
class Watcher:
    """Watches one folder and reports files it has not seen before."""

    folder: Path
    recursive: bool = True
    started_at: float = field(default_factory=time.time)

    _known: set[str] = field(default_factory=set, repr=False)
    _pending: dict[str, tuple[int, float]] = field(default_factory=dict, repr=False)
    _found: list[str] = field(default_factory=list, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    error: str = ""

    def start(self, include_existing: bool = False) -> None:
        """Begin watching. Files already present are ignored unless asked for."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        if not include_existing:
            self._known = {str(p) for p in scan_folder(self.folder, self.recursive)}
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def take_found(self) -> list[str]:
        """Return newly settled files and forget them, so each is reported once."""
        with self._lock:
            found, self._found = self._found, []
        return found

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._sweep()
            except OSError as exc:
                self.error = f"The watched folder could not be read: {exc}"
            self._stop.wait(POLL_SECONDS)

    def _sweep(self) -> None:
        if not self.folder.is_dir():
            self.error = "The watched folder no longer exists."
            self.stop()
            return
        self.error = ""

        now = time.time()
        for path in scan_folder(self.folder, self.recursive):
            key = str(path)
            if key in self._known:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue

            previous = self._pending.get(key)
            if previous is None or previous[0] != size:
                # Still growing, or seen for the first time. Start the clock.
                self._pending[key] = (size, now)
                continue

            if now - previous[1] >= SETTLE_SECONDS and size > 0:
                self._known.add(key)
                self._pending.pop(key, None)
                with self._lock:
                    self._found.append(key)

    def to_dict(self) -> dict:
        return {
            "watching": self.running,
            "folder": str(self.folder),
            "recursive": self.recursive,
            "known": len(self._known),
            "settling": len(self._pending),
            "error": self.error,
        }


def valid_folder(raw: str) -> tuple[Path | None, str]:
    """Check a folder can be watched, returning it or an explanation."""
    if not raw:
        return None, "Choose a folder to watch."
    folder = Path(raw).expanduser()
    if not folder.is_dir():
        return None, "That folder does not exist."
    return folder, ""
