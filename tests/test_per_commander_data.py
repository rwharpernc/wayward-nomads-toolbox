"""
Data that belongs to one commander is stored separately and never shared.

Two commanders on one install must not see or change each other's hotspots, driven ground, survey finds, Codex tally or
session history. These tests save for one commander, then load for another, and check nothing crosses over. They use only
temporary folders and JSON keys (never a commander name in a file name), so they behave the same on Windows and Linux.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import commander_data  # noqa: E402
from plugin import mining_coverage as coverage  # noqa: E402
from plugin import mining_hotspots as hotspots  # noqa: E402
from plugin import codex_backfill, codex_completionist_state as codex_state  # noqa: E402
from plugin import store as pp_store  # noqa: E402
from plugin import survey_log  # noqa: E402

RADIUS = 1_000_000.0


class CommanderDataTests(unittest.TestCase):
    def test_keys_ignore_case_and_spaces_and_a_blank_name_has_none(self) -> None:
        self.assertEqual(commander_data.key_for("  BOCHEAUX "), commander_data.key_for("Bocheaux"))
        self.assertEqual(commander_data.key_for(None), "")

    def test_each_commander_has_their_own_payload(self) -> None:
        store = commander_data.new_store()
        commander_data.payload_for(store, "Alice", list).append(1)
        commander_data.payload_for(store, "Bob", list).append(2)
        self.assertEqual(commander_data.payload_for(store, "alice", list), [1])
        self.assertEqual(commander_data.payload_for(store, "BOB", list), [2])

    def test_old_shared_data_is_claimed_once_by_the_first_commander_only(self) -> None:
        store = commander_data.new_store()
        store["legacy"] = ["old"]
        self.assertEqual(commander_data.payload_for(store, "Alice", list), ["old"])
        self.assertEqual(commander_data.payload_for(store, "Bob", list), [])
        self.assertIsNone(store["legacy"])

    def test_file_round_trip_old_shape_and_bad_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "x.json")
            self.assertEqual(commander_data.read(path, lambda raw: True)["commanders"], {})   # missing
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(["a", "b"], handle)                                                    # the old flat shape
            self.assertEqual(commander_data.read(path, lambda raw: isinstance(raw, list))["legacy"], ["a", "b"])
            store = commander_data.new_store()
            commander_data.put(store, "Alice", {"n": 1})
            commander_data.put(store, "Bob", {"n": 2})
            commander_data.write(path, store)
            loaded = commander_data.read(path, lambda raw: False)
            self.assertEqual(commander_data.payload_for(loaded, "bob", dict), {"n": 2})
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not json")
            self.assertEqual(commander_data.read(path, lambda raw: True)["commanders"], {})     # unreadable


class HotspotIsolationTests(unittest.TestCase):
    def spot(self, name: str) -> "hotspots.Hotspot":
        return hotspots.Hotspot(system="Sol", body="Mars 1", material=name, latitude=1.0, longitude=2.0)

    def test_hotspots_saved_by_one_commander_are_invisible_to_another(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repo = hotspots.HotspotRepository()
            repo.load(folder)
            repo.set_commander("Alice")
            repo.add(self.spot("Monazite"))
            repo.set_commander("Bob")
            self.assertEqual(repo.all(), [])
            repo.add(self.spot("Painite"))
            repo.set_commander("alice")
            self.assertEqual([h.material for h in repo.all()], ["Monazite"])

            again = hotspots.HotspotRepository()      # a fresh start reads the same two lists
            again.load(folder)
            again.set_commander("Bob")
            self.assertEqual([h.material for h in again.all()], ["Painite"])

    def test_changes_by_one_commander_never_reach_the_other(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repo = hotspots.HotspotRepository()
            repo.load(folder)
            repo.set_commander("Alice")
            repo.add(self.spot("Monazite"))
            repo.set_commander("Bob")
            repo.add(self.spot("Painite"))
            repo.remove(0)
            repo.set_commander("Alice")
            self.assertEqual(len(repo.all()), 1)

    def test_old_shared_list_goes_to_the_first_commander_seen_only(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, hotspots.HOTSPOTS_FILENAME), "w", encoding="utf-8") as handle:
                json.dump([{"system": "Sol", "body": "Mars 1", "material": "Old"}], handle)
            repo = hotspots.HotspotRepository()
            repo.load(folder)
            self.assertEqual(repo.all(), [])                  # nothing shown until someone is known
            repo.set_commander("Alice")
            self.assertEqual([h.material for h in repo.all()], ["Old"])
            repo.set_commander("Bob")
            self.assertEqual(repo.all(), [])

    def test_a_hotspot_added_before_any_commander_is_known_goes_to_the_first_one(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repo = hotspots.HotspotRepository()
            repo.load(folder)
            repo.add(self.spot("Early"))
            repo.set_commander("Alice")
            repo.set_commander("Bob")
            self.assertEqual(repo.all(), [])
            repo.set_commander("Alice")
            self.assertEqual([h.material for h in repo.all()], ["Early"])


class CoverageIsolationTests(unittest.TestCase):
    def test_driven_ground_is_per_commander(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repo = coverage.CoverageRepository()
            repo.load(folder)
            repo.set_commander("Alice")
            repo.record("Sol", "Earth", 10.0, 20.0, RADIUS)
            repo.set_commander("Bob")
            self.assertIsNone(repo.for_body("Sol", "Earth"))
            repo.record("Sol", "Earth", -5.0, 5.0, RADIUS)
            repo.set_commander("Alice")
            self.assertEqual(repo.for_body("Sol", "Earth").center, coverage.CoveragePoint(10.0, 20.0))

    def test_old_shared_map_goes_to_the_first_commander_seen_only(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, coverage.COVERAGE_FILENAME), "w", encoding="utf-8") as handle:
                json.dump({"sol|earth": {"center": {"latitude": 1.0, "longitude": 2.0}, "points": []}}, handle)
            repo = coverage.CoverageRepository()
            repo.load(folder)
            repo.set_commander("Alice")
            self.assertIsNotNone(repo.for_body("Sol", "Earth"))
            repo.set_commander("Bob")
            self.assertIsNone(repo.for_body("Sol", "Earth"))


class SurveyLogIsolationTests(unittest.TestCase):
    def log_with(self, system: str) -> "survey_log.SurveyLog":
        log = survey_log.SurveyLog()
        log.record_scan(system, system + " 1", boxel_key=None, planet_class="Earthlike body",
                        terraform_state=None, distance_ls=10.0)
        return log

    def test_finds_are_per_commander(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            survey_log.save_log(folder, "Alice", self.log_with("Alpha"))
            survey_log.save_log(folder, "Bob", self.log_with("Beta"))
            alice = survey_log.load_log(folder, "ALICE")
            bob = survey_log.load_log(folder, "bob")
            self.assertEqual([row["system"] for row in alice.export_rows()], ["Alpha"])
            self.assertEqual([row["system"] for row in bob.export_rows()], ["Beta"])
            self.assertEqual(survey_log.load_log(folder, "Carol").export_rows(), [])

    def test_saving_one_commander_does_not_disturb_another(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            survey_log.save_log(folder, "Alice", self.log_with("Alpha"))
            survey_log.save_log(folder, "Bob", survey_log.SurveyLog())
            self.assertEqual(len(survey_log.load_log(folder, "Alice").export_rows()), 1)

    def test_an_old_shared_log_goes_to_the_first_commander_seen_only(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, survey_log.LOG_FILENAME), "w", encoding="utf-8") as handle:
                json.dump(self.log_with("Old").to_dict(), handle)
            self.assertEqual(len(survey_log.load_log(folder, "Alice").export_rows()), 1)
            self.assertEqual(survey_log.load_log(folder, "Bob").export_rows(), [])


class CodexIsolationTests(unittest.TestCase):
    def test_each_commander_has_their_own_tally_and_the_old_shared_one_is_not_handed_out(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, codex_state.STATE_FILENAME), "w", encoding="utf-8") as handle:
                json.dump([{"name": "mixed"}], handle)                      # the old single tally, everyone's finds
            self.assertTrue(codex_state.has_old_shared_tally(folder))
            self.assertIsNone(codex_state.load_commander(folder, "Alice"))      # nobody inherits it
            codex_state.save_commander(folder, "Alice", {"entries": [{"name": "a"}], "last_event_at": "t1"})
            codex_state.save_commander(folder, "Bob", {"entries": [{"name": "b"}], "last_event_at": "t2"})
            self.assertEqual(codex_state.load_commander(folder, "ALICE")["entries"], [{"name": "a"}])
            self.assertEqual(codex_state.load_commander(folder, "bob")["entries"], [{"name": "b"}])
            self.assertIsNone(codex_state.load_commander(folder, "Carol"))
            self.assertTrue(codex_state.has_old_shared_tally(folder))           # kept, untouched, for safety


    def test_the_old_shared_tally_is_kept_for_a_while_then_removed_only_once_someone_has_their_own(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, codex_state.STATE_FILENAME)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump([{"name": "mixed"}], handle)
            self.assertFalse(codex_state.tidy_old_tally(folder, "2026-10-10T00:00:00Z"))   # first seen: the clock starts
            self.assertFalse(codex_state.tidy_old_tally(folder, "2026-11-30T00:00:00Z"))   # 51 days: kept
            self.assertTrue(codex_state.has_old_shared_tally(folder))
            self.assertFalse(codex_state.tidy_old_tally(folder, "2026-12-30T00:00:00Z"))   # old enough, but nobody has their own yet
            codex_state.save_commander(folder, "Alice", {"entries": [], "last_event_at": "t"})
            self.assertTrue(codex_state.tidy_old_tally(folder, "2026-12-30T00:00:00Z"))
            self.assertFalse(codex_state.has_old_shared_tally(folder))
            self.assertIsNotNone(codex_state.load_commander(folder, "Alice"))             # their tally is untouched
            self.assertFalse(codex_state.tidy_old_tally(folder, "2027-06-01T00:00:00Z"))   # nothing left to do

    def test_journal_readers_return_only_the_named_commanders_finds(self) -> None:
        def find(name: str, stamp: str) -> dict:
            return {"event": "CodexEntry", "Name": name, "timestamp": stamp}
        with tempfile.TemporaryDirectory() as folder:
            lines = [{"event": "Commander", "Name": "ALICE"}, find("a1", "2026-01-01T00:00:00Z"),
                     {"event": "LoadGame", "Commander": "Bob"}, find("b1", "2026-01-02T00:00:00Z"),
                     {"event": "LoadGame", "Commander": "Alice"}, find("a2", "2026-01-03T00:00:00Z")]
            with open(os.path.join(folder, "Journal.1.log"), "w", encoding="utf-8") as handle:
                for line in lines:
                    handle.write(json.dumps(line) + chr(10))
            self.assertEqual([e["Name"] for e in codex_backfill.scan_all_codex_entries("alice", folder)], ["a1", "a2"])
            self.assertEqual([e["Name"] for e in codex_backfill.scan_all_codex_entries("Bob", folder)], ["b1"])
            self.assertEqual(codex_backfill.scan_all_codex_entries("Carol", folder), [])


class PowerplayHistoryIsolationTests(unittest.TestCase):
    def session(self, cmdr: str, n: int) -> dict:
        return {"cmdr": cmdr, "started_at": f"2026-10-{n:02d}"}

    def test_a_commander_only_sees_their_own_sessions_and_unknown_gets_none(self) -> None:
        history = [self.session("Alice", 1), self.session("BOB", 2), self.session("alice", 3), {"started_at": "old"}]
        self.assertEqual([s["started_at"] for s in pp_store.sessions_of(history, "Alice")], ["2026-10-01", "2026-10-03"])
        self.assertEqual([s["started_at"] for s in pp_store.sessions_of(history, "bob")], ["2026-10-02"])
        self.assertEqual(pp_store.sessions_of(history, ""), [])         # nobody to show the unattributed ones to
        self.assertEqual(pp_store.sessions_of(history, None), [])

    def test_the_history_limit_is_per_commander_so_one_cannot_push_out_another(self) -> None:
        history = [self.session("Bob", 1)] + [self.session("Alice", 2) for _ in range(5)]
        kept = pp_store.trim(history, limit=3)
        self.assertEqual([s["cmdr"] for s in kept].count("Alice"), 3)
        self.assertEqual([s["cmdr"] for s in kept].count("Bob"), 1)      # Bob's only session survives Alice's busy spell
        self.assertEqual(kept[0]["cmdr"], "Bob")                         # order kept

    def test_the_file_round_trips_for_every_commander(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            saver = pp_store.SessionStore(folder)
            saver.save([self.session("Alice", 1), self.session("Bob", 2)], self.session("Alice", 3))
            history, current = pp_store.SessionStore(folder).load()
            self.assertEqual(len(history), 2)
            self.assertEqual(current["cmdr"], "Alice")


if __name__ == "__main__":
    unittest.main()
