"""Turning a set of choices into an ffmpeg command, and running it."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterator

from . import features, hwaccel, images, metadata, raw
from .deps import Tools, _no_window
from .images import ImageError, ImageSpec
from .probe import IMAGE_EXTENSIONS, MediaInfo, ProbeError, probe
from .paths import LOG_DIR, human_size, system_key

# --------------------------------------------------------------------------
# The vocabulary
# --------------------------------------------------------------------------

#: Our codec keys mapped to the software encoder that implements them.
SOFTWARE_ENCODERS = {
    "h265": "libx265",
    "h264": "libx264",
    "av1": "libsvtav1",
    "vp9": "libvpx-vp9",
}

CODEC_LABELS = {
    "h265": "H.265 / HEVC",
    "h264": "H.264",
    "av1": "AV1",
    "vp9": "VP9",
    "copy": "Copy (no re-encode)",
}

#: Named quality levels, expressed as the CRF each codec needs to reach roughly
#: the same visual result. Lower numbers mean better quality and bigger files.
QUALITY_CRF = {
    "maximum": {"h265": 18, "h264": 16, "av1": 20, "vp9": 24},
    "high":    {"h265": 22, "h264": 20, "av1": 26, "vp9": 28},
    "balanced":{"h265": 28, "h264": 23, "av1": 32, "vp9": 32},
    "small":   {"h265": 32, "h264": 28, "av1": 38, "vp9": 38},
    "tiny":    {"h265": 36, "h264": 32, "av1": 45, "vp9": 45},
}

QUALITY_LABELS = {
    "maximum": "Maximum (near lossless, large)",
    "high": "High",
    "balanced": "Balanced (recommended)",
    "small": "Small",
    "tiny": "Tiny (visible quality loss)",
}

CRF_RANGE = {"h265": (0, 51), "h264": (0, 51), "av1": (1, 63), "vp9": (0, 63)}

#: Speed names shared across codecs, translated per encoder further down.
SPEEDS = ["ultrafast", "veryfast", "fast", "medium", "slow", "veryslow"]

SVT_AV1_SPEED = {"ultrafast": 12, "veryfast": 10, "fast": 8, "medium": 6, "slow": 4, "veryslow": 2}
VP9_CPU_USED = {"ultrafast": 8, "veryfast": 6, "fast": 4, "medium": 2, "slow": 1, "veryslow": 0}

#: Which codecs and audio formats each container will accept.
CONTAINER_RULES = {
    "mp4": {"video": {"h265", "h264", "av1", "copy"}, "audio": {"aac", "opus", "mp3", "copy", "none"}},
    "mkv": {"video": {"h265", "h264", "av1", "vp9", "copy"}, "audio": {"aac", "opus", "mp3", "flac", "copy", "none"}},
    "webm": {"video": {"vp9", "av1"}, "audio": {"opus", "none"}},
    "mov": {"video": {"h265", "h264", "copy"}, "audio": {"aac", "copy", "none"}},
    "m4a": {"video": set(), "audio": {"aac", "copy"}},
    "mp3": {"video": set(), "audio": {"mp3"}},
}

AUDIO_ENCODERS = {"opus": "libopus", "aac": "aac", "mp3": "libmp3lame", "flac": "flac"}

#: Standard heights, used for the "resize to" choices. The value is the shorter
#: side of the frame, so it means the same thing for portrait and landscape.
SCALE_PRESETS = {"2160": 2160, "1440": 1440, "1080": 1080, "720": 720, "480": 480, "360": 360}

#: The render node VA-API uses. This is the standard location on Linux, which is
#: the only platform where VA-API applies.
VAAPI_DEVICE = "/dev/dri/renderD128"

#: The tone-mapping chain that converts HDR to SDR without the washed-out grey
#: look you get from a naive pixel-format conversion.
TONEMAP_CHAIN = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv"
)


class EncodeError(RuntimeError):
    """Raised when an encode cannot be set up or fails partway."""


# --------------------------------------------------------------------------
# The job description
# --------------------------------------------------------------------------


@dataclass
class JobSpec:
    """Everything the user chose, independent of any particular input file."""

    # What to produce
    video_codec: str = "h265"          # h265 | h264 | av1 | vp9 | copy
    container: str = "mp4"             # mp4 | mkv | webm | mov | m4a | mp3
    audio_codec: str = "opus"          # opus | aac | mp3 | flac | copy | none
    audio_bitrate: int = 128           # kbps

    # How good it should look
    quality_mode: str = "quality"      # quality | size | bitrate
    quality: str = "balanced"          # a QUALITY_CRF key
    crf: int | None = None             # overrides `quality` when set
    target_size_mb: float | None = None
    video_bitrate: int | None = None   # kbps, for quality_mode == "bitrate"
    speed: str = "veryfast"
    ten_bit: bool = False

    # Reshaping
    scale: int | None = None           # target shorter side, e.g. 1080
    scale_exact: tuple[int, int] | None = None
    allow_upscale: bool = False
    fps: float | None = None
    fps_max: float | None = None       # cap without raising a lower framerate
    trim_start: float | None = None
    trim_end: float | None = None

    # Clean-up filters
    tonemap_hdr: bool = True           # only acts on HDR input
    denoise: bool = False
    deinterlace: bool = False

    # Stills. These are ignored unless the input is an image, in which case
    # everything above is ignored instead.
    image_format: str = "jpeg"
    image_quality: int = 82
    image_lossless: bool = False
    image_max_dimension: int | None = None
    image_background: str = "white"

    # Camera RAW. A sensor reading is not a photograph, and something has to
    # decide how bright it is and how strong its colour is; see raw.py.
    raw_look: str = "natural"          # natural | neutral
    image_saturation: float = 1.0      # set from raw_look, not by the user

    # Practicalities
    hardware: str = "off"              # off | auto | an explicit encoder name
    faststart: bool = True             # put the index first, for web playback
    keep_subtitles: bool = False
    keep_metadata: bool = True
    extra_args: list[str] = field(default_factory=list)

    def resolved_crf(self) -> int:
        if self.crf is not None:
            return self.crf
        table = QUALITY_CRF.get(self.quality) or QUALITY_CRF["balanced"]
        return table.get(self.video_codec, 28)


@dataclass
class JobResult:
    """What happened to one file."""

    source: Path
    output: Path | None
    ok: bool
    message: str = ""
    source_bytes: int = 0
    output_bytes: int = 0
    elapsed: float = 0.0
    replaced: bool = False
    command: list[str] = field(default_factory=list)

    @property
    def saved_bytes(self) -> int:
        return max(0, self.source_bytes - self.output_bytes)

    @property
    def ratio(self) -> float:
        """How many times smaller the result is."""
        if self.output_bytes <= 0:
            return 0.0
        return self.source_bytes / self.output_bytes

    @property
    def percent_saved(self) -> float:
        if self.source_bytes <= 0:
            return 0.0
        return 100.0 * self.saved_bytes / self.source_bytes


@dataclass
class Progress:
    """A snapshot of an encode in flight."""

    fraction: float          # 0..1, or -1 when unknown
    seconds_done: float
    seconds_total: float
    speed: float             # times realtime
    bytes_written: int
    eta: float               # seconds remaining, or -1
    pass_number: int = 1
    pass_count: int = 1


ProgressFn = Callable[[Progress], None]


# --------------------------------------------------------------------------
# Choosing sane combinations
# --------------------------------------------------------------------------


def normalise(spec: JobSpec, info: MediaInfo, tools: Tools) -> tuple[JobSpec, list[str]]:
    """Fix up impossible combinations, returning the spec and any notes.

    The interface tries to prevent bad combinations, but presets, the command
    line and edited settings files can all produce them, so this is the single
    place where they are made safe.
    """
    notes: list[str] = []
    spec = replace(spec)

    rules = CONTAINER_RULES.get(spec.container)
    if rules is None:
        notes.append(f"Unknown container '{spec.container}', using MP4 instead.")
        spec.container = "mp4"
        rules = CONTAINER_RULES["mp4"]

    audio_only = not rules["video"]

    # Video codec has to fit the container.
    if not audio_only and spec.video_codec not in rules["video"]:
        fallback = "vp9" if spec.container == "webm" else "h264"
        notes.append(
            f"{CODEC_LABELS.get(spec.video_codec, spec.video_codec)} cannot go in a "
            f".{spec.container} file, switching to {CODEC_LABELS[fallback]}."
        )
        spec.video_codec = fallback

    # Audio codec has to fit the container.
    if spec.audio_codec not in rules["audio"]:
        fallback = "opus" if spec.container == "webm" else "aac"
        notes.append(f"Audio switched to {fallback.upper()} to fit a .{spec.container} file.")
        spec.audio_codec = fallback

    # Opus inside MP4 works, but only on reasonably current ffmpeg builds.
    if spec.container == "mp4" and spec.audio_codec == "opus" and tools.needs_strict_opus:
        notes.append("This ffmpeg is old, so Opus in MP4 is being enabled explicitly.")

    # The encoder has to exist in this build.
    if not audio_only and spec.video_codec != "copy":
        needed = SOFTWARE_ENCODERS[spec.video_codec]
        if not tools.has(needed):
            for alternative in ("h264", "h265"):
                if tools.has(SOFTWARE_ENCODERS[alternative]) and alternative in rules["video"]:
                    notes.append(
                        f"This ffmpeg cannot encode {CODEC_LABELS[spec.video_codec]}, "
                        f"using {CODEC_LABELS[alternative]} instead."
                    )
                    spec.video_codec = alternative
                    break
            else:
                raise EncodeError("This ffmpeg build has no usable video encoder.")

    if spec.audio_codec in AUDIO_ENCODERS and not tools.has(AUDIO_ENCODERS[spec.audio_codec]):
        for alternative in ("aac", "opus", "mp3"):
            if alternative in rules["audio"] and tools.has(AUDIO_ENCODERS[alternative]):
                notes.append(f"Audio switched to {alternative.upper()}; this ffmpeg lacks the other encoder.")
                spec.audio_codec = alternative
                break

    # Input without the stream we were told to produce.
    if not info.has_audio and spec.audio_codec != "none":
        spec.audio_codec = "none"
    if not info.has_video and not audio_only:
        notes.append(f"{info.path.name} has no video, writing an audio file instead.")
        spec.container = "m4a" if spec.audio_codec in ("aac", "copy") else "mp3"
        spec.audio_codec = "aac" if spec.container == "m4a" else "mp3"

    # Copying the video stream rules out anything that would need re-encoding.
    if spec.video_codec == "copy":
        conflicting = [
            name
            for name, value in (
                ("resize", spec.scale or spec.scale_exact),
                ("framerate change", spec.fps or spec.fps_max),
                ("denoise", spec.denoise),
                ("deinterlace", spec.deinterlace),
            )
            if value
        ]
        if conflicting:
            notes.append(f"Cannot {', '.join(conflicting)} while copying the video stream; ignoring those.")
            spec.scale = spec.scale_exact = None
            spec.fps = spec.fps_max = None
            spec.denoise = spec.deinterlace = False

    # Target size needs a duration to divide by.
    if spec.quality_mode == "size":
        if not spec.target_size_mb or spec.target_size_mb <= 0:
            notes.append("No target size given, falling back to a quality setting.")
            spec.quality_mode = "quality"
        elif info.duration <= 0:
            notes.append("Cannot work out a bitrate without a duration, using a quality setting.")
            spec.quality_mode = "quality"

    # Never enlarge a video unless explicitly asked.
    if spec.scale and info.has_video and not spec.allow_upscale:
        shorter = min(info.display_width, info.display_height)
        if shorter and spec.scale > shorter:
            notes.append(
                f"{info.path.name} is already smaller than {spec.scale}p, keeping its size."
            )
            spec.scale = None

    if spec.trim_start and spec.trim_end and spec.trim_end <= spec.trim_start:
        notes.append("The trim end is before the trim start; ignoring the trim.")
        spec.trim_start = spec.trim_end = None

    return spec, notes


def output_duration(spec: JobSpec, info: MediaInfo) -> float:
    """How long the result will be, once trimming is taken into account."""
    start = spec.trim_start or 0.0
    end = spec.trim_end if spec.trim_end else info.duration
    return max(0.0, min(end, info.duration) - start) if info.duration else 0.0


# --------------------------------------------------------------------------
# Building the command
# --------------------------------------------------------------------------


def _even(value: int) -> int:
    """Round down to an even number, never below 2.

    Subsampled formats refuse odd dimensions. AVIF and AV1 do not refuse them
    loudly: they write a file of zero length and report success.
    """
    return max(2, int(value) - (int(value) % 2))


def _scaled_dimensions(spec: JobSpec, info: MediaInfo) -> tuple[int, int] | None:
    """Work out the exact output size, keeping the aspect ratio and even numbers."""
    if spec.scale_exact:
        # Even here, where the size was asked for explicitly. A custom preset
        # may name an odd number, and AV1 and AVIF answer an odd dimension by
        # writing an empty file and reporting success.
        return _even(spec.scale_exact[0]), _even(spec.scale_exact[1])
    if not spec.scale or not info.display_width or not info.display_height:
        return None

    width, height = info.display_width, info.display_height
    shorter = min(width, height)
    if shorter == spec.scale:
        return None
    factor = spec.scale / shorter
    new_width = max(2, int(round(width * factor / 2)) * 2)
    new_height = max(2, int(round(height * factor / 2)) * 2)
    return new_width, new_height


def _has_filter(tools: Tools, name: str) -> bool:
    """Check a filter exists before relying on it."""
    try:
        result = subprocess.run(
            [str(tools.ffmpeg), "-hide_banner", "-filters"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", timeout=30, **_no_window(),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(re.search(rf"^\s*\S+\s+{re.escape(name)}\s", result.stdout, re.M))


def build_filters(spec: JobSpec, info: MediaInfo, tools: Tools) -> tuple[str, list[str]]:
    """Assemble the video filter chain. Returns the chain and any notes."""
    notes: list[str] = []
    chain: list[str] = []

    if spec.deinterlace:
        chain.append("yadif=deint=interlaced")

    if spec.denoise:
        chain.append("hqdn3d=2:1:2:3")

    if spec.tonemap_hdr and info.is_hdr:
        if _has_filter(tools, "zscale"):
            chain.append(TONEMAP_CHAIN)
            notes.append("HDR footage detected, converting it to standard range.")
        else:
            notes.append(
                "This is HDR footage but the ffmpeg build has no zscale filter, "
                "so colours may look washed out. Delete the bin folder and restart "
                "to fetch a build that supports it."
            )

    dimensions = _scaled_dimensions(spec, info)
    if dimensions:
        chain.append(f"scale={dimensions[0]}:{dimensions[1]}:flags=lanczos")

    if spec.fps:
        chain.append(f"fps={spec.fps:g}")
    elif spec.fps_max and info.fps and info.fps > spec.fps_max:
        chain.append(f"fps={spec.fps_max:g}")

    return ",".join(chain), notes


def _pixel_format(spec: JobSpec) -> str:
    if spec.ten_bit:
        return "yuv420p10le"
    return "yuv420p"


def _video_quality_args(spec: JobSpec, encoder: str, target_kbps: int | None, pass_number: int) -> list[str]:
    """The rate-control flags, which differ for every encoder family."""
    args: list[str] = []
    crf = spec.resolved_crf()

    if target_kbps is not None:
        args += ["-b:v", f"{target_kbps}k"]
        if encoder in ("libx264", "libx265"):
            args += ["-pass", str(pass_number)]
        elif encoder == "libvpx-vp9":
            args += ["-pass", str(pass_number)]
        else:
            # Single-pass hardware and AV1 encoders behave better when they are
            # given room to move around the average.
            args += ["-maxrate", f"{int(target_kbps * 1.5)}k", "-bufsize", f"{target_kbps * 2}k"]
        return args

    if encoder in ("libx264", "libx265"):
        args += ["-crf", str(crf), "-preset", spec.speed]
    elif encoder == "libsvtav1":
        args += ["-crf", str(crf), "-preset", str(SVT_AV1_SPEED.get(spec.speed, 6))]
    elif encoder == "libvpx-vp9":
        args += ["-crf", str(crf), "-b:v", "0", "-cpu-used", str(VP9_CPU_USED.get(spec.speed, 2)), "-row-mt", "1"]
    elif encoder.endswith("_nvenc"):
        args += ["-rc", "vbr", "-cq", str(crf), "-preset", "p4", "-b:v", "0"]
    elif encoder.endswith("_qsv"):
        args += ["-global_quality", str(crf), "-look_ahead", "1"]
    elif encoder.endswith("_amf"):
        args += ["-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf)]
    elif encoder.endswith("_videotoolbox"):
        # VideoToolbox wants a quality percentage rather than a CRF.
        quality = max(1, min(100, int(round(100 - (crf / 51) * 100))))
        args += ["-q:v", str(quality)]
    elif encoder.endswith("_vaapi"):
        args += ["-rc_mode", "CQP", "-qp", str(crf)]
    else:
        args += ["-crf", str(crf)]
    return args


def _target_bitrate(spec: JobSpec, info: MediaInfo) -> int | None:
    """Work out the video bitrate needed to land on the requested file size."""
    if spec.quality_mode == "bitrate" and spec.video_bitrate:
        return int(spec.video_bitrate)
    if spec.quality_mode != "size" or not spec.target_size_mb:
        return None

    duration = output_duration(spec, info)
    if duration <= 0:
        return None

    # Leave a little headroom for container overhead so we land under the limit.
    total_kbits = spec.target_size_mb * 1024 * 1024 * 8 / 1000 * 0.96
    total_kbps = total_kbits / duration
    audio_kbps = 0 if spec.audio_codec == "none" else spec.audio_bitrate
    video_kbps = int(total_kbps - audio_kbps)

    if video_kbps < 50:
        raise EncodeError(
            f"{spec.target_size_mb:g} MB is not enough for "
            f"{int(duration)} seconds of video. Try trimming it, "
            f"lowering the resolution, or reducing the audio bitrate."
        )

    # A size limit is a ceiling, not a quota. If the source is already leaner
    # than the target, spending the full budget would inflate the file and add
    # nothing, so never allocate more bits than the original actually used.
    # Both figures ffprobe reports are in bits per second, so convert first.
    source_bps = info.video_bitrate or int(info.overall_bitrate * 0.95)
    source_kbps = source_bps // 1000
    if source_kbps > 0:
        video_kbps = min(video_kbps, source_kbps)

    return video_kbps


def uses_two_pass(spec: JobSpec, encoder: str) -> bool:
    """Two-pass gives noticeably better results when hitting an exact size."""
    if spec.quality_mode not in ("size", "bitrate"):
        return False
    return encoder in ("libx264", "libx265", "libvpx-vp9")


def choose_encoder(spec: JobSpec, tools: Tools) -> tuple[str, str]:
    """Pick the encoder to use. Returns (encoder name, note)."""
    if spec.video_codec == "copy":
        return "copy", ""
    if spec.hardware == "off":
        return SOFTWARE_ENCODERS[spec.video_codec], ""
    if spec.hardware not in ("auto", "off"):
        return spec.hardware, ""

    found = hwaccel.best_for(tools, spec.video_codec)
    if found:
        return found.encoder, f"Using the {found.vendor} hardware encoder."
    return (
        SOFTWARE_ENCODERS[spec.video_codec],
        "No working hardware encoder for this codec, using the processor instead.",
    )


def build_command(
    spec: JobSpec,
    info: MediaInfo,
    tools: Tools,
    output: Path,
    pass_number: int = 1,
    pass_total: int = 1,
    passlog: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Produce the full ffmpeg command line. Returns (command, notes)."""
    notes: list[str] = []
    encoder, encoder_note = choose_encoder(spec, tools)
    if encoder_note:
        notes.append(encoder_note)

    command = [str(tools.ffmpeg), "-hide_banner", "-nostdin", "-y", "-loglevel", "error"]
    command += ["-progress", "pipe:1", "-nostats"]

    # VA-API is the one hardware family that cannot take ordinary frames: the
    # device has to be opened and the frames uploaded to it explicitly. The
    # others accept software frames and need none of this.
    uses_vaapi = encoder.endswith("_vaapi")
    if uses_vaapi:
        command += ["-vaapi_device", VAAPI_DEVICE]

    # Seeking before the input is much faster than after it.
    if spec.trim_start:
        command += ["-ss", f"{spec.trim_start:.3f}"]

    command += ["-i", str(info.path)]

    if spec.trim_end:
        length = spec.trim_end - (spec.trim_start or 0.0)
        command += ["-t", f"{length:.3f}"]

    audio_only = not CONTAINER_RULES[spec.container]["video"]

    # ---- video ----------------------------------------------------------
    if audio_only:
        command += ["-vn"]
    elif spec.video_codec == "copy":
        command += ["-c:v", "copy"]
    else:
        target_kbps = _target_bitrate(spec, info)
        filters, filter_notes = build_filters(spec, info, tools)
        notes += filter_notes

        if uses_vaapi:
            # Everything else has to happen in software first, then the finished
            # frames are handed to the card. This must be last in the chain.
            filters = ",".join(filter(None, [filters, "format=nv12", "hwupload"]))

        if filters:
            command += ["-vf", filters]

        command += ["-c:v", encoder]
        command += _video_quality_args(spec, encoder, target_kbps, pass_number)

        # The pixel format is decided by the upload for VA-API, so setting it
        # here would conflict with the hardware frame context.
        if encoder in ("libx264", "libx265", "libsvtav1"):
            command += ["-pix_fmt", _pixel_format(spec)]
        if encoder == "libx265":
            command += ["-x265-params", "log-level=error"]
        # Apple's players need this tag to recognise H.265 in an MP4.
        if spec.video_codec == "h265" and spec.container in ("mp4", "mov"):
            command += ["-tag:v", "hvc1"]

    # ---- audio ----------------------------------------------------------
    if spec.audio_codec == "none":
        command += ["-an"]
    elif spec.audio_codec == "copy":
        command += ["-c:a", "copy"]
    else:
        command += ["-c:a", AUDIO_ENCODERS[spec.audio_codec]]
        if spec.audio_codec != "flac":
            command += ["-b:a", f"{spec.audio_bitrate}k"]

    if spec.container == "mp4" and spec.audio_codec == "opus" and tools.needs_strict_opus:
        command += ["-strict", "-2"]

    # ---- everything else -------------------------------------------------
    if spec.keep_subtitles and info.subtitle_count and not audio_only:
        command += ["-map", "0:v:0?", "-map", "0:a?", "-map", "0:s?"]
        command += ["-c:s", "mov_text" if spec.container in ("mp4", "mov") else "copy"]

    if not spec.keep_metadata:
        command += ["-map_metadata", "-1"]

    if spec.faststart and spec.container in ("mp4", "mov", "m4a"):
        command += ["-movflags", "+faststart"]

    command += spec.extra_args

    # First pass writes statistics, not a file.
    if pass_total > 1 and pass_number == 1:
        if passlog:
            command += ["-passlogfile", str(passlog)]
        command += ["-an", "-f", "null", "-"]
    else:
        if pass_total > 1 and passlog:
            command += ["-passlogfile", str(passlog)]
        command += [str(output)]

    return command, notes


