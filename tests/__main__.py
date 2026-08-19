"""Run the suite.

    python3 -m tests             everything
    python3 -m tests --fast      skip anything that shells out to ffmpeg
    python3 -m tests -k image    only cases whose name matches
    python3 -m tests -v          one line per case
"""

from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(prog="python3 -m tests", description=__doc__)
    parser.add_argument("--fast", action="store_true",
                        help="Skip anything that needs ffmpeg. Seconds rather than a minute.")
    parser.add_argument("-k", metavar="PATTERN", help="Only run cases matching this.")
    parser.add_argument("-v", "--verbose", action="store_true", help="One line per case.")
    args = parser.parse_args()

    if args.fast:
        os.environ["HALVEIT_TESTS_FAST"] = "1"

    # Import only after the flag is set, so support.py reads it at import time.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    loader = unittest.TestLoader()
    if args.k:
        loader.testNamePatterns = [f"*{args.k}*"]
    suite = loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))

    from tests import support
    if not args.fast and support.tools() is None:
        print("  ffmpeg was not found, so the tests that measure real output "
              "will skip.\n  Run 'python3 -m halveit --setup' to fetch it.\n")

    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    return 0 if runner.run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
