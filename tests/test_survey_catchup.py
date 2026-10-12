"""
Catching the Boxel Survey log up from recent journals (survey_catchup.py): what it recovers, and that a second run, or a system the
log already had, is never counted twice. Event shapes follow the game's journal. Temporary folders only.
"""
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

from plugin import survey_catchup as C, survey_log as L  # noqa: E402


def scan(system, body, cls=None, terraform=None, ts="2026-10-10T10:00:00Z", ls=100.0):
    entry = {"timestamp": ts, "event": "Scan", "ScanType": "Detailed", "BodyName": body, "StarSystem": system,
             "DistanceFromArrivalLS": ls}
    if cls:
        entry["PlanetClass"] = cls
    if terraform:
        entry["TerraformState"] = terraform
    return entry


def bio(body, count=2, ts="2026-10-10T10:05:00Z", kind="FSSBodySignals"):
    return {"timestamp": ts, "event": kind, "BodyName": body,
            "Signals": [{"Type": L.BIO_SIGNAL_TYPE, "Type_Localised": "Biological", "Count": count}]}


def key_for(system):
    return "Sector|A" if system.startswith("Boxel") else None


class ApplyTests(unittest.TestCase):
    def test_a_new_system_gets_its_notable_bodies_and_a_count_of_distinct_bodies(self):
        log = L.SurveyLog()
        events = [("Sys A", scan("Sys A", "Sys A 1", "Earthlike body")), ("Sys A", scan("Sys A", "Sys A 2")),
                  ("Sys A", scan("Sys A", "Sys A 2")),                    # the same body scanned again
                  ("Sys A", scan("Sys A", "Sys A 3", "Water world"))]
        result = C.apply(log, events)
        self.assertEqual((result.systems_added, result.notable_found), (1, 2))
        data = log.to_dict()["Sys A"]
        self.assertEqual(data["bodies_scanned"], 3)
        self.assertEqual(sorted(data["notable_bodies"]), ["Sys A 1", "Sys A 3"])
        self.assertEqual(data["notable_bodies"]["Sys A 1"]["tags"], ["elw"])

    def test_the_system_is_first_seen_at_the_time_of_the_old_event(self):
        log = L.SurveyLog()
        C.apply(log, [("Sys A", scan("Sys A", "Sys A 1", ts="2026-10-03T12:00:00Z"))])
        self.assertEqual(log.to_dict()["Sys A"]["first_seen"], "2026-10-03T12:00:00Z")

    def test_a_system_the_log_already_had_keeps_its_count_but_gains_missing_finds(self):
        log = L.SurveyLog()
        log.record_scan("Sys A", "Sys A 1", boxel_key=None, planet_class=None, terraform_state=None, distance_ls=1.0)
        log.record_scan("Sys A", "Sys A 2", boxel_key=None, planet_class=None, terraform_state=None, distance_ls=2.0)
        result = C.apply(log, [("Sys A", scan("Sys A", "Sys A 1")), ("Sys A", scan("Sys A", "Sys A 4", "Earthlike body"))])
        self.assertEqual(log.to_dict()["Sys A"]["bodies_scanned"], 2)                        # not 4
        self.assertEqual((result.systems_added, result.notable_found), (0, 1))
        self.assertIn("Sys A 4", log.to_dict()["Sys A"]["notable_bodies"])

    def test_running_it_twice_changes_nothing_the_second_time(self):
        log = L.SurveyLog()
        events = [("Sys A", scan("Sys A", "Sys A 1", "Earthlike body")), ("Sys A", scan("Sys A", "Sys A 2")),
                  ("Sys B", scan("Sys B", "Sys B 1")), ("Sys B", bio("Sys B 1"))]
        C.apply(log, events)
        once = json.dumps(log.to_dict(), sort_keys=True)
        second = C.apply(log, events)
        self.assertEqual(json.dumps(log.to_dict(), sort_keys=True), once)
        self.assertEqual((second.systems_added, second.notable_found), (0, 0))

    def test_biological_signals_are_recovered_and_tag_the_body(self):
        log = L.SurveyLog()
        C.apply(log, [("Sys A", scan("Sys A", "Sys A 1")), ("Sys A", bio("Sys A 1", 3)),
                      ("Sys A", bio("Sys A 1", 5, kind="SAASignalsFound"))])
        body = log.to_dict()["Sys A"]["notable_bodies"]["Sys A 1"]
        self.assertEqual((body["tags"], body["bio_signal_count"]), (["bio"], 5))          # the larger count wins

    def test_a_signal_without_a_biological_count_is_ignored(self):
        log = L.SurveyLog()
        C.apply(log, [("Sys A", {"event": "FSSBodySignals", "BodyName": "Sys A 1", "Signals": [{"Type": "$SAA_SignalType_Geological;", "Count": 4}]})])
        self.assertEqual(log.to_dict().get("Sys A", {}).get("notable_bodies", {}), {})

    def test_the_boxel_is_filled_in_for_procedural_names(self):
        log = L.SurveyLog()
        C.apply(log, [("Boxel 1", scan("Boxel 1", "Boxel 1 A"))], key_for)
        self.assertEqual(log.to_dict()["Boxel 1"]["boxel_key"], "Sector|A")

    def test_events_without_a_body_are_skipped(self):
        log = L.SurveyLog()
        self.assertEqual(C.apply(log, [("Sys A", {"event": "Scan", "timestamp": "2026-10-10T10:00:00Z"})]).scans_seen, 0)
        self.assertFalse(log.has_system("Sys A"))

    def test_a_live_scan_still_adds_one_each_time(self):
        log = L.SurveyLog()
        for _ in range(3):
            log.record_scan("Sys A", "Sys A 1", boxel_key=None, planet_class=None, terraform_state=None, distance_ls=1.0)
        self.assertEqual(log.to_dict()["Sys A"]["bodies_scanned"], 3)


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def journal(self, name, who, events, age=0.0):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            for entry in [{"event": "Fileheader"}, {"event": "Commander", "Name": who}, *events]:
                handle.write(json.dumps(entry) + "\n")
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))

    def test_scans_and_signals_come_back_with_the_system_they_happened_in(self):
        self.journal("Journal.1.log", "Alice", [
            {"event": "FSDJump", "StarSystem": "Sys A", "timestamp": "2026-10-10T09:00:00Z"},
            scan("Sys A", "Sys A 1", "Earthlike body"), bio("Sys A 1"),         # the signal event names no system
            {"event": "FSDJump", "StarSystem": "Sys B", "timestamp": "2026-10-10T11:00:00Z"},
            bio("Sys B 1", kind="SAASignalsFound")])
        found = C.read_since("Alice", 0.0, self.dir)
        self.assertEqual([(s, e["event"]) for s, e in found], [("Sys A", "Scan"), ("Sys A", "FSSBodySignals"), ("Sys B", "SAASignalsFound")])

    def test_only_the_commanders_own_events_and_recent_files_are_read(self):
        self.journal("Journal.1.log", "Alice", [scan("Sys A", "Sys A 1")])
        self.journal("Journal.2.log", "Bob", [scan("Sys B", "Sys B 1")])
        self.journal("Journal.3.log", "Alice", [scan("Sys C", "Sys C 1")], age=40 * 86400)
        since = time.time() - 14 * 86400
        self.assertEqual([s for s, _ in C.read_since("alice", since, self.dir)], ["Sys A"])
        self.assertEqual([s for s, _ in C.read_since("Bob", since, self.dir)], ["Sys B"])
        self.assertEqual(C.read_since("", 0.0, self.dir), [])

    def test_a_missing_folder_gives_nothing(self):
        self.assertEqual(C.read_since("Alice", 0.0, os.path.join(self.dir, "nope")), [])

    def test_the_whole_path_from_files_to_log_is_safe_to_repeat(self):
        self.journal("Journal.1.log", "Alice", [{"event": "FSDJump", "StarSystem": "Sys A"}, scan("Sys A", "Sys A 1", "Earthlike body"),
                                                scan("Sys A", "Sys A 2")])
        log = L.SurveyLog()
        for _ in range(2):
            C.apply(log, C.read_since("Alice", 0.0, self.dir))
        data = log.to_dict()["Sys A"]
        self.assertEqual((data["bodies_scanned"], sorted(data["notable_bodies"])), (2, ["Sys A 1"]))


if __name__ == "__main__":
    unittest.main()
