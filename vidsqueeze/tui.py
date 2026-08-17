"""Step-by-step questions, for people who prefer the terminal to a browser."""

from __future__ import annotations

from pathlib import Path

from . import presets
from .cli import run_batch
from .deps import Tools
from .paths import OUTPUT_DIR, human_size
from .server import expand_selection


def _ask(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{question}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0)
    return answer or default


def _ask_yes_no(question: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = _ask(f"{question} ({hint})").lower()
    if not answer:
        return default
    return answer.startswith("y")


def _choose(title: str, options: list[tuple[str, str]], default_index: int = 0) -> str:
    """Print a numbered menu and return the chosen key."""
    print(f"\n{title}")
    for number, (_, label) in enumerate(options, start=1):
        marker = "*" if number - 1 == default_index else " "
        print(f"  {marker}{number:2d}. {label}")
    while True:
        raw = _ask("\nNumber", str(default_index + 1))
        try:
            index = int(raw) - 1
        except ValueError:
            print("  Please type one of the numbers.")
            continue
        if 0 <= index < len(options):
            return options[index][0]
        print(f"  Please choose between 1 and {len(options)}.")


def wizard(tools: Tools) -> int:
    """Walk the user through a batch, then run it."""
    print("\n  VidSqueeze")
    print("  ----------")
    print("  Answer a few questions, or press Ctrl+C to leave.\n")

    # 1. What to compress
    while True:
        raw = _ask("Which file or folder should I compress?")
        if not raw:
            print("  Type a path, or drag a file into this window and press Enter.")
            continue
        # Terminals often quote or escape dragged paths.
        cleaned = raw.strip().strip("'\"").replace("\\ ", " ")
        files, problems = expand_selection([cleaned])
        for problem in problems:
            print(f"  {problem}")
        if files:
            break
        print("  I could not find any video or audio files there. Try again.")

    total = sum(f.stat().st_size for f in files if f.exists())
    print(f"\n  Found {len(files)} file{'s' if len(files) != 1 else ''}, {human_size(total)} in total.")
    for path in files[:8]:
        print(f"    {path.name}")
    if len(files) > 8:
        print(f"    and {len(files) - 8} more")

    # 2. What to do with it
    preset_list = presets.all_presets()[0]
    options = [(p.key, f"{p.name}  -  {p.description.splitlines()[0]}") for p in preset_list]
    default_index = next((i for i, p in enumerate(preset_list) if p.key == presets.DEFAULT_PRESET), 0)
    chosen = _choose("What would you like to do?", options, default_index)
    preset = presets.get(chosen)
    assert preset is not None
    spec = preset.spec()

    # 3. Where it goes
    print(f"\n  Results are saved in {OUTPUT_DIR}")
    if not _ask_yes_no("  Use that folder?", True):
        spec_dir = _ask("  Folder to use")
        output_dir = Path(spec_dir).expanduser() if spec_dir else OUTPUT_DIR
    else:
        output_dir = OUTPUT_DIR

    # 4. The irreversible bit
    replace = False
    if _ask_yes_no("\n  Delete each original once the new file is verified?", False):
        print("\n  Originals will be permanently deleted, but only after the new file")
        print("  has been checked for length, contents and size. This cannot be undone.")
        replace = _ask("  Type 'yes' to confirm").lower() == "yes"
        if not replace:
            print("  Originals will be kept.")

    print()
    return run_batch(tools, files, spec, output_dir, replace, preset.key)
