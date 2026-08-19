"""Telling the user a file will get bigger, before it does.

"The result is not smaller" fired on every RAW to PNG conversion. It was true,
unavoidable, and read like a fault in the program rather than a property of the
format the user had chosen. Said beforehand it is useful, because there is still
a choice to make.

There is one implementation of this, in images.py, reached by both the command
line and the window. Two implementations would eventually disagree, and the one
the user saw would be whichever they happened to be looking at.
"""

from __future__ import annotations

import unittest

from halveit import images
from halveit.encode import JobSpec, image_spec_of
from halveit.images import ImageSpec


def note(fmt="png", quality=82, lossless=False, source="jpeg", is_raw=False) -> str:
    spec = ImageSpec(image_format=fmt, quality=quality, lossless=lossless)
    return images.size_expectation(spec, source, is_raw=is_raw)



def setUpModule():
    """Skip the whole module in a build that does not offer pictures."""
    from halveit import features
    if not features.images_enabled():
        raise unittest.SkipTest("this build does not offer pictures")

class WarnsWhereItWillGrow(unittest.TestCase):
    def test_raw_to_png(self):
        self.assertIn("larger", note(fmt="png", is_raw=True))

    def test_raw_to_png_at_full_depth_says_several_times(self):
        self.assertIn("several times", note(fmt="png", quality=95, is_raw=True))

    def test_raw_to_tiff(self):
        self.assertTrue(note(fmt="tiff", is_raw=True))

    def test_an_already_compressed_photograph_to_png(self):
        self.assertIn("already compressed", note(fmt="png", source="jpeg"))

    def test_heic_to_png(self):
        self.assertTrue(note(fmt="png", source="heic"))

    def test_lossless_webp_from_a_compressed_source(self):
        self.assertTrue(note(fmt="webp", lossless=True, source="jpeg"))


class StaysQuietWhereItWillNot(unittest.TestCase):
    """A warning on every conversion is a warning nobody reads."""

    def test_raw_to_jpeg(self):
        self.assertEqual(note(fmt="jpeg", is_raw=True), "")

    def test_raw_to_webp(self):
        self.assertEqual(note(fmt="webp", is_raw=True), "")

    def test_raw_to_avif(self):
        self.assertEqual(note(fmt="avif", is_raw=True), "")

    def test_lossy_webp_from_a_compressed_source(self):
        self.assertEqual(note(fmt="webp", lossless=False, source="jpeg"), "")

    def test_png_from_an_uncompressed_source(self):
        """PNG from a BMP or another PNG is not news."""
        self.assertEqual(note(fmt="png", source="bmp"), "")

    def test_jpeg_from_jpeg(self):
        self.assertEqual(note(fmt="jpeg", source="jpeg"), "")


class TheAdviceIsActionable(unittest.TestCase):
    """A warning that does not say what to do instead is just bad news."""

    def test_raw_to_png_names_a_smaller_format(self):
        text = note(fmt="png", is_raw=True)
        self.assertTrue(any(name in text for name in ("JPEG", "WebP", "AVIF")))

    def test_full_depth_warning_mentions_the_quality_threshold(self):
        self.assertIn(str(images.FULL_CHROMA_FROM), note(fmt="png", quality=95, is_raw=True))

    def test_no_long_dashes_anywhere_in_the_wording(self):
        """House style, and these strings go straight to the user.

        The two characters are written as escapes rather than themselves,
        because the publishing script greps every published file for them and
        this file is published. Spelling them out here would block a release.
        """
        banned = ("\u2014", "\u2013")   # em dash, en dash
        for fmt in ("png", "tiff"):
            for quality in (82, 95):
                for is_raw in (True, False):
                    text = note(fmt=fmt, quality=quality, is_raw=is_raw)
                    for character in banned:
                        self.assertNotIn(character, text)


class ReachableFromAJob(unittest.TestCase):
    def test_a_job_spec_converts_into_something_this_can_read(self):
        spec = JobSpec()
        spec.image_format = "png"
        spec.image_quality = 95
        self.assertIn("several times",
                      images.size_expectation(image_spec_of(spec), "", is_raw=True))
