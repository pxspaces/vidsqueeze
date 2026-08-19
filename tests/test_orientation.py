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

from halveit import images
from halveit.images import ImageSpec
from halveit.probe import probe

from .support import decoded_size, fake_image_info, make_oriented_jpeg, needs_ffmpeg, tools

#: EXIF orientations that put the long side the other way round.
SWAPPING = (5, 6, 7, 8)
UPRIGHT = (1, 2, 3, 4)



def setUpModule():
    """Skip the whole module in a build that does not offer pictures."""
    from halveit import features
    if not features.images_enabled():
        raise unittest.SkipTest("this build does not offer pictures")

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


class EveryFormatThatCanRecordItIsRead(unittest.TestCase):
    """Four formats keep this note in four different places. A reader that only
    understands JPEG gets the other three silently wrong, because ffmpeg rotates
    them and says nothing. PNG was missed the first time round.
    """

    def test_png_exif_chunk_is_read(self):
        from halveit.metadata import build_block
        from halveit.probe import _exif_orientation
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "x.png"
            block = build_block({0x0112: (3, [6])})
            # Minimal PNG: signature, then an eXIf chunk, then IHDR-ish filler.
            chunk = (len(block).to_bytes(4, "big") + b"eXIf" + block + b"\x00\x00\x00\x00")
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk)
            # build_block normalises orientation to upright, so read what it wrote.
            self.assertEqual(_exif_orientation(path), 1)

    def test_a_png_carrying_a_sideways_flag_is_understood(self):
        """Written by hand, because the block builder deliberately writes
        upright and this needs the awkward case."""
        from halveit.probe import _exif_orientation
        from .support import exif_orientation_block
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "y.png"
            app1 = exif_orientation_block(6)
            tiff = app1[10:]                     # strip the JPEG marker and Exif\0\0
            chunk = len(tiff).to_bytes(4, "big") + b"eXIf" + tiff + b"\x00\x00\x00\x00"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk)
            self.assertEqual(_exif_orientation(path), 6)

    def test_pixel_data_stops_the_search(self):
        """A reader that keeps going past IDAT is reading compressed pixels as
        if they were headers."""
        from halveit.probe import _exif_orientation
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "z.png"
            idat = (4).to_bytes(4, "big") + b"IDAT" + b"\x00" * 4 + b"\x00" * 4
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + idat + b"\xff" * 64)
            self.assertEqual(_exif_orientation(path), 0)

    def test_rubbish_does_not_raise(self):
        from halveit.probe import _exif_orientation
        with tempfile.TemporaryDirectory() as work:
            for name, data in (("a.png", b"\x89PNG\r\n\x1a\n"),
                               ("b.webp", b"RIFF\x00\x00\x00\x00WEBP"),
                               ("c.jpg", b"\xff\xd8")):
                path = Path(work) / name
                path.write_bytes(data)
                self.assertEqual(_exif_orientation(path), 0, name)


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
    from halveit.deps import Tools

    return Tools(ffmpeg=Path("ffmpeg"), ffprobe=Path("ffprobe"), version="9.0",
                 encoders=frozenset({"mjpeg", "png", "libwebp", "libsvtav1", "tiff", "bmp"}),
                 source="system")


class TheCameraPreviewIsNotLeftSideways(unittest.TestCase):
    """When no RAW decoder is installed, the camera's own preview is used. Which
    way up it goes is recorded in the RAW's directory, not inside the preview, so
    the extracted bytes say nothing about rotation. Every portrait photograph came
    out sideways on exactly the machines that depend on this path."""

    def test_the_orientation_is_carried_into_the_preview(self):
        from halveit import metadata
        from halveit.probe import _exif_orientation
        with tempfile.TemporaryDirectory() as work:
            preview = Path(work) / "p.jpg"
            from .support import make_test_image
            make_test_image(preview, size="80x60")
            self.assertEqual(_exif_orientation(preview), 0, "nothing to start with")
            metadata.splice_into_jpeg(preview, metadata.orientation_block(8))
            self.assertEqual(_exif_orientation(preview), 8)

    def test_an_orientation_block_records_what_it_is_given(self):
        """Unlike build_block, which forces upright because the pixels it
        describes have already been turned. Two opposite jobs, two functions."""
        from halveit import metadata
        from halveit.probe import _exif_orientation
        with tempfile.TemporaryDirectory() as work:
            for wanted in (1, 3, 6, 8):
                path = Path(work) / f"o{wanted}.jpg"
                from .support import make_test_image
                make_test_image(path, size="60x40")
                metadata.splice_into_jpeg(path, metadata.orientation_block(wanted))
                self.assertEqual(_exif_orientation(path), wanted)

    def test_build_block_still_forces_upright(self):
        from halveit import metadata
        from halveit.probe import _exif_orientation
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "dev.jpg"
            from .support import make_test_image
            make_test_image(path, size="60x40")
            metadata.splice_into_jpeg(path, metadata.build_block({0x0112: (3, [6])}))
            self.assertEqual(_exif_orientation(path), 1)

    def test_rubbish_orientation_falls_back_to_upright(self):
        from halveit import metadata
        from halveit.probe import _exif_orientation
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "bad.jpg"
            from .support import make_test_image
            make_test_image(path, size="60x40")
            metadata.splice_into_jpeg(path, metadata.orientation_block(99))
            self.assertEqual(_exif_orientation(path), 1)