# --------------------------------------------------------------------------
# Running it
# --------------------------------------------------------------------------


def _parse_progress_stream(stream, total_seconds: float, pass_number: int, pass_count: int) -> Iterator[Progress]:
    """Turn ffmpeg's -progress output into Progress snapshots."""
    started = time.monotonic()
    current: dict[str, str] = {}
    for raw_line in stream:
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        current[key] = value
        if key != "progress":
            continue

        micros = current.get("out_time_us") or current.get("out_time_ms") or "0"
        try:
            seconds_done = int(micros) / 1_000_000
        except ValueError:
            seconds_done = 0.0

        try:
            speed = float((current.get("speed") or "0x").rstrip("x"))
        except ValueError:
            speed = 0.0

        try:
            written = int(current.get("total_size") or 0)
        except ValueError:
            written = 0

        fraction = seconds_done / total_seconds if total_seconds > 0 else -1.0
        fraction = min(1.0, max(0.0, fraction)) if fraction >= 0 else -1.0

        if fraction > 0.001:
            elapsed = time.monotonic() - started
            eta = elapsed / fraction - elapsed
        else:
            eta = -1.0

        yield Progress(
            fraction=fraction,
            seconds_done=seconds_done,
            seconds_total=total_seconds,
            speed=speed,
            bytes_written=written,
            eta=eta,
            pass_number=pass_number,
            pass_count=pass_count,
        )
        current.clear()


