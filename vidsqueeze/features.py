"""What this build of the program offers.

One flag, in one file, read everywhere. `tools/prepare-public.sh` rewrites it when
building the published copy, which is the same trick used for the ignore file and
the landing page: the difference between the private and public builds lives in the
publishing script rather than being remembered by hand.

**Images are held back from the published build on purpose.** Video and audio are
finished work. The picture side is not: the RAW rendering has been recalibrated
twice and the second attempt only stopped being obviously wrong yesterday, so it is
not something to put in front of strangers with a wedding shoot. It stays fully
present and fully tested in development, and comes out of hiding when it is good
enough that nobody has to apologise for it.

This is a product decision, not a security boundary. Anybody who edits this file in
a published copy gets the picture features back, and that is fine: the point is not
to stop them, it is to avoid advertising something unfinished.
"""

from __future__ import annotations

#: Whether stills and camera RAW are offered at all. Rewritten to False by the
#: publishing script. Search for FEATURE_IMAGES in tools/prepare-public.sh.
IMAGES = False      # FEATURE_IMAGES


def images_enabled() -> bool:
    """Whether this build offers pictures. A function so callers read it live,
    rather than binding the value at import time and making tests awkward."""
    return bool(IMAGES)
