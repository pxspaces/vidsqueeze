"""Photographs taken with the camera turned sideways.

Almost every phone and camera records a portrait shot as a landscape frame plus
an orientation flag. ffmpeg's decoder honours that flag and hands back a rotated
picture. ffprobe reports the dimensions as stored and mentions the flag nowhere:
no tag, no side data. So anything reasoning about the shape of an image has to
read the flag itself, or it will disagree with the decoder about which side is
the long one.

Getting that wrong does not fail loudly. It quietly resizes the wrong axis, and
enlarges a picture that was supposed to be made smaller.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vidsqueeze import images
from vidsqueeze.images import ImageSpec
from vidsqueeze.probe import probe

from .support import decoded_size, fake_image_info, make_oriented_jpeg, needs_ffmpeg, tools

#: EXIF orientations that put the long side the other way round.
SWAPPING = (5, 6, 7, 8)
UPRIGHT = (1, 2, 3, 4)


class ProbeAgreesWithTheDecoder(unittest.TestCase):
    @needs_ffmpeg
    def test_sideways_photographs_report_their_displayed_shape(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            for orientation in SWAPPING:
                with self.subTest(orientation=orientation):
                    source = make_oriented_jpeg(work / f"o{orientation}.jpg", orientation)
                    info = probe(tools(), source)
                    self.assertEqual(
                        (info.display_width, info.display_height), decoded_size(source),
                        f"orientation {orientation}: probe disagrees with the decoder",
                    )

    @needs_ffmpeg
    def test_upright_photographs_are_left_alone(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            for orientation in UPRIGHT:
                with self.subTest(orientation=orientation):
                    source = make_oriented_jpeg(work / f"o{orientation}.jpg", orientation)
                    info = probe(tools(), source)
                    self.assertEqual((info.display_width, info.display_height), (800, 400))

    @needs_ffmpeg
    def test_a_photograph_with_no_exif_at_all_still_works(self):
        with tempfile.TemporaryDirectory() as work:
            from .support import make_test_image
            source = make_test_image(Path(work) / "plain.png", size="800x400")
            info = probe(tools(), source)
            self.assertEqual((info.display_width, info.display_height), (800, 400))


class LongestSideNeverEnlarges(unittest.TestCase):
    """The documented promise. A sideways photograph broke it: asked to fit
    inside 500 pixels, it came back 1000 pixels tall and four times the size."""

    @needs_ffmpeg
    def test_sideways_photograph_is_shrunk_not_grown(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = make_oriented_jpeg(work / "portrait.jpg", 6)   # displays 400x800
            info = probe(tools(), source)
            output = work / "out.png"

            command, _ = images.build_command(
                ImageSpec(image_format="png", max_dimension=500), info, tools(), output
            )
            from .support import run_command
            self.assertEqual(run_command(command).returncode, 0)

            width, height = decoded_size(output)
            self.assertLessEqual(max(width, height), 500,
                                 f"asked for a longest side of 500, got {width}x{height}")
            self.assertEqual((width, height), (250, 500))

    @needs_ffmpeg
    def test_upright_photograph_is_unaffected(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = make_oriented_jpeg(work / "landscape.jpg", 1)
            info = probe(tools(), source)
            output = work / "out.png"
            command, _ = images.build_command(
                ImageSpec(image_format="png", max_dimension=500), info, tools(), output
            )
            from .support import run_command
            self.assertEqual(run_command(command).returncode, 0)
            self.assertEqual(decoded_size(output), (500, 250))

    def test_the_scaling_axis_follows_the_displayed_shape(self):
        """No encoder needed: the filter itself has to name the right axis."""
        portrait = fake_image_info(width=800, height=400)
        portrait.rotation = 90          # stored landscape, displayed portrait
        command, _ = images.build_command(
            ImageSpec(image_format="png", max_dimension=500), portrait, _stub(), Path("o.png")
        )
        chain = " ".join(str(part) for part in command)
        self.assertIn("scale=-2:500", chain,
                      "a portrait image must be limited on its height")
        self.assertNotIn("scale=500:-2", chain)


def _stub():
    from vidsqueeze.deps import Tools

    return Tools(ffmpeg=Path("ffmpeg"), ffprobe=Path("ffprobe"), version="9.0",
                 encoders=frozenset({"mjpeg", "png", "libwebp", "libsvtav1", "tiff", "bmp"}),
                 source="system")
