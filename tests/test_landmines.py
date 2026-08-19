"""One test per known way this program has broken before.

Every one of these pins a bug that actually shipped, or that was one careless
edit away from shipping. Each carries the reason in its own docstring, because
a failing test here usually looks like a test that is simply wrong: the obvious
fix is generally the very thing that caused the original bug. Read the reason
before changing the assertion.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from halveit import images, raw
from halveit.images import ImageSpec

from .support import arg_after, fake_image_info

WEB = Path(__file__).resolve().parent.parent / "halveit" / "web"
SOURCE = Path(__file__).resolve().parent.parent / "halveit"


class ScalingKeepsEvenDimensions(unittest.TestCase):
    """Odd dimensions make AVIF and AV1 write an empty file, silently."""

    def test_image_scaling_never_uses_minus_one(self):
        info = fake_image_info(width=4000, height=3000)
        spec = ImageSpec(image_format="avif", max_dimension=1999)
        command, _ = images.build_command(spec, info, _tools(), Path("out.avif"))
        chain = " ".join(str(part) for part in command)
        self.assertIn("scale=1999:-2", chain)
        self.assertNotIn(":-1", chain)

    def test_no_source_file_scales_with_minus_one(self):
        """A grep, deliberately. It catches the mistake in code paths no test
        happens to exercise, which is exactly where it hid last time."""
        offenders = []
        for path in SOURCE.rglob("*.py"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(r"scale=[^\"',]*:-1(?![0-9])", line):
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
        self.assertEqual(offenders, [], "scale with -1 rounds to odd heights, use -2")


class HiddenAttributeStillWins(unittest.TestCase):
    """`display: grid` beats a bare `hidden` attribute, which once left a modal
    covering the whole interface."""

    def test_stylesheet_forces_hidden_to_none(self):
        css = (WEB / "style.css").read_text()
        self.assertRegex(
            css,
            r"\[hidden\]\s*\{\s*display:\s*none\s*!important",
            "the [hidden] override is gone, modals will reappear over the page",
        )


class AvifMuxerRules(unittest.TestCase):
    def test_avif_does_not_get_update_flag(self):
        """`-update 1` makes the AVIF muxer write nothing at all."""
        spec = ImageSpec(image_format="avif")
        command, _ = images.build_command(spec, fake_image_info(), _tools(), Path("o.avif"))
        self.assertNotIn("-update", [str(part) for part in command])
        self.assertEqual(arg_after(command, "-f"), "avif")

    def test_other_formats_do_get_update_flag(self):
        for fmt, ext in (("png", "png"), ("jpeg", "jpg"), ("webp", "webp")):
            with self.subTest(fmt=fmt):
                spec = ImageSpec(image_format=fmt)
                command, _ = images.build_command(spec, fake_image_info(), _tools(), Path(f"o.{ext}"))
                self.assertEqual(arg_after(command, "-update"), "1")

    def test_avif_stays_four_two_zero(self):
        """SVT-AV1 encodes 4:2:0 only. Asking for 4:4:4 fails the conversion."""
        for quality in (50, 95):
            with self.subTest(quality=quality):
                chosen = images.pixel_format(
                    ImageSpec(image_format="avif", quality=quality), fake_image_info()
                )
                self.assertIn(chosen, ("yuv420p", "yuv420p10le"))


class BitrateUnits(unittest.TestCase):
    """ffprobe reports bits per second. Treating it as kilobits once made the
    file size ceiling a silent no-op."""

    def test_overall_bitrate_is_bits_per_second(self):
        info = fake_image_info()
        info.size_bytes = 1_000_000     # 8 million bits
        info.duration = 8.0             # over 8 seconds
        self.assertEqual(info.overall_bitrate, 1_000_000)

    def test_no_duration_gives_zero_rather_than_dividing(self):
        info = fake_image_info()
        info.size_bytes = 1_000_000
        info.duration = 0.0
        self.assertEqual(info.overall_bitrate, 0)


class BrowserOpening(unittest.TestCase):
    """Python's webbrowser module has its own idea of the default browser and it
    is often wrong, so the operating system opener has to be tried first."""

    def test_server_prefers_the_system_opener(self):
        source = (SOURCE / "server.py").read_text()
        self.assertIn("startfile", source)
        self.assertTrue(
            "xdg-open" in source and '"open"' in source,
            "the system opener should be used before falling back to webbrowser",
        )

    def test_webbrowser_is_only_the_fallback(self):
        source = (SOURCE / "server.py").read_text()
        opener = source.index("xdg-open")
        fallback = source.rindex("webbrowser.open")
        self.assertLess(opener, fallback, "webbrowser.open must come last, as a fallback")


class RawDevelopment(unittest.TestCase):
    """The RAW decoders default to settings that quietly ruin the result."""

    def test_develop_asks_for_sixteen_bit(self):
        self.assertIn("-6", raw.DEVELOP_FLAGS, "8 bit throws away most of a 14 bit sensor")

    def test_develop_asks_for_srgb_gamma(self):
        """The default is BT.709, 2.222 4.5, which every viewer misreads as
        sRGB and renders too dark."""
        flags = raw.DEVELOP_FLAGS
        self.assertIn("-g", flags)
        index = flags.index("-g")
        self.assertEqual(flags[index + 1:index + 3], ["2.4", "12.92"])

    def test_develop_asks_for_camera_white_balance(self):
        self.assertIn("-w", raw.DEVELOP_FLAGS)

    def test_staging_keeps_output_out_of_the_source_folder(self):
        """dcraw writes beside its input. Given the user's own file that means
        a large TIFF landing in their photo folder."""
        import tempfile

        with tempfile.TemporaryDirectory() as source_dir, \
             tempfile.TemporaryDirectory() as work_dir:
            original = Path(source_dir) / "shot.cr2"
            original.write_bytes(b"not really a raw file")
            staged = raw._stage(original, Path(work_dir))

            self.assertEqual(staged.parent, Path(work_dir))
            self.assertEqual(staged.suffix, ".cr2")
            self.assertEqual(staged.read_bytes(), original.read_bytes())
            # Whatever the decoder writes beside `staged` lands in work_dir.
            self.assertEqual(list(Path(source_dir).iterdir()), [original])


def _tools():
    """A stand-in toolchain. Command building only reads the ffmpeg path and
    the encoder list, so a real install is not needed here."""
    from halveit.deps import Tools

    return Tools(
        ffmpeg=Path("ffmpeg"), ffprobe=Path("ffprobe"), version="9.0",
        encoders=frozenset({"mjpeg", "png", "libwebp", "libsvtav1", "tiff", "bmp", "libjxl"}),
        source="system",
    )


class TheMacInstructionsCoverBothMacOSGenerations(unittest.TestCase):
    """Apple removed the Control-click override in macOS 15, so instructions that
    only give that route strand anybody on a current Mac. They only strand people
    who downloaded through a **browser**: that is what marks a file as having come
    from the internet, and a clone or a terminal download is not marked at all,
    which is why this went unnoticed. Verified on this machine: a cloned checkout
    carries no quarantine attribute, a curl download carries none either, and one
    that does carry it is refused by spctl but still runs from a terminal.

    A test cannot know when Apple changes something again. What it can do is stop
    somebody tidying one of the two routes away.
    """

    ROOT = Path(__file__).resolve().parent.parent

    def documents(self):
        for name in ("README.md", "USER-GUIDE.md"):
            path = self.ROOT / name
            if path.exists():
                yield name, path.read_text()

    def test_the_newer_route_is_given(self):
        for name, text in self.documents():
            with self.subTest(document=name):
                self.assertIn("Open Anyway", text,
                              f"{name} does not say how to start it on macOS 15 or later")
                self.assertIn("Privacy", text)

    def test_the_older_route_is_still_given(self):
        """Not everyone is on a current Mac."""
        for name, text in self.documents():
            with self.subTest(document=name):
                self.assertRegex(text.lower(), r"right.click",
                                 f"{name} dropped the route for macOS 14 and earlier")

    def test_the_landing_page_says_the_same(self):
        script = self.ROOT / "tools" / "prepare-public.sh"
        if not script.exists():
            self.skipTest("this is the published copy, which does not carry the script")
        text = script.read_text()
        self.assertIn("Open Anyway", text)
        self.assertIn("right click", text.lower())

    def test_nothing_claims_the_right_click_is_required(self):
        """The old wording said you *must* use right click and that double clicking
        gives a warning with no way past it. Both are now wrong."""
        for name, text in self.documents():
            with self.subTest(document=name):
                self.assertNotIn("You must use right-click", text)
                self.assertNotIn("with no way past it", text)
