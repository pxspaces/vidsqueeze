"""Carrying the camera, the lens and the date across a conversion.

ffmpeg writes pixels and nothing else for stills, so without this a converted
photograph is stamped with the day it was converted and a shoot loses the order
it was taken in. That is quiet, permanent damage to somebody's photographs, so
these cases are worth more than their length suggests.
"""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from halveit import metadata
from halveit.metadata import (ASCII, DATETIME_ORIGINAL, EXPOSURE_TIME, ISO, LENS_MODEL,
                                 MAKE, MODEL, ORIENTATION, RATIONAL, SHORT)
from halveit.probe import _exif_orientation

from .support import make_test_image, needs_ffmpeg, tools

SAMPLE = {
    MAKE: (ASCII, ["Canon"]),
    MODEL: (ASCII, ["Canon EOS 6D Mark II"]),
    DATETIME_ORIGINAL: (ASCII, ["2026:08:15 16:53:14"]),
    EXPOSURE_TIME: (RATIONAL, [(1, 160)]),
    ISO: (SHORT, [1000]),
    LENS_MODEL: (ASCII, ["EF24-70mm f/2.8L II USM"]),
}


def jpeg_with(fields: dict, target: Path) -> Path:
    """A real JPEG carrying the given details."""
    make_test_image(target, size="64x48")
    assert metadata.splice_into_jpeg(target, metadata.build_block(fields))
    return target



def setUpModule():
    """Skip the whole module in a build that does not offer pictures."""
    from halveit import features
    if not features.images_enabled():
        raise unittest.SkipTest("this build does not offer pictures")

class BlockSurvivesARoundTrip(unittest.TestCase):
    @needs_ffmpeg
    def test_every_field_comes_back(self):
        with tempfile.TemporaryDirectory() as work:
            path = jpeg_with(SAMPLE, Path(work) / "x.jpg")
            back = metadata.read(path)
            for tag, (kind, values) in SAMPLE.items():
                with self.subTest(tag=hex(tag)):
                    self.assertIn(tag, back)
                    self.assertEqual(back[tag][1], values)

    @needs_ffmpeg
    def test_the_result_is_still_a_readable_image(self):
        """A malformed block would make the file unopenable, which would be a
        far worse outcome than losing the details it was trying to save."""
        with tempfile.TemporaryDirectory() as work:
            from .support import probe_pix_fmt
            path = jpeg_with(SAMPLE, Path(work) / "x.jpg")
            self.assertNotEqual(probe_pix_fmt(path), "")

    @needs_ffmpeg
    def test_splicing_twice_replaces_rather_than_stacks(self):
        with tempfile.TemporaryDirectory() as work:
            path = jpeg_with(SAMPLE, Path(work) / "x.jpg")
            first_size = path.stat().st_size
            first_fields = metadata.read(path)

            metadata.splice_into_jpeg(path, metadata.build_block(SAMPLE))

            self.assertEqual(path.stat().st_size, first_size, "a second block was added")
            self.assertEqual(metadata.read(path), first_fields)
            self.assertEqual(_exif_orientation(path), 1)


class RotationIsNotAppliedTwice(unittest.TestCase):
    """The pixels have already been turned by the time the details are written.
    Carrying the original orientation across would turn them again in every
    viewer that honours it."""

    @needs_ffmpeg
    def test_orientation_is_written_upright(self):
        with tempfile.TemporaryDirectory() as work:
            sideways = dict(SAMPLE)
            sideways[ORIENTATION] = (SHORT, [6])
            path = jpeg_with(sideways, Path(work) / "x.jpg")
            self.assertEqual(_exif_orientation(path), 1)


