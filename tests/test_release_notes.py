"""What is new in a version, shown before the user takes it.

The notes are written on the release and were being fetched and thrown away, so
every install offered an update and said nothing whatever about what it contained.

The interesting risk here is not formatting. A release description is text from the
internet, and the window that shows it holds the key that lets the program convert
and delete the user's files. Handing that text to innerHTML would let a release
description run whatever it liked, so the page builds nodes instead and only
understands a small, well defined part of Markdown. The cases below pin both the
Python side and the promises the renderer makes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from halveit import updates

SCRIPT = (Path(__file__).resolve().parent.parent / "halveit" / "web" / "app.js").read_text()


class TheNotesAreCarriedThrough(unittest.TestCase):
    def test_the_fetcher_returns_three_things_now(self):
        """It used to return two and drop the description on the floor."""
        import inspect
        signature = inspect.getsource(updates.latest_app_version)
        self.assertIn("tuple[str, str, str]", signature)

    def test_a_report_carries_notes(self):
        report = {"app": {}}
        # check() builds this, so assert on the shape it promises the page.
        source = inspect_source(updates.check)
        self.assertIn('"notes": notes', source)

    def test_notes_are_capped(self):
        """A very long description should not push the window off the screen."""
        self.assertLessEqual(updates.NOTES_LIMIT, 20000)
        self.assertGreaterEqual(updates.NOTES_LIMIT, 1000)

    def test_a_tag_with_no_release_still_answers(self):
        """Tags carry no description. The version is still worth reporting."""
        source = inspect_source(updates.latest_app_version)
        self.assertIn('return newest, PROJECT_URL, ""', source)


class TheRendererNeverTrustsTheText(unittest.TestCase):
    """These are greps over the page script. They are worth having anyway: the
    thing being guarded against is somebody later reaching for innerHTML because
    it is shorter, and that is exactly the change a grep catches."""

    def test_release_notes_are_not_built_with_inner_html(self):
        block = SCRIPT[SCRIPT.index("function renderReleaseNotes"):]
        block = block[:block.index("function renderUpdates")]
        self.assertNotIn("innerHTML", block)
        self.assertNotIn("insertAdjacentHTML", block)
        self.assertNotIn("outerHTML", block)

    def test_inline_markdown_is_not_built_with_inner_html(self):
        block = SCRIPT[SCRIPT.index("function inlineMarkdown"):]
        block = block[:block.index("function renderReleaseNotes")]
        self.assertNotIn("innerHTML", block)
        self.assertIn("textContent", block)

    def test_only_http_links_are_made_clickable(self):
        """A javascript: target in a release description must render as text."""
        self.assertRegex(SCRIPT, r"const SAFE_LINK = /\^https\?:\\/\\//i")
        block = SCRIPT[SCRIPT.index("function inlineMarkdown"):]
        block = block[:block.index("function renderReleaseNotes")]
        self.assertIn("SAFE_LINK.test", block)

    def test_links_do_not_hand_over_the_window(self):
        block = SCRIPT[SCRIPT.index("function inlineMarkdown"):]
        block = block[:block.index("function renderReleaseNotes")]
        self.assertIn("noopener", block)

    def test_the_notes_only_appear_when_there_is_an_update(self):
        """Listing what you already have is not news."""
        self.assertIn("app.update_available && app.notes", SCRIPT)


class TheMarkdownSubsetIsWhatTheNotesActuallyUse(unittest.TestCase):
    """The release descriptions this project writes use headings, bullets, bold,
    code spans and wrapped continuation lines. If the renderer stops handling one
    of those, the notes degrade quietly rather than failing, so it is pinned."""

    def setUp(self):
        block = SCRIPT[SCRIPT.index("function renderReleaseNotes"):]
        self.block = block[:block.index("function renderUpdates")]

    def test_headings(self):
        self.assertRegex(self.block, r"\^#\{1,6\}")

    def test_bullets_with_either_marker(self):
        self.assertRegex(self.block, r"\^\[-\*\]")

    def test_wrapped_lines_join_the_bullet_above(self):
        self.assertIn("list.lastChild.append", self.block)

    def test_a_blank_line_ends_a_list(self):
        self.assertIn("list = null", self.block)

    def test_only_a_blank_line_ends_a_paragraph(self):
        """These notes are hard wrapped. Treating every newline as a paragraph
        break split sentences down the middle and read like a ransom note."""
        self.assertIn("para.append(' ')", self.block)
        self.assertIn("para = null", self.block)

    def test_fenced_blocks_become_a_pre_rather_than_stray_backticks(self):
        """The notes show what the program prints. Without this the fence markers
        appeared as backticks and the block collapsed into a paragraph."""
        self.assertIn("startsWith('```')", self.block)
        self.assertIn("createElement('pre')", self.block)

    def test_bold_and_code_and_links_are_all_handled(self):
        inline = SCRIPT[SCRIPT.index("function inlineMarkdown"):]
        inline = inline[:inline.index("function renderReleaseNotes")]
        self.assertIn("createElement('strong')", inline)
        self.assertIn("createElement('code')", inline)
        self.assertIn("createElement('a')", inline)


def inspect_source(function) -> str:
    import inspect
    return inspect.getsource(function)
