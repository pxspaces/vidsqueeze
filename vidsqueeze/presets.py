"""Ready-made settings for the things people actually want to do.

Presets are ordinary JobSpec values with a name attached. Anything here can be
overridden, and users can add their own by editing VidSqueeze/presets.json,
which is merged over the built-in list at startup.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from typing import Any

from . import features
from .encode import JobSpec
from .paths import PRESETS_FILE


class Preset:
    """A named set of encoding choices."""

    def __init__(self, key: str, name: str, description: str, group: str,
                 kinds: tuple[str, ...] = ("video", "audio"), **overrides: Any):
        self.key = key
        self.name = name
        self.description = description
        self.group = group
        #: Which media this preset is offered for: video, audio or image.
        self.kinds = kinds
        self.overrides = overrides

    def spec(self) -> JobSpec:
        return JobSpec(**self.overrides)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "group": self.group,
            "kinds": list(self.kinds),
            "spec": asdict(self.spec()),
        }


GROUP_ORDER = ["Everyday", "Share and upload", "Convert", "Audio", "Images"]


BUILT_IN: list[Preset] = [
    # -- Everyday ----------------------------------------------------------
    Preset(
        "balanced",
        "Balanced",
        "The best all-round choice. Looks essentially the same as the original at a "
        "fraction of the size. Start here.",
        "Everyday",
        video_codec="h265", container="mp4", audio_codec="opus", audio_bitrate=128,
        quality="balanced", speed="veryfast",
    ),
    Preset(
        "high_quality",
        "High quality",
        "Noticeably closer to the original than Balanced, at roughly twice the size. "
        "Good for footage you plan to edit later.",
        "Everyday",
        video_codec="h265", container="mp4", audio_codec="opus", audio_bitrate=160,
        quality="high", speed="medium",
    ),
    Preset(
        "archive",
        "Archive",
        "Near-lossless and slow to produce. For master copies you want to keep "
        "indefinitely.",
        "Everyday",
        video_codec="h265", container="mkv", audio_codec="flac",
        quality="maximum", speed="slow", ten_bit=True,
    ),
    Preset(
        "small",
        "Small",
        "Clearly smaller files with a mild quality cost. Fine for viewing, less so "
        "for editing.",
        "Everyday",
        video_codec="h265", container="mp4", audio_codec="opus", audio_bitrate=96,
        quality="small", speed="veryfast",
    ),
    Preset(
        "shrink_to_1080",
        "Shrink to 1080p",
        "Scales 4K and other large footage down to 1080p. The single biggest saving "
        "available if you do not need the full resolution.",
        "Everyday",
        video_codec="h265", container="mp4", audio_codec="opus", audio_bitrate=128,
        quality="balanced", speed="veryfast", scale=1080,
    ),
    Preset(
        "shrink_to_720",
        "Shrink to 720p",
        "For phones, messaging and anywhere bandwidth is tight.",
        "Everyday",
        video_codec="h265", container="mp4", audio_codec="opus", audio_bitrate=96,
        quality="balanced", speed="veryfast", scale=720,
    ),

    # -- Share and upload --------------------------------------------------
    Preset(
        "whatsapp",
        "WhatsApp (16 MB)",
        "Fits WhatsApp's attachment limit. Uses H.264 so it plays on every phone.",
        "Share and upload",
        video_codec="h264", container="mp4", audio_codec="aac", audio_bitrate=96,
        quality_mode="size", target_size_mb=15.5, scale=720, speed="medium",
    ),
    Preset(
        "discord",
        "Discord free (10 MB)",
        "Fits the 10 MB limit on a free Discord account.",
        "Share and upload",
        video_codec="h264", container="mp4", audio_codec="aac", audio_bitrate=96,
        quality_mode="size", target_size_mb=9.5, scale=720, speed="medium",
    ),
    Preset(
        "email",
        "Email (25 MB)",
        "Fits Gmail and most other mail providers.",
        "Share and upload",
        video_codec="h264", container="mp4", audio_codec="aac", audio_bitrate=128,
        quality_mode="size", target_size_mb=24.0, scale=1080, speed="medium",
    ),
    Preset(
        "short_form",
        "Short-form video",
        "For Reels, Shorts and TikTok. 1080p at 30fps in the format every platform "
        "accepts without re-processing.",
        "Share and upload",
        video_codec="h264", container="mp4", audio_codec="aac", audio_bitrate=192,
        quality="high", speed="medium", scale=1080, fps_max=30,
    ),
    Preset(
        "youtube",
        "YouTube upload",
        "Keeps the full resolution and uses a generous bitrate, because YouTube "
        "re-encodes whatever you send it and a better source means a better result.",
        "Share and upload",
        video_codec="h264", container="mp4", audio_codec="aac", audio_bitrate=192,
        quality="high", speed="medium",
    ),
    Preset(
        "web",
        "Website",
        "1080p H.264 with the index moved to the front so it starts playing before "
        "it has finished downloading.",
        "Share and upload",
        video_codec="h264", container="mp4", audio_codec="aac", audio_bitrate=128,
        quality="balanced", speed="medium", scale=1080, faststart=True,
    ),

    # -- Convert -----------------------------------------------------------
    Preset(
        "compatible",
        "Plays anywhere",
        "H.264 and AAC in an MP4. The safest possible combination if something "
        "refuses to open your video.",
        "Convert",
        video_codec="h264", container="mp4", audio_codec="aac", audio_bitrate=192,
        quality="high", speed="medium",
    ),
    Preset(
        "av1",
        "AV1",
        "The newest codec, and the smallest files, but slow to produce and not yet "
        "playable everywhere. Best for storage rather than sharing.",
        "Convert",
        video_codec="av1", container="mkv", audio_codec="opus", audio_bitrate=128,
        quality="balanced", speed="fast", ten_bit=True,
    ),
    Preset(
        "webm",
        "WebM",
        "VP9 and Opus, for websites that want an open format.",
        "Convert",
        video_codec="vp9", container="webm", audio_codec="opus", audio_bitrate=128,
        quality="balanced", speed="fast",
    ),
    Preset(
        "remux",
        "Change container only",
        "Repackages the existing video and audio into an MP4 without re-encoding. "
        "Takes seconds and loses nothing, but does not make the file smaller.",
        "Convert",
        video_codec="copy", container="mp4", audio_codec="copy",
    ),

    # -- Audio -------------------------------------------------------------
    Preset(
        "audio_mp3",
        "Extract audio as MP3",
        "Throws away the video and keeps a widely compatible audio file.",
        "Audio",
        container="mp3", audio_codec="mp3", audio_bitrate=192,
    ),
    Preset(
        "audio_m4a",
        "Extract audio as M4A",
        "Better quality than MP3 at the same size. Plays on Apple devices natively.",
        "Audio",
        container="m4a", audio_codec="aac", audio_bitrate=192,
    ),

    # -- Images ------------------------------------------------------------
    Preset(
        "photo_web",
        "Photo for the web",
        "JPEG at a sensible quality, no larger than 2560 pixels. The safe default "
        "for websites, documents and sharing.",
        "Images", kinds=("image",),
        image_format="jpeg", image_quality=82, image_max_dimension=2560,
    ),
    Preset(
        "photo_webp",
        "WebP",
        "Roughly a third smaller than JPEG at the same quality, and it keeps "
        "transparency. Every current browser reads it.",
        "Images", kinds=("image",),
        image_format="webp", image_quality=80, image_max_dimension=2560,
    ),
    Preset(
        "photo_avif",
        "AVIF",
        "The smallest of the common formats, often half the size of JPEG. Needs a "
        "recent browser or photo viewer.",
        "Images", kinds=("image",),
        image_format="avif", image_quality=72, image_max_dimension=2560,
    ),
    Preset(
        "photo_png",
        "PNG",
        "Lossless, keeps transparency. Right for logos, screenshots and diagrams, "
        "wasteful for photographs.",
        "Images", kinds=("image",),
        image_format="png",
    ),
    Preset(
        "photo_message",
        "Photo for messaging",
        "Smaller and narrower, for sending by chat or email without filling an "
        "inbox.",
        "Images", kinds=("image",),
        image_format="jpeg", image_quality=75, image_max_dimension=1600,
    ),
    Preset(
        "photo_thumbnail",
        "Thumbnail",
        "A small preview image, at most 512 pixels on its longest side.",
        "Images", kinds=("image",),
        image_format="jpeg", image_quality=78, image_max_dimension=512,
    ),
    Preset(
        "photo_archive",
        "Archive quality",
        "Lossless WebP. Keeps every pixel of the original while still being far "
        "smaller than PNG or TIFF.",
        "Images", kinds=("image",),
        image_format="webp", image_lossless=True,
    ),
]

DEFAULT_PRESET = "balanced"


def _valid_spec_keys() -> set[str]:
    return {f.name for f in fields(JobSpec)}


def load_user_presets() -> tuple[list[Preset], list[str]]:
    """Read presets.json, if the user has made one. Returns (presets, warnings)."""
    if not PRESETS_FILE.exists():
        return [], []

    try:
        data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"Ignoring presets.json because it could not be read: {exc}"]

    if not isinstance(data, list):
        return [], ["Ignoring presets.json because it should contain a list of presets."]

    allowed = _valid_spec_keys()
    presets: list[Preset] = []
    warnings: list[str] = []

    for index, entry in enumerate(data):
        if not isinstance(entry, dict) or "key" not in entry:
            warnings.append(f"Skipping presets.json entry {index + 1}: it needs a 'key'.")
            continue
        overrides = entry.get("spec") or {}
        unknown = set(overrides) - allowed
        if unknown:
            warnings.append(
                f"Preset '{entry['key']}' ignores unknown settings: {', '.join(sorted(unknown))}."
            )
            overrides = {k: v for k, v in overrides.items() if k in allowed}
        if isinstance(overrides.get("scale_exact"), list):
            overrides["scale_exact"] = tuple(overrides["scale_exact"])
        kinds = entry.get("kinds") or ["video", "audio"]
        presets.append(
            Preset(
                key=str(entry["key"]),
                name=str(entry.get("name") or entry["key"]),
                description=str(entry.get("description") or "Custom preset."),
                group=str(entry.get("group") or "My presets"),
                kinds=tuple(str(k) for k in kinds),
                **overrides,
            )
        )
    return presets, warnings


def all_presets() -> tuple[list[Preset], list[str]]:
    """Built-in presets with any user presets merged over the top."""
    user, warnings = load_user_presets()
    by_key = {preset.key: preset for preset in BUILT_IN}
    for preset in user:
        by_key[preset.key] = preset  # user definitions win

    # A build without pictures must not offer presets that only apply to them.
    # Filtered here, once, rather than at each of the places that list presets.
    if not features.images_enabled():
        by_key = {k: p for k, p in by_key.items() if tuple(p.kinds) != ("image",)}

    ordered: list[Preset] = []
    for group in GROUP_ORDER:
        ordered += [p for p in by_key.values() if p.group == group]
    ordered += [p for p in by_key.values() if p.group not in GROUP_ORDER]
    return ordered, warnings


def for_kinds(kinds: set[str]) -> list[Preset]:
    """Presets that suit the media currently selected.

    With a mixed selection we show anything relevant to any of it, and the
    encoder ignores whatever does not apply to a given file.
    """
    presets, _ = all_presets()
    if not kinds:
        return presets
    return [p for p in presets if kinds & set(p.kinds)]


def default_for_kind(kind: str) -> str:
    """The preset to select when a particular kind of file is chosen."""
    return {"image": "photo_web", "audio": "audio_m4a"}.get(kind, DEFAULT_PRESET)


def get(key: str) -> Preset | None:
    presets, _ = all_presets()
    for preset in presets:
        if preset.key == key:
            return preset
    return None


def write_example_file() -> None:
    """Write a sample file so custom presets are discoverable.

    It is deliberately written as presets.example.json rather than
    presets.json, so the sample never appears as a real choice in the
    interface. Renaming it is what switches it on.
    """
    example_path = PRESETS_FILE.with_name("presets.example.json")
    if example_path.exists() or PRESETS_FILE.exists():
        return
    example = [
        {
            "key": "my-preset",
            "name": "My preset",
            "description": "Rename this file to presets.json to switch it on.",
            "group": "My presets",
            "spec": {
                "video_codec": "h265",
                "container": "mp4",
                "audio_codec": "opus",
                "audio_bitrate": 128,
                "quality": "balanced",
                "speed": "veryfast",
                "scale": 1080,
            },
        }
    ]
    try:
        example_path.write_text(json.dumps(example, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
