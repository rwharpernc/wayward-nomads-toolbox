"""
Unit tests for plugin/powerplay_ledger.py and powerplay_state.py.

Pure logic - no EDMC runtime needed. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# powerplay_state imports EDMC's `config`; give it a stand-in only if EDMC isn't there.
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"  # type: ignore[attr-defined]
    _stub.config = types.SimpleNamespace(get_str=lambda *_a, **_k: "")  # type: ignore[attr-defined]
    sys.modules["config"] = _stub

from plugin import powerplay_ledger as L, powerplay_state  # noqa: E402
from plugin.formulas import ACQUISITION, REINFORCEMENT  # noqa: E402

# 2026-10-01 is a Thursday: a cycle began 2026-10-01 07:00 UTC.
CYCLE_1 = "2026-10-01T07:00:00Z"
IN_CYCLE_1 = "2026-10-02T12:00:00Z"
IN_CYCLE_1_LATER = "2026-10-03T12:00:00Z"
IN_CYCLE_2 = "2026-10-09T08:00:00Z"
BEFORE_CYCLE_1 = "2026-09-30T20:00:00Z"


def _jump(ts: str, progress: float = 0.5, reinforcement: int = 100, undermining: int = 50,
          state: str = "Fortified", controller: str = "Pranav Antal") -> dict:
    return {
        "timestamp": ts, "event": "FSDJump", "StarSystem": "Ngurii", "PowerplayState": state,
        "ControllingPower": controller, "Powers": [controller, "Aisling Duval"],
        "PowerplayStateControlProgress": progress, "PowerplayStateReinforcement": reinforcement,
        "PowerplayStateUndermining": undermining,
    }


def _feed(ledger: L.PowerplayLedger, entry: dict, system: str = "Ngurii") -> None:
    snap = L.parse_snapshot(entry)
    assert snap is not None
    ledger.record_snapshot(system, snap)


class CycleStartTests(unittest.TestCase):
    def _start(self, text: str) -> str:
        return L.format_ts(L.cycle_start_for(L.parse_ts(text)))

    def test_thursday_after_seven_starts_that_day(self):
        self.assertEqual(self._start("2026-10-01T07:00:00Z"), CYCLE_1)
        self.assertEqual(self._start("2026-10-01T23:00:00Z"), CYCLE_1)

    def test_thursday_before_seven_belongs_to_the_previous_cycle(self):
        self.assertEqual(self._start("2026-10-01T06:59:59Z"), "2026-09-24T07:00:00Z")

    def test_mid_week_and_wednesday_night(self):
        self.assertEqual(self._start("2026-10-04T10:00:00Z"), CYCLE_1)
        self.assertEqual(self._start("2026-10-07T23:59:00Z"), CYCLE_1)


class SnapshotTests(unittest.TestCase):
    def test_parses_powerplay_fields(self):
        snap = L.parse_snapshot(_jump(IN_CYCLE_1, progress=0.52, reinforcement=7, undermining=9))
        self.assertEqual((snap.state, snap.controller, snap.progress, snap.reinforcement, snap.undermining),
                         ("Fortified", "Pranav Antal", 0.52, 7, 9))
        self.assertEqual(snap.powers, ["Pranav Antal", "Aisling Duval"])

    def test_non_powerplay_system_is_ignored(self):
        self.assertIsNone(L.parse_snapshot({"timestamp": IN_CYCLE_1, "event": "FSDJump"}))

    def test_bad_timestamp_is_ignored(self):
        self.assertIsNone(L.parse_snapshot({"timestamp": "nope", "PowerplayState": "Fortified"}))

    def test_round_trip(self):
        snap = L.parse_snapshot(_jump(IN_CYCLE_1))
        self.assertEqual(L.Snapshot.from_dict(snap.to_dict()), snap)


class LedgerTests(unittest.TestCase):
    def test_standing_change_within_a_cycle(self):
        ledger = L.PowerplayLedger()
        _feed(ledger, _jump(IN_CYCLE_1, progress=0.50, reinforcement=100, undermining=50))
        _feed(ledger, _jump(IN_CYCLE_1_LATER, progress=0.45, reinforcement=130, undermining=90))
        record = ledger.records["ngurii"]
        self.assertAlmostEqual(record.progress_change(), -5.0)
        self.assertEqual(record.now.undermining - record.before.undermining, 40)

    def test_single_reading_has_no_change(self):
        ledger = L.PowerplayLedger()
        _feed(ledger, _jump(IN_CYCLE_1))
        self.assertEqual(ledger.records["ngurii"].progress_change(), 0.0)

    def test_out_of_order_reading_does_not_replace_newer(self):
        ledger = L.PowerplayLedger()
        _feed(ledger, _jump(IN_CYCLE_1, progress=0.1))
        _feed(ledger, _jump(IN_CYCLE_1_LATER, progress=0.3))
        _feed(ledger, _jump("2026-10-02T18:00:00Z", progress=0.2))
        self.assertEqual(ledger.records["ngurii"].now.progress, 0.3)

    def test_merits_tally_per_system_and_activity(self):
        ledger = L.PowerplayLedger()
        self.assertTrue(ledger.record_merits("Ngurii", ACQUISITION, 100, IN_CYCLE_1))
        self.assertTrue(ledger.record_merits("ngurii", ACQUISITION, 50, IN_CYCLE_1_LATER))
        self.assertTrue(ledger.record_merits("Ngurii", REINFORCEMENT, 25, IN_CYCLE_1_LATER))
        record = ledger.records["ngurii"]
        self.assertEqual(record.merits, {ACQUISITION: 150, REINFORCEMENT: 25})
        self.assertEqual(record.events[ACQUISITION], 2)
        self.assertEqual(record.last_at, IN_CYCLE_1_LATER)

    def test_unusable_merits_are_ignored(self):
        ledger = L.PowerplayLedger()
        self.assertFalse(ledger.record_merits("", ACQUISITION, 10, IN_CYCLE_1))
        self.assertFalse(ledger.record_merits("Ngurii", ACQUISITION, 0, IN_CYCLE_1))
        self.assertFalse(ledger.record_merits("Ngurii", ACQUISITION, 10, None))

    def test_merits_from_before_the_cycle_are_ignored(self):
        ledger = L.PowerplayLedger()
        ledger.record_merits("Ngurii", ACQUISITION, 10, IN_CYCLE_1)
        self.assertFalse(ledger.record_merits("Ngurii", ACQUISITION, 10, BEFORE_CYCLE_1))
        self.assertEqual(ledger.records["ngurii"].total_merits(), 10)

    def test_rollover_archives_and_carries_the_baseline(self):
        ledger = L.PowerplayLedger()
        _feed(ledger, _jump(IN_CYCLE_1, progress=0.50))
        _feed(ledger, _jump(IN_CYCLE_1_LATER, progress=0.60))
        ledger.record_merits("Ngurii", ACQUISITION, 100, IN_CYCLE_1_LATER)

        _feed(ledger, _jump(IN_CYCLE_2, progress=0.70))

        self.assertEqual(len(ledger.archive), 1)
        self.assertEqual(ledger.archive[0]["cycle_start"], CYCLE_1)
        record = ledger.records["ngurii"]
        self.assertEqual(record.total_merits(), 0)               # merits reset
        self.assertEqual(record.before.progress, 0.60)           # last reading became the baseline
        self.assertAlmostEqual(record.progress_change(), 10.0)
        archived = L.view_from_archive(ledger.archive[0]).record_for("Ngurii")
        self.assertEqual(archived.total_merits(), 100)

    def test_roll_to_archives_a_cycle_that_ended_while_closed(self):
        ledger = L.PowerplayLedger()
        ledger.record_merits("Ngurii", ACQUISITION, 100, IN_CYCLE_1)
        ledger.roll_to(datetime(2026, 10, 20, tzinfo=timezone.utc))
        self.assertEqual(len(ledger.archive), 1)
        self.assertEqual(ledger.records, {})

    def test_archive_is_capped(self):
        ledger = L.PowerplayLedger()
        moment = L.parse_ts(IN_CYCLE_1)
        for week in range(L.MAX_ARCHIVE + 3):
            ledger.record_merits("Ngurii", ACQUISITION, 1, L.format_ts(moment + L.CYCLE * week))
        self.assertEqual(len(ledger.archive), L.MAX_ARCHIVE)

    def test_serialisation_round_trip(self):
        ledger = L.PowerplayLedger()
        _feed(ledger, _jump(IN_CYCLE_1))
        ledger.record_merits("Ngurii", ACQUISITION, 100, IN_CYCLE_1)
        _feed(ledger, _jump(IN_CYCLE_2))
        again = L.PowerplayLedger.from_dict(ledger.to_dict())
        self.assertEqual(again.to_dict(), ledger.to_dict())

    def test_from_dict_survives_junk(self):
        for junk in (None, [], "x", {"systems": {"a": 3}, "archive": "no", "cycle_start": 5}):
            self.assertIsInstance(L.PowerplayLedger.from_dict(junk), L.PowerplayLedger)


class ViewTests(unittest.TestCase):
    def _ledger(self) -> L.PowerplayLedger:
        ledger = L.PowerplayLedger()
        for day, name in enumerate(["Alpha", "Bravo", "Charlie", "Delta"], start=1):
            ledger.record_merits(name, ACQUISITION, 5, f"2026-10-0{day + 1}T12:00:00Z")
        return ledger

    def test_most_recent_first_and_limit(self):
        view = self._ledger().views()[0]
        self.assertEqual(view.systems(limit=2), ["Delta", "Charlie"])

    def test_current_system_leads_even_without_data(self):
        view = self._ledger().views()[0]
        self.assertEqual(view.systems("Zed", limit=2), ["Zed", "Delta"])

    def test_pinned_first_always_and_not_counted_in_limit(self):
        view = self._ledger().views()[0]
        prefs = L.TabPrefs(pinned=["Alpha", "Nowhere"])
        self.assertEqual(view.systems(None, prefs, limit=2), ["Alpha", "Nowhere", "Delta", "Charlie"])

    def test_hidden_are_skipped(self):
        view = self._ledger().views()[0]
        self.assertEqual(view.systems(None, L.TabPrefs(hidden=["Delta"]), limit=2), ["Charlie", "Bravo"])


class TabPrefsTests(unittest.TestCase):
    def test_pin_cap(self):
        prefs = L.TabPrefs()
        for n in range(L.MAX_PINNED):
            self.assertTrue(prefs.toggle_pin(f"S{n}"))
        self.assertFalse(prefs.toggle_pin("One too many"))
        self.assertFalse(prefs.add("One too many"))
        self.assertEqual(len(prefs.pinned), L.MAX_PINNED)

    def test_unpin_frees_a_slot_and_is_case_insensitive(self):
        prefs = L.TabPrefs(pinned=["Alpha"])
        self.assertTrue(prefs.toggle_pin("ALPHA"))
        self.assertEqual(prefs.pinned, [])

    def test_close_unpins_and_hides_and_add_brings_back(self):
        prefs = L.TabPrefs(pinned=["Alpha"])
        prefs.close("alpha")
        self.assertEqual((prefs.pinned, prefs.hidden), ([], ["alpha"]))
        prefs.close("Alpha")
        self.assertEqual(len(prefs.hidden), 1)
        self.assertTrue(prefs.add("Alpha"))
        self.assertEqual((prefs.pinned, prefs.hidden), (["Alpha"], []))

    def test_add_of_an_already_pinned_system_works_at_the_cap(self):
        prefs = L.TabPrefs(pinned=[f"S{n}" for n in range(L.MAX_PINNED)])
        self.assertTrue(prefs.add("s0"))

    def test_from_dict_reapplies_cap_and_clips(self):
        prefs = L.TabPrefs.from_dict([f"S{n}" for n in range(9)], ["H", None, ""])
        self.assertEqual(len(prefs.pinned), L.MAX_PINNED)
        self.assertEqual(prefs.hidden, ["H"])
        self.assertEqual(L.TabPrefs.from_dict(["y" * 200], []).pinned, ["y" * L.MAX_NAME_CHARS])
        self.assertEqual(L.TabPrefs.from_dict("junk", 5), L.TabPrefs())


class CycleNumberAndPowerTests(unittest.TestCase):
    def test_cycle_numbers_count_weeks_from_101(self):
        def number(text):
            return L.cycle_number(L.cycle_start_for(L.parse_ts(text)))
        self.assertEqual(number("2026-10-01T07:00:00Z"), 101)
        self.assertEqual(number("2026-10-07T23:00:00Z"), 101)   # still 101 until Thursday 07:00 UTC
        self.assertEqual(number("2026-10-08T07:00:00Z"), 102)
        self.assertEqual(number("2026-09-30T00:00:00Z"), 100)
        self.assertIsNone(L.cycle_number(None))

    def test_powers_are_recorded_per_cycle_and_archived(self):
        ledger = L.PowerplayLedger()
        ledger.record_power(None)
        ledger.record_power("")
        self.assertEqual(ledger.powers, [])
        ledger.record_power("Pranav Antal")
        ledger.record_power("Pranav Antal")
        ledger.record_merits("Ngurii", ACQUISITION, 10, IN_CYCLE_1)
        ledger.record_merits("Ngurii", ACQUISITION, 10, IN_CYCLE_2)   # rolls to cycle 102
        self.assertEqual(L.view_from_archive(ledger.archive[0]).powers, ["Pranav Antal"])
        self.assertEqual(ledger.powers, ["Pranav Antal"])             # carried into the new cycle
        self.assertEqual(ledger.views()[0].number, 102)
        self.assertEqual(ledger.views()[1].number, 101)

    def test_defecting_adds_a_second_power_to_the_cycle(self):
        ledger = L.PowerplayLedger()
        ledger.record_power("Pranav Antal")
        ledger.record_power("Aisling Duval")
        self.assertEqual(ledger.powers, ["Pranav Antal", "Aisling Duval"])
        self.assertEqual(L.PowerplayLedger.from_dict(ledger.to_dict()).powers, ledger.powers)

    def test_unpledged_commander_has_no_power_but_keeps_standing(self):
        ledger = L.PowerplayLedger()
        _feed(ledger, _jump(IN_CYCLE_1))
        view = ledger.views()[0]
        self.assertEqual(view.powers, [])
        self.assertEqual(view.merit_totals(), {})
        self.assertEqual(view.systems_worked(), 0)
        self.assertEqual(view.systems(), ["Ngurii"])

    def test_cycle_totals_span_systems(self):
        ledger = L.PowerplayLedger()
        ledger.record_merits("Alpha", ACQUISITION, 100, IN_CYCLE_1)
        ledger.record_merits("Bravo", ACQUISITION, 50, IN_CYCLE_1)
        ledger.record_merits("Bravo", REINFORCEMENT, 25, IN_CYCLE_1_LATER)
        view = ledger.views()[0]
        self.assertEqual(view.merit_totals(), {ACQUISITION: 150, REINFORCEMENT: 25})
        self.assertEqual(view.systems_worked(), 2)

    def test_commanders_are_kept_apart_on_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = L.PowerplayLedger(), L.PowerplayLedger()
            a.record_power("Pranav Antal"); a.record_merits("Alpha", ACQUISITION, 10, IN_CYCLE_1)
            b.record_power("Aisling Duval"); b.record_merits("Bravo", REINFORCEMENT, 20, IN_CYCLE_1)
            powerplay_state.save_state(folder, "Bocheaux", {"ledger": a.to_dict()})
            powerplay_state.save_state(folder, "Mactavious", {"ledger": b.to_dict()})
            back_a = L.PowerplayLedger.from_dict(powerplay_state.load_state(folder, "Bocheaux")["ledger"])
            back_b = L.PowerplayLedger.from_dict(powerplay_state.load_state(folder, "Mactavious")["ledger"])
            self.assertEqual((back_a.powers, list(back_a.records)), (["Pranav Antal"], ["alpha"]))
            self.assertEqual((back_b.powers, list(back_b.records)), (["Aisling Duval"], ["bravo"]))


class StateTests(unittest.TestCase):
    def test_per_commander_round_trip_keeps_others(self):
        with tempfile.TemporaryDirectory() as folder:
            powerplay_state.save_state(folder, "Bocheaux", {"pinned_systems": ["A"]})
            powerplay_state.save_state(folder, "Mactavious", {"pinned_systems": ["B"]})
            powerplay_state.save_state(folder, "BOCHEAUX", {"pinned_systems": ["C"]})
            self.assertEqual(powerplay_state.load_state(folder, "bocheaux"), {"pinned_systems": ["C"]})
            self.assertEqual(powerplay_state.load_state(folder, "Mactavious"), {"pinned_systems": ["B"]})
            self.assertIsNone(powerplay_state.load_state(folder, "Nobody"))
            self.assertIsNone(powerplay_state.load_state(folder, ""))

    def test_unreadable_file_is_none(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, powerplay_state.STATE_FILENAME), "w", encoding="utf-8") as fh:
                fh.write("{not json")
            self.assertIsNone(powerplay_state.load_state(folder, "Bocheaux"))


if __name__ == "__main__":
    unittest.main()
