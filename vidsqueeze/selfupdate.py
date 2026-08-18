"""Updating VidSqueeze itself, without a terminal.

Someone who downloaded a ZIP should not have to learn git, or hunt for the
download page again, to get a fix. This replaces the program's own files with
the newest published version and leaves everything belonging to the user alone.

Two routes. A folder cloned with git is updated with git, because that is what
the person who cloned it will expect. Anything else has the newest release
downloaded and unpacked over it. Either way the previous copy is kept, so a
failed update can be undone rather than leaving a broken program.
"""

from __future__ import annotations

import io
import json
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from . import deps
from .paths import APP_DIR, CACHE_DIR

TARBALL_API = "https://api.github.com/repos/pxspaces/vidsqueeze/releases/latest"
BACKUP_DIR = APP_DIR / ".cache" / "previous-version"

#: Everything the program is made of. Anything not listed here belongs to the
#: user, or is a tool we downloaded, and is never touched.
DISTRIBUTED = [
    "vidsqueeze",
    "docs",
    "README.md",
    "FEATURES.md",
    "CHANGELOG.md",
    "USER-GUIDE.md",
    "LICENSE",
    "presets.example.json",
    "Start VidSqueeze.bat",
    "Start VidSqueeze.command",
    "start-vidsqueeze.sh",
    "create-desktop-shortcut.sh",
]

ProgressFn = Callable[[str, float], None]


#: What perform() says when it changed something, and when it did not. The server
#: compares against these to decide whether a restart is worth attempting, so they
#: are constants rather than strings written out twice.
NO_CHANGE = "Already the newest version."
CHANGED = "Updated."


def changed(result: str) -> bool:
    """Whether an update actually replaced anything."""
    return bool(result) and result != NO_CHANGE

class UpdateError(RuntimeError):
    """Raised when an update cannot be carried out."""


def _run(command: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", timeout=180, **deps._no_window(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return result.returncode == 0, (result.stdout or "").strip()


def method() -> str:
    """How this copy can be updated: 'git', 'download', or 'none'."""
    if (APP_DIR / ".git").exists() and shutil.which("git"):
        return "git"
    # Updating means rewriting the program's own folder, so it has to be
    # writable. A copy in a system location is not ours to change.
    probe = APP_DIR / ".vidsqueeze-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return "none"
    return "download"


def describe() -> dict:
    """What the interface should say about updating in place."""
    how = method()
    return {
        "method": how,
        "can_update": how != "none",
        "explanation": {
            "git": "This copy was cloned with git, so updating pulls the newest version.",
            "download": "The newest version will be downloaded and unpacked over this folder. "
                        "Your converted files, settings and history are untouched.",
            "none": "This folder cannot be written to, so VidSqueeze cannot update itself. "
                    "Download the newest version and replace the folder by hand.",
        }[how],
        "backup": str(BACKUP_DIR),
    }


# --------------------------------------------------------------------------
# The two routes
# --------------------------------------------------------------------------


def _update_with_git(progress: ProgressFn | None) -> str:
    if progress:
        progress("Checking for changes", -1)

    ok, output = _run(["git", "status", "--porcelain"], APP_DIR)
    if ok and output.strip():
        raise UpdateError(
            "This copy has local changes, so updating would overwrite them. "
            "Commit or discard them first, or update by hand."
        )

    if progress:
        progress("Fetching the newest version", -1)
    ok, output = _run(["git", "pull", "--ff-only"], APP_DIR)
    if not ok:
        raise UpdateError(f"git could not update this copy: {output[-300:]}")
    if "Already up to date" in output or "Already up-to-date" in output:
        return NO_CHANGE
    return CHANGED


def _download_tarball(progress: ProgressFn | None) -> bytes:
    request = urllib.request.Request(TARBALL_API, headers={"User-Agent": deps.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.load(response)
    except (urllib.error.URLError, ssl.SSLError, OSError, ValueError) as exc:
        raise UpdateError(f"Could not reach the update server: {exc}") from exc

    url = release.get("tarball_url")
    if not url:
        raise UpdateError("There is no published version to download yet.")

    if progress:
        progress("Downloading the newest version", -1)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": deps.USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as response:
            total = int(response.headers.get("Content-Length") or 0)
            chunks, done = [], 0
            while True:
                chunk = response.read(262144)
                if not chunk:
                    break
                chunks.append(chunk)
                done += len(chunk)
                if progress:
                    progress("Downloading the newest version", done / total if total else -1)
        return b"".join(chunks)
    except (urllib.error.URLError, ssl.SSLError, OSError) as exc:
        raise UpdateError(f"The download failed: {exc}") from exc


def _update_with_download(progress: ProgressFn | None) -> str:
    payload = _download_tarball(progress)

    if progress:
        progress("Unpacking", -1)
    with tempfile.TemporaryDirectory(prefix="vidsqueeze-update-") as tmp:
        staging = Path(tmp)
        try:
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
                # GitHub wraps everything in one directory named after the commit.
                archive.extractall(staging, filter="data")
        except (tarfile.TarError, OSError, TypeError) as exc:
            raise UpdateError(f"The download could not be unpacked: {exc}") from exc

        roots = [p for p in staging.iterdir() if p.is_dir()]
        if not roots:
            raise UpdateError("The download did not contain what was expected.")
        source = roots[0]

        if not (source / "vidsqueeze").is_dir():
            raise UpdateError("The download did not contain the program.")

        if progress:
            progress("Keeping a copy of the current version", -1)
        _back_up()

        if progress:
            progress("Installing", -1)
        try:
            for name in DISTRIBUTED:
                incoming = source / name
                if not incoming.exists():
                    continue
                target = APP_DIR / name
                if incoming.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                    shutil.copytree(incoming, target)
                else:
                    shutil.copy2(incoming, target)
                    # Launchers have to stay runnable.
                    if name.endswith((".sh", ".command")):
                        target.chmod(0o755)
        except OSError as exc:
            raise UpdateError(
                f"Installing failed part way: {exc}. The previous version is in {BACKUP_DIR}."
            ) from exc

    return CHANGED


def _back_up() -> None:
    """Keep the current program files, so a bad update can be undone."""
    shutil.rmtree(BACKUP_DIR, ignore_errors=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for name in DISTRIBUTED:
        current = APP_DIR / name
        if not current.exists():
            continue
        try:
            if current.is_dir():
                shutil.copytree(current, BACKUP_DIR / name)
            else:
                shutil.copy2(current, BACKUP_DIR / name)
        except OSError:
            # A backup that cannot be written is not a reason to refuse the
            # update, but it is a reason not to pretend one exists.
            pass
    try:
        (BACKUP_DIR / "taken-at.txt").write_text(
            time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8"
        )
    except OSError:
        pass


def perform(progress: ProgressFn | None = None) -> str:
    """Update this copy in place. Returns a message for the user."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    how = method()
    if how == "git":
        return _update_with_git(progress)
    if how == "download":
        return _update_with_download(progress)
    raise UpdateError(
        "This folder cannot be written to, so VidSqueeze cannot update itself. "
        "Download the newest version and replace the folder by hand."
    )


def restore() -> str:
    """Put the previous version back, if one was kept."""
    if not BACKUP_DIR.is_dir():
        raise UpdateError("There is no previous version to go back to.")
    for name in DISTRIBUTED:
        kept = BACKUP_DIR / name
        if not kept.exists():
            continue
        target = APP_DIR / name
        if kept.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(kept, target)
        else:
            shutil.copy2(kept, target)
    return "The previous version has been put back. Restart VidSqueeze."
