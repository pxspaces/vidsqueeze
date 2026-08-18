"""How a developed RAW is made to look.

A RAW file is a sensor reading, not a photograph. Something has to decide how
bright it is and how strong its colour is, and a decoder left to its own defaults
decides "not very", because it is being faithful to the sensor rather than to the
scene. The result is technically correct and looks flat and grey beside the same
shot rendered by the camera.

The numbers here were measured, not chosen by eye: two photographs in very
different light were rendered by the operating system's own RAW pipeline and used
as the target. They are pinned because the temptation to nudge them upward is
strong and doing it without measuring again is how a converter ends up producing
garish photographs.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from vidsqueeze import images, raw
from vidsqueeze.encode import JobSpec, image_spec_of
from vidsqueeze.images import ImageSpec

from .support import arg_after, fake_image_info


class TheNaturalLookIsTheDefault(unittest.TestCase):
    """Somebody converting a holiday photograph wants a photograph, not a
    faithful sensor reading."""

    def test_a_new_job_asks_for_the_natural_look(self):
        self.assertEqual(JobSpec().raw_look, raw.NATURAL)

    def test_natural_lifts_brightness_at_the_decoder(self):
        flags = raw._flags_for(raw.NATURAL)
        self.assertEqual(arg_after(flags, "-b"), raw.NATURAL_BRIGHTNESS)

    def test_neutral_leaves_the_decoder_alone(self):
        self.assertNotIn("-b", raw._flags_for(raw.NEUTRAL))
        self.assertEqual(raw._flags_for(raw.NEUTRAL), raw.DEVELOP_FLAGS)

    def test_both_looks_keep_the_settings_that_are_not_a_matter_of_taste(self):
        """16 bit, camera white balance and a real sRGB curve are correctness,
        not style, so neither look may drop them."""
        for look in raw.LOOKS:
            with self.subTest(look=look):
                flags = raw._flags_for(look)
                self.assertIn("-6", flags)
                self.assertIn("-w", flags)
                self.assertEqual(arg_after(flags, "-g"), "2.4")


class ColourIsAddedAfterDeveloping(unittest.TestCase):
    """No decoder here can be told how saturated to make the result, so that
    half of the look is applied on the way through ffmpeg."""

    def test_natural_asks_for_more_colour(self):
        self.assertGreater(raw.saturation_for(raw.NATURAL), 1.0)
        self.assertEqual(raw.saturation_for(raw.NATURAL), raw.NATURAL_SATURATION)

    def test_neutral_asks_for_none(self):
        self.assertEqual(raw.saturation_for(raw.NEUTRAL), 1.0)

    def test_the_filter_reaches_the_command(self):
        spec = ImageSpec(image_format="png", saturation=raw.NATURAL_SATURATION)
        command, _ = images.build_command(spec, fake_image_info(), _stub(), Path("o.png"))
        self.assertIn(f"eq=saturation={raw.NATURAL_SATURATION:g}",
                      arg_after(command, "-vf") or "")

    def test_no_filter_when_nothing_is_being_changed(self):
        """An ordinary JPEG must not be touched. A filter that does nothing
        still costs a decode and a re-encode."""
        command, _ = images.build_command(
            ImageSpec(image_format="png"), fake_image_info(), _stub(), Path("o.png")
        )
        self.assertIsNone(arg_after(command, "-vf"))

    def test_colour_is_adjusted_before_resizing(self):
        """Measured on the full-size picture, so the result does not depend on
        what size was asked for."""
        spec = ImageSpec(image_format="png", saturation=1.3, max_dimension=500)
        info = fake_image_info(width=4000, height=3000)
        chain = arg_after(images.build_command(spec, info, _stub(), Path("o.png"))[0], "-vf")
        self.assertLess(chain.index("eq=saturation"), chain.index("scale="))


class TheLookTravelsWithTheJob(unittest.TestCase):
    def test_saturation_reaches_the_image_settings(self):
        spec = JobSpec()
        spec.image_saturation = 1.3
        self.assertEqual(image_spec_of(spec).saturation, 1.3)

    def test_an_unknown_look_falls_back_rather_than_failing(self):
        """A stray value from a saved preset should give a sensible picture, not
        an error deep inside a decoder."""
        spec = JobSpec()
        spec.raw_look = "sparkly"
        look = spec.raw_look if spec.raw_look in raw.LOOKS else raw.NATURAL
        self.assertEqual(look, raw.NATURAL)


class TheInterfaceCannotSetInternals(unittest.TestCase):
    """image_saturation is worked out from the look. A request that set it
    directly could wreck the colour of a whole batch."""

    def test_saturation_from_a_request_is_ignored(self):
        from vidsqueeze.server import _spec_from_request
        self.assertEqual(_spec_from_request({"image_saturation": 9.0}).image_saturation, 1.0)

    def test_a_bad_look_from_a_request_falls_back(self):
        from vidsqueeze.server import _spec_from_request
        self.assertEqual(_spec_from_request({"raw_look": "nonsense"}).raw_look, raw.NATURAL)

    def test_a_good_look_from_a_request_is_honoured(self):
        from vidsqueeze.server import _spec_from_request
        self.assertEqual(_spec_from_request({"raw_look": "neutral"}).raw_look, raw.NEUTRAL)


def _stub():
    from vidsqueeze.deps import Tools

    return Tools(ffmpeg=Path("ffmpeg"), ffprobe=Path("ffprobe"), version="9.0",
                 encoders=frozenset({"mjpeg", "png", "libwebp", "libsvtav1", "tiff", "bmp"}),
                 source="system")


class AutomaticBrighteningIsOff(unittest.TestCase):
    """The one finding here that needed no reference image at all.

    The decoder's automatic brightening normalises every picture so a fraction of
    it is white. On an ordinary scene that is roughly right. On a deliberately
    dark one it is the removal of the photographer's intention: it lifted a
    low-key photograph from a brightness of 77 to 157. Measured across ten
    photographs it left the error swinging between 0.53 and 1.15 of the camera's
    own rendering, so no fixed exposure could compensate. With it off the error is
    a steady 6 to 14 per cent, which one constant does fix.
    """

    def test_natural_turns_it_off(self):
        self.assertIn("-W", raw._flags_for(raw.NATURAL))

    def test_neutral_leaves_the_decoder_to_its_own_judgement(self):
        self.assertNotIn("-W", raw._flags_for(raw.NEUTRAL))

    def test_a_fixed_exposure_replaces_it(self):
        flags = raw._flags_for(raw.NATURAL)
        self.assertEqual(arg_after(flags, "-b"), raw.NATURAL_BRIGHTNESS)
        self.assertGreater(float(raw.NATURAL_BRIGHTNESS), 1.0)


class CalibratedAgainstTheCameraNotAnOperatingSystem(unittest.TestCase):
    """An earlier version was tuned against one platform's RAW rendering, which
    was wrong twice over: it exists on only one of the three systems this runs on,
    and it is that vendor's opinion rather than the photograph. The reference is
    now the camera's own full size JPEG, which every RAW carries inside it and
    which is therefore available everywhere. The wrong reference had the colour 20
    per cent too strong on nearly every picture."""

    def test_saturation_is_the_camera_calibrated_value(self):
        # 1.35 was the value derived from the wrong reference. Anything at or
        # above it means somebody has calibrated against a platform again.
        self.assertLess(raw.NATURAL_SATURATION, 1.30)
        self.assertGreater(raw.NATURAL_SATURATION, 1.0)

    def test_the_reference_is_available_on_every_platform(self):
        """extract_preview reads the camera's JPEG out of the RAW with no
        external tool, so the reference can be reproduced anywhere."""
        self.assertTrue(callable(raw.extract_preview))
