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
from plugin import mission_cargo  # noqa: E402


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

    def test_journal_derived_active_set_shows_without_a_login_event(self) -> None:
        self.tracker.load_history({"A": {1: _accepted(1), 2: _accepted(2)}}, {"A": {2, 99}})
        self.tracker.switch_to("A")
        self.assertEqual(list(self.tracker.snapshot()), [2])
        self.tracker.sync_login("A", [1])   # the real login list wins
        self.assertEqual(list(self.tracker.snapshot()), [1])

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

    def test_combat_bond_kills_are_collected_like_bounties(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            _stub.journal_dir = folder
            self._write(folder, "Journal.1.log", [
                {"event": "Commander", "Name": "A"},
                {"event": "Bounty", "VictimFaction": "Pirates"},
                {"event": "FactionKillBond", "VictimFaction": "Pirates", "AwardingFaction": "Navy", "Reward": 1000},
            ])
            log = journal_scan.read_backlog(dt.date.today() - dt.timedelta(days=14))
        self.assertEqual(len(log.bounties["A"]), 2)

    def test_active_set_is_worked_out_from_the_journals(self) -> None:
        def event(name: str, mission_id: int) -> dict:
            return {"event": name, "MissionID": mission_id}
        with tempfile.TemporaryDirectory() as folder:
            _stub.journal_dir = folder
            self._write(folder, "Journal.1.log", [
                {"event": "Commander", "Name": "A"},
                _accepted(1), _accepted(2),
                {"event": "Missions", "Active": [{"MissionID": 1}, {"MissionID": 2}], "Failed": [], "Complete": []},
                _accepted(3), event("MissionCompleted", 1), _accepted(4), event("MissionAbandoned", 4),
                {"event": "Commander", "Name": "B"},
                _accepted(5), event("MissionFailed", 5),
            ], age_days=2)
            self._write(folder, "Journal.2.log", [
                {"event": "Commander", "Name": "A"}, event("MissionFailed", 2), _accepted(6),
            ], age_days=1)
            log = journal_scan.read_backlog(dt.date.today() - dt.timedelta(days=14))
        self.assertEqual(log.active_ids["A"], {3, 6})
        self.assertEqual(log.active_ids["B"], set())

    def test_a_later_login_list_replaces_the_derived_set(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            _stub.journal_dir = folder
            self._write(folder, "Journal.1.log", [
                {"event": "Commander", "Name": "A"}, _accepted(1), _accepted(2),
                {"event": "Missions", "Active": [{"MissionID": 2}], "Failed": [], "Complete": []},
            ])
            log = journal_scan.read_backlog(dt.date.today() - dt.timedelta(days=14))
        self.assertEqual(log.active_ids["A"], {2})

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


class MissionCargoTests(unittest.TestCase):
    @staticmethod
    def depot(mission_id: int, collected: int, delivered: int, total: int) -> dict:
        return {"event": "CargoDepot", "MissionID": mission_id, "ItemsCollected": collected,
                "ItemsDelivered": delivered, "TotalItemsToDeliver": total}

    def test_progress_reads_the_event_and_rejects_junk(self) -> None:
        progress = mission_cargo.from_event(self.depot(1, 120, 80, 200))
        self.assertEqual((progress.collected, progress.delivered, progress.total), (120, 80, 200))
        self.assertEqual(progress.still_to_collect, 80)
        self.assertEqual(mission_cargo.CargoProgress(0, 50, 50).still_to_collect, 0)   # delivered counts as collected
        self.assertIsNone(mission_cargo.from_event({"event": "CargoDepot", "MissionID": 1}))
        self.assertIsNone(mission_cargo.from_event(self.depot(1, 0, 0, 0)))

    def test_tracker_updates_forgets_and_tells_subscribers_only_on_change(self) -> None:
        tracker = mission_cargo.MissionCargo()
        heard: list = []
        tracker.changed.connect(lambda: heard.append(1))
        tracker.update("A", self.depot(1, 10, 0, 100))
        tracker.update("A", self.depot(1, 10, 0, 100))   # unchanged
        tracker.update("A", self.depot(1, 40, 0, 100))
        self.assertEqual(len(heard), 2)
        self.assertEqual(tracker.get("A", 1).collected, 40)
        self.assertIsNone(tracker.get("B", 1))
        tracker.forget("A", 1)
        self.assertIsNone(tracker.get("A", 1))

    def test_backlog_keeps_the_newest_event_per_mission(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            _stub.journal_dir = folder
            JournalScanTests._write(folder, "Journal.1.log", [
                {"event": "Commander", "Name": "A"},
                self.depot(7, 10, 0, 100), self.depot(7, 60, 20, 100),
            ])
            log = journal_scan.read_backlog(dt.date.today() - dt.timedelta(days=14))
        tracker = mission_cargo.MissionCargo()
        tracker.initialize(log.cargo)
        self.assertEqual(tracker.get("A", 7).delivered, 20)

    def test_a_collect_missions_needed_count_drops_by_what_is_collected(self) -> None:
        from plugin import all_missions
        event = {"event": "MissionAccepted", "MissionID": 9, "Name": "Mission_Collect_Boom", "Commodity": "$Gold_Name;",
                 "Commodity_Localised": "Gold", "Count": 200, "Faction": "F", "LocalisedName": "Collect gold"}
        plain = all_missions.MissionSummary.from_event(event)
        withcargo = all_missions.MissionSummary.from_event(event, mission_cargo.CargoProgress(120, 0, 200))
        self.assertEqual(plain.needed_commodity_count, 200)
        self.assertEqual(withcargo.needed_commodity_count, 80)
        self.assertEqual(withcargo.cargo.collected, 120)


if __name__ == "__main__":
    unittest.main()