def _run_pass(
    command: list[str],
    total_seconds: float,
    on_progress: ProgressFn | None,
    cancel: threading.Event | None,
    pass_number: int,
    pass_count: int,
) -> tuple[int, str]:
    """Run one ffmpeg invocation. Returns (exit code, captured errors)."""
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        bufsize=1,
        **_no_window(),
    )

    errors: list[str] = []

    def drain_errors() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            line = line.rstrip()
            if line:
                errors.append(line)

    error_thread = threading.Thread(target=drain_errors, daemon=True)
    error_thread.start()

    try:
        assert process.stdout is not None
        for snapshot in _parse_progress_stream(process.stdout, total_seconds, pass_number, pass_count):
            if cancel is not None and cancel.is_set():
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                return 130, "Cancelled"
            if on_progress:
                on_progress(snapshot)
    finally:
        process.wait()
        error_thread.join(timeout=5)

    return process.returncode, "\n".join(errors[-25:])


def unique_path(path: Path) -> Path:
    """Avoid overwriting an existing file by adding a counter to the name."""
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    for counter in range(2, 1000):
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
    return parent / f"{stem} ({int(time.time())}){suffix}"


def plan_output(info: MediaInfo, spec: JobSpec, output_dir: Path, keep_tree_from: Path | None = None) -> Path:
    """Decide where a result should be written."""
    destination = output_dir
    if keep_tree_from:
        try:
            relative = info.path.parent.relative_to(keep_tree_from)
            destination = output_dir / relative
        except ValueError:
            destination = output_dir
    destination.mkdir(parents=True, exist_ok=True)

    candidate = destination / f"{info.path.stem}.{spec.container}"
    if candidate.resolve() == info.path.resolve():
        candidate = destination / f"{info.path.stem} - converted.{spec.container}"
    return unique_path(candidate)


