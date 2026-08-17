"""The version number.

This looks like the most trivial thing in the suite and it is here because it
caused a real, confusing failure. The version was written down twice, in
`__init__.py` and in `cli.py`. One was bumped and the other was not, so the
command line announced the new version while the interface and the update check
still reported the old one. The program told the user it was up to date when it
was a release behind, which is the single most annoying way for an updater to be
wrong.

There is now one definition. These cases keep it that way.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

import vidsqueeze
from vidsqueeze import cli

SOURCE = Path(__file__).resolve().parent.parent / "vidsqueeze"
ROOT = SOURCE.parent


class ThereIsOnlyOneVersion(unittest.TestCase):
    def test_the_command_line_and_the_package_agree(self):
        self.assertEqual(cli.VERSION, vidsqueeze.__version__)

    def test_the_interface_reads_the_same_one(self):
        """The interface and the update check import it from the package. If
        that import ever changes to a literal, this fails."""
        from vidsqueeze import server
        self.assertEqual(server.VERSION, vidsqueeze.__version__)

    def test_nothing_else_writes_a_version_literal(self):
        """A grep, deliberately. One definition is only true while it stays the
        only one, and the way this broke was somebody adding a second."""
        pattern = re.compile(r"""^\s*(?:__version__|VERSION)\s*=\s*["']\d+\.\d+""")
        offenders = []
        for path in sorted(SOURCE.rglob("*.py")):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.match(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
        self.assertEqual(
            offenders, [f"vidsqueeze/__init__.py:{_version_line()}: "
                        f'__version__ = "{vidsqueeze.__version__}"'],
            "the version must be written in __init__.py and nowhere else",
        )

    def test_it_looks_like_a_version(self):
        self.assertRegex(vidsqueeze.__version__, r"^\d+\.\d+\.\d+$")


class TheReportedVersionIsTheRealOne(unittest.TestCase):
    def test_version_flag_prints_the_package_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "vidsqueeze", "--version"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", timeout=120,
        )
        self.assertIn(vidsqueeze.__version__, result.stdout)


class TheChangelogKeepsUp(unittest.TestCase):
    """A living document, per the working agreement. A released version with no
    entry means somebody shipped without saying what changed."""

    def test_the_current_version_has_an_entry(self):
        changelog = (ROOT / "CHANGELOG.md").read_text()
        self.assertIn(
            f"## {vidsqueeze.__version__}", changelog,
            f"CHANGELOG.md has no entry for {vidsqueeze.__version__}",
        )


def _version_line() -> int:
    for number, line in enumerate((SOURCE / "__init__.py").read_text().splitlines(), 1):
        if line.startswith("__version__"):
            return number
    return 0
