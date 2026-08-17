"""The work queue shared by the browser interface and the terminal.

Both front ends do the same thing: build a list of files, hand it to a Queue,
and watch it. Keeping that logic here means the two never drift apart.

Files can be encoded more than one at a time. Video encoders already use every
core, so this is not a straight multiplier, but it does recover the time each
file spends starting up and finishing off, which matters on long batches of
short clips.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import history
from .deps import Tools
from .encode import JobResult, JobSpec, Progress, encode_one
from .paths import human_duration, human_size

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


def sensible_concurrency(requested: int | None = None) -> int:
    """How many files to encode at once.

    One is the safe default. Beyond two there is little to gain and a real risk
    of every file crawling at once, which feels worse even at the same total
    throughput, so we cap it.
    """
    cores = os.cpu_count() or 4
    ceiling = 1 if cores <= 2 else min(3, max(1, cores // 4))
    if requested is None:
        return 1
    return max(1, min(int(requested), ceiling))


@dataclass
class QueueItem:
    """One file on its way through the queue."""

    item_id: int
    source: Path
    status: str = STATUS_QUEUED
    fraction: float = 0.0
    speed: float = 0.0
    eta: float = -1.0
    pass_number: int = 1
    pass_count: int = 1
    notes: list[str] = field(default_factory=list)
    result: JobResult | None = None
    source_bytes: int = 0

    def to_dict(self) -> dict:
        data = {
            "id": self.item_id,
            "name": self.source.name,
            "path": str(self.source),
            "folder": str(self.source.parent),
            "status": self.status,
            "fraction": round(self.fraction, 4),
            "speed": round(self.speed, 2),
            "eta": round(self.eta, 1),
            "pass_number": self.pass_number,
            "pass_count": self.pass_count,
            "notes": self.notes,
            "source_bytes": self.source_bytes,
            "source_size": human_size(self.source_bytes) if self.source_bytes else "",
        }
        if self.result is not None:
            data.update(
                {
                    "ok": self.result.ok,
                    "message": self.result.message,
                    "output": str(self.result.output) if self.result.output else "",
                    "output_name": self.result.output.name if self.result.output else "",
                    "output_bytes": self.result.output_bytes,
                    "output_size": human_size(self.result.output_bytes),
                    "ratio": round(self.result.ratio, 2),
                    "percent_saved": round(self.result.percent_saved, 1),
                    "elapsed": round(self.result.elapsed, 1),
                    "elapsed_text": human_duration(self.result.elapsed),
                    "replaced": self.result.replaced,
                }
            )
        return data


class Queue:
    """Runs a list of files through the encoder."""

    def __init__(
        self,
        tools: Tools,
        spec: JobSpec,
        output_dir: Path,
        replace_originals: bool = False,
        keep_tree_from: Path | None = None,
        concurrency: int = 1,
        preset_key: str = "",
    ):
        self.tools = tools
        self.spec = spec
        self.output_dir = Path(output_dir)
        self.replace_originals = replace_originals
        self.keep_tree_from = keep_tree_from
        self.concurrency = sensible_concurrency(concurrency)
        self.preset_key = preset_key

        self.items: list[QueueItem] = []
        self.started_at: float | None = None
        self.finished_at: float | None = None

        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._workers: list[threading.Thread] = []
        self._file_cancels: dict[int, threading.Event] = {}
        self._next_id = 1
        self._listeners: list[Callable[[], None]] = []

    # -- building ---------------------------------------------------------

    def add(self, paths: list[Path]) -> list[QueueItem]:
        added = []
        with self._lock:
            existing = {str(item.source) for item in self.items}
            for path in paths:
                path = Path(path)
                if str(path) in existing:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                item = QueueItem(item_id=self._next_id, source=path, source_bytes=size)
                self._next_id += 1
                self.items.append(item)
                added.append(item)
        self._notify()
        return added

    def remove(self, item_id: int) -> bool:
        with self._lock:
            for index, item in enumerate(self.items):
                if item.item_id == item_id and item.status == STATUS_QUEUED:
                    del self.items[index]
                    self._notify()
                    return True
        return False

    def cancel_item(self, item_id: int) -> bool:
        """Stop one file without touching the rest of the batch."""
        with self._lock:
            event = self._file_cancels.get(item_id)
        if event is not None:
            event.set()
            return True
        return self.remove(item_id)

    def clear_finished(self) -> None:
        with self._lock:
            self.items = [i for i in self.items if i.status in (STATUS_QUEUED, STATUS_RUNNING)]
        self._notify()

    # -- running ----------------------------------------------------------

    @property
    def running(self) -> bool:
        return any(worker.is_alive() for worker in self._workers)

    def start(self) -> None:
        if self.running:
            return
        self._cancel.clear()
        self.finished_at = None
        self.started_at = time.time()
        self._workers = [
            threading.Thread(target=self._work, daemon=True, name=f"vidsqueeze-{n}")
            for n in range(self.concurrency)
        ]
        for worker in self._workers:
            worker.start()
        threading.Thread(target=self._await_finish, daemon=True).start()

    def cancel(self) -> None:
        """Stop everything, abandoning whatever is part-way through."""
        self._cancel.set()
        with self._lock:
            events = list(self._file_cancels.values())
        for event in events:
            event.set()

    def wait(self, timeout: float | None = None) -> None:
        deadline = None if timeout is None else time.monotonic() + timeout
        for worker in self._workers:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            worker.join(remaining)

    def _claim(self) -> QueueItem | None:
        """Take the next waiting file, atomically, so two workers cannot share one."""
        with self._lock:
            for item in self.items:
                if item.status == STATUS_QUEUED:
                    item.status = STATUS_RUNNING
                    item.fraction = 0.0
                    self._file_cancels[item.item_id] = threading.Event()
                    return item
        return None

    def _work(self) -> None:
        while not self._cancel.is_set():
            item = self._claim()
            if item is None:
                break
            self._notify()

            per_file_cancel = self._file_cancels[item.item_id]

            def on_progress(snapshot: Progress, target=item) -> None:
                target.fraction = max(0.0, snapshot.fraction)
                target.speed = snapshot.speed
                target.eta = snapshot.eta
                target.pass_number = snapshot.pass_number
                target.pass_count = snapshot.pass_count
                self._notify()

            def on_note(note: str, target=item) -> None:
                if note not in target.notes:
                    target.notes.append(note)
                self._notify()

            result = encode_one(
                self.tools,
                item.source,
                self.spec,
                self.output_dir,
                on_progress=on_progress,
                on_note=on_note,
                cancel=per_file_cancel,
                replace_original=self.replace_originals,
                keep_tree_from=self.keep_tree_from,
            )

            with self._lock:
                self._file_cancels.pop(item.item_id, None)

            item.result = result
            if result.ok:
                item.status = STATUS_DONE
                item.fraction = 1.0
                history.record(
                    source=item.source,
                    output=result.output,
                    source_bytes=result.source_bytes,
                    output_bytes=result.output_bytes,
                    preset=self.preset_key,
                    elapsed=result.elapsed,
                    replaced=result.replaced,
                )
            elif result.message == "Cancelled":
                item.status = STATUS_CANCELLED
            else:
                item.status = STATUS_FAILED
            self._notify()

    def _await_finish(self) -> None:
        for worker in self._workers:
            worker.join()
        if self._cancel.is_set():
            with self._lock:
                for item in self.items:
                    if item.status == STATUS_QUEUED:
                        item.status = STATUS_CANCELLED
        self.finished_at = time.time()
        self._notify()

    # -- reporting --------------------------------------------------------

    def on_change(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:  # noqa: BLE001 - a broken listener must not stop encoding
                pass

    def totals(self) -> dict:
        done = [i for i in self.items if i.status == STATUS_DONE and i.result]
        source_bytes = sum(i.result.source_bytes for i in done if i.result)
        output_bytes = sum(i.result.output_bytes for i in done if i.result)
        completed = len([i for i in self.items if i.status in (STATUS_DONE, STATUS_FAILED, STATUS_CANCELLED)])

        overall = 0.0
        if self.items:
            overall = sum(
                1.0 if i.status == STATUS_DONE else (i.fraction if i.status == STATUS_RUNNING else 0.0)
                for i in self.items
            ) / len(self.items)

        # Time left across the batch, from how fast the finished ones went.
        eta = -1.0
        if self.started_at and 0 < overall < 1:
            elapsed = time.time() - self.started_at
            eta = elapsed / overall - elapsed

        return {
            "total": len(self.items),
            "completed": completed,
            "succeeded": len(done),
            "failed": len([i for i in self.items if i.status == STATUS_FAILED]),
            "cancelled": len([i for i in self.items if i.status == STATUS_CANCELLED]),
            "replaced": len([i for i in done if i.result and i.result.replaced]),
            "running": self.running,
            "concurrency": self.concurrency,
            "overall_fraction": round(overall, 4),
            "eta": round(eta, 1),
            "source_bytes": source_bytes,
            "output_bytes": output_bytes,
            "saved_bytes": max(0, source_bytes - output_bytes),
            "source_size": human_size(source_bytes),
            "output_size": human_size(output_bytes),
            "saved_size": human_size(max(0, source_bytes - output_bytes)),
            "percent_saved": round(100 * (source_bytes - output_bytes) / source_bytes, 1) if source_bytes else 0.0,
            "ratio": round(source_bytes / output_bytes, 2) if output_bytes else 0.0,
            "elapsed": round((self.finished_at or time.time()) - self.started_at, 1) if self.started_at else 0.0,
        }

    def snapshot(self) -> dict:
        with self._lock:
            items = [item.to_dict() for item in self.items]
        return {"items": items, "totals": self.totals(), "output_dir": str(self.output_dir)}
