"""The queue, for runs long enough that the ergonomics matter.

Sixty files is twenty minutes of the machine being busy. Two things follow from
that: it has to be possible to put the work down for a while, and the summary at
the end has to say something more useful than a single count.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from halveit.encode import JobResult, JobSpec
from halveit.jobs import STATUS_DONE, QueueItem, Queue


def queue_of(*sizes) -> Queue:
    """A queue with finished items of the given (source, output) sizes.

    Built by hand rather than by encoding, because what is being tested is the
    arithmetic of the summary, not the encoder.
    """
    q = Queue(tools=None, spec=JobSpec(), output_dir=Path("/tmp/nowhere"))
    for index, (source_bytes, output_bytes) in enumerate(sizes, start=1):
        item = QueueItem(item_id=index, source=Path(f"f{index}.jpg"),
                         source_bytes=source_bytes)
        item.status = STATUS_DONE
        item.result = JobResult(source=item.source, output=Path(f"f{index}.png"), ok=True,
                                source_bytes=source_bytes, output_bytes=output_bytes)
        item.grew = output_bytes >= source_bytes
        q.items.append(item)
    return q


class TheSummarySeparatesTheTwoKindsOfSuccess(unittest.TestCase):
    """Sixty files of which forty grew is a different outcome from sixty that all
    shrank, and one "succeeded" count hides which happened."""

    def test_all_smaller(self):
        totals = queue_of((1000, 400), (1000, 500)).totals()
        self.assertEqual((totals["succeeded"], totals["smaller"], totals["grew"]), (2, 2, 0))

    def test_all_larger(self):
        totals = queue_of((1000, 1400), (1000, 2000)).totals()
        self.assertEqual((totals["succeeded"], totals["smaller"], totals["grew"]), (2, 0, 2))

    def test_a_mixture(self):
        totals = queue_of((1000, 400), (1000, 3000), (1000, 900)).totals()
        self.assertEqual((totals["succeeded"], totals["smaller"], totals["grew"]), (3, 2, 1))

    def test_exactly_the_same_size_counts_as_no_saving(self):
        totals = queue_of((1000, 1000)).totals()
        self.assertEqual(totals["grew"], 1)

    def test_smaller_and_grew_always_add_up_to_succeeded(self):
        totals = queue_of((1000, 400), (1000, 3000), (500, 500), (900, 100)).totals()
        self.assertEqual(totals["smaller"] + totals["grew"], totals["succeeded"])


class Pausing(unittest.TestCase):
    def test_a_new_queue_is_not_paused(self):
        self.assertFalse(queue_of((10, 5)).paused)

    def test_pause_and_carry_on(self):
        q = queue_of((10, 5))
        q.pause()
        self.assertTrue(q.paused)
        self.assertTrue(q.totals()["paused"])
        q.resume()
        self.assertFalse(q.paused)
        self.assertFalse(q.totals()["paused"])

    def test_pausing_twice_is_harmless(self):
        q = queue_of((10, 5))
        q.pause()
        q.pause()
        self.assertTrue(q.paused)
        q.resume()
        self.assertFalse(q.paused)

    def test_resuming_when_not_paused_is_harmless(self):
        q = queue_of((10, 5))
        q.resume()
        self.assertFalse(q.paused)

    def test_cancelling_releases_a_paused_queue(self):
        """A paused worker is sitting on an event. Cancelling has to wake it, or
        the threads never exit and the program will not close."""
        q = queue_of((10, 5))
        q.pause()
        q.cancel()
        self.assertTrue(q._carry_on.is_set(), "a paused worker would never wake to exit")

    def test_a_pause_does_not_ruin_the_time_remaining(self):
        """The estimate comes from elapsed time against progress. Counting a ten
        minute coffee break as encoding time makes it nonsense afterwards."""
        import time
        q = queue_of((1000, 400))
        q.started_at = time.time() - 10
        before = q.started_at
        q.pause()
        time.sleep(0.2)
        q.resume()
        self.assertGreater(q.started_at, before, "the pause was charged to the batch")


class TheServerExposesIt(unittest.TestCase):
    def test_pause_and_resume_have_routes(self):
        source = (Path(__file__).resolve().parent.parent / "halveit" / "server.py").read_text()
        self.assertIn('"/api/queue/pause"', source)
        self.assertIn('"/api/queue/resume"', source)

    def test_the_page_reads_the_paused_flag_and_the_two_counts(self):
        script = (Path(__file__).resolve().parent.parent
                  / "halveit" / "web" / "app.js").read_text()
        for name in ("totals.paused", "totals.grew", "totals.smaller"):
            with self.subTest(name=name):
                self.assertIn(name, script)