def verify_output(tools: Tools, source: MediaInfo, output: Path, spec: JobSpec) -> tuple[bool, str]:
    """Confirm a result is a real, complete, smaller file before trusting it.

    This is the gate that has to pass before an original may be deleted.
    """
    if not output.exists():
        return False, "the new file was not created"

    size = output.stat().st_size
    if size < 1024:
        return False, "the new file is empty"

    try:
        result = probe(tools, output)
    except ProbeError as exc:
        return False, f"the new file cannot be read back ({exc})"

    if source.has_video and not result.has_video:
        return False, "the new file has no video stream"
    if spec.audio_codec != "none" and source.has_audio and not result.has_audio:
        return False, "the new file has no audio stream"

    expected = output_duration(spec, source)
    if expected > 0 and result.duration > 0:
        drift = abs(result.duration - expected)
        # Allow a second, or one percent on long files, for container rounding.
        if drift > max(1.0, expected * 0.01):
            return False, (
                f"the new file is {result.duration:.1f}s long but should be {expected:.1f}s"
            )

    return True, ""


def image_spec_of(spec: JobSpec) -> ImageSpec:
    """Pull the still-image settings out of a job."""
    return ImageSpec(
        image_format=spec.image_format,
        quality=spec.image_quality,
        lossless=spec.image_lossless,
        max_dimension=spec.image_max_dimension,
        background=spec.image_background,
        keep_metadata=spec.keep_metadata,
        saturation=spec.image_saturation,
    )


