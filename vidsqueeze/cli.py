"""The command line.

Running VidSqueeze with no arguments opens the browser interface, because that
is what most people want. Everything the interface can do is also available as
a flag here, so it can be scripted or run over SSH.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import shutil
import sys
from pathlib import Path

from . import __version__, deps, history, hwaccel, images, presets
from .encode import CODEC_LABELS, QUALITY_LABELS, SPEEDS, JobSpec, encode_one
from .jobs import Queue
from .paths import OUTPUT_DIR, ensure_dirs, human_duration, human_size
from .probe import ProbeError, probe
from .server import expand_selection

#: The version lives in __init__.py and nowhere else. It was once written here
#: as well, and the two drifted apart, so the command line announced a new
#: version while the interface and the update check still reported the old one.
VERSION = __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vidsqueeze",
        description="Make video files smaller. Run with no arguments to open the interface.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  vidsqueeze                          open the interface in your browser\n"
            "  vidsqueeze holiday.mp4              compress one file with the default settings\n"
            "  vidsqueeze ~/Videos                 compress every video in a folder\n"
            "  vidsqueeze -p whatsapp clip.mov     make it fit WhatsApp's size limit\n"
            "  vidsqueeze -p shrink_to_1080 *.MP4  scale a batch down to 1080p\n"
            "  vidsqueeze --terminal               step-by-step questions instead of flags\n"
        ),
    )

    parser.add_argument("inputs", nargs="*", help="Files or folders to compress.")
    parser.add_argument("--version", action="version", version=f"VidSqueeze {VERSION}")

    modes = parser.add_argument_group("how to run")
    modes.add_argument("--web", action="store_true", help="Open the browser interface (the default).")
    modes.add_argument("--terminal", "-t", action="store_true", help="Ask questions in the terminal instead.")
    modes.add_argument("--port", type=int, help="Port for the interface.")
    modes.add_argument("--no-browser", action="store_true", help="Start the interface but do not open a browser.")
    modes.add_argument("--browser", metavar="NAME",
                       help="Which browser to open, for example chromium or firefox. Remembered for next time.")
    modes.add_argument("--setup", action="store_true", help="Download ffmpeg and exit.")
    modes.add_argument("--update", action="store_true",
                       help="Update VidSqueeze itself to the newest published version.")
    modes.add_argument("--list-presets", action="store_true", help="Show the available presets and exit.")
    modes.add_argument("--info", action="store_true", help="Describe the input files and exit.")
    modes.add_argument("--dry-run", action="store_true", help="Show the ffmpeg command without running it.")
    modes.add_argument("--no-download", action="store_true", help="Never download ffmpeg automatically.")

    output = parser.add_argument_group("output")
    output.add_argument("-o", "--output", help=f"Where to write results (default: {OUTPUT_DIR}).")
    output.add_argument("-p", "--preset", default=presets.DEFAULT_PRESET, help="Preset to start from.")
    output.add_argument("--replace", action="store_true",
                        help="Delete each original once the new file has been verified.")
    output.add_argument("--no-recursive", action="store_true", help="Do not look inside subfolders.")

    video = parser.add_argument_group("video")
    video.add_argument("--codec", choices=sorted(CODEC_LABELS), help="Video codec.")
    video.add_argument("--container", choices=["mp4", "mkv", "webm", "mov", "m4a", "mp3"], help="Output file type.")
    video.add_argument("--quality", choices=sorted(QUALITY_LABELS), help="Named quality level.")
    video.add_argument("--crf", type=int, help="Exact quality value. Lower is better.")
    video.add_argument("--size", type=float, metavar="MB", help="Fit the result into this many megabytes.")
    video.add_argument("--bitrate", type=int, metavar="KBPS", help="Exact video bitrate.")
    video.add_argument("--speed", choices=SPEEDS, help="Encoding speed against compression.")
    video.add_argument("--scale", type=int, metavar="HEIGHT", help="Resize so the shorter side is this many pixels.")
    video.add_argument("--fps", type=float, help="Cap the framerate.")
    video.add_argument("--trim-start", type=float, metavar="SECONDS", help="Skip this much from the start.")
    video.add_argument("--trim-end", type=float, metavar="SECONDS", help="Stop at this point.")
    video.add_argument("--10bit", dest="ten_bit", action="store_true", help="Encode in 10-bit colour.")
    video.add_argument("--denoise", action="store_true", help="Reduce grain before encoding.")
    video.add_argument("--deinterlace", action="store_true", help="Fix interlaced footage.")
    video.add_argument("--no-tonemap", action="store_true", help="Do not convert HDR to standard range.")
    video.add_argument("--hardware", choices=["off", "auto"], help="Use the graphics card if one works.")

    audio = parser.add_argument_group("audio")
    audio.add_argument("--audio", choices=["opus", "aac", "mp3", "flac", "copy", "none"], help="Audio codec.")
    audio.add_argument("--audio-bitrate", type=int, metavar="KBPS", help="Audio bitrate.")

    stills = parser.add_argument_group("images")
    stills.add_argument("--image-format", choices=sorted(images.IMAGE_FORMATS),
                        help="Output format for stills and camera RAW.")
    stills.add_argument("--image-quality", type=int, metavar="1-100",
                        help="Still image quality. 90 and above keeps full colour detail.")
    stills.add_argument("--lossless", action="store_true",
                        help="Lossless stills. WebP and JPEG XL only.")
    stills.add_argument("--max-dimension", type=int, metavar="PIXELS",
                        help="Shrink so the longest side is at most this many pixels.")
    stills.add_argument("--background", metavar="COLOUR",
                        help="Background colour when flattening transparency.")
    stills.add_argument("--raw-look", choices=["natural", "neutral"],
                        help="How a camera RAW should look: natural, like the "
                             "photograph, or neutral and flat for editing.")

    extras = parser.add_argument_group("extras")
    extras.add_argument("--keep-subtitles", action="store_true", help="Carry subtitles across.")
    extras.add_argument("--no-metadata", action="store_true", help="Strip dates and camera information.")

    return parser


def _looks_like_still(tools, path: Path) -> bool:
    """Whether a file would take the picture route rather than the video one."""
    try:
        return probe(tools, path).is_image
    except ProbeError:
        return False


def _assumed_shape(path: Path):
    """A stand-in for a RAW's shape, which cannot be measured until it is
    developed. Only the dry run needs this: it prints a command rather than
    running one, and the size only affects whether a resize is added."""
    from .probe import MediaInfo

    return MediaInfo(path=path, size_bytes=0, duration=0.0, container="tiff_pipe",
                     has_video=True, has_audio=False, width=6000, height=4000,
                     frame_count=1)


def spec_from_args(args: argparse.Namespace) -> JobSpec:
    """Start from the chosen preset, then apply any explicit flags over it."""
    preset = presets.get(args.preset)
    if preset is None:
        known = ", ".join(p.key for p in presets.all_presets()[0])
        raise SystemExit(f"Unknown preset '{args.preset}'. Available: {known}")

    spec = preset.spec()

    if args.codec:
        spec.video_codec = args.codec
    if args.container:
        spec.container = args.container
    if args.quality:
        spec.quality = args.quality
    if args.crf is not None:
        spec.crf = args.crf
    if args.speed:
        spec.speed = args.speed
    if args.scale:
        spec.scale = args.scale
    if args.fps:
        spec.fps_max = args.fps
    if args.audio:
        spec.audio_codec = args.audio
    if args.audio_bitrate:
        spec.audio_bitrate = args.audio_bitrate
    if args.size is not None:
        spec.quality_mode = "size"
        spec.target_size_mb = args.size
    if args.bitrate is not None:
        spec.quality_mode = "bitrate"
        spec.video_bitrate = args.bitrate
    if args.trim_start is not None:
        spec.trim_start = args.trim_start
    if args.trim_end is not None:
        spec.trim_end = args.trim_end
    if args.ten_bit:
        spec.ten_bit = True
    if args.denoise:
        spec.denoise = True
    if args.deinterlace:
        spec.deinterlace = True
    if args.no_tonemap:
        spec.tonemap_hdr = False
    if args.hardware:
        spec.hardware = args.hardware
    if args.keep_subtitles:
        spec.keep_subtitles = True
    if args.no_metadata:
        spec.keep_metadata = False

    if args.image_format:
        spec.image_format = args.image_format
    if args.image_quality is not None:
        if not 1 <= args.image_quality <= 100:
            raise SystemExit("--image-quality takes a number from 1 to 100.")
        spec.image_quality = args.image_quality
    if args.lossless:
        if args.image_format and args.image_format not in ("webp", "jxl"):
            raise SystemExit(
                f"--lossless does not apply to {args.image_format}. "
                "It is for WebP and JPEG XL. PNG, TIFF and BMP are always lossless."
            )
        spec.image_lossless = True
    if args.max_dimension is not None:
        if args.max_dimension < 1:
            raise SystemExit("--max-dimension takes a positive number of pixels.")
        spec.image_max_dimension = args.max_dimension
    if args.background:
        spec.image_background = args.background
    if args.raw_look:
        spec.raw_look = args.raw_look

    return spec


# --------------------------------------------------------------------------
# Terminal output
# --------------------------------------------------------------------------


def _width() -> int:
    return max(40, min(shutil.get_terminal_size((80, 24)).columns, 100))


class LineProgress:
    """A single-line progress bar that rewrites itself in place."""

    def __init__(self, label: str, index: int, total: int):
        self.label = label
        self.prefix = f"[{index}/{total}] " if total > 1 else ""
        self.active = sys.stdout.isatty()

    def update(self, snapshot) -> None:
        if not self.active:
            return
        width = _width()
        passes = f" p{snapshot.pass_number}/{snapshot.pass_count}" if snapshot.pass_count > 1 else ""
        tail = f" {snapshot.fraction * 100:5.1f}%{passes} {snapshot.speed:4.1f}x"
        if snapshot.eta > 0:
            tail += f" eta {human_duration(snapshot.eta)}"
        room = width - len(self.prefix) - len(tail) - 4
        name = self.label if len(self.label) <= room else self.label[: max(3, room - 1)] + "…"
        bar_room = max(6, room - len(name) - 1)
        filled = int(bar_room * max(0.0, min(1.0, snapshot.fraction)))
        bar = "█" * filled + "░" * (bar_room - filled)
        sys.stdout.write(f"\r{self.prefix}{name} {bar}{tail}")
        sys.stdout.flush()

    def clear(self) -> None:
        if self.active:
            sys.stdout.write("\r" + " " * _width() + "\r")
            sys.stdout.flush()


def run_batch(tools: deps.Tools, files: list[Path], spec: JobSpec, output_dir: Path,
              replace: bool, preset_key: str = "") -> int:
    """Compress a list of files, printing progress. Returns an exit code."""
    output_dir.mkdir(parents=True, exist_ok=True)
    total_source = total_output = 0
    failures = 0

    print(f"\nCompressing {len(files)} file{'s' if len(files) != 1 else ''} into {output_dir}\n")

    for index, path in enumerate(files, start=1):
        bar = LineProgress(path.name, index, len(files))
        notes: list[str] = []
        result = encode_one(
            tools, path, spec, output_dir,
            on_progress=bar.update,
            on_note=notes.append,
            replace_original=replace,
        )
        bar.clear()

        prefix = f"[{index}/{len(files)}] " if len(files) > 1 else ""
        if result.ok:
            total_source += result.source_bytes
            total_output += result.output_bytes
            history.record(
                source=path,
                output=result.output,
                source_bytes=result.source_bytes,
                output_bytes=result.output_bytes,
                preset=preset_key,
                elapsed=result.elapsed,
                replaced=result.replaced,
            )
            saved = f"{result.percent_saved:.0f}% smaller" if result.percent_saved > 0 else "no saving"
            replaced = "  original deleted" if result.replaced else ""
            print(f"{prefix}{path.name}")
            print(f"      {human_size(result.source_bytes)} -> {human_size(result.output_bytes)}"
                  f"  ({saved}, {human_duration(result.elapsed)}){replaced}")
        else:
            failures += 1
            print(f"{prefix}{path.name}\n      failed: {result.message}")

        for note in notes:
            print(f"      note: {note}")
        if result.ok and result.message:
            print(f"      note: {result.message}")

    if total_source:
        saved = total_source - total_output
        print(
            f"\nDone. {human_size(total_source)} -> {human_size(total_output)}, "
            f"{human_size(max(0, saved))} saved"
            f" ({100 * saved / total_source:.0f}%)."
        )
    if failures:
        print(f"{failures} file{'s' if failures != 1 else ''} failed.")
    print(f"Results are in {output_dir}\n")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ensure_dirs()

    if args.list_presets:
        for preset in presets.all_presets()[0]:
            print(f"  {preset.key:18s} {preset.name}")
            print(f"  {'':18s} {preset.description}\n")
        return 0

    interactive = sys.stdout.isatty()

    def progress(message: str, fraction: float) -> None:
        # Rewriting the line only makes sense on a real terminal. When the
        # output is piped to a file we print nothing, to keep it clean.
        if not interactive:
            return
        if fraction >= 0:
            print(f"\r  {message}: {fraction * 100:5.1f}%", end="", flush=True)
        else:
            print(f"\r  {message}...", end="", flush=True)

    if args.update:
        from . import selfupdate

        how = selfupdate.describe()
        print(f"\n  {how['explanation']}\n")
        if not how["can_update"]:
            return 1
        try:
            message = selfupdate.perform(progress)
        except selfupdate.UpdateError as exc:
            print(f"\n  {exc}\n")
            return 1
        print(f"\n  {message}\n")
        return 0

    if args.setup:
        try:
            tools = deps.install_ffmpeg(progress)
        except deps.DependencyError as exc:
            print(f"\nSetup failed: {exc}")
            return 1
        print(f"\n  ffmpeg {tools.version} is ready.\n")
        return 0

    # No files and no explicit terminal request means the browser interface.
    if not args.inputs and not args.terminal:
        from .server import serve

        serve(open_browser=not args.no_browser, port=args.port, browser=args.browser)
        return 0

    try:
        tools = deps.ensure_tools(progress, allow_download=not args.no_download)
    except deps.DependencyError as exc:
        print(f"\n{exc}\n\nYou could also install it yourself:\n  {deps.system_install_hint()}\n")
        return 1
    if interactive:
        print("\r" + " " * 60 + "\r", end="")

    if args.terminal and not args.inputs:
        from .tui import wizard

        return wizard(tools)

    files, problems = expand_selection(args.inputs, recursive=not args.no_recursive)
    for problem in problems:
        print(f"  {problem}")
    if not files:
        print("Nothing to do: no video or audio files were found.")
        return 1

    if args.info:
        for path in files:
            try:
                print(f"{path}\n    {probe(tools, path).summary()}")
            except ProbeError as exc:
                print(f"{path}\n    {exc}")
        return 0

    spec = spec_from_args(args)
    output_dir = Path(args.output).expanduser() if args.output else OUTPUT_DIR

    if args.dry_run:
        from . import raw
        from .encode import (build_command, choose_encoder, image_spec_of, normalise,
                             uses_two_pass)
        from .images import build_command as build_image_command
        from .images import output_name

        for path in files:
            # Stills and camera RAW never touch the video pipeline, so showing a
            # video command for them is not a preview of anything. This printed
            # an H.265 command for a photograph, which was worse than useless.
            if raw.is_raw(path):
                print(f"# {path.name} is a {raw.camera_of(path)} RAW file.")
                decoder = raw.find_decoder()
                if decoder is None:
                    print(f"  # No decoder installed, the camera's preview would be used."
                          f" Install one: {raw.install_hint()}")
                else:
                    look = spec.raw_look if spec.raw_look in raw.LOOKS else raw.NATURAL
                    flags = " ".join(raw._flags_for(look))
                    print(f"  {decoder.name} {flags} <staged copy>   # develop, {look} look")
                    spec = replace(spec, image_saturation=raw.saturation_for(look))
                print("  # then, as an ordinary picture:")

            if raw.is_raw(path) or _looks_like_still(tools, path):
                image = image_spec_of(spec)
                destination = output_dir / output_name(path, image)
                shape = probe(tools, path) if not raw.is_raw(path) else None
                command, notes = build_image_command(
                    image, shape or _assumed_shape(path), tools, destination
                )
                print(" ".join(str(part) for part in command))
                for note in notes:
                    print(f"  # {note}")
                continue

            info = probe(tools, path)
            normalised, notes = normalise(spec, info, tools)
            destination = output_dir / f"{path.stem}.{normalised.container}"
            encoder, _ = choose_encoder(normalised, tools)
            passes = 2 if uses_two_pass(normalised, encoder) else 1
            for pass_number in range(1, passes + 1):
                command, more = build_command(
                    normalised, info, tools, destination, pass_number, passes,
                    Path("/tmp/vidsqueeze-passlog") if passes > 1 else None,
                )
                if passes > 1:
                    print(f"  # pass {pass_number} of {passes}")
                print(" ".join(command))
            for note in notes + more:
                print(f"  # {note}")
        return 0

    if args.replace:
        print(f"\n  Warning: originals will be deleted after each file is verified.")
        if sys.stdin.isatty():
            answer = input("  Type 'yes' to continue: ").strip().lower()
            if answer != "yes":
                print("  Cancelled.")
                return 1

    return run_batch(tools, files, spec, output_dir, args.replace, args.preset)


if __name__ == "__main__":
    sys.exit(main())
