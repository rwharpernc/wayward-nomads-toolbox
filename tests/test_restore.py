"""Restoring the last commander when EDMC starts without the game: reading the newest journal, and telling every
feature without one failing the rest."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("myNotebook", mock.MagicMock())
sys.modules.setdefault("theme", mock.MagicMock())
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import restore  # noqa: E402


def write(folder: str, name: str, events: list, mtime: float) -> None:
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join(json.dumps(event) + "\n" for event in events))
    os.utime(path, (mtime, mtime))


class LatestCommanderTests(unittest.TestCase):
    def test_last_login_in_the_newest_journal(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "Journal.2026-10-09T100000.01.log", [{"event": "LoadGame", "Commander": "MACTAVIOUS"}], 1000)
            write(folder, "Journal.2026-10-10T100000.01.log",
                  [{"event": "Commander", "Name": "BOCHEAUX"}, {"event": "LoadGame", "Commander": "BOCHEAUX"}], 2000)
            self.assertEqual(restore.latest_commander(folder), "BOCHEAUX")

    def test_skips_a_newest_journal_with_no_login_yet(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "Journal.2026-10-09T100000.01.log", [{"event": "LoadGame", "Commander": "MACTAVIOUS"}], 1000)
            write(folder, "Journal.2026-10-10T100000.01.log", [{"event": "Fileheader"}], 2000)
            self.assertEqual(restore.latest_commander(folder), "MACTAVIOUS")

    def test_no_journals(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.dict(sys.modules, {"monitor": types.SimpleNamespace(monitor=types.SimpleNamespace(cmdr=None))}):
                self.assertEqual(restore.latest_commander(folder), "")


class DispatchTests(unittest.TestCase):
    def test_every_feature_hears_it_and_one_failing_does_not_stop_the_rest(self) -> None:
        heard = []

        class Good:
            def handle_event(self, entry, cmdr, system, station, state):
                heard.append((entry["event"], cmdr, system, station, state))

        class Bad:
            def handle_event(self, *args):
                raise RuntimeError("boom")

        with self.assertLogs(level="ERROR"):
            handled = restore.dispatch([Good(), Bad(), Good()], "BOCHEAUX")
        self.assertEqual(handled, 2)
        self.assertEqual(heard, [(restore.RESTORE_EVENT, "BOCHEAUX", None, None, {})] * 2)

    def test_it_is_not_a_login_or_startup(self) -> None:
        self.assertNotIn(restore.RESTORE_EVENT, ("StartUp", "LoadGame", "Commander"))


if __name__ == "__main__":
    unittest.main()
