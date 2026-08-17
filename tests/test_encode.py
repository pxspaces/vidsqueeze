"""Video job planning: sizes, filters and the arithmetic behind file size."""

from __future__ import annotations

import unittest
from pathlib import Path

from vidsqueeze.encode import JobSpec, _scaled_dimensions
from vidsqueeze.probe import MediaInfo


def video(width=1920, height=1080, duration=60.0, size_bytes=100_000_000):
    return MediaInfo(
        path=Path("clip.mp4"), size_bytes=size_bytes, duration=duration,
        container="mov,mp4,m4a", has_video=True, has_audio=True,
        video_codec="h264", width=width, height=height, fps=30.0, frame_count=1800,
    )


class ScaledDimensionsStayEven(unittest.TestCase):
    """Odd dimensions make AV1 and AVIF write an empty file and report success."""

    def test_computed_sizes_are_even(self):
        # 1440x1080 down to a 719 shorter side is deliberately awkward.
        for target in (719, 721, 1081, 337):
            with self.subTest(target=target):
                spec = JobSpec(scale=target)
                width, height = _scaled_dimensions(spec, video(1440, 1080))
                self.assertEqual(width % 2, 0, f"{width} is odd")
                self.assertEqual(height % 2, 0, f"{height} is odd")

    def test_explicit_sizes_are_also_forced_even(self):
        """A custom preset may name an odd number. It must not reach ffmpeg."""
        spec = JobSpec(scale_exact=(801, 601))
        self.assertEqual(_scaled_dimensions(spec, video()), (800, 600))

    def test_explicit_even_sizes_are_left_alone(self):
        spec = JobSpec(scale_exact=(1280, 720))
        self.assertEqual(_scaled_dimensions(spec, video()), (1280, 720))

    def test_never_collapses_to_zero(self):
        spec = JobSpec(scale_exact=(1, 1))
        self.assertEqual(_scaled_dimensions(spec, video()), (2, 2))

    def test_no_scaling_asked_for_means_no_filter(self):
        self.assertIsNone(_scaled_dimensions(JobSpec(), video()))

    def test_already_the_right_size_means_no_filter(self):
        self.assertIsNone(_scaled_dimensions(JobSpec(scale=1080), video(1920, 1080)))

    def test_aspect_ratio_is_kept(self):
        width, height = _scaled_dimensions(JobSpec(scale=720), video(1920, 1080))
        self.assertEqual((width, height), (1280, 720))

    def test_portrait_scales_on_its_shorter_side(self):
        width, height = _scaled_dimensions(JobSpec(scale=720), video(1080, 1920))
        self.assertEqual((width, height), (720, 1280))


class BitrateArithmetic(unittest.TestCase):
    """ffprobe reports bits per second. A units mix-up once made the file size
    ceiling a silent no-op."""

    def test_overall_bitrate_matches_size_over_duration(self):
        info = video(size_bytes=12_000_000, duration=96.0)
        self.assertEqual(info.overall_bitrate, 1_000_000)

    def test_zero_duration_does_not_divide(self):
        self.assertEqual(video(duration=0.0).overall_bitrate, 0)
