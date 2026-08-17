"""A record of what has been compressed, and how much space it saved."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .paths import APP_DIR, human_size

HISTORY_FILE = APP_DIR / "history.json"
MAX_ENTRIES = 500


def _load() -> list[dict]:
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _save(entries: list[dict]) -> None:
    try:
        HISTORY_FILE.write_text(json.dumps(entries[-MAX_ENTRIES:], indent=1), encoding="utf-8")
    except OSError:
        pass  # History is a nicety; failing to write it must not break a job.


def record(
    source: Path,
    output: Path | None,
    source_bytes: int,
    output_bytes: int,
    preset: str,
    elapsed: float,
    replaced: bool = False,
) -> None:
    """Append one finished file."""
    entries = _load()
    entries.append(
        {
            "when": time.time(),
            "source": str(source),
            "name": Path(source).name,
            "output": str(output) if output else "",
            "source_bytes": source_bytes,
            "output_bytes": output_bytes,
            "preset": preset,
            "elapsed": round(elapsed, 1),
            "replaced": replaced,
        }
    )
    _save(entries)


def summary(limit: int = 40) -> dict:
    """Recent jobs plus lifetime totals."""
    entries = _load()
    total_source = sum(e.get("source_bytes", 0) for e in entries)
    total_output = sum(e.get("output_bytes", 0) for e in entries)
    saved = max(0, total_source - total_output)

    recent = []
    for entry in reversed(entries[-limit:]):
        source_bytes = entry.get("source_bytes", 0)
        output_bytes = entry.get("output_bytes", 0)
        recent.append(
            {
                **entry,
                "source_size": human_size(source_bytes),
                "output_size": human_size(output_bytes),
                "percent_saved": round(100 * (source_bytes - output_bytes) / source_bytes, 1)
                if source_bytes
                else 0.0,
                "output_exists": bool(entry.get("output") and Path(entry["output"]).exists()),
                "source_exists": bool(entry.get("source") and Path(entry["source"]).exists()),
                "ago": _ago(entry.get("when", 0)),
            }
        )

    return {
        "count": len(entries),
        "recent": recent,
        "total_source": human_size(total_source),
        "total_output": human_size(total_output),
        "total_saved": human_size(saved),
        "total_saved_bytes": saved,
    }


def clear() -> None:
    try:
        HISTORY_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _ago(when: float) -> str:
    """A rough, readable age such as '3 days ago'."""
    if not when:
        return ""
    seconds = max(0, time.time() - when)
    if seconds < 90:
        return "just now"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)} min ago"
    hours = minutes / 60
    if hours < 24:
        return f"{int(hours)} hour{'s' if int(hours) != 1 else ''} ago"
    days = hours / 24
    if days < 30:
        return f"{int(days)} day{'s' if int(days) != 1 else ''} ago"
    months = days / 30
    if months < 12:
        return f"{int(months)} month{'s' if int(months) != 1 else ''} ago"
    return f"{int(months / 12)} year{'s' if int(months / 12) != 1 else ''} ago"
