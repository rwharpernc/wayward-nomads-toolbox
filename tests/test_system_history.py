"""System history (system_history.py): visits and scans built from a commander's journals, finished journals saved and the newest kept live."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
for name in ("myNotebook", "ttkHyperlinkLabel", "theme", "monitor", "plug", "l10n", "requests"):
    sys.modules.setdefault(name, mock.MagicMock())
if "config" not in sys.modules:
    config_stub = types.ModuleType("config")
    config_stub.appname = "EDMarketConnector"
    config_stub.config = mock.MagicMock()
    sys.modules["config"] = config_stub

from plugin import system_history as H  # noqa: E402


def write(folder, name, cmdr, events):
    lines = [{"timestamp": "2026-01-01T00:00:00Z", "event": "LoadGame", "Commander": cmdr}] + events
    with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(e) for e in lines) + "\n")


def jump(system, stamp):
    return {"timestamp": stamp, "event": "FSDJump", "StarSystem": system, "SystemAddress": 1}


class History(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = os.path.join(self.tmp.name, "journals")
        os.makedirs(self.folder)
        self.h = H.SystemHistory()
        self.h.pause = 0
        self.h.start(self.tmp.name)
        write(self.folder, "Journal.2026-01-01T000000.01.log", "Alice", [jump("A", "2026-01-01T01:00:00Z"), {"event": "Scan", "timestamp": "x"},
                                                                    jump("B", "2026-01-01T02:00:00Z"), jump("A", "2026-01-01T03:00:00Z")])
        write(self.folder, "Journal.2026-01-02T000000.01.log", "Bob", [jump("A", "2026-01-02T01:00:00Z"), jump("C", "2026-01-02T02:00:00Z")])
        write(self.folder, "Journal.2026-01-03T000000.01.log", "Alice", [{"event": "Location", "timestamp": "2026-01-03T01:00:00Z", "StarSystem": "A"},
                                                                    jump("D", "2026-01-03T02:00:00Z")])
        write(self.folder, "Journal.2026-01-04T000000.01.log", "Alice", [{"event": "Location", "timestamp": "2026-01-04T01:00:00Z", "StarSystem": "D"}])

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        self.h._cmdr = "Alice"
        self.h._read_all("Alice", self.folder)

    def test_visits_scans_and_other_commanders(self):
        self.read()
        a = self.h.lookup("a")
        self.assertEqual((a.visits, a.scanned), (2, True), "A, B, A is two visits; the Location in A after a relog is the same visit")
        self.assertIsNone(self.h.lookup("C"), "Bob's journal is not Alice's history")
        self.assertEqual(self.h.lookup("B").visits, 1)
        self.assertEqual(a.files, ["Journal.2026-01-01T000000.01.log", "Journal.2026-01-03T000000.01.log"])

    def test_the_newest_journal_is_live_and_a_relog_is_not_a_new_visit(self):
        self.read()
        d = self.h.lookup("D")
        self.assertEqual(d.visits, 1, "D arrived in file 3 and the newest file starts there again")
        self.assertEqual(self.h.unindexed_files(self.folder), [os.path.join(self.folder, "Journal.2026-01-04T000000.01.log")])

    def test_a_live_arrival_is_counted_once_and_a_second_read_adds_nothing(self):
        self.read()
        self.h.record(jump("E", "2026-01-04T05:00:00Z"))
        self.h.record(jump("E", "2026-01-04T05:00:00Z"))
        self.assertEqual(self.h.lookup("E").visits, 1)
        before = self.h.lookup("A").visits
        self.read()
        self.assertEqual(self.h.lookup("A").visits, before)

    def test_visit_line(self):
        self.read()
        H.history = self.h
        self.h.ready = True
        self.assertEqual(H.visit_line("Never"), "First visit here")
        self.assertTrue(H.visit_line("A").startswith("Been here 1 time before · last 3 Jan 2026"), H.visit_line("A"))
        self.assertTrue(H.visit_line("A").endswith("you scanned here"))


if __name__ == "__main__":
    unittest.main()
