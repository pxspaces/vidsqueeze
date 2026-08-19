"""The command line.

A setting that exists only in the browser interface cannot be tested, scripted
or reported in a bug. Every image setting the page offers is reachable here too,
and these cases keep it that way.
"""

from __future__ import annotations

import contextlib
import io
import unittest

from halveit.cli import build_parser, spec_from_args


def parse(*argv):
    return spec_from_args(build_parser().parse_args(list(argv)))


@contextlib.contextmanager
def quiet():
    """argparse prints its usage to stderr when it rejects something. That is
    correct behaviour and unwanted noise in a test run."""
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        yield


def _images_on() -> bool:
    from halveit import features
    return features.images_enabled()


@unittest.skipUnless(_images_on(), "this build does not offer pictures")
class ImageOptionsReachTheSpec(unittest.TestCase):
    def test_format(self):
        self.assertEqual(parse("--image-format", "png", "x.cr2").image_format, "png")

    def test_quality(self):
        self.assertEqual(parse("--image-quality", "95", "x.jpg").image_quality, 95)

    def test_lossless(self):
        self.assertTrue(parse("--lossless", "--image-format", "webp", "x.png").image_lossless)

    def test_max_dimension(self):
        self.assertEqual(parse("--max-dimension", "2048", "x.jpg").image_max_dimension, 2048)

    def test_background(self):
        self.assertEqual(parse("--background", "black", "x.png").image_background, "black")

    def test_defaults_are_left_alone_when_nothing_is_asked_for(self):
        spec = parse("x.jpg")
        self.assertEqual(spec.image_format, "jpeg")
        self.assertFalse(spec.image_lossless)
        self.assertIsNone(spec.image_max_dimension)


@unittest.skipUnless(_images_on(), "this build does not offer pictures")
class BadInputIsRefusedClearly(unittest.TestCase):
    """A wrong number should be a sentence, not a traceback."""

    def test_quality_out_of_range(self):
        for value in ("0", "101", "-3"):
            with self.subTest(value=value):
                with quiet(), self.assertRaises(SystemExit):
                    parse("--image-quality", value, "x.jpg")

    def test_lossless_on_a_format_that_cannot_do_it(self):
        with quiet(), self.assertRaises(SystemExit):
            parse("--lossless", "--image-format", "jpeg", "x.jpg")

    def test_lossless_is_accepted_where_it_applies(self):
        for fmt in ("webp", "jxl"):
            with self.subTest(fmt=fmt):
                self.assertTrue(parse("--lossless", "--image-format", fmt, "x.png").image_lossless)

    def test_max_dimension_must_be_positive(self):
        with quiet(), self.assertRaises(SystemExit):
            parse("--max-dimension", "0", "x.jpg")

    def test_unknown_format_is_refused_by_the_parser(self):
        with quiet(), self.assertRaises(SystemExit):
            parse("--image-format", "heic", "x.jpg")
