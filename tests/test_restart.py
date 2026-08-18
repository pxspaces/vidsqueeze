"""Restarting itself after an update.

The old message told the user to close the window, find the terminal VidSqueeze
was started from, stop it, and start it again. That is four steps and a concept,
the terminal, that the people this program is for should never have to meet.

The awkward part is not the restart. It is that every start mints a new access
token, so the tab the button was pressed in cannot be carried over: its key stops
working the moment the old process dies. The replacement therefore opens a tab of
its own, which is what it already does on startup, and the message says to expect
that rather than leaving somebody staring at a dead page.
"""

from __future__ import annotations

import inspect
import unittest

from vidsqueeze import selfupdate, server


class TheUpdateResultSaysWhetherAnythingChanged(unittest.TestCase):
    """A restart is only worth attempting when files were actually replaced."""

    def test_changed_is_true_for_an_update(self):
        self.assertTrue(selfupdate.changed(selfupdate.CHANGED))

    def test_changed_is_false_when_already_current(self):
        self.assertFalse(selfupdate.changed(selfupdate.NO_CHANGE))

    def test_changed_is_false_for_nothing(self):
        self.assertFalse(selfupdate.changed(""))
        self.assertFalse(selfupdate.changed(None))

    def test_the_constants_are_used_rather_than_repeated(self):
        """Both of the two places that finish an update return the constant, so
        the interface and the command line cannot disagree about the wording."""
        source = inspect.getsource(selfupdate)
        self.assertNotIn('return "Updated. Restart', source)
        self.assertGreaterEqual(source.count("return CHANGED"), 2)


class TheRestartIsSafeToAttempt(unittest.TestCase):
    def setUp(self):
        self.source = inspect.getsource(server.restart_after_update)

    def test_it_is_reachable_without_a_request(self):
        """A module level function, so it can be tested and so the worker thread
        that finishes an update can call it directly."""
        self.assertTrue(inspect.isfunction(server.restart_after_update))
        self.assertFalse(hasattr(server.Handler, "restart_after_update"))

    def test_the_replacement_is_detached(self):
        """Otherwise it dies with the console that started it, and the user is
        left with nothing running at all."""
        self.assertIn("start_new_session", self.source)   # POSIX
        self.assertIn("creationflags", self.source)       # Windows

    def test_the_socket_is_released_before_the_replacement_starts(self):
        """So the new copy can claim a port rather than fighting for one."""
        self.assertIn("server_close", self.source)
        self.assertLess(self.source.index("server_close"),
                        self.source.index("Popen"))

    def test_no_arguments_are_carried_over(self):
        """--no-browser above all. Passing it on would start a replacement with
        no window and no way to reach it."""
        import re
        argv = re.search(r"Popen\(\[(.*?)\]", self.source, re.S).group(1)
        self.assertIn("vidsqueeze", argv)
        self.assertNotIn("no-browser", argv)
        self.assertNotIn("argv", argv)

    def test_the_reply_goes_out_before_the_process_dies(self):
        """Set should_quit immediately and the browser never learns what
        happened, so there is a wait first and the quit comes last."""
        self.assertIn("time.sleep", self.source)
        self.assertLess(self.source.index("time.sleep"),
                        self.source.index("should_quit"))

    def test_a_failure_to_spawn_is_reported_rather_than_hidden(self):
        """Exiting into nothing after telling the user it is restarting would be
        the worst outcome available."""
        self.assertIn("OSError", self.source)
        self.assertIn("could not be started", self.source)
        # And it must not quit in that case.
        after = self.source[self.source.index("could not be started"):]
        self.assertIn("return", after.split("should_quit")[0])


class TheMessageSetsTheRightExpectation(unittest.TestCase):
    def setUp(self):
        self.source = inspect.getsource(server.Handler._update_self)

    def test_it_says_a_new_tab_is_coming(self):
        self.assertIn("new tab", self.source)

    def test_it_says_this_tab_stops_working(self):
        """Because it does. The token changes."""
        self.assertIn("stops working", self.source)

    def test_it_keeps_the_manual_fallback(self):
        """The old instruction is still the answer when the restart fails, so it
        survives as a fallback rather than being deleted."""
        self.assertIn("close this window", self.source.lower())
        self.assertIn("start it again", self.source)

    def test_the_restart_only_runs_when_something_changed(self):
        self.assertIn("selfupdate.changed(result)", self.source)

    def test_the_page_is_told_a_restart_is_happening(self):
        self.assertIn('"restarting"', self.source)
        self.assertIn("restarting", server.Session().update_state)


class TheCommandLineDoesNotPretendToRestart(unittest.TestCase):
    """`vidsqueeze --update` has no server running and is about to exit, so
    telling the user it is restarting would be a lie."""

    def test_it_says_to_start_the_program(self):
        from vidsqueeze import cli
        source = inspect.getsource(cli)
        self.assertIn("Start VidSqueeze to use the new version", source)

    def test_it_does_not_claim_to_be_restarting(self):
        from vidsqueeze import cli
        source = inspect.getsource(cli.main) if hasattr(cli, "main") else inspect.getsource(cli)
        self.assertNotIn("is restarting", source)