class Timestamps(unittest.TestCase):
    @needs_ffmpeg
    def test_the_date_taken_becomes_the_file_date(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = jpeg_with(SAMPLE, work / "source.jpg")
            output = make_test_image(work / "out.png", size="64x48")
            os.utime(output, (time.time(), time.time()))

            metadata.carry(source, output)

            from datetime import datetime
            expected = datetime.strptime("2026:08:15 16:53:14", "%Y:%m:%d %H:%M:%S").timestamp()
            self.assertAlmostEqual(output.stat().st_mtime, expected, delta=2)

    @needs_ffmpeg
    def test_without_a_date_the_source_file_date_is_used(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = make_test_image(work / "source.png", size="64x48")
            output = make_test_image(work / "out.png", size="64x48")
            old = time.time() - 86_400
            os.utime(source, (old, old))

            metadata.carry(source, output)
            self.assertAlmostEqual(output.stat().st_mtime, old, delta=2)


class NeverBreaksAConversion(unittest.TestCase):
    """A conversion that worked must not be reported as a failure because a
    date could not be copied."""

    def test_unreadable_source_is_survivable(self):
        self.assertEqual(metadata.read(Path("/nowhere/at/all.jpg")), {})

    def test_a_file_that_is_not_an_image_is_survivable(self):
        with tempfile.TemporaryDirectory() as work:
            junk = Path(work) / "junk.jpg"
            junk.write_bytes(b"this is not a JPEG")
            self.assertEqual(metadata.read(junk), {})
            self.assertIsInstance(metadata.carry(junk, junk), str)

    def test_truncated_jpeg_is_survivable(self):
        with tempfile.TemporaryDirectory() as work:
            cut = Path(work) / "cut.jpg"
            cut.write_bytes(b"\xff\xd8\xff\xe1\x00\x40Exif\x00\x00II*\x00")
            self.assertEqual(metadata.read(cut), {})

    def test_carry_into_a_missing_output_does_not_raise(self):
        with tempfile.TemporaryDirectory() as work:
            source = Path(work) / "s.jpg"
            source.write_bytes(b"\xff\xd8\xff\xd9")
            self.assertIsInstance(metadata.carry(source, Path(work) / "gone.jpg"), str)


class TheWholePipelineCarriesThem(unittest.TestCase):
    """The cases above exercise the module directly, which proves the module and
    nothing else. This one goes through a real conversion, which is what a user
    actually does, and is the case that fails if the wiring is dropped."""

    @needs_ffmpeg
    def test_converting_a_photograph_keeps_its_details(self):
        from halveit.encode import JobSpec, encode_one

        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = jpeg_with(SAMPLE, work / "shot.jpg")
            out_dir = work / "out"
            out_dir.mkdir()

            job = encode_one(tools(), source, JobSpec(image_format="jpeg"), out_dir)
            self.assertTrue(job.ok, job.message)

            carried = metadata.read(job.output)
            self.assertEqual(carried.get(MODEL, (None, [None]))[1], ["Canon EOS 6D Mark II"])
            self.assertEqual(carried.get(LENS_MODEL, (None, [None]))[1],
                             ["EF24-70mm f/2.8L II USM"])

            from datetime import datetime
            expected = datetime.strptime("2026:08:15 16:53:14", "%Y:%m:%d %H:%M:%S").timestamp()
            self.assertAlmostEqual(job.output.stat().st_mtime, expected, delta=2)

    @needs_ffmpeg
    def test_asking_to_strip_them_actually_strips_them(self):
        from halveit.encode import JobSpec, encode_one

        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = jpeg_with(SAMPLE, work / "shot.jpg")
            out_dir = work / "out"
            out_dir.mkdir()

            spec = JobSpec(image_format="jpeg")
            spec.keep_metadata = False
            job = encode_one(tools(), source, spec, out_dir)
            self.assertTrue(job.ok, job.message)
            self.assertEqual(metadata.read(job.output), {},
                             "details were kept despite being asked to strip them")


class BigEndianFilesAreReadToo(unittest.TestCase):
    """Nikon and others write the other byte order. Reading only one would
    silently lose everything from half the cameras on the market."""

    def test_motorola_order_is_understood(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "mm.tif"
            # MM header, one entry: Make = "Nikon", stored inline.
            path.write_bytes(
                b"MM\x00\x2a\x00\x00\x00\x08"
                b"\x00\x01"
                b"\x01\x0f" b"\x00\x02" b"\x00\x00\x00\x06"
                b"\x00\x00\x00\x1a"
                b"\x00\x00\x00\x00"
                b"Nikon\x00"
            )
            self.assertEqual(metadata.read(path).get(MAKE, (None, [None]))[1], ["Nikon"])
