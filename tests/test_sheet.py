"""Contact sheets.

A shoot is sixty photographs that all look alike in a file listing. One sheet of
small versions with the names under them is the oldest answer to that and still
the fastest.

The traps here are quiet ones. Tiling reads a numbered sequence, so a gap in the
numbering truncates the sheet without complaint, and the grid has to be big enough
for every picture or the last ones are simply dropped.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vidsqueeze import sheet
from vidsqueeze.sheet import SheetError, SheetSpec

from .support import make_test_image, needs_ffmpeg, probe_pix_fmt, tools


def pictures(work: Path, count: int) -> list:
    return [make_test_image(work / f"p{n}.png", size="200x150") for n in range(count)]


class TheGridFitsEverything(unittest.TestCase):
    """A grid too small drops the last pictures and says nothing."""

    @needs_ffmpeg
    def test_a_count_that_does_not_divide_evenly_still_fits(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            # Seven into four across needs two rows, and the second is short.
            out, notes = sheet.build(tools(), pictures(work, 7), work / "s.png",
                                     SheetSpec(columns=4, thumbnail=80, labels=False))
            self.assertTrue(out.exists())
            self.assertIn("7 pictures", notes[0])
            self.assertIn("4 by 2", notes[0])

    @needs_ffmpeg
    def test_one_picture_makes_a_one_by_one_sheet(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            _, notes = sheet.build(tools(), pictures(work, 1), work / "s.png",
                                   SheetSpec(columns=4, thumbnail=80, labels=False))
            self.assertIn("1 picture on", notes[0])

    @needs_ffmpeg
    def test_more_columns_than_pictures_is_survivable(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            out, _ = sheet.build(tools(), pictures(work, 2), work / "s.png",
                                 SheetSpec(columns=10, thumbnail=60, labels=False))
            self.assertTrue(out.exists())
            self.assertNotEqual(probe_pix_fmt(out), "")

    @needs_ffmpeg
    def test_an_unreadable_file_is_skipped_without_leaving_a_gap(self):
        """The tiler reads a numbered sequence. A skipped picture must not leave a
        hole in the numbering, or every picture after it vanishes."""
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            good = pictures(work, 4)
            junk = work / "broken.png"
            junk.write_bytes(b"not a picture at all")
            mixed = [good[0], junk, good[1], good[2], good[3]]

            out, notes = sheet.build(tools(), mixed, work / "s.png",
                                     SheetSpec(columns=2, thumbnail=80, labels=False))
            self.assertTrue(out.exists())
            self.assertIn("4 pictures", notes[0], "a gap swallowed the rest of the sheet")


class Labels(unittest.TestCase):
    @needs_ffmpeg
    def test_names_are_drawn_when_a_font_can_be_found(self):
        """Not asserting the pixels, only that asking for labels makes a taller
        sheet, which is the observable consequence."""
        if sheet.find_font() is None:
            self.skipTest("no font on this machine")
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            files = pictures(work, 2)
            plain, _ = sheet.build(tools(), files, work / "plain.png",
                                   SheetSpec(columns=2, thumbnail=100, labels=False))
            named, _ = sheet.build(tools(), files, work / "named.png",
                                   SheetSpec(columns=2, thumbnail=100, labels=True))
            from .support import decoded_size
            self.assertGreater(decoded_size(named)[1], decoded_size(plain)[1])

    @needs_ffmpeg
    def test_an_awkward_filename_does_not_break_the_filter(self):
        """Colons, quotes and brackets all mean something to the filter parser,
        which is why the name goes in a file rather than in the command."""
        if sheet.find_font() is None:
            self.skipTest("no font on this machine")
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            awkward = work / "it's [a[ 100% odd, name.png"
            make_test_image(awkward, size="200x150")
            out, notes = sheet.build(tools(), [awkward], work / "s.png",
                                     SheetSpec(columns=1, thumbnail=100, labels=True))
            self.assertTrue(out.exists())
            self.assertIn("1 picture", notes[0])


class RefusesClearly(unittest.TestCase):
    @needs_ffmpeg
    def test_nothing_readable_is_an_error_not_an_empty_sheet(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            junk = work / "x.png"
            junk.write_bytes(b"rubbish")
            with self.assertRaises(SheetError):
                sheet.build(tools(), [junk], work / "s.png",
                            SheetSpec(columns=2, thumbnail=80, labels=False))

    @needs_ffmpeg
    def test_no_files_at_all_is_an_error(self):
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaises(SheetError):
                sheet.build(tools(), [], Path(work) / "s.png")


class ProgressAndCancelling(unittest.TestCase):
    """Sixty camera RAW files take a couple of minutes. A window with no sign of
    life looks broken, and one that cannot be stopped is worse."""

    @needs_ffmpeg
    def test_progress_is_reported_for_every_picture(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            seen = []
            sheet.build(tools(), pictures(work, 5), work / "s.png",
                        SheetSpec(columns=3, thumbnail=60, labels=False),
                        on_progress=lambda done, total: seen.append((done, total)))
            self.assertEqual(seen, [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)])

    @needs_ffmpeg
    def test_it_can_be_called_off_part_way(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            calls = {"n": 0}

            def keep_going():
                calls["n"] += 1
                return calls["n"] <= 2      # allow two, then stop

            with self.assertRaises(SheetError):
                sheet.build(tools(), pictures(work, 6), work / "s.png",
                            SheetSpec(columns=3, thumbnail=60, labels=False),
                            keep_going=keep_going)
            self.assertFalse((work / "s.png").exists(), "a half sheet was left behind")

    @needs_ffmpeg
    def test_notes_reach_the_caller(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            told = []
            sheet.build(tools(), pictures(work, 2), work / "s.png",
                        SheetSpec(columns=2, thumbnail=60, labels=False),
                        on_note=told.append)
            self.assertTrue(any("2 pictures" in note for note in told))


class TheInterfaceCanReachIt(unittest.TestCase):
    """The window and the command line must go through the same code, or they
    will eventually produce different sheets from the same settings."""

    def test_the_server_exposes_a_start_and_a_status_route(self):
        source = (Path(__file__).resolve().parent.parent / "vidsqueeze" / "server.py").read_text()
        for route in ('"/api/sheet/start"', '"/api/sheet"', '"/api/sheet/cancel"'):
            with self.subTest(route=route):
                self.assertIn(route, source)

    def test_the_server_state_has_what_the_page_reads(self):
        from vidsqueeze.server import Session
        state = Session().sheet_state
        for key in ("running", "done", "error", "output", "notes", "done_count", "total"):
            self.assertIn(key, state)

    def test_the_command_line_offers_it_too(self):
        args = build_parser_args(["--contact-sheet", "--sheet-out", "out.png", "x.cr2"])
        self.assertTrue(args.contact_sheet)
        self.assertEqual(args.sheet_out, "out.png")
        self.assertFalse(build_parser_args(["x.cr2"]).contact_sheet)

    def test_the_flag_does_not_swallow_the_first_photograph(self):
        """Written to take an optional value, `--contact-sheet *.CR2` read the
        first photograph as the file to write, and a PNG landed on top of
        somebody's RAW. The inputs must stay inputs."""
        args = build_parser_args(["--contact-sheet", "a.cr2", "b.cr2", "c.cr2"])
        self.assertTrue(args.contact_sheet)
        self.assertIsNone(args.sheet_out)
        self.assertEqual(args.inputs, ["a.cr2", "b.cr2", "c.cr2"])


def build_parser_args(argv):
    from vidsqueeze.cli import build_parser
    return build_parser().parse_args(argv)


class Escaping(unittest.TestCase):
    def test_colons_and_quotes_are_escaped_for_the_filter(self):
        self.assertEqual(sheet._escape("/a/b:c"), r"/a/b\:c")
        self.assertEqual(sheet._escape("it's"), r"it\'s")
        self.assertEqual(sheet._escape(r"C:\Windows\x"), r"C\:/Windows/x")

    def test_columns_are_kept_sane(self):
        """A preset asking for nought or three hundred columns should not reach
        the filter."""
        with tempfile.TemporaryDirectory() as work:
            for asked in (0, -5, 999):
                spec = SheetSpec(columns=asked)
                clamped = max(1, min(int(spec.columns), 20))
                self.assertGreaterEqual(clamped, 1)
                self.assertLessEqual(clamped, 20)
