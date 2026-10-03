"""
Unit tests for plugin/game_mode.py. No EDMC runtime needed.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import game_mode as gm  # noqa: E402


class ModeTextTests(unittest.TestCase):
    def test_the_three_game_modes(self) -> None:
        self.assertEqual(gm.mode_text("Solo"), "You are in Solo mode.")
        self.assertEqual(gm.mode_text("Open"), "You are in Open mode.")
        self.assertEqual(gm.mode_text("Group", "Wayward Nomads"), "You are in Private Group mode (Wayward Nomads).")
        self.assertEqual(gm.mode_text("Group"), "You are in Private Group mode.")

    def test_unknown_or_missing_mode_is_neutral(self) -> None:
        self.assertIn("waiting for login", gm.mode_text(None))
        self.assertIn("waiting for login", gm.mode_text("SomethingNew"))


class TrackerTests(unittest.TestCase):
    def _event(self, tracker: gm.GameModeTracker, entry: dict) -> None:
        tracker.handle_event(entry, "Bocheaux", None, None, {})

    def test_loadgame_sets_the_mode_and_shutdown_clears_it(self) -> None:
        tracker = gm.GameModeTracker()
        self.assertIn("waiting for login", tracker.text())
        self._event(tracker, {"event": "LoadGame", "GameMode": "Solo"})
        self.assertEqual(tracker.text(), "You are in Solo mode.")
        self._event(tracker, {"event": "LoadGame", "GameMode": "Group", "Group": "Nomads"})
        self.assertEqual(tracker.text(), "You are in Private Group mode (Nomads).")
        self._event(tracker, {"event": "Shutdown"})
        self.assertIn("waiting for login", tracker.text())

    def test_unrelated_events_leave_it_alone(self) -> None:
        tracker = gm.GameModeTracker()
        self._event(tracker, {"event": "LoadGame", "GameMode": "Open"})
        self._event(tracker, {"event": "FSDJump"})
        self.assertEqual(tracker.text(), "You are in Open mode.")

    def test_startup_recovers_the_mode_from_the_journal_file(self) -> None:
        lines = [{"event": "Fileheader"}, {"event": "Commander", "Name": "Bocheaux"},
                 {"event": "LoadGame", "GameMode": "Solo", "Credits": 5}]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "Journal.test.log")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(json.dumps(line) for line in lines) + "\n")
            self.assertEqual(gm.read_mode_from_journal(path), ("Solo", None))
            tracker = gm.GameModeTracker()
            with mock.patch.object(gm, "_current_logfile", return_value=path):
                self._event(tracker, {"event": "StartUp"})
            self.assertEqual(tracker.text(), "You are in Solo mode.")

    def test_a_pathlib_logfile_is_turned_into_a_plain_string(self) -> None:
        import pathlib
        import types

        fake_monitor = types.SimpleNamespace(monitor=types.SimpleNamespace(logfile=pathlib.Path("J1.log")))
        with mock.patch.dict(sys.modules, {"monitor": fake_monitor}):
            self.assertEqual(gm._current_logfile(), str(pathlib.Path("J1.log")))

    def test_missing_or_unreadable_journal_gives_no_mode(self) -> None:
        self.assertIsNone(gm.read_mode_from_journal(None))
        self.assertIsNone(gm.read_mode_from_journal(os.path.join(tempfile.gettempdir(), "no-such-journal.log")))


if __name__ == "__main__":
    unittest.main()
