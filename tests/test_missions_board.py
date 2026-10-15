"""The Missions window's data (missions_board.py) and the pinned-mission book (mission_pins.py): the rows, their order, progress, the totals line, grouping by
place, the detail lines, and pins kept per commander on disk. No Tk: the window itself is exercised by a real-Tk smoke script when a display exists."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _Anything(types.ModuleType):
    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        return mock.MagicMock(name=f"{self.__name__}.{name}")


import tkinter  # noqa: E402,F401

_EDMC = ("theme", "myNotebook", "monitor", "ttkHyperlinkLabel", "edmc_data", "plug", "companion", "EDMCLogging", "l10n", "timeout_session",
         "protocol", "prefs", "killswitch", "Tooltips", "ttkDefaults", "requests")
_CONFIG = types.ModuleType("config")
_CONFIG.appname = "EDMarketConnector"  # type: ignore[attr-defined]
_CONFIG.config = types.SimpleNamespace(get_str=lambda *_a, **_k: "", get_bool=lambda *_a, default=False, **_k: default, set=lambda *_a: None)  # type: ignore[attr-defined]

import plugin as _plugin_package  # noqa: E402

_BEFORE = set(sys.modules)
with mock.patch.dict(sys.modules, {**{name: _Anything(name) for name in _EDMC}, "config": _CONFIG}):
    B = importlib.import_module("plugin.missions_board")
    pins = importlib.import_module("plugin.mission_pins")
    all_missions = importlib.import_module("plugin.all_missions")
    mission_cargo = importlib.import_module("plugin.mission_cargo")
    mission_types = importlib.import_module("plugin.mission_types")
    _ADDED = [name for name in sys.modules if name not in _BEFORE and name.startswith("plugin.")]
for _name in _ADDED:
    _short = _name.split(".", 1)[1]
    if "." not in _short and hasattr(_plugin_package, _short):
        delattr(_plugin_package, _short)

NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)


def iso(minutes):
    return (NOW + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def summary(mission_id, name="Deliver Gold", system="Sol", station="Dock", minutes=600, reward=1_000_000, category=mission_types.TRADE, cargo=None,
            commodity="", needed=0, wing=False, illegal=False):
    return all_missions.MissionSummary(
        id=mission_id, name=name, source_faction="Faction", destination_system=system, destination_station=station, reward=reward, is_wing=wing,
        expiry=iso(minutes) if minutes is not None else "", accepted_at=iso(-600), category=category, is_illegal=illegal, commodity=commodity,
        needed_commodity=commodity, needed_commodity_count=needed, cargo=cargo)


def board(*summaries, **kw):
    return B.rows_from({s.id: s for s in summaries}, **kw)


class RowsTests(unittest.TestCase):
    def test_ready_first_then_soonest_then_no_expiry_last(self):
        rows = board(summary(1, minutes=300), summary(2, minutes=60), summary(3, minutes=None), summary(4, minutes=900), redirected={4})
        self.assertEqual([r.id for r in rows], [4, 2, 1, 3])

    def test_a_redirected_mission_goes_to_its_new_hand_in_place(self):
        rows = board(summary(1, system="Sol", station="Dock"), redirected={1}, redirects={1: {"system": "Lave", "station": "Lave Station"}})
        self.assertEqual((rows[0].system, rows[0].station, rows[0].ready, rows[0].fraction), ("Lave", "Lave Station", True, 1.0))
        self.assertEqual(rows[0].where(), "Lave / Lave Station")

    def test_cargo_progress(self):
        cargo = mission_cargo.CargoProgress(total=40, collected=30, delivered=10)
        row = board(summary(1, cargo=cargo))[0]
        self.assertEqual((row.progress, row.fraction), ("10/40", 0.25))
        self.assertIn("30/40 collected", row.cargo_note)

    def test_kill_progress_marks_an_estimate_until_it_is_ready(self):
        row = board(summary(1, category=mission_types.MASSACRE_SPACE), kills={1: (18, 40, True)})[0]
        self.assertEqual((row.progress, row.fraction), ("~18/40 kills", 0.45))
        done = board(summary(1, category=mission_types.MASSACRE_SPACE), kills={1: (40, 40, True)}, redirected={1})[0]
        self.assertEqual(done.progress, "40/40 kills")

    def test_pinned_ids_are_marked(self):
        rows = board(summary(1), summary(2), pinned={2})
        self.assertEqual({r.id: r.pinned for r in rows}, {1: False, 2: True})


class TotalsTests(unittest.TestCase):
    def test_the_totals_line(self):
        rows = board(summary(1, minutes=30, reward=2_000_000), summary(2, minutes=900, reward=10_400_000), summary(3, minutes=5000, reward=0), redirected={2},
                     pinned={1})
        totals = B.totals(rows, NOW)
        self.assertEqual((totals.count, totals.ready, totals.soon, totals.reward, totals.ready_reward, totals.pinned), (3, 1, 1, 12_400_000, 10_400_000, 1))
        self.assertEqual(totals.text(), "3 missions · 1 ready · 1 under 1h · 1 pinned · 12.4M cr held (10.4M ready)")

    def test_money(self):
        self.assertEqual([B.money(n) for n in (950, 85_000, 1_000_000, 12_350_000)], ["950", "85K", "1M", "12.3M"])

    def test_nothing(self):
        self.assertEqual(B.totals([], NOW).text(), "0 missions")


class PlaceTests(unittest.TestCase):
    def test_places_are_ordered_here_then_next_then_by_urgency(self):
        rows = board(summary(1, system="Lave", minutes=600), summary(2, system="Sol", minutes=30), summary(3, system="Alioth", minutes=900),
                     summary(4, system="Lave", minutes=100))
        places = B.by_place(rows, here="Alioth", next_system="Lave")
        self.assertEqual([p.system for p in places], ["Alioth", "Lave", "Sol"])
        self.assertTrue(places[0].here and places[1].next_jump)
        self.assertEqual([r.id for r in places[1].rows], [4, 1])

    def test_system_names_group_ignoring_case(self):
        rows = board(summary(1, system="Sol"), summary(2, system="SOL"))
        self.assertEqual(len(B.by_place(rows)), 1)


class DetailTests(unittest.TestCase):
    def test_the_detail_lines(self):
        row = board(summary(1, commodity="Gold", needed=120, illegal=True, wing=True, cargo=mission_cargo.CargoProgress(total=200, collected=80, delivered=0)))[0]
        detail = dict(B.detail(row, NOW))
        self.assertIn("Illegal", detail["Kind"])
        self.assertEqual(detail["Status"], "In progress")
        self.assertIn("120 t still needed", detail["Commodity"])
        self.assertEqual(detail["Wing mission"], "Yes")
        self.assertIn("10h00m left", detail["Expires"])
        self.assertEqual(detail["Pinned"], "No")


class PinBookTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.book = pins.PinBook()
        self.book.load(self.dir.name)

    def test_toggling_and_per_commander_separation(self):
        self.assertTrue(self.book.toggle("Bocheaux", 5))
        self.assertTrue(self.book.is_pinned("BOCHEAUX", 5))             # the journal may write the name in capitals
        self.assertEqual(self.book.pinned("Other"), set())
        self.assertFalse(self.book.toggle("Bocheaux", 5))
        self.assertEqual(self.book.pinned("Bocheaux"), set())

    def test_pins_are_saved_and_loaded_again(self):
        self.book.pin_many("Bocheaux", [3, 4])
        again = pins.PinBook()
        again.load(self.dir.name)
        self.assertEqual(again.pinned("Bocheaux"), {3, 4})
        with open(os.path.join(self.dir.name, pins.STATE_FILENAME), encoding="utf-8") as handle:
            raw = json.load(handle)
        self.assertEqual(list(raw["commanders"]), ["bocheaux"])          # a commander is a key, never part of a file name

    def test_pins_go_with_their_missions(self):
        self.book.pin_many("Bocheaux", [1, 2, 3])
        self.assertEqual(self.book.prune("Bocheaux", [2, 3, 9]), [1])
        self.assertEqual(self.book.pinned("Bocheaux"), {2, 3})

    def test_unpin_all_and_no_commander(self):
        self.book.pin_many("Bocheaux", [1])
        self.book.clear("Bocheaux")
        self.assertEqual(self.book.pinned("Bocheaux"), set())
        self.assertFalse(self.book.toggle(None, 1))
        self.assertEqual(self.book.prune(None, []), [])

    def test_a_missing_or_broken_file_is_an_empty_book(self):
        with open(os.path.join(self.dir.name, pins.STATE_FILENAME), "w", encoding="utf-8") as handle:
            handle.write("not json")
        broken = pins.PinBook()
        broken.load(self.dir.name)
        self.assertEqual(broken.pinned("Bocheaux"), set())


if __name__ == "__main__":
    unittest.main()
