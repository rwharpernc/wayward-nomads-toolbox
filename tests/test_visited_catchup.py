"""Boxel Survey's visited systems are found again in the journals after EDMC was closed."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import visited_systems  # noqa: E402


def write(folder: str, name: str, events: list, age_days: float = 0.0) -> None:
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    stamp = time.time() - age_days * 86400
    os.utime(path, (stamp, stamp))


class ArrivalsTests(unittest.TestCase):
    def test_finds_only_this_commanders_arrivals_in_recent_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "Journal.1.log", [
                {"event": "Commander", "Name": "Alice"},
                {"event": "FSDJump", "StarSystem": "Sol"}, {"event": "Location", "StarSystem": "Lave"},
                {"event": "Scan", "StarSystem": "ignored"},
            ], age_days=1)
            write(folder, "Journal.2.log", [
                {"event": "LoadGame", "Commander": "BOB"}, {"event": "FSDJump", "StarSystem": "Achenar"},
                {"event": "LoadGame", "Commander": "alice"}, {"event": "FSDJump", "StarSystem": "Diso"},
            ], age_days=0.5)
            write(folder, "Journal.old.log", [{"event": "Commander", "Name": "Alice"}, {"event": "FSDJump", "StarSystem": "Old"}],
                  age_days=60)
            found = visited_systems.arrivals_since("Alice", time.time() - 14 * 86400, folder)
        self.assertEqual(found, {"Sol", "Lave", "Diso"})

    def test_no_commander_or_folder_gives_nothing(self) -> None:
        self.assertEqual(visited_systems.arrivals_since("", 0, "."), set())
        self.assertEqual(visited_systems.arrivals_since("Alice", 0, os.path.join(tempfile.gettempdir(), "no-such-journal-dir")), set())


if __name__ == "__main__":
    unittest.main()
