"""The build that does not offer pictures.

One flag in features.py decides whether stills and camera RAW exist at all, and
the publishing script turns it off. That makes it the only difference between
the copy developed here and the copy people download, so it is worth more than
a glance.

These cases run in both states, because they set the flag themselves. That is
deliberate: a flag only ever exercised in its default state is a flag nobody has
tested.

What made this file necessary: the first attempt gated the list of file
extensions, which reads correctly and covered folder scanning, and left a
photograph named directly on the command line converting perfectly happily
through a pipeline with no settings to control it.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from halveit import features, probe
from halveit.probe import KIND_AUDIO, KIND_IMAGE, KIND_VIDEO


def without_pictures():
    return mock.patch.object(features, "IMAGES", False)


def with_pictures():
    return mock.patch.object(features, "IMAGES", True)


class TheFlagIsReadEveryTime(unittest.TestCase):
    """Anything deciding this once, at import, cannot be tested and cannot be
    turned off by the publishing script either."""

    def test_off_means_off(self):
        with without_pictures():
            self.assertFalse(features.images_enabled())

    def test_on_means_on(self):
        with with_pictures():
            self.assertTrue(features.images_enabled())


class OfferedKinds(unittest.TestCase):
    def test_video_and_audio_are_always_offered(self):
        for state in (with_pictures(), without_pictures()):
            with state:
                self.assertIn(KIND_VIDEO, probe.offered_kinds())
                self.assertIn(KIND_AUDIO, probe.offered_kinds())

    def test_pictures_follow_the_flag(self):
        with with_pictures():
            self.assertIn(KIND_IMAGE, probe.offered_kinds())
        with without_pictures():
            self.assertNotIn(KIND_IMAGE, probe.offered_kinds())


class NoFilterDoesNotMeanEverything(unittest.TestCase):
    """The actual bug. "No kind asked for" was read as "any kind at all", so a
    photograph named on the command line went straight through."""

    PICTURES = ("shot.jpg", "shot.png", "shot.cr2", "shot.heic", "shot.tif")
    MOVING = ("clip.mp4", "clip.mkv", "song.mp3", "song.flac")

    def test_a_named_photograph_is_refused_with_no_filter(self):
        with without_pictures():
            for name in self.PICTURES:
                with self.subTest(name=name):
                    self.assertFalse(probe.matches_kinds(Path(name), None), name)

    def test_video_and_audio_still_pass_with_no_filter(self):
        with without_pictures():
            for name in self.MOVING:
                with self.subTest(name=name):
                    self.assertTrue(probe.matches_kinds(Path(name), None), name)

    def test_everything_passes_when_pictures_are_on(self):
        with with_pictures():
            for name in self.PICTURES + self.MOVING:
                with self.subTest(name=name):
                    self.assertTrue(probe.matches_kinds(Path(name), None), name)

    def test_a_picture_filter_from_the_page_cannot_reinstate_them(self):
        """The mode is remembered in a settings file. One saved while pictures
        were available must not be a way back in."""
        with without_pictures():
            self.assertFalse(probe.matches_kinds(Path("shot.jpg"), {KIND_IMAGE}))
            self.assertFalse(probe.matches_kinds(Path("shot.cr2"), {"image", "video"}))
            self.assertTrue(probe.matches_kinds(Path("clip.mp4"), {"image", "video"}))


class TheSelectionSaysWhyRatherThanSwallowing(unittest.TestCase):
    def test_a_named_photograph_produces_a_sentence(self):
        from halveit.server import expand_selection

        with without_pictures(), tempfile.TemporaryDirectory() as work:
            shot = Path(work) / "holiday.jpg"
            shot.write_bytes(b"\xff\xd8\xff\xd9")
            files, problems = expand_selection([str(shot)])
            self.assertEqual(files, [])
            self.assertTrue(problems, "the file vanished without explanation")
            self.assertIn("holiday.jpg", problems[0])

    def test_a_folder_of_photographs_is_not_a_folder_of_nothing_in_particular(self):
        from halveit.server import expand_selection

        with without_pictures(), tempfile.TemporaryDirectory() as work:
            for name in ("a.jpg", "b.cr2"):
                (Path(work) / name).write_bytes(b"\x00")
            files, problems = expand_selection([work])
            self.assertEqual(files, [])
            self.assertTrue(problems)

    def test_video_in_the_same_folder_is_still_picked_up(self):
        from halveit.server import expand_selection

        with without_pictures(), tempfile.TemporaryDirectory() as work:
            (Path(work) / "a.jpg").write_bytes(b"\x00")
            clip = Path(work) / "b.mp4"
            clip.write_bytes(b"\x00")
            files, _ = expand_selection([work])
            self.assertEqual([p.name for p in files], ["b.mp4"])


class TheEncoderRefusesAsWell(unittest.TestCase):
    """The selection code is the polite refusal. This is the one that holds when
    a caller skips it, which is the only kind of gate worth having."""

    def test_a_photograph_reaching_the_encoder_is_refused_not_converted(self):
        from halveit.encode import JobSpec, encode_one
        from .support import tools

        with without_pictures(), tempfile.TemporaryDirectory() as work:
            work = Path(work)
            shot = work / "shot.jpg"
            shot.write_bytes(b"\xff\xd8\xff\xd9")
            out = work / "out"
            out.mkdir()
            result = encode_one(tools(), shot, JobSpec(), out)
            self.assertFalse(result.ok)
            self.assertIn("video and audio", result.message)
            self.assertEqual(list(out.iterdir()), [], "something was written anyway")

    def test_camera_raw_is_refused_too(self):
        from halveit.encode import JobSpec, encode_one
        from .support import tools

        with without_pictures(), tempfile.TemporaryDirectory() as work:
            work = Path(work)
            shot = work / "shot.cr2"
            shot.write_bytes(b"II*\x00")
            out = work / "out"
            out.mkdir()
            result = encode_one(tools(), shot, JobSpec(), out)
            self.assertFalse(result.ok)
            self.assertEqual(list(out.iterdir()), [])


class TheFlagIsTheOnlyDifference(unittest.TestCase):
    """A second copy of this decision would eventually disagree with the first,
    and the publishing script only knows how to turn off one of them."""

    def test_the_flag_keeps_the_shape_the_publishing_script_substitutes_on(self):
        """The script rewrites this line with a regular expression and refuses to
        publish if it cannot find it. Either value is correct depending on which
        copy this is running in, but the shape of the line is not negotiable, and
        this file is published, so it has to pass in both.
        """
        source = (Path(__file__).resolve().parent.parent
                  / "halveit" / "features.py").read_text()
        self.assertRegex(source, r"(?m)^IMAGES = (?:True|False)\s*# FEATURE_IMAGES$")

    def test_nothing_else_hard_codes_the_answer(self):
        """Every module that cares must ask features, not decide for itself."""
        root = Path(__file__).resolve().parent.parent / "halveit"
        for path in sorted(root.glob("*.py")):
            if path.name == "features.py":
                continue
            text = path.read_text()
            with self.subTest(module=path.name):
                self.assertNotIn("IMAGES = ", text,
                                 f"{path.name} keeps its own copy of the flag")


class TheStateSentToThePageMatchesTheBuild(unittest.TestCase):
    """What the program tells the page and what the program will actually do have
    to agree. They disagreed harmlessly at first: the page was sent a list of
    picture defaults and an instruction for installing a RAW decoder, in a build
    with no picture settings and no RAW."""

    def test_no_picture_defaults_are_offered(self):
        from halveit.server import _offered_defaults

        with without_pictures():
            leaked = [k for k in _offered_defaults() if k.startswith("image_")]
            self.assertEqual(leaked, [])
        with with_pictures():
            self.assertTrue(any(k.startswith("image_") for k in _offered_defaults()))

    def test_the_contact_sheet_route_refuses(self):
        source = (Path(__file__).resolve().parent.parent
                  / "halveit" / "server.py").read_text()
        self.assertIn("Contact sheets are not part of this version.", source)


class ThePageSurvivesLosingItsPictureControls(unittest.TestCase):
    """The published page has the picture markup removed rather than hidden, so
    the script asks for elements that are not there. One unguarded
    addEventListener on a missing element throws and stops the rest of the file,
    which would leave every control below it dead: the page would look fine and
    do nothing. Nothing in a suite that never opens a browser catches that, so
    these read the two files and check they still agree.
    """

    WEB = Path(__file__).resolve().parent.parent / "halveit" / "web"

    def marked_ids(self) -> list:
        """Every element id inside a section the publishing script removes."""
        import re

        html = (self.WEB / "index.html").read_text()
        sections = re.findall(r"<!--\s*IMAGES:START\s*-->(.*?)<!--\s*IMAGES:END\s*-->",
                              html, re.S)
        if not sections:
            # This file is published, and in the published copy the sections have
            # already been removed. There is nothing left to keep in step there,
            # and the OPTIONAL list below is what makes their absence survivable.
            self.skipTest("this page has already had its picture sections removed")
        return sorted({m for s in sections for m in re.findall(r'id="([A-Za-z0-9_]+)"', s)})

    def optional_ids(self) -> set:
        import re

        js = (self.WEB / "app.js").read_text()
        block = re.search(r"const OPTIONAL = new Set\(\[(.*?)\]\);", js, re.S)
        self.assertIsNotNone(block, "app.js no longer says which controls are optional")
        return {part.strip().strip("'\"") for part in block.group(1).split(",")
                if part.strip().strip("'\"")}

    def test_every_removed_control_is_known_to_be_optional(self):
        unlisted = [i for i in self.marked_ids() if i not in self.optional_ids()]
        self.assertEqual(unlisted, [], "these ids vanish from the published page but "
                                       "app.js still expects them")

    def test_the_lookup_helper_does_not_return_nothing(self):
        """Guarding every call site would be dozens of places to forget. The
        helper hands back a detached element instead, so reads give empty and
        writes go nowhere."""
        js = (self.WEB / "app.js").read_text()
        self.assertIn("document.createElement('input')", js)
        self.assertIn("absent.set(id", js)

    def test_a_mistyped_id_is_still_reported(self):
        """A helper that swallows every missing element silently would turn a typo
        into an afternoon."""
        js = (self.WEB / "app.js").read_text()
        self.assertIn("if (!OPTIONAL.has(id))", js)
        self.assertIn("console.warn", js)


class TheNoteSayingPicturesAreStillToCome(unittest.TestCase):
    """The published copy says pictures are coming later. That sentence is true
    there and false here, where they are present, so the private documents cannot
    carry it: the publishing script adds it. An insertion whose anchor has moved
    would quietly add nothing at all, which is the failure mode this guards.

    Skipped in the published copy, which has no publishing script.
    """

    ROOT = Path(__file__).resolve().parent.parent

    def script(self) -> str:
        path = self.ROOT / "tools" / "prepare-public.sh"
        if not path.exists():
            self.skipTest("this is the published copy, which does not carry the script")
        return path.read_text()

    def test_the_anchor_it_inserts_at_still_exists(self):
        import re

        anchors = re.findall(r'^\s*\("([^"]+)",\s*"([^"]+)",',
                             self.script(), re.M)
        self.assertTrue(anchors, "the script no longer lists any insertions")
        for name, anchor in anchors:
            with self.subTest(document=name):
                text = (self.ROOT / name).read_text()
                self.assertIn(anchor, text,
                              f"{name} has no {anchor!r} for the note to go before")

    def test_a_missing_anchor_stops_the_build_rather_than_doing_nothing(self):
        self.assertIn("would have gone in nowhere", self.script())

    def test_the_exemption_is_for_marked_blocks_only(self):
        """The check has to allow the one passage that names pictures in order to
        say they are absent. Allowing anything more would switch the check off."""
        text = self.script()
        self.assertIn("SOON:START", text)
        self.assertIn("camera raw|\\.cr2|photograph|contact sheet|--image-format", text)

    def test_the_private_documents_do_not_claim_pictures_are_missing(self):
        """They are not missing here, so nothing in this copy may say so."""
        self.script()   # skips in the published copy, where the note is correct
        for name in ("README.md", "FEATURES.md", "USER-GUIDE.md"):
            with self.subTest(document=name):
                self.assertNotIn("SOON:START", (self.ROOT / name).read_text())


class TrimmingLeavesTheDocumentsWellFormed(unittest.TestCase):
    """A marked section that ends after a closing code fence takes the fence with
    it. Nothing fails, the file is still valid Markdown, and every paragraph after
    it renders as one long code block. That is exactly what went out in the README
    of 1.14.0, and it was found by reading the published page rather than by any
    check, which is why there is now one.
    """

    ROOT = Path(__file__).resolve().parent.parent

    def test_no_marked_section_ends_between_a_pair_of_fences(self):
        import re

        for name in ("README.md", "FEATURES.md", "USER-GUIDE.md", "CHANGELOG.md"):
            path = self.ROOT / name
            if not path.exists():
                continue
            with self.subTest(document=name):
                lines = path.read_text().split("\n")
                inside = False
                for number, line in enumerate(lines, 1):
                    if line.startswith("```"):
                        inside = not inside
                    elif "IMAGES:START" in line or "IMAGES:END" in line:
                        self.assertFalse(
                            inside,
                            f"{name}:{number}: a marker sits inside a code fence, so "
                            f"removing the section would unbalance the fences",
                        )

    def test_the_fences_are_balanced_to_begin_with(self):
        for path in sorted(self.ROOT.glob("*.md")) + sorted((self.ROOT / "docs").glob("*.md")):
            with self.subTest(document=path.name):
                fences = [line for line in path.read_text().split("\n")
                          if line.startswith("```")]
                self.assertEqual(len(fences) % 2, 0, f"{path.name} has an unclosed fence")

    def test_the_publishing_script_checks_this_too(self):
        """The case above reads this copy. The script has to check the trimmed one,
        because that is where the fence actually goes missing."""
        path = self.ROOT / "tools" / "prepare-public.sh"
        if not path.exists():
            self.skipTest("this is the published copy, which does not carry the script")
        self.assertIn("code fences, so one is", path.read_text())