def encode_image(
    tools: Tools,
    info: MediaInfo,
    spec: JobSpec,
    output_dir: Path,
    on_note: Callable[[str], None] | None = None,
    replace_original: bool = False,
    keep_tree_from: Path | None = None,
    started: float | None = None,
    original: Path | None = None,
) -> JobResult:
    """Convert one still image. Much simpler than video: one pass, no progress.

    `original` is set when the input was developed from a RAW file: naming and
    any deletion then refer to the file the user actually chose, not to the
    temporary image we made from it.
    """
    started = started if started is not None else time.monotonic()
    image = image_spec_of(spec)
    named_after = original or info.path

    destination = output_dir
    if keep_tree_from:
        try:
            destination = output_dir / named_after.parent.relative_to(keep_tree_from)
        except ValueError:
            destination = output_dir
    destination.mkdir(parents=True, exist_ok=True)

    candidate = destination / images.output_name(named_after, image)
    if candidate.resolve() == named_after.resolve():
        extension = images.IMAGE_FORMATS[image.image_format]["ext"]
        candidate = destination / f"{named_after.stem} - converted.{extension}"
    output = unique_path(candidate)

    try:
        command, notes = images.build_command(image, info, tools, output)
    except ImageError as exc:
        return JobResult(source=info.path, output=None, ok=False, message=str(exc),
                         source_bytes=info.size_bytes)

    for note in notes:
        if on_note:
            on_note(note)

    try:
        result = subprocess.run(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, errors="replace", timeout=600, **_no_window(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return JobResult(source=info.path, output=None, ok=False,
                         message=f"Could not convert the image: {exc}",
                         source_bytes=info.size_bytes, command=command)

    if result.returncode != 0 or not output.exists():
        output.unlink(missing_ok=True)
        _write_log(info.path, command, result.stderr or "")
        return JobResult(source=info.path, output=None, ok=False,
                         message=_friendly_error(result.stderr or ""),
                         source_bytes=info.size_bytes, command=command)

    # ffmpeg writes pixels and nothing else for stills, so the camera, the lens
    # and the date the photograph was taken have to be carried over separately.
    # `named_after` rather than `info.path`: for a RAW the details live in the
    # file the user chose, not in the temporary image developed from it.
    if spec.keep_metadata:
        note = metadata.carry(named_after, output)
        if note and on_note:
            on_note(note)

    output_bytes = output.stat().st_size
    try:
        source_bytes = named_after.stat().st_size
    except OSError:
        source_bytes = info.size_bytes
    job = JobResult(
        source=named_after, output=output, ok=True,
        source_bytes=source_bytes, output_bytes=output_bytes,
        elapsed=time.monotonic() - started, command=command,
    )

    if output_bytes >= source_bytes and source_bytes > 0:
        job.message = (
            f"The result is not smaller ({human_size(output_bytes)}). "
            "The original was probably already well compressed."
        )

    if replace_original:
        ok, reason = verify_image(tools, info, output)
        if not ok:
            job.message = f"Original kept, because {reason}."
        elif output_bytes >= source_bytes:
            job.message = "Original kept, because the new file is not smaller."
        else:
            try:
                named_after.unlink()
                job.replaced = True
            except OSError as exc:
                job.message = f"Original kept, because it could not be deleted: {exc}"

    return job


def verify_image(tools: Tools, source: MediaInfo, output: Path) -> tuple[bool, str]:
    """Confirm a converted image is real and readable before trusting it."""
    if not output.exists():
        return False, "the new file was not created"
    if output.stat().st_size < 64:
        return False, "the new file is empty"
    try:
        result = probe(tools, output)
    except ProbeError as exc:
        return False, f"the new file cannot be read back ({exc})"
    if not result.has_video or not result.width:
        return False, "the new file contains no image"
    return True, ""


def _encode_raw(
    tools: Tools,
    source: Path,
    spec: JobSpec,
    output_dir: Path,
    on_progress: ProgressFn | None,
    on_note: Callable[[str], None] | None,
    replace_original: bool,
    keep_tree_from: Path | None,
    started: float,
) -> JobResult:
    """Develop a RAW file, then convert the result like any other picture."""
    if on_progress:
        on_progress(Progress(fraction=0.0, seconds_done=0, seconds_total=0,
                             speed=0, bytes_written=0, eta=-1))
    try:
        source_bytes = source.stat().st_size
    except OSError:
        source_bytes = 0

    look = spec.raw_look if spec.raw_look in raw.LOOKS else raw.NATURAL

    with tempfile.TemporaryDirectory(prefix="halveit-raw-") as tmp:
        try:
            developed, note = raw.develop(source, Path(tmp), look=look)
        except raw.RawError as exc:
            return JobResult(source=source, output=None, ok=False,
                             message=str(exc), source_bytes=source_bytes)
        if on_note:
            on_note(note)

        # The decoder can be told how bright to make it but has no way to say
        # how strong the colour should be, so that half is applied afterwards.
        spec = replace(spec, image_saturation=raw.saturation_for(look))

        try:
            info = probe(tools, developed)
        except ProbeError as exc:
            return JobResult(source=source, output=None, ok=False,
                             message=f"The developed image could not be read: {exc}",
                             source_bytes=source_bytes)

        job = encode_image(tools, info, spec, output_dir, on_note,
                           replace_original, keep_tree_from, started, original=source)

    if on_progress:
        on_progress(Progress(fraction=1.0, seconds_done=0, seconds_total=0,
                             speed=0, bytes_written=job.output_bytes, eta=0))
    return job


def encode_one(
    tools: Tools,
    source: Path,
    spec: JobSpec,
    output_dir: Path,
    on_progress: ProgressFn | None = None,
    on_note: Callable[[str], None] | None = None,
    cancel: threading.Event | None = None,
    replace_original: bool = False,
    keep_tree_from: Path | None = None,
) -> JobResult:
    """Compress a single file from start to finish."""
    started = time.monotonic()
    source = Path(source)

    # A build without pictures must not have a route into the picture pipeline,
    # not even an internal one. The selection code refuses these earlier and more
    # politely; this is here so that a caller which skips it cannot get through.
    if not features.images_enabled() and (
            raw.is_raw(source) or source.suffix.lower() in IMAGE_EXTENSIONS):
        return JobResult(source=source, output=None, ok=False,
                         message="This version converts video and audio only.")

    # Camera RAW cannot be read by ffmpeg at all, so it is developed into an
    # ordinary image first and then treated as one.
    if raw.is_raw(source):
        return _encode_raw(tools, source, spec, output_dir, on_progress, on_note,
                           replace_original, keep_tree_from, started)

    try:
        info = probe(tools, source)
    except ProbeError as exc:
        return JobResult(source=source, output=None, ok=False, message=str(exc))

    # Stills take an entirely different route, because none of the video
    # reasoning about duration and bitrate applies to them.
    if info.is_image:
        if on_progress:
            on_progress(Progress(fraction=0.0, seconds_done=0, seconds_total=0,
                                 speed=0, bytes_written=0, eta=-1))
        job = encode_image(tools, info, spec, output_dir, on_note,
                           replace_original, keep_tree_from, started)
        if on_progress:
            on_progress(Progress(fraction=1.0, seconds_done=0, seconds_total=0,
                                 speed=0, bytes_written=job.output_bytes, eta=0))
        return job

    try:
        spec, notes = normalise(spec, info, tools)
    except EncodeError as exc:
        return JobResult(source=source, output=None, ok=False, message=str(exc),
                         source_bytes=info.size_bytes)

    for note in notes:
        if on_note:
            on_note(note)

    output = plan_output(info, spec, output_dir, keep_tree_from)
    encoder, _ = choose_encoder(spec, tools)

    try:
        two_pass = uses_two_pass(spec, encoder)
        pass_count = 2 if two_pass else 1
        used_command: list[str] = []

        with tempfile.TemporaryDirectory(prefix="halveit-") as tmp:
            passlog = Path(tmp) / "passlog" if two_pass else None

            for pass_number in range(1, pass_count + 1):
                command, build_notes = build_command(
                    spec, info, tools, output, pass_number, pass_count, passlog
                )
                if pass_number == 1:
                    for note in build_notes:
                        if on_note:
                            on_note(note)
                used_command = command

                def scaled(snapshot: Progress, _pass=pass_number) -> None:
                    if on_progress is None:
                        return
                    if pass_count == 2:
                        base = 0.0 if _pass == 1 else 0.4
                        span = 0.4 if _pass == 1 else 0.6
                        if snapshot.fraction >= 0:
                            snapshot = replace(snapshot, fraction=base + snapshot.fraction * span)
                    on_progress(snapshot)

                code, errors = _run_pass(
                    command,
                    output_duration(spec, info),
                    scaled,
                    cancel,
                    pass_number,
                    pass_count,
                )

                if code == 130:
                    output.unlink(missing_ok=True)
                    return JobResult(source=source, output=None, ok=False, message="Cancelled",
                                     source_bytes=info.size_bytes, command=used_command)
                if code != 0:
                    output.unlink(missing_ok=True)
                    _write_log(source, command, errors)
                    return JobResult(
                        source=source, output=None, ok=False,
                        message=_friendly_error(errors),
                        source_bytes=info.size_bytes, command=used_command,
                    )
    except EncodeError as exc:
        return JobResult(source=source, output=None, ok=False, message=str(exc),
                         source_bytes=info.size_bytes)
    except OSError as exc:
        return JobResult(source=source, output=None, ok=False,
                         message=f"Could not write the result: {exc}",
                         source_bytes=info.size_bytes)

    output_bytes = output.stat().st_size if output.exists() else 0
    result = JobResult(
        source=source,
        output=output,
        ok=True,
        source_bytes=info.size_bytes,
        output_bytes=output_bytes,
        elapsed=time.monotonic() - started,
        command=used_command,
    )

    if output_bytes >= info.size_bytes and info.size_bytes > 0:
        result.message = (
            f"The result is not smaller ({human_size(output_bytes)}). "
            "The original was probably already well compressed."
        )

    if replace_original:
        ok, reason = verify_output(tools, info, output, spec)
        if not ok:
            result.message = f"Original kept, because {reason}."
        elif output_bytes >= info.size_bytes:
            result.message = "Original kept, because the new file is not smaller."
        else:
            try:
                source.unlink()
                result.replaced = True
            except OSError as exc:
                result.message = f"Original kept, because it could not be deleted: {exc}"

    return result


def _friendly_error(errors: str) -> str:
    """Translate the most common ffmpeg complaints into plain language."""
    text = errors.lower()
    if "no space left" in text:
        return "Ran out of disk space."
    if "permission denied" in text:
        return "Permission denied. Try a different output folder."
    if "invalid data found" in text or "moov atom not found" in text:
        return "The file appears to be damaged or incomplete."
    if "no usable encoding entrypoint" in text or "hardware" in text and "not" in text:
        return "The graphics card refused this encode. Turn hardware acceleration off and retry."
    if "experimental" in text:
        return "This ffmpeg build rejected the chosen codec combination."
    if not errors.strip():
        return "ffmpeg stopped without explaining why. See the logs folder."
    return errors.strip().splitlines()[-1]


def _write_log(source: Path, command: list[str], errors: str) -> None:
    """Keep a record of failures so problems can be diagnosed later."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        safe = re.sub(r"[^\w.-]+", "_", source.name)[:60]
        log = LOG_DIR / f"{stamp}_{safe}.log"
        log.write_text(
            "Command:\n" + " ".join(command) + "\n\nErrors:\n" + errors + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def free_space(path: Path) -> int:
    """Bytes available where we are about to write."""
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0
