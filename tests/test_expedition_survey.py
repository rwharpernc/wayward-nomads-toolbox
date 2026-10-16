"""Expedition survey tracking (expedition.py `on_survey`): what is scanned, discovered first and mapped is counted against the visited stop of the
active expedition, kept per commander, and survives a restart."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import expedition as X  # noqa: E402


class Clock:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return f"2026-10-16T12:{self.n:02d}:00Z"


def make(folder, cmdr="Bocheaux"):
    ids = iter(f"id{i}" for i in range(1, 1000))
    book = X.ExpeditionBook(now=Clock(), new_id=lambda: next(ids), clock=lambda: 1000.0)
    book.load(folder)
    book.set_commander(cmdr)
    return book


def scan(body, system="Sol", discovered=True, event="Scan"):
    return {"event": event, "BodyName": body, "StarSystem": system, "WasDiscovered": discovered}


class SurveyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)
        self.trip = self.book.create("Run")
        self.sol = self.book.add_stop(self.trip.id, "Sol")
        self.far = self.book.add_stop(self.trip.id, "Far Away")
        self.book.start(self.trip.id)
        self.book.on_arrival("Sol", "2026-10-16T01:00:00Z", 10.0, is_jump=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_scans_are_counted_once_per_body_and_first_discoveries_separately(self):
        self.assertIsNotNone(self.book.on_survey(scan("Sol A 1", discovered=False)))
        self.assertIsNotNone(self.book.on_survey(scan("Sol A 2")))
        self.assertIsNone(self.book.on_survey(scan("Sol A 1", discovered=False)), "a body scanned twice counts once")
        self.assertEqual((self.sol.scanned, self.sol.firsts), (["Sol A 1", "Sol A 2"], ["Sol A 1"]))

    def test_the_body_count_and_the_text(self):
        self.assertEqual(self.sol.survey_text(), "")
        self.book.on_survey({"event": "FSSDiscoveryScan", "SystemName": "Sol", "BodyCount": 12})
        self.assertEqual(self.sol.survey_text(), "0 of 12 scanned")
        self.book.on_survey(scan("Sol A 1", discovered=False))
        self.book.on_survey({"event": "SAAScanComplete", "BodyName": "Sol A 1"}, "Sol")
        self.assertEqual(self.sol.survey_text(), "1 of 12 scanned · 1 first · 1 mapped")
        self.book.on_survey({"event": "FSSAllBodiesFound", "SystemName": "Sol", "Count": 14})
        self.assertEqual(self.sol.bodies, 14)

    def test_belt_clusters_and_other_systems_count_for_nothing(self):
        self.assertIsNone(self.book.on_survey(scan("Sol A Belt Cluster 3")))
        self.assertIsNone(self.book.on_survey(scan("Elsewhere 1", system="Elsewhere")))
        self.assertEqual(self.sol.scanned, [])
        self.assertIsNone(self.book.on_survey(scan("Far Away 1", system="Far Away")), "a stop not reached yet counts nothing")

    def test_nothing_is_counted_without_an_active_expedition(self):
        self.book.pause(self.trip.id)
        self.assertIsNone(self.book.on_survey(scan("Sol A 1")))
        self.assertEqual(self.sol.scanned, [])

    def test_an_event_without_a_system_uses_the_one_given(self):
        self.assertIsNotNone(self.book.on_survey({"event": "SAAScanComplete", "BodyName": "Sol A 1"}, "sol"))
        self.assertIsNone(self.book.on_survey({"event": "SAAScanComplete", "BodyName": "Sol A 2"}, ""))

    def test_totals_across_stops(self):
        self.book.on_survey(scan("Sol A 1", discovered=False))
        self.book.on_arrival("Far Away", "2026-10-16T02:00:00Z", 10.0, is_jump=True)
        self.book.on_survey(scan("Far Away 1", system="Far Away", discovered=False))
        self.book.on_survey(scan("Far Away 2", system="Far Away"))
        self.assertEqual(self.trip.survey_totals(), (3, 2, 0))
        self.assertEqual(self.trip.survey_text(), "3 scanned · 2 first")

    def test_it_is_saved_per_commander_and_read_back(self):
        self.book.on_survey({"event": "FSSDiscoveryScan", "SystemName": "Sol", "BodyCount": 7})
        self.book.on_survey(scan("Sol A 1", discovered=False))
        self.book.flush()
        again = make(self.tmp.name)
        stop = again.get(self.trip.id).stops[0]
        self.assertEqual((stop.bodies, stop.scanned, stop.firsts), (7, ["Sol A 1"], ["Sol A 1"]))
        other = make(self.tmp.name, cmdr="Mactavious")
        self.assertEqual(other.expeditions(), [], "another commander sees none of it")

    def test_a_damaged_file_gives_clean_fields_and_a_stop_without_survey_adds_nothing_to_the_file(self):
        stop = X._stop_from_raw({"system": "Sol", "bodies": "many", "scanned": ["A", "A", 3, ""], "mapped": "x"})
        self.assertEqual((stop.bodies, stop.scanned, stop.mapped, stop.firsts), (0, ["A"], [], []))
        self.assertEqual(X._survey_to_raw(X.Stop("a", "Sol")), {})

    def test_the_lists_stop_growing_at_the_limit(self):
        for number in range(X.MAX_SURVEY_NAMES + 5):
            self.book.on_survey(scan(f"Sol A {number}"))
        self.assertEqual(len(self.sol.scanned), X.MAX_SURVEY_NAMES)


if __name__ == "__main__":
    unittest.main()
