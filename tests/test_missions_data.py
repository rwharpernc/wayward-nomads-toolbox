"""
Unit tests for the Missions data layer: active_missions.py, kill_missions.py
and journal_scan.py.

Pure logic - no EDMC runtime or display needed (EDMC's `config` module is
stubbed). Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import time
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
_stub = types.ModuleType("config")
_stub.appname = "EDMarketConnector"
_stub.journal_dir = ""
_stub.config = types.SimpleNamespace(
    get_str=lambda key: _stub.journal_dir if key == "journaldir" else "",
    default_journal_dir="")
sys.modules["config"] = _stub

from plugin import active_missions as am  # noqa: E402
from plugin import journal_scan  # noqa: E402
from plugin import kill_missions as km  # noqa: E402


def _accepted(mission_id: int, **extra) -> dict:
    return {"event": "MissionAccepted", "MissionID": mission_id, "Name": "Mission_Massacre_Boom", **extra}


class ActiveMissionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = am.ActiveMissions()
        self.heard: list = []
        self.tracker.changed.connect(self.heard.append)

    def test_unknown_until_the_login_event(self) -> None:
        self.tracker.load_history({"A": {1: _accepted(1)}})
        self.tracker.switch_to("A")
        self.assertIsNone(self.tracker.snapshot())
        self.assertEqual(self.heard, [None])

    def test_login_event_keeps_only_known_active_ids(self) -> None:
        self.tracker.load_history({"A": {1: _accepted(1), 2: _accepted(2)}})
        self.tracker.sync_login("A", [2, 99])
        self.assertEqual(list(self.tracker.snapshot()), [2])
        self.assertEqual(self.tracker.commander, "A")

    def test_commanders_are_kept_apart(self) -> None:
        self.tracker.load_history({"A": {1: _accepted(1)}, "B": {2: _accepted(2)}})
        self.tracker.sync_login("A", [1])
        self.tracker.sync_login("B", [2])
        self.assertEqual(list(self.tracker.snapshot()), [2])
        self.tracker.switch_to("A")
        self.assertEqual(list(self.tracker.snapshot()), [1])

    def test_accept_and_finish(self) -> None:
        self.tracker.sync_login("A", [])
        self.heard.clear()
        self.tracker.accept("A", _accepted(5))
        self.assertEqual(list(self.tracker.snapshot()), [5])
        self.tracker.finish("A", 5)
        self.assertEqual(self.tracker.snapshot(), {})
        self.assertEqual(len(self.heard), 2)

    def test_other_commanders_changes_are_silent(self) -> None:
        self.tracker.sync_login("A", [])
        self.heard.clear()
        self.tracker.accept("B", _accepted(7))
        self.assertEqual(self.heard, [])
        self.tracker.finish("B", 7)
        self.assertEqual(self.heard, [])

    def test_finishing_an_unknown_mission_is_silent(self) -> None:
        self.tracker.sync_login("A", [])
        self.heard.clear()
        self.tracker.finish("A", 123)
        self.assertEqual(self.heard, [])

    def test_missing_commander_is_ignored(self) -> None:
        self.tracker.accept("", _accepted(1))
        self.tracker.sync_login("", [1])
        self.assertEqual(self.heard, [])


class EstimateProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bounties: list = []
        self.redirected: set = set()
        tracker = km.kill_tracker
        self._saved = (tracker.current_cmdr, tracker.get_bounties, tracker.get_redirected, tracker.is_ground_kill)
        tracker.current_cmdr = "A"
        tracker.get_bounties = lambda cmdr: self.bounties
        tracker.get_redirected = lambda cmdr: self.redirected
        tracker.is_ground_kill = lambda bounty: bool(bounty.get("ground"))

    def tearDown(self) -> None:
        tracker = km.kill_tracker
        tracker.current_cmdr, tracker.get_bounties, tracker.get_redirected, tracker.is_ground_kill = self._saved

    @staticmethod
    def _mission(mission_id, giver, target="Pirates", count=3, at="2026-10-01T10:00:00Z", ground=False):
        return km.KillMission(id=mission_id, accepted_at=at, source_faction=giver, target_faction=target,
                              target_type="", target_system="S", target_settlement="", count=count,
                              reward=0, is_wing=False, is_ground=ground, is_illegal=False)

    def test_one_kill_counts_once_per_giver(self) -> None:
        missions = [self._mission(1, "G1"), self._mission(2, "G1"), self._mission(3, "G2")]
        self.bounties = [{"VictimFaction": "Pirates", "timestamp": "2026-10-01T11:00:00Z"}]
        self.assertEqual(km.estimate_progress(missions), {1: 1, 2: 0, 3: 1})

    def test_kills_fill_the_oldest_mission_first(self) -> None:
        missions = [self._mission(1, "G1", count=1, at="2026-10-01T10:00:00Z"),
                    self._mission(2, "G1", count=1, at="2026-10-01T09:00:00Z")]
        self.bounties = [{"VictimFaction": "Pirates", "timestamp": "2026-10-01T11:00:00Z"}] * 2
        self.assertEqual(km.estimate_progress(missions), {1: 1, 2: 1})

    def test_kills_before_acceptance_and_in_the_wrong_arena_do_not_count(self) -> None:
        missions = [self._mission(1, "G1")]
        self.bounties = [{"VictimFaction": "Pirates", "timestamp": "2026-10-01T09:00:00Z"},
                         {"VictimFaction": "Pirates", "timestamp": "2026-10-01T11:00:00Z", "ground": True},
                         {"VictimFaction": "Other", "timestamp": "2026-10-01T11:00:00Z"},
                         {"timestamp": "2026-10-01T11:00:00Z"}]
        self.assertEqual(km.estimate_progress(missions), {1: 0})

    def test_redirected_missions_are_complete_and_take_no_more_kills(self) -> None:
        missions = [self._mission(1, "G1", count=2), self._mission(2, "G1", count=2)]
        self.redirected = {1}
        self.bounties = [{"VictimFaction": "Pirates", "timestamp": "2026-10-01T11:00:00Z"}]
        self.assertEqual(km.estimate_progress(missions), {1: 2, 2: 1})


class JournalScanTests(unittest.TestCase):
    @staticmethod
    def _write(folder: str, name: str, events: list, age_days: float = 0.0) -> None:
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf8") as handle:
            handle.write("not json\n")
            for event in events:
                handle.write(json.dumps(event) + "\n")
        stamp = time.time() - age_days * 86400
        os.utime(path, (stamp, stamp))

    def test_collects_events_per_commander_and_skips_junk(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            _stub.journal_dir = folder
            self._write(folder, "Journal.1.log", [
                {"event": "Commander", "Name": "A"},
                _accepted(1),
                {"event": "Bounty", "VictimFaction": "Pirates"},
                {"event": "MissionRedirected", "MissionID": 1, "NewDestinationStation": "St"},
                {"event": "MissionAccepted"},  # missing MissionID: skipped
                {"event": "CommunityGoal", "CurrentGoals": [{"CGID": 4, "Title": "x"}]},
                {"event": "Commander", "Name": "B"},
                _accepted(2),
            ])
            log = journal_scan.read_backlog(dt.date.today() - dt.timedelta(days=14))
        self.assertEqual({c: list(m) for c, m in log.accepted.items()}, {"A": [1], "B": [2]})
        self.assertEqual(len(log.bounties["A"]), 1)
        self.assertEqual(log.redirected["A"], {1})
        self.assertEqual(log.redirect_targets["A"][1], {"station": "St", "system": ""})
        self.assertEqual(list(log.goals["A"]), [4])

    def test_old_files_are_left_out(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            _stub.journal_dir = folder
            self._write(folder, "Journal.old.log", [{"event": "Commander", "Name": "A"}, _accepted(1)], age_days=30)
            self._write(folder, "Journal.new.log", [{"event": "Commander", "Name": "A"}, _accepted(2)], age_days=1)
            log = journal_scan.read_backlog(dt.date.today() - dt.timedelta(days=14))
        self.assertEqual(list(log.accepted["A"]), [2])

    def test_missing_folder_gives_an_empty_result(self) -> None:
        _stub.journal_dir = os.path.join(tempfile.gettempdir(), "definitely-not-a-journal-folder")
        log = journal_scan.read_backlog(dt.date.today() - dt.timedelta(days=14))
        self.assertEqual(log.accepted, {})
        _stub.journal_dir = ""
        self.assertEqual(journal_scan.read_backlog(dt.date.today()).accepted, {})


if __name__ == "__main__":
    unittest.main()
