"""Still image conversion: what the command says, and what the file proves.

The command tests run anywhere. The output tests actually encode something and
measure it, because a pixel format that looks right in a command line can still
destroy the picture, and only measuring catches that.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from halveit import images
from halveit.images import ImageSpec

from .support import (arg_after, fake_image_info, make_test_image, needs_ffmpeg,
                      probe_pix_fmt, psnr, run_command, tools)



def setUpModule():
    """Skip the whole module in a build that does not offer pictures."""
    from halveit import features
    if not features.images_enabled():
        raise unittest.SkipTest("this build does not offer pictures")

class PixelFormatChoice(unittest.TestCase):
    """Forcing a pixel format is occasionally necessary and frequently
    harmful, so the default answer has to be "leave it alone"."""

    def test_lossless_webp_is_never_given_a_pixel_format(self):
        chosen = images.pixel_format(
            ImageSpec(image_format="webp", lossless=True), fake_image_info()
        )
        self.assertIsNone(chosen, "yuv420p makes lossless WebP neither lossless nor small")

    def test_lossless_jxl_is_never_given_a_pixel_format(self):
        chosen = images.pixel_format(
            ImageSpec(image_format="jxl", lossless=True), fake_image_info()
        )
        self.assertIsNone(chosen)

    def test_lossy_webp_is_left_to_ffmpeg(self):
        chosen = images.pixel_format(
            ImageSpec(image_format="webp", lossless=False), fake_image_info()
        )
        self.assertIsNone(chosen)

    def test_jpeg_keeps_full_colour_at_high_quality(self):
        self.assertEqual(
            images.pixel_format(ImageSpec(image_format="jpeg", quality=95), fake_image_info()),
            "yuvj444p",
        )

    def test_jpeg_subsamples_at_ordinary_quality(self):
        self.assertEqual(
            images.pixel_format(ImageSpec(image_format="jpeg", quality=82), fake_image_info()),
            "yuvj420p",
        )

    def test_png_depth_follows_quality(self):
        info = fake_image_info()
        self.assertEqual(
            images.pixel_format(ImageSpec(image_format="png", quality=82), info), "rgb24"
        )
        self.assertIsNone(
            images.pixel_format(ImageSpec(image_format="png", quality=95), info),
            "at high quality a 16 bit source should keep all 16 bits",
        )

    def test_png_with_transparency_keeps_its_alpha(self):
        info = fake_image_info(has_alpha=True)
        self.assertEqual(
            images.pixel_format(ImageSpec(image_format="png", quality=82), info), "rgba"
        )


class LosslessMeansLossless(unittest.TestCase):
    """The claim that gave this suite its reason to exist."""

    @needs_ffmpeg
    def test_lossless_webp_reproduces_the_source_exactly(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = make_test_image(work / "source.png")
            info = fake_image_info(width=640, height=480, path=str(source))
            spec = ImageSpec(image_format="webp", lossless=True)
            output = work / "out.webp"

            command, _ = images.build_command(spec, info, tools(), output)
            result = run_command(command)
            self.assertEqual(result.returncode, 0, result.stderr)

            score = psnr(source, output)
            self.assertEqual(
                score, float("inf"),
                f"lossless WebP scored {score} dB, so it is not lossless",
            )

    @needs_ffmpeg
    def test_forcing_subsampling_would_break_it(self):
        """Proves the failure the fix prevents, so nobody reintroduces it
        believing it is harmless."""
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = make_test_image(work / "source.png")
            output = work / "bad.webp"
            kit = tools()
            run_command([kit.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                         "-i", source, "-c:v", "libwebp", "-lossless", "1",
                         "-pix_fmt", "yuv420p", "-frames:v", "1", "-update", "1", output])
            self.assertLess(
                psnr(source, output), 60.0,
                "forcing yuv420p should visibly damage the image; if this passes "
                "the encoder has changed and the rule may be worth revisiting",
            )


class ColourDetail(unittest.TestCase):
    @needs_ffmpeg
    def test_high_quality_jpeg_keeps_more_colour_than_ordinary(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = make_test_image(work / "source.png")
            info = fake_image_info(width=640, height=480, path=str(source))

            scores = {}
            for quality, name in ((82, "ordinary.jpg"), (95, "high.jpg")):
                output = work / name
                command, _ = images.build_command(
                    ImageSpec(image_format="jpeg", quality=quality), info, tools(), output
                )
                self.assertEqual(run_command(command).returncode, 0)
                scores[quality] = psnr(source, output)

            self.assertGreater(
                scores[95], scores[82],
                "4:4:4 at high quality should measure better than 4:2:0",
            )


class OutputsAreRealFiles(unittest.TestCase):
    """An encoder that writes nothing at all has shipped here before."""

    @needs_ffmpeg
    def test_every_available_format_produces_a_readable_image(self):
        kit = tools()
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = make_test_image(work / "source.png")
            info = fake_image_info(width=640, height=480, path=str(source))

            for fmt in images.available_formats(kit):
                with self.subTest(fmt=fmt):
                    extension = images.IMAGE_FORMATS[fmt]["ext"]
                    output = work / f"out.{extension}"
                    command, _ = images.build_command(
                        ImageSpec(image_format=fmt), info, kit, output
                    )
                    result = run_command(command)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue(output.exists(), f"{fmt} wrote no file")
                    self.assertGreater(output.stat().st_size, 64, f"{fmt} wrote an empty file")
                    self.assertNotEqual(probe_pix_fmt(output), "", f"{fmt} is not readable")

    @needs_ffmpeg
    def test_odd_target_width_still_produces_a_real_file(self):
        """The AVIF failure that looked like a codec problem and was actually an
        odd height from `scale=W:-1`."""
        kit = tools()
        if "avif" not in images.available_formats(kit):
            self.skipTest("no AV1 encoder in this build")
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = make_test_image(work / "source.png", size="801x601")
            info = fake_image_info(width=801, height=601, path=str(source))
            output = work / "odd.avif"
            command, _ = images.build_command(
                ImageSpec(image_format="avif", max_dimension=399), info, kit, output
            )
            result = run_command(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertGreater(output.stat().st_size, 64, "AVIF wrote an empty file again")


class Flattening(unittest.TestCase):
    def test_transparency_is_flattened_only_where_it_must_be(self):
        transparent = fake_image_info(has_alpha=True)
        command, notes = images.build_command(
            ImageSpec(image_format="jpeg"), transparent, _stub(), Path("o.jpg")
        )
        self.assertIn("-filter_complex", [str(part) for part in command])
        self.assertTrue(any("background" in note for note in notes))

    def test_alpha_capable_formats_are_left_alone(self):
        transparent = fake_image_info(has_alpha=True)
        command, _ = images.build_command(
            ImageSpec(image_format="png"), transparent, _stub(), Path("o.png")
        )
        self.assertNotIn("-filter_complex", [str(part) for part in command])


def _stub():
    from halveit.deps import Tools

    return Tools(ffmpeg=Path("ffmpeg"), ffprobe=Path("ffprobe"), version="9.0",
                 encoders=frozenset({"mjpeg", "png", "libwebp", "libsvtav1", "tiff", "bmp"}),
                 source="system")
